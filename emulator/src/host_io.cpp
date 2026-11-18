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

// Executable directory (set by the frontend); SD.h uses it to find an sdcard folder
// next to a distributed binary, and the runtime files live there. Empty until set.
static std::string &base_dir() { static std::string *d = new std::string(); return *d; }
void ni404_set_base_dir(const char *d) { base_dir() = d ? d : ""; }
const char *ni404_base_dir() { return base_dir().c_str(); }

#ifndef EMU_TARGET_NAME
#define EMU_TARGET_NAME "emu"
#endif
const char *ni404_target_name() { return EMU_TARGET_NAME; }

// "<exe dir>/<target>-<name>": settings, EEPROM image, MIDI map/log per target.
const char *ni404_runtime_path(const char *name) {
    static thread_local std::string p;
    std::string dir = base_dir();
    p = dir.empty() ? std::string() : dir;
    if (!p.empty() && p.back() != '/' && p.back() != '\\') p += '/';
    p += EMU_TARGET_NAME;
    p += '-';
    p += name ? name : "";
    return p.c_str();
}

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

// ---- GPIO model + virtual wiring --------------------------------------------
// Teensy 4.1 has pins 0..54. Each remembers its pinMode and output latch; the wiring
// tables say which host control is soldered to which pin.
namespace {
const int NPINS = 64;
struct Gpio {
    std::atomic<uint8_t> mode[NPINS];
    std::atomic<uint8_t> out[NPINS];
    std::atomic<bool>    touched[NPINS];   // pinMode() was called at least once
    int btnSlot[NPINS];                    // host button wired here (-1 = none)
    int encClk[ENC_COUNT], encDt[ENC_COUNT];
    Gpio() {
        for (int i = 0; i < NPINS; i++) { mode[i] = INPUT; out[i] = LOW; touched[i] = false; btnSlot[i] = -1; }
        for (int i = 0; i < ENC_COUNT; i++) encClk[i] = encDt[i] = -1;
    }
};
Gpio &gpio() { static Gpio *g = new Gpio(); return *g; }   // construct-on-first-use
uint32_t g_noise = 0x2545F491u;
int floating_level() { g_noise ^= g_noise << 13; g_noise ^= g_noise >> 17; g_noise ^= g_noise << 5; return (int)(g_noise & 1); }
} // namespace

void pinMode(uint8_t pin, uint8_t mode) {
    if (pin >= NPINS) return;
    gpio().mode[pin] = mode;
    gpio().touched[pin] = true;
}
void digitalWrite(uint8_t pin, uint8_t val) {
    if (pin >= NPINS) return;
    gpio().out[pin] = val ? HIGH : LOW;
    // Arduino/Teensy: digitalWrite on an INPUT pin toggles its pull-up.
    if (gpio().mode[pin] == INPUT || gpio().mode[pin] == INPUT_PULLUP)
        gpio().mode[pin] = val ? INPUT_PULLUP : INPUT;
}
int digitalRead(uint8_t pin) {
    if (pin >= NPINS) return LOW;
    Gpio &g = gpio();
    const uint8_t m = g.mode[pin];
    if (m == OUTPUT) return g.out[pin];
    const int slot = g.btnSlot[pin];
    if (slot >= 0 && ni404_host_button_get(slot)) return LOW;   // closed: shorted to GND
    // Open switch / nothing connected: the pin is pulled, or floats.
    if (m == INPUT_PULLUP) return HIGH;
    if (m == INPUT_PULLDOWN) return LOW;
    return floating_level();
}
const char *ni404_pin_mode_name(int pin) {
    if (pin < 0 || pin >= NPINS || !gpio().touched[pin]) return "(not configured)";
    switch (gpio().mode[pin]) {
        case INPUT: return "INPUT"; case OUTPUT: return "OUTPUT";
        case INPUT_PULLUP: return "INPUT_PULLUP"; case INPUT_PULLDOWN: return "INPUT_PULLDOWN";
    }
    return "?";
}

void ni404_wire_encoder(int s, int clk, int dt) {
    if (s < 0 || s >= ENC_COUNT) return;
    gpio().encClk[s] = clk; gpio().encDt[s] = dt;
}
void ni404_wire_button(int s, int pin) {
    if (pin < 0 || pin >= NPINS || s < 0 || s >= BTN_COUNT) return;
    gpio().btnSlot[pin] = s;
}
int ni404_wiring_encoder_for(int clk, int dt, bool *reversed) {
    for (int s = 0; s < ENC_COUNT; s++) {
        if (gpio().encClk[s] == clk && gpio().encDt[s] == dt) { if (reversed) *reversed = false; return s; }
        if (gpio().encClk[s] == dt && gpio().encDt[s] == clk) { if (reversed) *reversed = true; return s; }
    }
    return -1;
}
int ni404_gpio_audit() {
    int warn = 0;
    for (int pin = 0; pin < NPINS; pin++) {
        if (gpio().btnSlot[pin] < 0) continue;
        const char *m = ni404_pin_mode_name(pin);
        const uint8_t mode = gpio().mode[pin];
        const char *why = nullptr;
        if (!gpio().touched[pin]) why = "never configured: floats";
        else if (mode == INPUT_PULLDOWN) why = "PULLDOWN on a button to GND: reads PRESSED while released";
        else if (mode == INPUT) why = "no pull-up: floats while released";
        else if (mode == OUTPUT) why = "driven as OUTPUT: the button would short it";
        std::printf("[gpio] pin %2d (button slot %d): %-16s %s%s\n", pin, gpio().btnSlot[pin], m,
                    why ? "WARNING: " : "ok", why ? why : "");
        if (why) warn++;
    }
    for (int s = 0; s < ENC_COUNT; s++)
        if (gpio().encClk[s] >= 0)
            std::printf("[gpio] encoder slot %d: CLK %d (%s), DT %d (%s)\n", s, gpio().encClk[s],
                        ni404_pin_mode_name(gpio().encClk[s]), gpio().encDt[s], ni404_pin_mode_name(gpio().encDt[s]));
    return warn;
}

// ---- interrupt lock + firmware lock -----------------------------------------
#include "emu_irq.h"
std::recursive_mutex &ni404_irq_lock() { static std::recursive_mutex *m = new std::recursive_mutex(); return *m; }
static thread_local bool t_irq_off = false;
void noInterrupts() { if (!t_irq_off) { ni404_irq_lock().lock(); t_irq_off = true; } }
void interrupts()   { if (t_irq_off) { t_irq_off = false; ni404_irq_lock().unlock(); } }

static std::recursive_mutex &fw_mutex() { static std::recursive_mutex *m = new std::recursive_mutex(); return *m; }
void ni404_fw_lock()   { fw_mutex().lock(); }
void ni404_fw_unlock() { fw_mutex().unlock(); }
static std::atomic<bool> g_fw_in_setup{false};
void ni404_fw_set_in_setup(bool v) { g_fw_in_setup = v; }
bool ni404_fw_in_setup() { return g_fw_in_setup.load(); }

// ---- global instances of the core/peripheral shims ------------------------
#include "EEPROM.h"
#include "SD.h"
#include "usb_midi.h"
#include "IntervalTimer.h"

EEPROMClass     EEPROM;
SDClass         SD;

static std::atomic<bool> g_sd_card{true};
void ni404_sd_set_card_present(bool present) { g_sd_card = present; }
bool ni404_sd_card_present() { return g_sd_card.load(); }
usb_midi_class  usbMIDI;

// ---- IntervalTimer thread ---------------------------------------------------
// One host thread plays the role of the Teensy's PIT interrupts: it sleeps until the
// earliest deadline, then runs every due callback under the interrupt lock. Started on
// the first IntervalTimer::begin(), so headless modes get real timers too.
#include <condition_variable>
void ni404_os_fine_timers(bool on);          // host_os.cpp (windows.h lives there)
void ni404_os_raise_thread_priority();
namespace {
std::vector<IntervalTimer *> &timers() { static std::vector<IntervalTimer *> *t = new std::vector<IntervalTimer *>(); return *t; }
std::mutex g_tmr_mtx;                 // guards the wake flag / thread state only
std::condition_variable g_tmr_cv;
bool g_tmr_wake = false, g_tmr_quit = false;
std::thread *g_tmr_thread = nullptr;

void timer_thread_main() {
    ni404_os_fine_timers(true);
    ni404_os_raise_thread_priority();        // it plays the part of an ISR
    for (;;) {
        long waitUs = 2000;   // re-check at least every 2 ms (timers may be added any time)
        {
            std::lock_guard<std::recursive_mutex> irq(ni404_irq_lock());
            const unsigned long now = micros();
            for (IntervalTimer *t : timers()) {
                long next = t->service(now);
                if (next < waitUs) waitUs = next;
            }
        }
        std::unique_lock<std::mutex> lk(g_tmr_mtx);
        if (g_tmr_quit) break;
        if (waitUs > 0)
            g_tmr_cv.wait_for(lk, std::chrono::microseconds(waitUs), [] { return g_tmr_wake || g_tmr_quit; });
        g_tmr_wake = false;
        if (g_tmr_quit) break;
    }
    ni404_os_fine_timers(false);
}
} // namespace

void ni404_register_timer(IntervalTimer *t) {
    std::lock_guard<std::recursive_mutex> irq(ni404_irq_lock());
    timers().push_back(t);
    std::lock_guard<std::mutex> lk(g_tmr_mtx);
    if (!g_tmr_thread) { g_tmr_quit = false; g_tmr_thread = new std::thread(timer_thread_main); }
}
void ni404_timers_wake() {
    std::lock_guard<std::mutex> lk(g_tmr_mtx);
    g_tmr_wake = true;
    g_tmr_cv.notify_one();
}
void ni404_timers_stop() {
    {
        std::lock_guard<std::mutex> lk(g_tmr_mtx);
        if (!g_tmr_thread) return;
        g_tmr_quit = true;
        g_tmr_cv.notify_one();
    }
    g_tmr_thread->join();
    delete g_tmr_thread;
    g_tmr_thread = nullptr;
}
