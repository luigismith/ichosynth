// sample_import.cpp — see sample_import.h. Decodes a source audio file (WAV/MP3/
// FLAC via audio_decode) to mono float, linearly resamples to 44.1 kHz and writes
// a 16-bit mono PCM WAV in the kit format the NI404/toern firmware expects.
#include "sample_import.h"
#include "audio_decode.h"
#include <cstdio>
#include <cstdint>
#include <vector>

static void fail(char *e, int n, const char *msg) { if (e && n > 0) std::snprintf(e, n, "%s", msg); }

bool ni404_wav_to_kit(const char *src, const char *dst, char *errbuf, int errlen) {
    std::vector<float> mono;
    unsigned int rate = 0;
    if (!ni404_decode_audio(src, mono, rate, errbuf, errlen)) return false;
    if (mono.empty())               { fail(errbuf, errlen, "empty audio"); return false; }
    if (rate < 4000 || rate > 384000) { fail(errbuf, errlen, "bad sample rate"); return false; }

    const size_t frames = mono.size();
    const int OUT_RATE = 44100;
    std::vector<int16_t> out;
    auto clamp16 = [](float v) -> int16_t {
        v *= 32767.0f; return (int16_t)(v > 32767.0f ? 32767 : v < -32768.0f ? -32768 : v);
    };
    if ((int)rate == OUT_RATE) {
        out.resize(frames);
        for (size_t i = 0; i < frames; i++) out[i] = clamp16(mono[i]);
    } else {
        const double ratio = (double)OUT_RATE / (double)rate;
        const size_t outN = (size_t)((double)frames * ratio);
        out.resize(outN);
        for (size_t i = 0; i < outN; i++) {
            double srcPos = (double)i / ratio;
            size_t i0 = (size_t)srcPos;
            double frac = srcPos - (double)i0;
            float a = mono[i0 < frames ? i0 : frames - 1];
            float b = mono[i0 + 1 < frames ? i0 + 1 : frames - 1];
            out[i] = clamp16(a + (b - a) * (float)frac);
        }
    }

    // Write a standard 44-byte-header 16-bit mono 44.1 kHz WAV.
    FILE *o = std::fopen(dst, "wb");
    if (!o) { fail(errbuf, errlen, "cannot write destination"); return false; }
    const uint32_t dataBytes = (uint32_t)(out.size() * 2);
    const uint32_t br = OUT_RATE * 2;
    auto w32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, o); };
    auto w16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, o); };
    std::fwrite("RIFF", 1, 4, o); w32(36 + dataBytes); std::fwrite("WAVE", 1, 4, o);
    std::fwrite("fmt ", 1, 4, o); w32(16); w16(1); w16(1);   // PCM, mono
    w32(OUT_RATE); w32(br); w16(2); w16(16);                 // rate, byterate, align, bits
    std::fwrite("data", 1, 4, o); w32(dataBytes);
    std::fwrite(out.data(), 2, out.size(), o);
    std::fclose(o);
    return true;
}
