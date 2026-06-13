// sample_import.cpp — see sample_import.h. Self-contained WAV reader + converter,
// no Arduino/firmware dependencies. Robust enough for typical sample libraries:
// parses the RIFF chunk list (skipping unknown chunks), supports PCM 8/16/24/32
// and IEEE float32, mono or stereo, any sample rate; downmixes to mono, linearly
// resamples to 44.1 kHz and writes 16-bit mono PCM.
#include "sample_import.h"
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <vector>
#include <cmath>

namespace {

struct Reader {
    FILE *f;
    bool u16(uint16_t &v) { return std::fread(&v, 2, 1, f) == 1; }
    bool u32(uint32_t &v) { return std::fread(&v, 4, 1, f) == 1; }
    bool tag(char out[4]) { return std::fread(out, 1, 4, f) == 4; }
};

static void fail(char *e, int n, const char *msg) { if (e && n > 0) std::snprintf(e, n, "%s", msg); }

// Little-endian helpers for packed sample frames.
static inline int32_t s24(const uint8_t *p) {
    int32_t v = (int32_t)(p[0] | (p[1] << 8) | (p[2] << 16));
    if (v & 0x800000) v |= ~0xFFFFFF;   // sign-extend
    return v;
}

} // namespace

bool ni404_wav_to_kit(const char *src, const char *dst, char *errbuf, int errlen) {
    FILE *f = std::fopen(src, "rb");
    if (!f) { fail(errbuf, errlen, "cannot open file"); return false; }
    Reader r{ f };

    char t[4];
    uint32_t riffSize = 0;
    if (!r.tag(t) || std::memcmp(t, "RIFF", 4) || !r.u32(riffSize) || !r.tag(t) || std::memcmp(t, "WAVE", 4)) {
        fail(errbuf, errlen, "not a WAV file"); std::fclose(f); return false;
    }

    uint16_t fmt = 0, channels = 0, bits = 0, blockAlign = 0;
    uint32_t rate = 0, byteRate = 0;
    bool haveFmt = false;
    std::vector<uint8_t> data;

    // Walk the chunk list.
    while (true) {
        char id[4]; uint32_t sz = 0;
        if (!r.tag(id) || !r.u32(sz)) break;
        if (!std::memcmp(id, "fmt ", 4)) {
            uint16_t af = 0;
            r.u16(af); r.u16(channels); r.u32(rate); r.u32(byteRate); r.u16(blockAlign); r.u16(bits);
            fmt = af;
            long extra = (long)sz - 16;
            if (af == 0xFFFE && extra >= 8) {       // WAVE_FORMAT_EXTENSIBLE: subformat tells PCM vs float
                uint16_t cbSize = 0, validBits = 0; uint32_t mask = 0; char guid[16];
                r.u16(cbSize); r.u16(validBits); r.u32(mask);
                std::fread(guid, 1, 16, f);
                fmt = (uint16_t)(guid[0] & 0xFF) | ((uint16_t)(guid[1] & 0xFF) << 8);
                extra -= 24;
            }
            if (extra > 0) std::fseek(f, extra, SEEK_CUR);   // skip the rest of fmt
            haveFmt = true;
        } else if (!std::memcmp(id, "data", 4)) {
            data.resize(sz);
            if (sz) std::fread(data.data(), 1, sz, f);
            if (sz & 1) std::fseek(f, 1, SEEK_CUR);          // chunks are word-aligned
        } else {
            std::fseek(f, sz + (sz & 1), SEEK_CUR);          // skip unknown chunk
        }
        if (std::feof(f)) break;
    }
    std::fclose(f);

    if (!haveFmt) { fail(errbuf, errlen, "no fmt chunk"); return false; }
    if (data.empty()) { fail(errbuf, errlen, "no audio data"); return false; }
    if (channels < 1 || channels > 8) { fail(errbuf, errlen, "bad channel count"); return false; }
    if (rate < 4000 || rate > 384000) { fail(errbuf, errlen, "bad sample rate"); return false; }

    const int bytesPerSample = bits / 8;
    if (bytesPerSample < 1) { fail(errbuf, errlen, "bad bit depth"); return false; }
    const int frameBytes = bytesPerSample * channels;
    const size_t frames = data.size() / (frameBytes ? frameBytes : 1);
    if (frames == 0) { fail(errbuf, errlen, "empty audio"); return false; }

    // Decode every frame to a mono float in [-1, 1] (average of channels).
    std::vector<float> mono(frames, 0.0f);
    const uint8_t *p = data.data();
    for (size_t i = 0; i < frames; i++) {
        float acc = 0.0f;
        const uint8_t *fp = p + i * frameBytes;
        for (int c = 0; c < channels; c++) {
            const uint8_t *sp = fp + c * bytesPerSample;
            float s = 0.0f;
            if (fmt == 3 && bits == 32) {                 // IEEE float
                float v; std::memcpy(&v, sp, 4); s = v;
            } else if (bits == 16) {
                int16_t v; std::memcpy(&v, sp, 2); s = v / 32768.0f;
            } else if (bits == 24) {
                s = s24(sp) / 8388608.0f;
            } else if (bits == 32) {                      // 32-bit int PCM
                int32_t v; std::memcpy(&v, sp, 4); s = v / 2147483648.0f;
            } else if (bits == 8) {                       // 8-bit unsigned PCM
                s = ((int)sp[0] - 128) / 128.0f;
            } else { fail(errbuf, errlen, "unsupported bit depth"); return false; }
            acc += s;
        }
        mono[i] = acc / channels;
    }

    // Linear-resample to 44100 Hz.
    const int OUT_RATE = 44100;
    std::vector<int16_t> out;
    if ((int)rate == OUT_RATE) {
        out.resize(frames);
        for (size_t i = 0; i < frames; i++) {
            float v = mono[i] * 32767.0f;
            out[i] = (int16_t)(v > 32767.0f ? 32767 : v < -32768.0f ? -32768 : v);
        }
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
            float v = (a + (b - a) * (float)frac) * 32767.0f;
            out[i] = (int16_t)(v > 32767.0f ? 32767 : v < -32768.0f ? -32768 : v);
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
