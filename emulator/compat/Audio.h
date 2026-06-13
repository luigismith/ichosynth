// Audio.h — desktop port of the (subset of the) Teensy Audio Library used by
// the NI404 firmware. Implements the 128-sample @44.1kHz block graph:
//   AudioStream base + AudioConnection routing + a block pool, and the nodes
//   AudioSynthWaveform, AudioEffectEnvelope, AudioFilterStateVariable,
//   AudioMixer4, AudioOutputI2S (ring-buffer sink) and AudioControlSGTL5000.
//
// The graph is *pull-driven by the audio callback*: the SDL callback runs
// audio_update_all() (one 128-sample tick of every node, in creation order)
// until enough output frames are queued. Param changes from the main thread are
// serialised against ticks by AudioNoInterrupts()/AudioInterrupts() (a global
// recursive mutex), which the firmware already brackets its critical sections
// with.  See audio_engine.cpp for the pool, registry iteration and ring buffer.
#ifndef NI404_COMPAT_AUDIO_H
#define NI404_COMPAT_AUDIO_H

#include "Arduino.h"
#include <cmath>
#include <vector>
#include <cstring>

#ifndef AUDIO_BLOCK_SAMPLES
#define AUDIO_BLOCK_SAMPLES 128
#endif
#ifndef AUDIO_SAMPLE_RATE
#define AUDIO_SAMPLE_RATE 44100.0f
#endif
#ifndef AUDIO_SAMPLE_RATE_EXACT
#define AUDIO_SAMPLE_RATE_EXACT 44100.0f
#endif

// Layout matches Teensy's audio_block_t exactly, so vendored Teensy audio nodes
// (e.g. the freeverb in toern-src/src/) — including their `zeroblock` aggregate
// initializer {0,0,0,{...}} — compile unchanged.
struct audio_block_t {
    uint8_t  ref_count;
    uint8_t  reserved1;
    uint16_t memory_pool_index;
    int16_t  data[AUDIO_BLOCK_SAMPLES];
};

// ---- block pool (defined in audio_engine.cpp) -----------------------------
audio_block_t *allocate(void);
void           release(audio_block_t *block);
void           transmit_init();
void           audio_memory_init(unsigned n);
#define AudioMemory(n) audio_memory_init(n)
#define AudioMemoryUsage() (0)
#define AudioMemoryUsageMax() (0)
inline void AudioMemoryUsageMaxReset() {}
#define AudioProcessorUsage() (0.0f)
#define AudioProcessorUsageMax() (0.0f)
inline void AudioProcessorUsageMaxReset() {}

// ---- interrupt guard: a global recursive mutex (audio_engine.cpp) ---------
void AudioNoInterrupts();
void AudioInterrupts();

class AudioStream;
class AudioConnection;

// Registry of every stream, in construction order = update order.
void audio_register_stream(AudioStream *s);
void audio_update_all();

class AudioConnection {
public:
    AudioConnection *next_dest = nullptr;
    AudioStream *src;
    AudioStream *dst;
    unsigned char src_index;
    unsigned char dest_index;
    AudioConnection(AudioStream &source, AudioStream &destination)
        : src(&source), dst(&destination), src_index(0), dest_index(0) { connect(); }
    AudioConnection(AudioStream &source, unsigned char sourceOutput,
                    AudioStream &destination, unsigned char destinationInput)
        : src(&source), dst(&destination), src_index(sourceOutput),
          dest_index(destinationInput) { connect(); }
    void connect();
};

class AudioStream {
public:
    AudioStream(unsigned char ninput, audio_block_t **iqueue)
        : num_inputs(ninput), inputQueue(iqueue), destination_list(nullptr) {
        for (unsigned char i = 0; i < num_inputs; i++) inputQueue[i] = nullptr;
        audio_register_stream(this);
    }
    virtual ~AudioStream() {}
    virtual void update(void) = 0;

    unsigned char num_inputs;
    audio_block_t **inputQueue;
    AudioConnection *destination_list;  // outgoing connections

protected:
    audio_block_t *allocate(void) { return ::allocate(); }
    void release(audio_block_t *block) { ::release(block); }

    // Pull the block sitting on input `index` (ownership transfers to caller).
    audio_block_t *receiveReadOnly(unsigned int index = 0) {
        if (index >= num_inputs) return nullptr;
        audio_block_t *in = inputQueue[index];
        inputQueue[index] = nullptr;
        return in;
    }
    audio_block_t *receiveWritable(unsigned int index = 0) {
        if (index >= num_inputs) return nullptr;
        audio_block_t *in = inputQueue[index];
        inputQueue[index] = nullptr;
        if (in && in->ref_count > 1) {
            audio_block_t *out = ::allocate();
            if (!out) { ::release(in); return nullptr; }
            std::memcpy(out->data, in->data, sizeof(out->data));
            ::release(in);
            return out;
        }
        return in;
    }
    // Send `block` to every input connected to output port `index`.
    void transmit(audio_block_t *block, unsigned char index = 0);

    friend class AudioConnection;
    friend void audio_update_all();
};

// ===========================================================================
// Waveform synth
// ===========================================================================
#define WAVEFORM_SINE              0
#define WAVEFORM_SAWTOOTH          1
#define WAVEFORM_SQUARE            2
#define WAVEFORM_TRIANGLE          3
#define WAVEFORM_ARBITRARY         4
#define WAVEFORM_PULSE             5
#define WAVEFORM_SAWTOOTH_REVERSE  6
#define WAVEFORM_SAMPLE_HOLD       7
#define WAVEFORM_TRIANGLE_VARIABLE 8

class AudioSynthWaveform : public AudioStream {
public:
    AudioSynthWaveform() : AudioStream(0, nullptr) {}
    void begin(short t_type) { tone_type = t_type; }
    void begin(float t_amp, float t_freq, short t_type) {
        amplitude(t_amp); frequency(t_freq); tone_type = t_type;
    }
    void amplitude(float n) { if (n < 0) n = 0; else if (n > 1) n = 1; mag = n; }
    void frequency(float f) {
        if (f < 0) f = 0; else if (f > AUDIO_SAMPLE_RATE / 2) f = AUDIO_SAMPLE_RATE / 2;
        freq = f;
    }
    void phase(float angle) { phase_acc = fmodf(angle, 360.0f) / 360.0f; }
    void pulseWidth(float w) { pw = (w < 0.05f) ? 0.05f : (w > 0.95f ? 0.95f : w); }
    void offset(float) {}
    void update(void) override;
private:
    short tone_type = WAVEFORM_SINE;
    float freq = 0, mag = 0;
    float phase_acc = 0;  // 0..1
    float pw = 0.5f;      // pulse width 0..1
};

// ===========================================================================
// ADSR envelope (linear segments; sustain is a 0..1 level)
// ===========================================================================
class AudioEffectEnvelope : public AudioStream {
public:
    AudioEffectEnvelope() : AudioStream(1, inputQueueArray) { release(5.0f); }
    void attack(float ms)  { attack_ms = ms; }
    void hold(float ms)    { hold_ms = ms; }
    void decay(float ms)   { decay_ms = ms; }
    void sustain(float lv) { if (lv < 0) lv = 0; else if (lv > 1) lv = 1; sustain_level = lv; }
    void release(float ms) { release_ms = ms; }
    void noteOn();
    void noteOff();
    bool isActive() { return state != 0; }
    bool isSustain() { return state == 4; }
    void update(void) override;
private:
    audio_block_t *inputQueueArray[1];
    enum { IDLE = 0, ATTACK = 1, HOLD = 5, DECAY = 2, SUSTAIN = 4, RELEASE = 3, FORCED = 6 };
    int   state = IDLE;
    float attack_ms = 10.5f, hold_ms = 0, decay_ms = 35, sustain_level = 0.5f, release_ms = 5;
    float mult = 0;       // current gain
    float inc = 0;        // per-sample increment
    int   count = 0;      // samples left in current segment
    int msToSamples(float ms) { return (int)(ms * (AUDIO_SAMPLE_RATE / 1000.0f)); }
    void  startSegmentTo(float target, float ms);
};

// ===========================================================================
// State-variable filter (Chamberlin), outputs: 0=LP 1=BP 2=HP
// input 0 = signal, input 1 = optional frequency control (ignored if absent)
// ===========================================================================
class AudioFilterStateVariable : public AudioStream {
public:
    AudioFilterStateVariable() : AudioStream(2, inputQueueArray) { frequency(1000); resonance(0.707f); }
    void frequency(float f) {
        // Cap well below Nyquist: the oversampled Chamberlin SVF goes unstable as
        // cutoff*resonance grows, so keep cutoff <= ~Fs/2.4 where it stays stable
        // even at max resonance.
        if (f < 20) f = 20; else if (f > AUDIO_SAMPLE_RATE * 0.42f) f = AUDIO_SAMPLE_RATE * 0.42f;
        fc = f;
    }
    void resonance(float q) {
        if (q < 0.7f) q = 0.7f; else if (q > 5.0f) q = 5.0f;
        damp = 1.0f / q;
    }
    void octaveControl(float n) { octave = n; }
    void update(void) override;
private:
    audio_block_t *inputQueueArray[2];
    float fc = 1000, damp = 0.707f, octave = 1.0f;
    float lp = 0, bp = 0;  // state
};

// ===========================================================================
// 4-input mixer
// ===========================================================================
class AudioMixer4 : public AudioStream {
public:
    AudioMixer4() : AudioStream(4, inputQueueArray) { for (int i = 0; i < 4; i++) multiplier[i] = 1.0f; }
    void gain(unsigned int ch, float g) { if (ch < 4) multiplier[ch] = g; }
    void update(void) override;
private:
    audio_block_t *inputQueueArray[4];
    float multiplier[4];
};

// ===========================================================================
// I2S output: the graph sink. Pushes received L/R into the output ring buffer.
// ===========================================================================
class AudioOutputI2S : public AudioStream {
public:
    AudioOutputI2S() : AudioStream(2, inputQueueArray) {}
    void update(void) override;
private:
    audio_block_t *inputQueueArray[2];
};

// ===========================================================================
// SGTL5000 codec control — mostly a no-op; volume() feeds a master gain.
// ===========================================================================
#define AUDIO_INPUT_LINEIN 0
#define AUDIO_INPUT_MIC    1
#define FLAT_FREQUENCY     0
#define PARAMETRIC_EQUALIZER 1
#define TONE_CONTROLS      2
#define GRAPHIC_EQUALIZER  3

class AudioControlSGTL5000 {
public:
    bool enable(void) { return true; }
    void volume(float n);            // 0..1 master gain (audio_engine.cpp)
    void volume(float, float) {}
    void lineOutLevel(int) {}
    void lineInLevel(int) {}
    void lineInLevel(int, int) {}
    void micGain(int) {}
    void unmuteLineout(void) {}
    void muteLineout(void) {}
    void unmuteHeadphone(void) {}
    void muteHeadphone(void) {}
    void inputSelect(int) {}
    void adcHighPassFilterEnable(void) {}
    void adcHighPassFilterDisable(void) {}
    void dacVolume(float) {}
    void dacVolume(float, float) {}
    void audioPreProcessorEnable(void) {}
    void audioPostProcessorEnable(void) {}
    void eqSelect(int) {}
    void eqBand(int, float) {}
    void eqBands(float, float, float, float, float) {}
    void eqBands(float, float) {}
    void enhanceBass(float, float) {}
    void enhanceBass(float, float, int, int) {}
    void enhanceBassEnable(void) {}
    void enhanceBassDisable(void) {}
    void autoVolumeControl(int, int, int, float, float, float) {}
    void autoVolumeEnable(void) {}
    void autoVolumeDisable(void) {}
    void surroundSound(int) {}
    void surroundSound(int, int) {}
    void surroundSoundEnable(void) {}
    void surroundSoundDisable(void) {}
    void audioProcessorDisable(void) {}
    unsigned short read(unsigned int) { return 0; }
    bool write(unsigned int, unsigned int) { return true; }
};

// Additional audio nodes used by the TŒRN firmware (harmless extra classes for
// the NI404 build).
#include "audio_extra.h"

// On Teensy, SD is pulled in via the Audio library; the firmware uses SD without
// an explicit include, so mirror that here.
#include "SD.h"

#endif // NI404_COMPAT_AUDIO_H
