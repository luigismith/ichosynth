// host_io.cpp — implementations shared by the whole emulator: the monotonic
// clock that backs millis()/micros()/delay(), the global Serial/CrashReport
// objects, and the LED framebuffer bridge between FastLED.show() and the SDL
// frontend.
#include "Arduino.h"
#include "FastLED.h"
#include <chrono>
#include <thread>
#include <mutex>
#include <vector>
#include <string>

// Executable directory (set by the frontend from argv[0]); SD.h uses it to find
// an _SDCARD folder next to a distributed binary. Empty until set.
static std::string &base_dir() { static std::string *d = new std::string(); return *d; }
void ni404_set_base_dir(const char *d) { base_dir() = d ? d : ""; }
const char *ni404_base_dir() { return base_dir().c_str(); }

using clock_t_ = std::chrono::steady_clock;
static const clock_t_::time_point g_start = clock_t_::now();

unsigned long millis() {
    return (unsigned long)std::chrono::duration_cast<std::chrono::milliseconds>(
               clock_t_::now() - g_start).count();
}

unsigned long micros() {
    return (unsigned long)std::chrono::duration_cast<std::chrono::microseconds>(
               clock_t_::now() - g_start).count();
}

void delay(unsigned long ms) {
    std::this_thread::sleep_for(std::chrono::milliseconds(ms));
}

void delayMicroseconds(unsigned long us) {
    std::this_thread::sleep_for(std::chrono::microseconds(us));
}

HardwareSerial Serial;
HardwareSerial Serial1, Serial2, Serial3, Serial4, Serial5, Serial6, Serial7, Serial8;
CrashReportClass CrashReport;

// sbrk: TŒRN calls sbrk(0) to compute free RAM. Provide a pseudo-heap so the
// free-memory readout is plausible (and never crashes) on desktop.
extern "C" char *sbrk(int incr) {
    static char heap[1 << 20];
    static char *cur = heap;
    char *prev = cur;
    cur += incr;
    return prev;
}

// ---- LED framebuffer bridge ----------------------------------------------
CFastLED FastLED;

static std::mutex g_led_mtx;
static std::vector<CRGB> g_led_frame;   // brightness already applied
static uint64_t g_led_generation = 0;   // bumps each show() for dirty-checking

void ni404_publish_leds(const CRGB *leds, int count, uint8_t brightness) {
    std::lock_guard<std::mutex> lk(g_led_mtx);
    g_led_frame.resize(count);
    for (int i = 0; i < count; i++) {
        CRGB c = leds[i];
        if (brightness != 255) c.nscale8(brightness);
        g_led_frame[i] = c;
    }
    g_led_generation++;
}

// Frontend pulls the latest frame. Returns the generation so callers can skip
// redraw when nothing changed. `out` must hold at least `max` CRGB entries.
uint64_t ni404_get_leds(CRGB *out, int max, int *count) {
    std::lock_guard<std::mutex> lk(g_led_mtx);
    int n = (int)g_led_frame.size();
    if (n > max) n = max;
    for (int i = 0; i < n; i++) out[i] = g_led_frame[i];
    if (count) *count = n;
    return g_led_generation;
}

void CFastLED::delay(unsigned long ms) {
    show();
    ::delay(ms);
}

// ---- I2C + OLED framebuffer bridge ----------------------------------------
#include "Wire.h"
TwoWire Wire, Wire1, Wire2;

static std::mutex g_oled_mtx;
static std::vector<uint8_t> g_oled_fb;   // 1 byte/pixel
static int g_oled_w = 0, g_oled_h = 0;
static uint64_t g_oled_gen = 0;

void ni404_publish_oled(const uint8_t *fb, int w, int h) {
    std::lock_guard<std::mutex> lk(g_oled_mtx);
    g_oled_w = w; g_oled_h = h;
    g_oled_fb.assign(fb, fb + (size_t)w * h);
    g_oled_gen++;
}

// Frontend pulls the latest OLED frame. Returns generation (0 = never drawn).
uint64_t ni404_get_oled(uint8_t *out, int maxBytes, int *w, int *h) {
    std::lock_guard<std::mutex> lk(g_oled_mtx);
    if (w) *w = g_oled_w;
    if (h) *h = g_oled_h;
    int n = (int)g_oled_fb.size();
    if (n > maxBytes) n = maxBytes;
    for (int i = 0; i < n; i++) out[i] = g_oled_fb[i];
    return g_oled_gen;
}

// ---- host input state (frontend writes, compat Encoder/Switch shims read) --
#include "ni404_host.h"
#include <atomic>

static std::atomic<long> g_enc[ENC_COUNT] = {};
static std::atomic<bool> g_btn[BTN_COUNT] = {};

void ni404_host_encoder_add(int idx, long delta) { if (idx >= 0 && idx < ENC_COUNT) g_enc[idx] += delta; }
long ni404_host_encoder_get(int idx) { return (idx >= 0 && idx < ENC_COUNT) ? g_enc[idx].load() : 0; }
void ni404_host_encoder_set(int idx, long v) { if (idx >= 0 && idx < ENC_COUNT) g_enc[idx].store(v); }
void ni404_host_button_set(int idx, bool down) { if (idx >= 0 && idx < BTN_COUNT) g_btn[idx].store(down); }
bool ni404_host_button_get(int idx) { return (idx >= 0 && idx < BTN_COUNT) ? g_btn[idx].load() : false; }

// ---- global instances of the core/peripheral shims ------------------------
#include "EEPROM.h"
#include "SD.h"
#include "usb_midi.h"
#include "IntervalTimer.h"

EEPROMClass     EEPROM;
SDClass         SD;
usb_midi_class  usbMIDI;

// ---- IntervalTimer registry (pumped each ni404_loop) ----------------------
static std::vector<IntervalTimer *> &timers() { static std::vector<IntervalTimer *> *t = new std::vector<IntervalTimer *>(); return *t; }
void ni404_register_timer(IntervalTimer *t) { timers().push_back(t); }
void ni404_pump_timers() { for (IntervalTimer *t : timers()) t->pump(); }
