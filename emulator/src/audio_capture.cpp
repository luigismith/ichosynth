// audio_capture.cpp — see audio_capture.h.
//
// SDL captures mono S16 at whatever rate the device grants (have.freq — commonly 48 kHz
// on Windows); the samples go into a preallocated single-producer / single-consumer ring
// (the SDL callback writes, the audio-graph thread reads), so the callback never
// allocates or locks. The reader resamples to 44.1 kHz with linear interpolation.
#define NOMINMAX
#include <SDL.h>
#include "audio_capture.h"
#include <atomic>
#include <cmath>
#include <cstdio>
#include <mutex>
#include <string>
#include <vector>

namespace {
std::string        g_devName;               // desired input device ("" = default)
std::mutex         g_ctl;                   // open/close bookkeeping (never in the callback)
SDL_AudioDeviceID  g_dev = 0;
bool               g_always = false;
int                g_requests = 0;          // recordings in progress

// ring: power of two, ~3 s at 48 kHz; allocated once, before the first open
const size_t RING = 1u << 17;
std::vector<int16_t> g_ring;
std::atomic<size_t> g_w{0}, g_r{0};        // free-running indices
std::atomic<int>    g_rate{0};              // granted device rate (0 = closed)
std::atomic<bool>   g_flush{false};         // consumer: drop stale samples on (re)open

// resampler state (consumer thread only)
double  g_pos = 0.0;                        // fractional read position between s0 and s1
int16_t g_s0 = 0, g_s1 = 0;
bool    g_primed = false;

void SDLCALL capture_cb(void *, Uint8 *stream, int len) {
    const int16_t *s = reinterpret_cast<const int16_t *>(stream);
    const size_t n = (size_t)len / sizeof(int16_t);
    size_t w = g_w.load(std::memory_order_relaxed);
    const size_t r = g_r.load(std::memory_order_acquire);
    for (size_t i = 0; i < n; i++) {
        if (w - r >= RING) break;           // full: the reader is not keeping up, drop the rest
        g_ring[w & (RING - 1)] = s[i];
        w++;
    }
    g_w.store(w, std::memory_order_release);
}

std::atomic<bool> g_test_mode{false};       // headless tests: never open a real device

void open_device() {
    if (g_dev || g_test_mode) return;
    if (SDL_WasInit(SDL_INIT_AUDIO) == 0) SDL_InitSubSystem(SDL_INIT_AUDIO);
    if (g_ring.empty()) g_ring.assign(RING, 0);
    SDL_AudioSpec want, have;
    SDL_zero(want);
    want.freq = 44100; want.format = AUDIO_S16SYS; want.channels = 1;
    want.samples = 512; want.callback = capture_cb;
    const char *name = g_devName.empty() ? nullptr : g_devName.c_str();
    // Take the device's native rate (no SDL resampling); we resample to 44.1 kHz ourselves.
    g_dev = SDL_OpenAudioDevice(name, 1, &want, &have, SDL_AUDIO_ALLOW_FREQUENCY_CHANGE);
    if (!g_dev) {
        std::fprintf(stderr, "[capture] cannot open input '%s': %s\n", name ? name : "(default)", SDL_GetError());
        return;
    }
    std::printf("[capture] input '%s' open at %d Hz (resampled to 44100)\n", name ? name : "(default)", have.freq);
    g_flush = true;
    g_rate = have.freq;
    SDL_PauseAudioDevice(g_dev, 0);
}

void close_device() {
    if (!g_dev) return;
    SDL_CloseAudioDevice(g_dev);
    g_dev = 0;
    g_rate = 0;
}

void reconcile() {   // with g_ctl held
    if (g_always || g_requests > 0) open_device(); else close_device();
}
} // namespace

void ni404_capture_set_device(const char *name) {
    std::lock_guard<std::mutex> lk(g_ctl);
    std::string n = name ? name : "";
    if (n == g_devName) return;
    g_devName = n;
    if (g_dev) { close_device(); reconcile(); }   // reopen on the new device
}

void ni404_capture_set_always(bool on) {
    std::lock_guard<std::mutex> lk(g_ctl);
    g_always = on;
    reconcile();
}

void ni404_capture_request(bool on) {
    std::lock_guard<std::mutex> lk(g_ctl);
    if (on) g_requests++;
    else if (g_requests > 0) g_requests--;
    reconcile();
}

int ni404_capture_rate() { return g_rate.load(); }

void ni404_capture_shutdown() {
    std::lock_guard<std::mutex> lk(g_ctl);
    g_always = false; g_requests = 0;
    close_device();
}

// Headless tests: a sine "plugged into LINE IN" while no real device is open.
static std::atomic<float> g_tone_hz{0.0f};
static double g_tone_ph = 0.0;
void ni404_capture_test_tone(float hz) {
    g_tone_hz = hz;
    if (hz > 0.0f) {                              // the tone replaces any real input
        std::lock_guard<std::mutex> lk(g_ctl);
        g_test_mode = true;
        close_device();
    }
}

void ni404_capture_pull(int16_t *out, int n) {
    const int rate = g_rate.load(std::memory_order_acquire);
    const float tone = g_tone_hz.load();
    if (tone > 0.0f) {
        for (int i = 0; i < n; i++) {
            out[i] = (int16_t)(12000.0 * std::sin(g_tone_ph));
            g_tone_ph += 6.283185307179586 * tone / 44100.0;
            if (g_tone_ph > 6.283185307179586) g_tone_ph -= 6.283185307179586;
        }
        return;
    }
    if (rate <= 0 || g_ring.empty()) {
        for (int i = 0; i < n; i++) out[i] = 0;
        g_primed = false;
        return;
    }
    size_t r = g_r.load(std::memory_order_relaxed);
    const size_t w = g_w.load(std::memory_order_acquire);
    if (g_flush.exchange(false)) { r = w; g_primed = false; g_pos = 0; }
    // Keep latency bounded: if more than ~100 ms piled up (clock drift), skip ahead.
    if (w - r > (size_t)rate / 10) r = w - (size_t)rate / 20;
    auto next = [&](int16_t &v) -> bool {
        if (r == w) return false;
        v = g_ring[r & (RING - 1)];
        r++;
        return true;
    };
    if (!g_primed) {
        if (!next(g_s0) || !next(g_s1)) {
            for (int i = 0; i < n; i++) out[i] = 0;
            g_r.store(r, std::memory_order_release);
            return;
        }
        g_primed = true;
        g_pos = 0;
    }
    const double step = (double)rate / 44100.0;    // device samples per output sample
    for (int i = 0; i < n; i++) {
        out[i] = (int16_t)(g_s0 + (g_s1 - g_s0) * g_pos);
        g_pos += step;
        bool ok = true;
        while (g_pos >= 1.0 && ok) {
            g_pos -= 1.0;
            g_s0 = g_s1;
            ok = next(g_s1);
        }
        if (!ok) {                                  // underrun: hold the last sample, re-prime
            g_primed = false;
            for (int k = i + 1; k < n; k++) out[k] = g_s1;
            break;
        }
    }
    g_r.store(r, std::memory_order_release);
}
