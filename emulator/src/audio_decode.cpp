// audio_decode.cpp — see audio_decode.h. Pulls in the dr_libs decoders (one TU
// owns the implementations) and exposes a single decode-to-mono-float entry.
#define DR_WAV_IMPLEMENTATION
#define DR_MP3_IMPLEMENTATION
#define DR_FLAC_IMPLEMENTATION
#include "dr_wav.h"
#include "dr_mp3.h"
#include "dr_flac.h"

#include "audio_decode.h"
#include <cstdio>
#include <cstring>
#include <string>

namespace {

static void fail(char *e, int n, const char *m) { if (e && n > 0) std::snprintf(e, n, "%s", m); }

static void downmix(const float *inter, unsigned int ch, size_t frames, std::vector<float> &mono) {
    mono.assign(frames, 0.0f);
    if (ch < 1) ch = 1;
    for (size_t i = 0; i < frames; i++) {
        float acc = 0.0f;
        for (unsigned int c = 0; c < ch; c++) acc += inter[i * ch + c];
        mono[i] = acc / (float)ch;
    }
}

static bool try_wav(const char *path, std::vector<float> &mono, unsigned int &rate) {
    unsigned int ch = 0, sr = 0; drwav_uint64 n = 0;
    float *d = drwav_open_file_and_read_pcm_frames_f32(path, &ch, &sr, &n, nullptr);
    if (!d) return false;
    downmix(d, ch, (size_t)n, mono); rate = sr; drwav_free(d, nullptr); return true;
}
static bool try_flac(const char *path, std::vector<float> &mono, unsigned int &rate) {
    unsigned int ch = 0, sr = 0; drflac_uint64 n = 0;
    float *d = drflac_open_file_and_read_pcm_frames_f32(path, &ch, &sr, &n, nullptr);
    if (!d) return false;
    downmix(d, ch, (size_t)n, mono); rate = sr; drflac_free(d, nullptr); return true;
}
static bool try_mp3(const char *path, std::vector<float> &mono, unsigned int &rate) {
    drmp3_config cfg; std::memset(&cfg, 0, sizeof cfg); drmp3_uint64 n = 0;
    float *d = drmp3_open_file_and_read_pcm_frames_f32(path, &cfg, &n, nullptr);
    if (!d) return false;
    downmix(d, cfg.channels, (size_t)n, mono); rate = cfg.sampleRate; drmp3_free(d, nullptr); return true;
}

static std::string ext_of(const char *path) {
    std::string s = path ? path : "";
    size_t dot = s.find_last_of('.');
    if (dot == std::string::npos) return "";
    std::string e = s.substr(dot + 1);
    for (char &c : e) c = (char)std::tolower((unsigned char)c);
    return e;
}

} // namespace

const char *ni404_decode_formats() { return "wav, mp3, flac"; }

bool ni404_decode_audio(const char *path, std::vector<float> &mono,
                        unsigned int &rate, char *err, int errlen) {
    if (!path || !*path) { fail(err, errlen, "no file"); return false; }
    std::string e = ext_of(path);
    // Try the format the extension suggests first, then fall back to sniffing the
    // others (so a mislabelled file still imports if it's a supported codec).
    bool ok = false;
    if (e == "mp3")                      ok = try_mp3(path, mono, rate);
    else if (e == "flac")                ok = try_flac(path, mono, rate);
    else if (e == "wav" || e == "wave")  ok = try_wav(path, mono, rate);
    if (!ok) ok = try_wav(path, mono, rate) || try_flac(path, mono, rate) || try_mp3(path, mono, rate);
    if (!ok) { fail(err, errlen, "formato non supportato (usa wav/mp3/flac)"); return false; }
    if (mono.empty()) { fail(err, errlen, "nessun audio nel file"); return false; }
    return true;
}
