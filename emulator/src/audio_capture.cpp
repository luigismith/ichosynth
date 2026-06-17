// audio_capture.cpp — see audio_capture.h. SDL audio capture into a mono int16
// ring buffer at 44100 Hz, served to the AudioRecordQueue shim in 128-sample
// blocks. Multi-channel / non-44100 inputs are downmixed/handled by SDL's audio
// stream conversion (we request mono S16 44100).
#define NOMINMAX
#include <SDL.h>
#include "audio_capture.h"
#include <deque>
#include <mutex>
#include <string>
#include <cstring>

namespace {
std::string        g_devName;          // desired input device ("" = default)
SDL_AudioDeviceID  g_dev = 0;
std::mutex         g_mtx;
std::deque<int16_t> g_ring;            // captured mono samples, 44100 Hz
const size_t       RING_MAX = 44100 * 12;   // cap (~12 s) so it can't grow unbounded

void SDLCALL capture_cb(void * /*ud*/, Uint8 *stream, int len) {
    const int16_t *s = reinterpret_cast<const int16_t *>(stream);
    int n = len / (int)sizeof(int16_t);
    std::lock_guard<std::mutex> lk(g_mtx);
    for (int i = 0; i < n; i++) {
        if (g_ring.size() >= RING_MAX) g_ring.pop_front();   // drop oldest on overflow
        g_ring.push_back(s[i]);
    }
}
} // namespace

void ni404_capture_set_device(const char *name) { g_devName = name ? name : ""; }

void ni404_capture_start() {
    if (g_dev) return;                          // already capturing
    if (SDL_WasInit(SDL_INIT_AUDIO) == 0) SDL_InitSubSystem(SDL_INIT_AUDIO);
    SDL_AudioSpec want, have; SDL_zero(want);
    want.freq = 44100; want.format = AUDIO_S16SYS; want.channels = 1;
    want.samples = 512; want.callback = capture_cb;
    const char *name = g_devName.empty() ? nullptr : g_devName.c_str();
    g_dev = SDL_OpenAudioDevice(name, 1 /*iscapture*/, &want, &have,
                                SDL_AUDIO_ALLOW_FREQUENCY_CHANGE);
    if (!g_dev) {
        std::fprintf(stderr, "[capture] cannot open input '%s': %s\n",
                     name ? name : "(default)", SDL_GetError());
        return;
    }
    { std::lock_guard<std::mutex> lk(g_mtx); g_ring.clear(); }
    SDL_PauseAudioDevice(g_dev, 0);             // start
}

void ni404_capture_stop() {
    if (!g_dev) return;
    SDL_CloseAudioDevice(g_dev);
    g_dev = 0;
}

int ni404_capture_available() {
    std::lock_guard<std::mutex> lk(g_mtx);
    return (int)(g_ring.size() / 128);
}

bool ni404_capture_read(int16_t *out128) {
    std::lock_guard<std::mutex> lk(g_mtx);
    if (g_ring.size() < 128) return false;
    for (int i = 0; i < 128; i++) { out128[i] = g_ring.front(); g_ring.pop_front(); }
    return true;
}
