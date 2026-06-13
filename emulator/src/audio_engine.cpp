// audio_engine.cpp — runtime for the Teensy-Audio-style graph in compat/Audio.h:
// the block pool, stream registry + per-tick update, AudioConnection routing,
// the DSP node update() bodies, the output ring buffer that bridges to the SDL
// audio callback, and the global interrupt-guard mutex.
#include "Audio.h"
#include <vector>
#include <mutex>
#include <atomic>

// ---- construct-on-first-use globals (avoid static-init-order fiasco) ------
static std::recursive_mutex &audio_mutex() { static std::recursive_mutex *m = new std::recursive_mutex(); return *m; }
static std::vector<AudioStream *> &registry() { static std::vector<AudioStream *> *r = new std::vector<AudioStream *>(); return *r; }

void AudioNoInterrupts() { audio_mutex().lock(); }
void AudioInterrupts()   { audio_mutex().unlock(); }

void audio_register_stream(AudioStream *s) { registry().push_back(s); }

// ---- block pool -----------------------------------------------------------
static std::vector<audio_block_t> &pool() { static std::vector<audio_block_t> *p = new std::vector<audio_block_t>(); return *p; }
static std::vector<uint16_t> &freelist() { static std::vector<uint16_t> *f = new std::vector<uint16_t>(); return *f; }

void audio_memory_init(unsigned n) {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    unsigned want = n < 600 ? 600 : n + 64;   // generous; the graph holds many slots
    pool().assign(want, audio_block_t{});
    freelist().clear();
    for (unsigned i = 0; i < want; i++) { pool()[i].memory_pool_index = (uint16_t)i; freelist().push_back((uint16_t)i); }
}

audio_block_t *allocate(void) {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    if (pool().empty()) audio_memory_init(600);
    if (freelist().empty()) return nullptr;
    uint16_t idx = freelist().back(); freelist().pop_back();
    audio_block_t *b = &pool()[idx];
    b->ref_count = 1;
    return b;
}

void release(audio_block_t *block) {
    if (!block) return;
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    if (block->ref_count > 1) { block->ref_count--; return; }
    block->ref_count = 0;
    freelist().push_back(block->memory_pool_index);
}

// ---- routing --------------------------------------------------------------
void AudioConnection::connect() {
    next_dest = src->destination_list;
    src->destination_list = this;
}

void AudioStream::transmit(audio_block_t *block, unsigned char index) {
    if (!block) return;
    for (AudioConnection *c = destination_list; c; c = c->next_dest) {
        if (c->src_index != index) continue;
        audio_block_t *prev = c->dst->inputQueue[c->dest_index];
        if (prev) ::release(prev);
        block->ref_count++;
        c->dst->inputQueue[c->dest_index] = block;
    }
}

void audio_update_all() {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    auto &r = registry();
    for (AudioStream *s : r) s->update();
}

// ===========================================================================
// Output ring buffer + master volume (SDL callback bridge)
// ===========================================================================
static std::atomic<float> g_master_vol{0.9f};
void AudioControlSGTL5000::volume(float n) { if (n < 0) n = 0; if (n > 1) n = 1; g_master_vol.store(n); }

// User-controllable output makeup gain (the menu's master volume). Applied at the
// i2s sink with saturation, on top of the firmware's own volume.
static std::atomic<float> g_output_gain{1.0f};
void  ni404_set_master_gain(float g) { if (g < 0) g = 0; if (g > 64) g = 64; g_output_gain.store(g); }
float ni404_get_master_gain() { return g_output_gain.load(); }

static std::vector<float> &ring() { static std::vector<float> *r = new std::vector<float>(1 << 16, 0.0f); return *r; } // interleaved stereo floats
static size_t g_ring_w = 0, g_ring_r = 0;
static inline size_t ring_cap() { return ring().size(); }
static inline size_t ring_count() { return (g_ring_w + ring_cap() - g_ring_r) % ring_cap(); } // # of floats queued

static void ring_push(float l, float r) {
    auto &rb = ring();
    size_t next = (g_ring_w + 2) % rb.size();
    if (next == g_ring_r) return;  // full: drop (shouldn't happen — we pull on demand)
    rb[g_ring_w] = l;
    rb[(g_ring_w + 1) % rb.size()] = r;
    g_ring_w = next;
}

void AudioOutputI2S::update(void) {
    audio_block_t *l = receiveReadOnly(0);
    audio_block_t *r = receiveReadOnly(1);
    float vol = g_master_vol.load() * g_output_gain.load();
    for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
        float fl = l ? l->data[i] * (1.0f / 32768.0f) * vol : 0.0f;
        float fr = r ? r->data[i] * (1.0f / 32768.0f) * vol : 0.0f;
        if (fl > 1) fl = 1; else if (fl < -1) fl = -1;   // saturate
        if (fr > 1) fr = 1; else if (fr < -1) fr = -1;
        ring_push(fl, fr);
    }
    if (l) release(l);
    if (r) release(r);
}

// Called by the SDL audio callback. Renders `frames` stereo frames into `out`
// (interleaved float), driving the graph as needed.
void ni404_audio_render(float *out, int frames) {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    int needed = frames * 2;
    int guard = 0;
    while ((int)ring_count() < needed && guard++ < frames / AUDIO_BLOCK_SAMPLES + 4) {
        audio_update_all();
    }
    auto &rb = ring();
    for (int i = 0; i < needed; i++) {
        if (g_ring_r == g_ring_w) { out[i] = 0.0f; continue; }
        out[i] = rb[g_ring_r];
        g_ring_r = (g_ring_r + 1) % rb.size();
    }
}

// ===========================================================================
// DSP node bodies
// ===========================================================================
static inline int16_t sat16(float v) {
    if (v > 32767.0f) return 32767;
    if (v < -32768.0f) return -32768;
    return (int16_t)v;
}

void AudioSynthWaveform::update(void) {
    if (mag <= 0.0f) return;  // silent -> no block (downstream sees silence)
    audio_block_t *b = allocate();
    if (!b) return;
    const float inc = freq / AUDIO_SAMPLE_RATE;  // cycles per sample
    for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
        float ph = phase_acc, v;
        switch (tone_type) {
            case WAVEFORM_SINE:             v = sinf(6.2831853f * ph); break;
            case WAVEFORM_SAWTOOTH:         v = 2.0f * ph - 1.0f; break;
            case WAVEFORM_SAWTOOTH_REVERSE: v = 1.0f - 2.0f * ph; break;
            case WAVEFORM_SQUARE:
            case WAVEFORM_PULSE:            v = ph < 0.5f ? 1.0f : -1.0f; break;
            case WAVEFORM_TRIANGLE:
            case WAVEFORM_TRIANGLE_VARIABLE:v = ph < 0.5f ? (4.0f * ph - 1.0f) : (3.0f - 4.0f * ph); break;
            default:                        v = sinf(6.2831853f * ph); break;
        }
        b->data[i] = sat16(v * mag * 32767.0f);
        phase_acc += inc;
        if (phase_acc >= 1.0f) phase_acc -= 1.0f;
    }
    transmit(b);
    release(b);
}

void AudioEffectEnvelope::startSegmentTo(float target, float ms) {
    int n = msToSamples(ms);
    if (n < 1) n = 1;
    inc = (target - mult) / (float)n;
    count = n;
}

void AudioEffectEnvelope::noteOn() {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    state = ATTACK;
    startSegmentTo(1.0f, attack_ms);
}

void AudioEffectEnvelope::noteOff() {
    std::lock_guard<std::recursive_mutex> lk(audio_mutex());
    if (state == IDLE) return;
    state = RELEASE;
    startSegmentTo(0.0f, release_ms);
}

void AudioEffectEnvelope::update(void) {
    audio_block_t *in = receiveReadOnly(0);
    if (state == IDLE) { if (in) ::release(in); return; }
    if (!in) {
        // No signal arrived this tick: still advance the envelope clock so that
        // a release in progress completes instead of hanging.
        int remain = AUDIO_BLOCK_SAMPLES;
        while (remain-- > 0) {
            mult += inc;
            if (--count <= 0) {
                if (state == ATTACK)  { state = DECAY;  startSegmentTo(sustain_level, decay_ms); }
                else if (state == DECAY) { state = SUSTAIN; inc = 0; count = 1 << 30; mult = sustain_level; }
                else if (state == RELEASE) { state = IDLE; mult = 0; break; }
                else { count = 1 << 30; inc = 0; }
            }
        }
        return;
    }
    audio_block_t *out = allocate();
    if (!out) { ::release(in); return; }
    for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
        out->data[i] = sat16((float)in->data[i] * mult);
        mult += inc;
        if (mult < 0) mult = 0;
        if (--count <= 0) {
            if (state == ATTACK)       { state = DECAY;   startSegmentTo(sustain_level, decay_ms); }
            else if (state == DECAY)   { state = SUSTAIN; inc = 0; count = 1 << 30; mult = sustain_level; }
            else if (state == RELEASE) { state = IDLE;    mult = 0; inc = 0; count = 1 << 30; }
            else                       { inc = 0; count = 1 << 30; }
        }
    }
    ::release(in);
    transmit(out);
    ::release(out);
}

void AudioFilterStateVariable::update(void) {
    audio_block_t *in = receiveReadOnly(0);
    audio_block_t *fcin = receiveReadOnly(1);
    if (fcin) release(fcin);  // frequency-modulation input unused by the firmware
    if (!in) return;
    audio_block_t *outLP = allocate();
    if (!outLP) { release(in); return; }
    // 4x-oversampled Chamberlin SVF. Oversampling keeps the coefficient
    // f (=2*sin(pi*fc/fs4)) small (~0.32 at 9 kHz) so the filter stays stable
    // even at high resonance; the NaN guard is a last-resort backstop only.
    const float fs4 = AUDIO_SAMPLE_RATE * 4.0f;
    float f = 2.0f * sinf(3.14159265f * fc / fs4);
    if (f > 0.9f) f = 0.9f;
    const float q = damp;
    for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
        float input = in->data[i] * (1.0f / 32768.0f);
        float low = 0;
        for (int os = 0; os < 4; os++) {
            float hp = input - lp - q * bp;
            bp += f * hp;
            lp += f * bp;
            low = lp;
        }
        if (!std::isfinite(lp)) { lp = 0; bp = 0; low = 0; }
        outLP->data[i] = sat16(low * 32768.0f);
    }
    release(in);
    transmit(outLP, 0);
    release(outLP);
}

void AudioMixer4::update(void) {
    audio_block_t *out = nullptr;
    for (int ch = 0; ch < 4; ch++) {
        audio_block_t *in = receiveReadOnly(ch);
        if (!in) continue;
        if (!out) {
            out = allocate();
            if (!out) { release(in); return; }
            std::memset(out->data, 0, sizeof(out->data));
        }
        float g = multiplier[ch];
        for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++)
            out->data[i] = sat16((float)out->data[i] + (float)in->data[i] * g);
        release(in);
    }
    if (out) { transmit(out); release(out); }
}
