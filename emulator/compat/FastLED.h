// FastLED.h — desktop shim. Emulates just enough of FastLED for the NI404:
// a CRGB type, a global FastLED controller whose show() snapshots the LED array
// into a shared framebuffer that the SDL frontend renders, brightness, clear,
// and fadeToBlackBy. Color order is irrelevant on screen (we draw r/g/b
// directly), so the BRG template argument is accepted and ignored.
#ifndef NI404_COMPAT_FASTLED_H
#define NI404_COMPAT_FASTLED_H

#include <cstdint>
#include <cstring>

// EOrder color-order tokens (ignored on desktop), as int constants so they work
// as non-type template arguments.
static const int RGB = 0, RBG = 1, GRB = 2, GBR = 3, BRG = 4, BGR = 5;

struct CHSV {
    union {
        struct { uint8_t h; uint8_t s; uint8_t v; };
        uint8_t raw[3];
    };
    CHSV() : h(0), s(0), v(0) {}
    CHSV(uint8_t hh, uint8_t ss, uint8_t vv) : h(hh), s(ss), v(vv) {}
};

static inline void ni404_hsv2rgb(uint8_t hh, uint8_t ss, uint8_t vv,
                                 uint8_t &r, uint8_t &g, uint8_t &b) {
    float H = hh / 255.0f * 6.0f, S = ss / 255.0f, V = vv / 255.0f;
    int i = (int)H; float f = H - i;
    float p = V * (1 - S), q = V * (1 - S * f), t = V * (1 - S * (1 - f));
    float rr, gg, bb;
    switch (((i % 6) + 6) % 6) {
        case 0: rr = V; gg = t; bb = p; break;
        case 1: rr = q; gg = V; bb = p; break;
        case 2: rr = p; gg = V; bb = t; break;
        case 3: rr = p; gg = q; bb = V; break;
        case 4: rr = t; gg = p; bb = V; break;
        default: rr = V; gg = p; bb = q;
    }
    r = (uint8_t)(rr * 255); g = (uint8_t)(gg * 255); b = (uint8_t)(bb * 255);
}

struct CRGB {
    union {
        struct { uint8_t r; uint8_t g; uint8_t b; };
        uint8_t raw[3];
    };
    CRGB() : r(0), g(0), b(0) {}
    CRGB(uint8_t ir, uint8_t ig, uint8_t ib) : r(ir), g(ig), b(ib) {}
    CRGB(uint32_t code) : r((code >> 16) & 0xFF), g((code >> 8) & 0xFF), b(code & 0xFF) {}
    CRGB(const CHSV &c) { ni404_hsv2rgb(c.h, c.s, c.v, r, g, b); }
    CRGB &operator=(const CHSV &c) { ni404_hsv2rgb(c.h, c.s, c.v, r, g, b); return *this; }

    enum HTMLColorCode : uint32_t {
        Black = 0x000000, White = 0xFFFFFF, Red = 0xFF0000,
        Green = 0x008000, Blue = 0x0000FF
    };

    CRGB &operator=(const CRGB &o) { r = o.r; g = o.g; b = o.b; return *this; }
    CRGB &operator=(uint32_t code) { r = (code >> 16) & 0xFF; g = (code >> 8) & 0xFF; b = code & 0xFF; return *this; }
    bool operator==(const CRGB &o) const { return r == o.r && g == o.g && b == o.b; }
    bool operator!=(const CRGB &o) const { return !(*this == o); }

    CRGB &fadeToBlackBy(uint8_t fade) {
        uint16_t scale = 255 - fade;
        r = (uint16_t)r * scale / 255;
        g = (uint16_t)g * scale / 255;
        b = (uint16_t)b * scale / 255;
        return *this;
    }
    // Scale a colour by an integer factor (the firmware does `col[i] * 12`),
    // clamping each channel to 255.
    CRGB operator*(int f) const {
        auto c = [f](uint8_t v) { int x = (int)v * f; return (uint8_t)(x > 255 ? 255 : (x < 0 ? 0 : x)); };
        return CRGB(c(r), c(g), c(b));
    }
    // Divide each channel (the firmware dims colours with `col[i] / n`).
    CRGB operator/(int d) const {
        if (d == 0) return *this;
        return CRGB((uint8_t)(r / d), (uint8_t)(g / d), (uint8_t)(b / d));
    }
    // Truthiness = "is this colour non-black" (firmware uses `if (!color)`).
    bool operator!() const { return r == 0 && g == 0 && b == 0; }
    CRGB &nscale8(uint8_t s) {
        r = (uint16_t)r * s / 255;
        g = (uint16_t)g * s / 255;
        b = (uint16_t)b * s / 255;
        return *this;
    }
    // Like nscale8 but a non-zero channel never scales fully to 0 (video safe).
    CRGB &nscale8_video(uint8_t scale) {
        auto sc = [scale](uint8_t v) -> uint8_t {
            uint8_t x = (uint16_t)v * scale >> 8;
            if (v && scale && x == 0) x = 1;
            return x;
        };
        r = sc(r); g = sc(g); b = sc(b);
        return *this;
    }
    CRGB &operator+=(const CRGB &o) {
        int t;
        t = r + o.r; r = t > 255 ? 255 : t;
        t = g + o.g; g = t > 255 ? 255 : t;
        t = b + o.b; b = t > 255 ? 255 : t;
        return *this;
    }
};

// Linear blend between two colours: amount 0 -> a, 255 -> b.
inline CRGB blend(const CRGB &a, const CRGB &b, uint8_t amount) {
    auto mix = [amount](uint8_t x, uint8_t y) -> uint8_t {
        return (uint8_t)(((uint16_t)x * (255 - amount) + (uint16_t)y * amount) / 255);
    };
    return CRGB(mix(a.r, b.r), mix(a.g, b.g), mix(a.b, b.b));
}

inline void hsv2rgb_rainbow(const CHSV &hsv, CRGB &rgb) {
    ni404_hsv2rgb(hsv.h, hsv.s, hsv.v, rgb.r, rgb.g, rgb.b);
}
inline CHSV rgb2hsv_approximate(const CRGB &rgb) {
    int r = rgb.r, g = rgb.g, b = rgb.b;
    int mx = r > g ? (r > b ? r : b) : (g > b ? g : b);
    int mn = r < g ? (r < b ? r : b) : (g < b ? g : b);
    int d = mx - mn;
    uint8_t v = (uint8_t)mx;
    uint8_t s = mx == 0 ? 0 : (uint8_t)(255 * d / mx);
    float h = 0;
    if (d != 0) {
        if (mx == r) h = (float)(g - b) / d;
        else if (mx == g) h = 2 + (float)(b - r) / d;
        else h = 4 + (float)(r - g) / d;
        h *= 60; if (h < 0) h += 360;
    }
    return CHSV((uint8_t)(h / 360.0f * 255), s, v);
}

// Free-function form: fadeToBlackBy(leds, count, amount).
inline void fadeToBlackBy(CRGB *leds, int count, uint8_t fade) {
    for (int i = 0; i < count; i++) leds[i].fadeToBlackBy(fade);
}
inline void fill_solid(CRGB *leds, int count, const CRGB &c) {
    for (int i = 0; i < count; i++) leds[i] = c;
}

// Implemented in host_io.cpp; publishes the current LED frame to the frontend.
void ni404_publish_leds(const CRGB *leds, int count, uint8_t brightness);

class CFastLED {
public:
    CRGB *_leds = nullptr;
    int _count = 0;
    uint8_t _brightness = 255;

    // The FIRST addLeds() (the main 16x16 matrix) is the panel we publish to the
    // frontend. Later strips (e.g. toern's external WS2812 strip) are ignored for
    // display so they don't overwrite the matrix.
    template <int CHIPSET, int PIN, int ORDER>
    CFastLED &addLeds(CRGB *data, int count) {
        if (!_leds) { _leds = data; _count = count; }
        return *this;
    }
    void setBrightness(uint8_t b) { _brightness = b; }
    void show() { if (_leds) ni404_publish_leds(_leds, _count, _brightness); }
    void clear(bool writeNow = false) {
        if (_leds) std::memset(_leds, 0, sizeof(CRGB) * _count);
        if (writeNow) show();
    }
    void delay(unsigned long ms);  // show() then sleep; defined in host_io.cpp
};

extern CFastLED FastLED;

#endif // NI404_COMPAT_FASTLED_H
