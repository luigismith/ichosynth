// gen_samples.cpp — synthesize a drum/tonal sample kit as 16-bit mono 44.1 kHz
// WAVs (standard 44-byte header) into the SD card structure, matching the format
// the NI404/toern firmware expects (samples/<folder>/_<id>.wav).
//
//   g++ -O2 -std=c++17 gen_samples.cpp -o gen_samples && ./gen_samples <outdir>
//
// Writes _300.._311.wav into <outdir> (default ../_SDCARD/3). Non-destructive.
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <vector>
#include <string>
#include <random>

static const int SR = 44100;
static std::mt19937 rng(1234);
static float frand() { return std::uniform_real_distribution<float>(-1.f, 1.f)(rng); }

static void writeWav(const std::string &path, const std::vector<float> &mono) {
    std::vector<int16_t> pcm(mono.size());
    for (size_t i = 0; i < mono.size(); i++) {
        float v = mono[i]; if (v > 1) v = 1; if (v < -1) v = -1;
        pcm[i] = (int16_t)std::lround(v * 32767.0);
    }
    uint32_t dataBytes = (uint32_t)pcm.size() * 2;
    uint32_t riff = 36 + dataBytes;
    FILE *f = std::fopen(path.c_str(), "wb");
    if (!f) { std::printf("ERR open %s\n", path.c_str()); return; }
    auto u32 = [&](uint32_t v) { std::fwrite(&v, 4, 1, f); };
    auto u16 = [&](uint16_t v) { std::fwrite(&v, 2, 1, f); };
    std::fwrite("RIFF", 1, 4, f); u32(riff); std::fwrite("WAVE", 1, 4, f);
    std::fwrite("fmt ", 1, 4, f); u32(16); u16(1); u16(1);          // PCM, mono
    u32(SR); u32(SR * 2); u16(2); u16(16);                          // rate, byterate, align, bits
    std::fwrite("data", 1, 4, f); u32(dataBytes);
    std::fwrite(pcm.data(), 2, pcm.size(), f);
    std::fclose(f);
    std::printf("  wrote %s (%.2fs)\n", path.c_str(), (double)mono.size() / SR);
}

static std::vector<float> buf(double sec) { return std::vector<float>((size_t)(sec * SR), 0.f); }
static float env(int i, int n, float a, float d) {  // simple AD envelope
    float t = (float)i / SR;
    if (t < a) return t / a;
    float td = t - a;
    return std::exp(-td / d);
}

// --- one-pole lowpass state ---
struct LP { float y = 0, a; LP(float cut) { a = 1.f - std::exp(-2.f * 3.14159f * cut / SR); } float p(float x) { y += a * (x - y); return y; } };

int main(int argc, char **argv) {
    std::string out = argc > 1 ? argv[1] : "../_SDCARD/3";
    std::printf("Generating kit into %s\n", out.c_str());

    // 300 KICK: pitch-swept sine
    { auto b = buf(0.45); LP lp(1200);
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float f = 120.f * std::exp(-t / 0.03f) + 42.f;
        static float ph = 0; ph += 2 * 3.14159f * f / SR;
        b[i] = lp.p(std::sin(ph)) * std::exp(-t / 0.18f); }
      writeWav(out + "/_300.wav", b); }

    // 301 SNARE: tone + noise
    { auto b = buf(0.25); float ph = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        ph += 2 * 3.14159f * 180.f / SR;
        float tone = std::sin(ph) * 0.5f, noise = frand();
        b[i] = (tone * 0.4f + noise * 0.7f) * std::exp(-t / 0.09f); }
      writeWav(out + "/_301.wav", b); }

    // 302 CLOSED HAT: hp-ish noise, short
    { auto b = buf(0.08); LP lp(9000), lp2(4000);
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float n = frand(); n = lp.p(n) - lp2.p(n);
        b[i] = n * std::exp(-t / 0.02f); }
      writeWav(out + "/_302.wav", b); }

    // 303 OPEN HAT: longer
    { auto b = buf(0.4); LP lp(10000), lp2(4500);
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float n = frand(); n = lp.p(n) - lp2.p(n);
        b[i] = n * std::exp(-t / 0.18f); }
      writeWav(out + "/_303.wav", b); }

    // 304 CLAP: 3 noise bursts + tail
    { auto b = buf(0.3); LP lp(6000), lp2(1500);
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float g = 0; for (float d : {0.f, 0.01f, 0.02f}) if (t >= d) g += std::exp(-(t - d) / 0.008f);
        g += 0.5f * std::exp(-t / 0.08f);
        float n = frand(); n = lp.p(n) - lp2.p(n);
        b[i] = n * g * 0.6f; }
      writeWav(out + "/_304.wav", b); }

    // 305 RIM: short bright click
    { auto b = buf(0.06); float ph = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        ph += 2 * 3.14159f * 1700.f / SR;
        b[i] = (std::sin(ph) * 0.6f + frand() * 0.4f) * std::exp(-t / 0.012f); }
      writeWav(out + "/_305.wav", b); }

    // 306 TOM: pitch-swept sine
    { auto b = buf(0.35); float ph = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float f = 180.f * std::exp(-t / 0.08f) + 90.f; ph += 2 * 3.14159f * f / SR;
        b[i] = std::sin(ph) * std::exp(-t / 0.16f); }
      writeWav(out + "/_306.wav", b); }

    // 307 COWBELL: two squares
    { auto b = buf(0.3); float p1 = 0, p2 = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        p1 += 2 * 3.14159f * 540.f / SR; p2 += 2 * 3.14159f * 800.f / SR;
        float s = ((std::sin(p1) > 0 ? 1 : -1) + (std::sin(p2) > 0 ? 1 : -1)) * 0.25f;
        b[i] = s * std::exp(-t / 0.12f); }
      writeWav(out + "/_307.wav", b); }

    // 308 BASS (C1 ~32.7 Hz saw, lowpassed)
    { auto b = buf(0.6); LP lp(900); float ph = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        ph += 65.41f / SR; if (ph >= 1) ph -= 1;
        b[i] = lp.p(2 * ph - 1) * std::exp(-t / 0.35f); }
      writeWav(out + "/_308.wav", b); }

    // 309 SQUARE BLIP (A4 440)
    { auto b = buf(0.18); float ph = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        ph += 2 * 3.14159f * 440.f / SR;
        b[i] = (std::sin(ph) > 0 ? 0.5f : -0.5f) * env((int)i, (int)b.size(), 0.002f, 0.05f); }
      writeWav(out + "/_309.wav", b); }

    // 310 SAW STAB (A3 220, lowpass decay) — persistent 1-pole, swept cutoff
    { auto b = buf(0.4); float ph = 0, y = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        ph += 220.f / SR; if (ph >= 1) ph -= 1;
        float cut = 3000.f * std::exp(-t / 0.2f) + 400.f;
        float a = 1.f - std::exp(-2.f * 3.14159f * cut / SR);
        y += a * ((2 * ph - 1) - y);
        b[i] = y * std::exp(-t / 0.22f); }
      writeWav(out + "/_310.wav", b); }

    // 311 NOISE SWEEP — persistent 1-pole whose cutoff rises over time
    { auto b = buf(0.5); float y = 0;
      for (size_t i = 0; i < b.size(); i++) { float t = (float)i / SR;
        float cut = 500.f + 8000.f * (t / 0.5f);
        float a = 1.f - std::exp(-2.f * 3.14159f * cut / SR);
        y += a * (frand() - y);
        b[i] = y * (1.f - t / 0.5f) * 0.8f; }
      writeWav(out + "/_311.wav", b); }

    std::printf("Done: 12 sounds (_300.._311) in %s\n", out.c_str());
    return 0;
}
