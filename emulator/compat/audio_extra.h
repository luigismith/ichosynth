// audio_extra.h — additional Teensy Audio Library nodes used by the TŒRN
// firmware (beyond the NI404 set in Audio.h): Amplifier, Bitcrusher, WaveformDc,
// AnalyzePeak, FilterLadder (Moog-style), plus I/O nodes (InputI2S, RecordQueue,
// PlaySdWav, Granular) that are stubbed for the standalone desktop build.
// Included at the end of Audio.h.
#ifndef NI404_COMPAT_AUDIO_EXTRA_H
#define NI404_COMPAT_AUDIO_EXTRA_H

#include <cmath>
#include <cstring>

// ---- AudioAmplifier: simple gain -----------------------------------------
class AudioAmplifier : public AudioStream {
public:
    AudioAmplifier() : AudioStream(1, inputQueueArray) {}
    void gain(float n) { mult = n; }
    void update(void) override {
        audio_block_t *in = receiveReadOnly(0);
        if (!in) return;
        if (mult == 1.0f) { transmit(in); ::release(in); return; }
        audio_block_t *out = allocate();
        if (!out) { ::release(in); return; }
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
            float v = in->data[i] * mult;
            out->data[i] = v > 32767 ? 32767 : (v < -32768 ? -32768 : (int16_t)v);
        }
        ::release(in);
        transmit(out);
        ::release(out);
    }
private:
    audio_block_t *inputQueueArray[1];
    float mult = 1.0f;
};

// ---- AudioEffectBitcrusher: bit-depth + sample-rate reduction --------------
class AudioEffectBitcrusher : public AudioStream {
public:
    AudioEffectBitcrusher() : AudioStream(1, inputQueueArray) {}
    void bits(uint8_t b) { if (b < 1) b = 1; if (b > 16) b = 16; crushBits = b; }
    void sampleRate(float hz) {
        if (hz < 1) hz = 1; if (hz > AUDIO_SAMPLE_RATE) hz = AUDIO_SAMPLE_RATE;
        step = (uint32_t)(AUDIO_SAMPLE_RATE / hz);
        if (step < 1) step = 1;
    }
    void update(void) override {
        audio_block_t *in = receiveReadOnly(0);
        if (!in) return;
        audio_block_t *out = allocate();
        if (!out) { ::release(in); return; }
        // Sign-extended 32-bit mask so the AND keeps the sign of negative samples
        // (a uint16_t mask drops the sign bits and mangles the negative half).
        int32_t mask = (crushBits >= 16) ? ~0 : ~((1 << (16 - crushBits)) - 1);
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
            if (sampleCounter == 0) held = (int16_t)((int32_t)in->data[i] & mask);
            if (++sampleCounter >= step) sampleCounter = 0;
            out->data[i] = held;
        }
        ::release(in);
        transmit(out);
        ::release(out);
    }
private:
    audio_block_t *inputQueueArray[1];
    uint8_t  crushBits = 16;
    uint32_t step = 1, sampleCounter = 0;
    int16_t  held = 0;
};

// ---- AudioSynthWaveformDc: constant / ramped DC source --------------------
class AudioSynthWaveformDc : public AudioStream {
public:
    AudioSynthWaveformDc() : AudioStream(0, nullptr) {}
    void amplitude(float n) { if (n < -1) n = -1; if (n > 1) n = 1; target = n; current = n; }
    void amplitude(float n, float /*ms*/) { amplitude(n); }
    float read() { return current; }
    void update(void) override {
        audio_block_t *b = allocate();
        if (!b) return;
        int16_t v = (int16_t)(current * 32767.0f);
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) b->data[i] = v;
        transmit(b);
        ::release(b);
    }
private:
    float target = 0, current = 0;
};

// ---- AudioAnalyzePeak: peak meter -----------------------------------------
class AudioAnalyzePeak : public AudioStream {
public:
    AudioAnalyzePeak() : AudioStream(1, inputQueueArray) {}
    bool available() { return newOutput; }
    float read() { newOutput = false; int16_t p = peak; peak = 0; return p / 32767.0f; }
    void update(void) override {
        audio_block_t *in = receiveReadOnly(0);
        if (!in) return;
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
            int16_t v = in->data[i]; if (v < 0) v = -v;
            if (v > peak) peak = v;
        }
        newOutput = true;
        ::release(in);
    }
private:
    audio_block_t *inputQueueArray[1];
    int16_t peak = 0;
    bool newOutput = false;
};

// ---- AudioFilterLadder: 4-pole Moog-style ladder (lowpass out) ------------
class AudioFilterLadder : public AudioStream {
public:
    AudioFilterLadder() : AudioStream(2, inputQueueArray) {}
    void frequency(float hz) {
        if (hz < 1) hz = 1; if (hz > AUDIO_SAMPLE_RATE * 0.49f) hz = AUDIO_SAMPLE_RATE * 0.49f;
        fc = hz;
    }
    void resonance(float r) { if (r < 0) r = 0; if (r > 1.8f) r = 1.8f; res = r; }
    void octaveControl(float n) { octave = n; }
    void inputDrive(float d) { drive = d < 0 ? 0 : d; }
    void passbandGain(float) {}
    void update(void) override {
        audio_block_t *in = receiveReadOnly(0);
        audio_block_t *fcmod = receiveReadOnly(1);
        if (fcmod) ::release(fcmod);
        if (!in) return;
        audio_block_t *out = allocate();
        if (!out) { ::release(in); return; }
        // Linear 4-pole (24 dB/oct) Moog-style ladder. Using linear one-pole
        // stages (not tanh-per-stage) gives the proper steep rolloff; resonance
        // feeds the 4th stage back to the input. tanh only on the feedback keeps
        // it from blowing up at high resonance, and a state clamp is the backstop.
        float g = 1.0f - expf(-2.0f * 3.14159265f * fc / AUDIO_SAMPLE_RATE);
        float k = 4.0f * res;  // ~4 = self-oscillation threshold
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
            float x = (in->data[i] * (1.0f / 32768.0f)) * (drive > 0 ? drive : 1.0f);
            float input = x - k * tanhf(s4);
            s1 += g * (input - s1);
            s2 += g * (s1 - s2);
            s3 += g * (s2 - s3);
            s4 += g * (s3 - s4);
            if (!std::isfinite(s4) || s4 > 4.0f || s4 < -4.0f) { s1 = s2 = s3 = s4 = 0; }
            float v = s4 * 32768.0f;
            out->data[i] = v > 32767 ? 32767 : (v < -32768 ? -32768 : (int16_t)v);
        }
        ::release(in);
        transmit(out);
        ::release(out);
    }
private:
    audio_block_t *inputQueueArray[2];
    float fc = 1000, res = 0, octave = 1, drive = 1;
    float s1 = 0, s2 = 0, s3 = 0, s4 = 0;
};

// ---- I/O nodes: stubbed for the standalone desktop build ------------------
// AudioInputI2S: hardware audio-in. No capture device wired -> silence.
class AudioInputI2S : public AudioStream {
public:
    AudioInputI2S() : AudioStream(0, nullptr) {}
    void update(void) override {}   // transmit nothing -> downstream silent
};

// AudioRecordQueue: would buffer AudioInputI2S; no input -> never has data.
class AudioRecordQueue : public AudioStream {
public:
    AudioRecordQueue() : AudioStream(1, inputQueueArray) {}
    void begin() { enabled = true; }
    void end() { enabled = false; }
    int available() { return 0; }
    int16_t *readBuffer() { return nullptr; }
    void freeBuffer() {}
    void clear() {}
    void update(void) override { audio_block_t *in = receiveReadOnly(0); if (in) ::release(in); }
private:
    audio_block_t *inputQueueArray[1];
    bool enabled = false;
};

// AudioPlaySdWav: minimal stub (the firmware uses one instance; returns silence
// and "not playing" so logic proceeds). Full SD-WAV streaming can be added later.
class AudioPlaySdWav : public AudioStream {
public:
    AudioPlaySdWav() : AudioStream(0, nullptr) {}
    bool play(const char *) { playing = false; return false; }
    void stop() { playing = false; }
    bool isPlaying() { return playing; }
    uint32_t positionMillis() { return 0; }
    uint32_t lengthMillis() { return 0; }
    void update(void) override {}
private:
    bool playing = false;
};

// AudioEffectGranular: pass-through stub (1 use). Real granular can be added later.
class AudioEffectGranular : public AudioStream {
public:
    AudioEffectGranular() : AudioStream(1, inputQueueArray) {}
    void begin(int16_t *, int) {}
    void beginFreeze(float) {}
    void beginPitchShift(float) {}
    void stop() {}
    void setSpeed(float) {}
    void update(void) override {
        audio_block_t *in = receiveReadOnly(0);
        if (in) { transmit(in); ::release(in); }
    }
private:
    audio_block_t *inputQueueArray[1];
};

#endif // NI404_COMPAT_AUDIO_EXTRA_H
