// audio_engine.cpp — runtime for the Teensy-Audio-style graph in compat/Audio.h:
// the block pool, stream registry + per-tick update, AudioConnection routing,
// the DSP node update() bodies and the output ring buffer that bridges to the SDL
// audio callback. All of it runs under the emulator's interrupt lock (emu_irq.h).
#include "Audio.h"
#include <vector>
#include <mutex>
#include <atomic>

#include "emu_irq.h"
#include <chrono>

// ---- construct-on-first-use globals (avoid static-init-order fiasco) ------
static std::vector<AudioStream *> &registry() { static std::vector<AudioStream *> *r = new std::vector<AudioStream *>(); return *r; }

// AudioNoInterrupts() holds the emulator's interrupt lock (emu_irq.h) — the lock the
// graph update, the IntervalTimer thread and noInterrupts() use. Like the Teensy's
// NVIC disable it does not nest: one AudioInterrupts() re-enables.
static thread_local bool t_audio_off = false;
void AudioNoInterrupts() { if (!t_audio_off) { ni404_irq_lock().lock(); t_audio_off = true; } }
void AudioInterrupts()   { if (t_audio_off) { t_audio_off = false; ni404_irq_lock().unlock(); } }

void audio_register_stream(AudioStream *s) { registry().push_back(s); }

// ---- block pool -----------------------------------------------------------
// Static storage (never reallocated, so queued block pointers stay valid). Only the
// first AudioMemory(n) blocks are handed out: when they are all in use, allocate()
// returns NULL and the node that asked drops its output, exactly like the Teensy.
static const unsigned POOL_MAX = 1024;
static audio_block_t g_pool[POOL_MAX];
static uint16_t g_free[POOL_MAX];
static unsigned g_nfree = 0, g_ninit = 0, g_used = 0, g_used_max = 0, g_alloc_fail = 0;

void audio_memory_init(unsigned n) {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    if (n > POOL_MAX) n = POOL_MAX;
    if (n <= g_ninit) return;                       // idempotent; never shrinks
    for (unsigned i = g_ninit; i < n; i++) {
        g_pool[i] = audio_block_t{};
        g_pool[i].memory_pool_index = (uint16_t)i;
        g_free[g_nfree++] = (uint16_t)i;
    }
    g_ninit = n;
}

audio_block_t *allocate(void) {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    if (g_nfree == 0) { g_alloc_fail++; return nullptr; }   // pool exhausted (or no AudioMemory yet)
    audio_block_t *b = &g_pool[g_free[--g_nfree]];
    b->ref_count = 1;
    if (++g_used > g_used_max) g_used_max = g_used;
    return b;
}

void release(audio_block_t *block) {
    if (!block) return;
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    if (block->ref_count > 1) { block->ref_count--; return; }
    block->ref_count = 0;
    g_free[g_nfree++] = block->memory_pool_index;
    g_used--;
}

unsigned AudioMemoryUsage()    { return g_used; }
unsigned AudioMemoryUsageMax() { return g_used_max; }
void     AudioMemoryUsageMaxReset() { std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock()); g_used_max = g_used; }
unsigned audio_memory_total()  { return g_ninit; }
unsigned audio_alloc_failures() { return g_alloc_fail; }   // allocate() calls that got NULL

// ---- routing --------------------------------------------------------------
void AudioConnection::connect() {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    next_dest = src->destination_list;
    src->destination_list = this;
    src->active = true;
    dst->active = true;
}

// Teensy transmit(): a destination input that still holds an unconsumed block keeps
// it; the new block is not delivered there.
void AudioStream::transmit(audio_block_t *block, unsigned char index) {
    if (!block) return;
    for (AudioConnection *c = destination_list; c; c = c->next_dest) {
        if (c->src_index != index) continue;
        if (c->dst->inputQueue[c->dest_index] == nullptr) {
            c->dst->inputQueue[c->dest_index] = block;
            block->ref_count++;
        }
    }
}

static float g_cpu = 0, g_cpu_max = 0;
float AudioProcessorUsage()    { return g_cpu; }
float AudioProcessorUsageMax() { return g_cpu_max; }
void  AudioProcessorUsageMaxReset() { g_cpu_max = g_cpu; }

void audio_update_all() {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    const auto t0 = std::chrono::steady_clock::now();
    for (AudioStream *s : registry()) if (s->active) s->update();
    const double us = std::chrono::duration<double, std::micro>(std::chrono::steady_clock::now() - t0).count();
    g_cpu = (float)(us * 100.0 / (AUDIO_BLOCK_SAMPLES * 1e6 / AUDIO_SAMPLE_RATE_EXACT));
    if (g_cpu > g_cpu_max) g_cpu_max = g_cpu;
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
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
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
    if (mag <= 0.0f) {        // silent -> no block, but the phase keeps running (Teensy)
        phase_acc += freq / AUDIO_SAMPLE_RATE * AUDIO_BLOCK_SAMPLES;
        phase_acc -= floorf(phase_acc);
        return;
    }
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

// ---- AudioEffectEnvelope (Teensy effect_envelope.cpp, in float) -------------
void AudioEffectEnvelope::noteOn() {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    if (state == IDLE || state == DELAY || release_forced_count == 0) {
        mult = 0;
        count = delay_count;
        if (count > 0) { state = DELAY; inc = 0; }
        else { state = ATTACK; count = attack_count; inc = 1.0f / (float)count; }
    } else if (state != FORCED) {
        state = FORCED;                    // retrigger: ramp the running note to 0 first
        count = release_forced_count;
        inc = -mult / (float)count;
    }
}

void AudioEffectEnvelope::noteOff() {
    std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
    if (state != IDLE && state != FORCED) {
        state = RELEASE;
        count = release_count;
        inc = -mult / (float)count;
    }
}

bool AudioEffectEnvelope::isActive()  { std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock()); return state != IDLE; }
bool AudioEffectEnvelope::isSustain() { std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock()); return state == SUSTAIN; }

void AudioEffectEnvelope::update(void) {
    audio_block_t *block = receiveWritable(0);
    if (!block) return;                                   // no audio: the envelope does not run
    if (state == IDLE) { ::release(block); return; }      // idle: transmits nothing
    int16_t *p = block->data, *end = block->data + AUDIO_BLOCK_SAMPLES;
    while (p < end) {
        if (count == 0) {                                 // end of a segment: next state
            if (state == ATTACK) {
                count = hold_count;
                if (count > 0) { state = HOLD; mult = 1.0f; inc = 0; }
                else { state = DECAY; count = decay_count; inc = (sustain_mult - 1.0f) / (float)count; }
                continue;
            } else if (state == HOLD) {
                state = DECAY; count = decay_count; inc = (sustain_mult - 1.0f) / (float)count;
                continue;
            } else if (state == DECAY) {
                state = SUSTAIN; count = 0xFFFF; mult = sustain_mult; inc = 0;
            } else if (state == SUSTAIN) {
                count = 0xFFFF;
            } else if (state == RELEASE) {
                state = IDLE;
                while (p < end) *p++ = 0;
                break;
            } else if (state == FORCED) {
                mult = 0;
                count = delay_count;
                if (count > 0) { state = DELAY; inc = 0; }
                else { state = ATTACK; count = attack_count; inc = 1.0f / (float)count; }
            } else if (state == DELAY) {
                state = ATTACK; count = attack_count; inc = 1.0f / (float)count;
                continue;
            }
        }
        // 8 samples, gain ramping linearly by inc/8 per sample (as the fixed-point code)
        const float step = inc * 0.125f;
        float m = mult;
        for (int k = 0; k < 8; k++) {
            m += step;
            float v = (float)p[k] * m;
            p[k] = v > 32767.0f ? 32767 : (v < -32768.0f ? -32768 : (int16_t)v);
        }
        p += 8;
        mult += inc;
        if (mult < 0) mult = 0;
        count--;
    }
    transmit(block);
    ::release(block);
}

// ---- AudioFilterStateVariable (Teensy filter_variable.cpp, in float) ----------
void AudioFilterStateVariable::update(void) {
    audio_block_t *in = receiveReadOnly(0);
    audio_block_t *ctl = receiveReadOnly(1);
    if (!in) { if (ctl) release(ctl); return; }
    audio_block_t *lpb = allocate();
    if (!lpb) { release(in); if (ctl) release(ctl); return; }
    audio_block_t *bpb = allocate();
    if (!bpb) { release(in); release(lpb); if (ctl) release(ctl); return; }
    audio_block_t *hpb = allocate();
    if (!hpb) { release(in); release(lpb); release(bpb); if (ctl) release(ctl); return; }

    const float k = 3.14159265f / (AUDIO_SAMPLE_RATE_EXACT * 2.0f);   // 2x oversampled
    float fmult = 2.0f * sinf(fc * k);
    float lp = lowpass, bp = bandpass, xprev = inputprev;
    for (int i = 0; i < AUDIO_BLOCK_SAMPLES; i++) {
        if (ctl) {                                  // per-sample corner modulation
            float f = fc * exp2f(octave * (ctl->data[i] * (1.0f / 32768.0f)));
            if (f > AUDIO_SAMPLE_RATE_EXACT / 2.5f) f = AUDIO_SAMPLE_RATE_EXACT / 2.5f;
            fmult = 2.0f * sinf(f * k);
        }
        const float x = (float)in->data[i];
        lp += fmult * bp;
        float hp = (x + xprev) * 0.5f - lp - damp * bp;
        xprev = x;
        bp += fmult * hp;
        float lpt = lp, bpt = bp, hpt = hp;
        lp += fmult * bp;
        hp = x - lp - damp * bp;
        bp += fmult * hp;
        lpt = (lpt + lp) * 0.5f; bpt = (bpt + bp) * 0.5f; hpt = (hpt + hp) * 0.5f;
        lpb->data[i] = sat16(lpt);
        bpb->data[i] = sat16(bpt);
        hpb->data[i] = sat16(hpt);
    }
    // The fixed-point original saturates its state; keep ours finite and bounded too.
    if (!std::isfinite(lp) || !std::isfinite(bp) || std::fabs(lp) > 1e7f || std::fabs(bp) > 1e7f) lp = bp = 0;
    lowpass = lp; bandpass = bp; inputprev = xprev;
    release(in);
    if (ctl) release(ctl);
    transmit(lpb, 0); release(lpb);
    transmit(bpb, 1); release(bpb);
    transmit(hpb, 2); release(hpb);
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
