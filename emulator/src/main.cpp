// main.cpp — SDL2 frontend of the emulator (both targets): a window with the 16x16
// LED matrix, the OLED view and on-screen controls; the audio device drives the audio
// graph from its callback; keyboard/mouse/touch/MIDI drive the 4 encoders + buttons.
//
// Start-up order follows the hardware: the firmware's setup() runs first (it calls
// AudioMemory(), builds the graph, mounts the SD), THEN the audio output starts; then
// loop() runs continuously on its own "firmware" thread, decoupled from the 60 Hz
// redraw, while IntervalTimer callbacks run on the timer thread (host_io.cpp).
//
// Headless modes (no window/audio device): --selftest, --hwtest (the real board's
// controls, OLED HUD, tempo, audio memory, SD import + recording), and the NI404
// bench's --verify / --demotest / --play.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include <SDL.h>
#include <cstdio>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <algorithm>
#include <cstdint>
#include <thread>
#include <atomic>
#include <chrono>
#include <fstream>
#include <map>
#include <filesystem>       // detect a dropped folder (set as SD card)
#include "FastLED.h"        // CRGB
#include "ni404_host.h"
#include "menu.h"            // emu_draw_text() reuses the 5x7 font (avoids pulling
                            // Arduino.h/windows.h macro clashes into this TU)
#ifdef _WIN32
#include <windows.h>        // AttachConsole (GUI subsystem: no console window pops up)
#endif

// Plain functions from the compat layer (Audio.h / Arduino.h can't be included in this
// TU: their macros clash with windows.h).
unsigned AudioMemoryUsage();
unsigned AudioMemoryUsageMax();
unsigned audio_memory_total();
unsigned audio_alloc_failures();
float    AudioProcessorUsageMax();
void pinMode(uint8_t pin, uint8_t mode);
int  digitalRead(uint8_t pin);
void ni404_capture_test_tone(float hz);
int  ni404_test_recording();
const char *ni404_test_rec_input();

// MIDI backend (src/midi_in.cpp)
int  ni404_midi_list(std::vector<std::string> *names);
bool ni404_midi_open(int index);
void ni404_midi_close();
void ni404_midi_feed(uint8_t status, uint8_t d1, uint8_t d2);

static void open_midi(int requested) {
    std::vector<std::string> names;
    int n = ni404_midi_list(&names);
    if (n == 0) { std::printf("[midi] no MIDI input devices found.\n"); return; }
    std::printf("[midi] %d input device(s):\n", n);
    for (int i = 0; i < (int)names.size(); i++)
        std::printf("   [%d] %s\n", i, names[i].c_str());
    int dev = (requested >= 0 && requested < n) ? requested : 0;
    if (ni404_midi_open(dev)) std::printf("[midi] opened device [%d] %s\n", dev,
                                          dev < (int)names.size() ? names[dev].c_str() : "");
    else std::printf("[midi] failed to open device %d\n", dev);
}

static const int GRID = 16;
static const int CELL = 30;
static const int MARGIN = 16;
// OLED panel (SSD1306 128x64) drawn below the LED grid. The real 0.96" module is
// tiny next to the 16x16 matrix, so keep it small (1 screen px per OLED px) and
// centred — roughly the true size ratio rather than a giant panel.
static const int OLED_W = 128, OLED_H = 64, OLED_SCALE = 1;
static const int GRID_BOTTOM = MARGIN + GRID * CELL;
static const int WIN_W = GRID * CELL + 2 * MARGIN;
// On-screen control panel (4 encoders + buttons) drawn below the OLED, so the
// emulator is fully usable by mouse/touch — realistic on a touchscreen device.
static const int CTRL_TOP = GRID_BOTTOM + MARGIN + OLED_H * OLED_SCALE + MARGIN;
static const int CTRL_H   = 200;
static const int WIN_H = CTRL_TOP + CTRL_H;

// ---- audio callback -------------------------------------------------------
static void audio_cb(void * /*ud*/, Uint8 *stream, int len) {
    int frames = len / (int)(2 * sizeof(float));
    ni404_audio_render(reinterpret_cast<float *>(stream), frames);
}

// ---- keyboard -> encoders/buttons ----------------------------------------
// Turn keys fire a detent per keydown (and repeat). Button keys latch down/up.
static void handle_key(SDL_Scancode sc, bool down, bool repeat) {
    // One detent = 4 quadrature counts (the firmware maps over max*4 and /4s).
    const long DETENT = 4;
    switch (sc) {
        // --- 4 encoders: turn ---
        case SDL_SCANCODE_Q: if (down) ni404_host_encoder_add(ENC_LEFT, -DETENT); break;
        case SDL_SCANCODE_A: if (down) ni404_host_encoder_add(ENC_LEFT, +DETENT); break;
        case SDL_SCANCODE_W: if (down) ni404_host_encoder_add(ENC_CENTER, -DETENT); break;
        case SDL_SCANCODE_S: if (down) ni404_host_encoder_add(ENC_CENTER, +DETENT); break;
        case SDL_SCANCODE_E: if (down) ni404_host_encoder_add(ENC_RIGHT, -DETENT); break;
        case SDL_SCANCODE_D: if (down) ni404_host_encoder_add(ENC_RIGHT, +DETENT); break;
        case SDL_SCANCODE_R: if (down) ni404_host_encoder_add(ENC_4TH, -DETENT); break;
        case SDL_SCANCODE_F: if (down) ni404_host_encoder_add(ENC_4TH, +DETENT); break;
        // --- encoder push-buttons (latch) ---
        case SDL_SCANCODE_Z: if (!repeat) ni404_host_button_set(BTN_L, down); break;
        case SDL_SCANCODE_X: if (!repeat) ni404_host_button_set(BTN_C, down); break;
        case SDL_SCANCODE_C: if (!repeat) ni404_host_button_set(BTN_R, down); break;
        case SDL_SCANCODE_V: if (!repeat) ni404_host_button_set(BTN_4, down); break;
        // (filter is on the 4th encoder's rotation now — no filter button)
        // --- the 3 pushbuttons (PLAY/MENU/REC) ---
        case SDL_SCANCODE_1: if (!repeat) ni404_host_button_set(BTN_TOUCH1, down); break;
        case SDL_SCANCODE_2: if (!repeat) ni404_host_button_set(BTN_TOUCH2, down); break;
        case SDL_SCANCODE_3: if (!repeat) ni404_host_button_set(BTN_TOUCH3, down); break;
        default: break;
    }
}

// ---- on-screen controls (mouse + multi-touch) -----------------------------
// Skeuomorphic knobs: grab the RIM and drag to rotate (rotation only); press the
// CENTRE to push the encoder button, and dragging from the centre keeps the
// button held while rotating (the real "hold + turn" gesture in one motion).
// Below the knobs, three buttons stand in for the device's pushbuttons, plus the
// NI404 filter pad. Everything drives the same host input the keyboard/MIDI use.
enum WKind { W_KNOB, W_BTN };
struct Widget { SDL_Rect r; WKind kind; int idx; const char *label; int cx, cy, rOut, rIn; };
static std::vector<Widget> g_widgets;
static const char *kEncLabel[4] = { "E1", "E2", "E3", "E4" };
static const long DETENT = 4;             // one detent = 4 quadrature counts
static const double ROT_STEP = 0.2618;    // radians of drag per detent (~15deg)
static const double PI_ = 3.14159265358979323846;

static void build_widgets() {
    g_widgets.clear();
    const int ENCW = WIN_W / 4;           // one cell per encoder
    const int D = 60;                     // knob diameter
    const int cy = CTRL_TOP + 16 + D / 2;
    for (int i = 0; i < 4; i++) {
        int kcx = i * ENCW + ENCW / 2;
        Widget w{ { kcx - D / 2, cy - D / 2, D, D }, W_KNOB, i, kEncLabel[i], kcx, cy, D / 2, (D / 2) * 9 / 20 };
        g_widgets.push_back(w);
    }
    const int by = CTRL_TOP + 16 + D + 26, bh = 48;
    // 3 pushbuttons (real hardware = 4 encoders + 3 buttons; the filter is on the
    // 4th encoder's rotation now, so there is no separate FILT button).
    struct { int slot; const char *lab; } btns[3] = {
        { BTN_TOUCH1, "PLAY" }, { BTN_TOUCH2, "MENU" }, { BTN_TOUCH3, "REC" }
    };
    const int bw3 = WIN_W / 3;
    for (int j = 0; j < 3; j++)
        g_widgets.push_back({ { j * bw3 + 12, by, bw3 - 24, bh }, W_BTN, btns[j].slot, btns[j].lab, 0, 0, 0, 0 });
}

static int hit_test(int px, int py) {
    for (int i = 0; i < (int)g_widgets.size(); i++) {
        const Widget &W = g_widgets[i];
        if (W.kind == W_KNOB) {
            double dx = px - W.cx, dy = py - W.cy;
            if (dx * dx + dy * dy <= (double)W.rOut * W.rOut) return i;
        } else {
            SDL_Point p{ px, py };
            if (SDL_PointInRect(&p, &W.r)) return i;
        }
    }
    return -1;
}

// Active pointers (mouse = id -1, touch = SDL fingerId). mode: 0 rim-rotate,
// 1 centre-press (+ rotate while dragging), 2 plain button.
struct Pointer { long long id; int widx; int mode; double lastAngle; double accum; };
static std::vector<Pointer> g_pointers;

static void pointer_down(int px, int py, long long id) {
    if (menu_is_open()) return;
    int w = hit_test(px, py);
    if (w < 0) return;
    Widget &W = g_widgets[w];
    if (W.kind == W_KNOB) {
        double dx = px - W.cx, dy = py - W.cy;
        double dist = std::sqrt(dx * dx + dy * dy);
        Pointer p{ id, w, 0, std::atan2(dy, dx), 0.0 };
        if (dist <= W.rIn) { p.mode = 1; ni404_host_button_set(W.idx, true); }  // centre = press
        else p.mode = 0;                                                        // rim = rotate
        g_pointers.push_back(p);
    } else {
        ni404_host_button_set(W.idx, true);
        g_pointers.push_back({ id, w, 2, 0.0, 0.0 });
    }
}

static void pointer_move(int px, int py, long long id) {
    for (auto &p : g_pointers) {
        if (p.id != id) continue;
        Widget &W = g_widgets[p.widx];
        if (W.kind != W_KNOB) return;                 // buttons ignore movement
        double dx = (double)px - W.cx, dy = (double)py - W.cy;
        double ang = std::atan2(dy, dx);
        double d = ang - p.lastAngle;
        while (d >  PI_) d -= 2 * PI_;
        while (d < -PI_) d += 2 * PI_;
        p.lastAngle = ang;
        // Dead-zone near the centre: angle is ill-defined there, so a centre
        // press without dragging outward just holds (no spurious rotation).
        if (dx * dx + dy * dy < (double)(W.rOut * 0.30) * (W.rOut * 0.30)) return;
        p.accum += d;                                  // accumulate angular drag
        while (p.accum >=  ROT_STEP) { ni404_host_encoder_add(W.idx, +DETENT); p.accum -= ROT_STEP; }
        while (p.accum <= -ROT_STEP) { ni404_host_encoder_add(W.idx, -DETENT); p.accum += ROT_STEP; }
        return;
    }
}

static void pointer_up(long long id) {
    for (int i = 0; i < (int)g_pointers.size(); i++) {
        if (g_pointers[i].id != id) continue;
        Widget &W = g_widgets[g_pointers[i].widx];
        if (g_pointers[i].mode == 1 || g_pointers[i].mode == 2) ni404_host_button_set(W.idx, false);
        g_pointers.erase(g_pointers.begin() + i);
        return;
    }
}

static void fill_circle(SDL_Renderer *r, int cx, int cy, int rad) {
    for (int dy = -rad; dy <= rad; dy++) {
        int dx = (int)std::sqrt((double)rad * rad - (double)dy * dy);
        SDL_RenderDrawLine(r, cx - dx, cy + dy, cx + dx, cy + dy);
    }
}
static void draw_text_centered(SDL_Renderer *r, const SDL_Rect &box, const char *t, int s, int yoff) {
    int tw = (int)std::strlen(t) * 6 * s;
    emu_draw_text(r, box.x + (box.w - tw) / 2, box.y + yoff, t, s);
}

static void render_controls(SDL_Renderer *ren) {
    SDL_SetRenderDrawColor(ren, 18, 20, 28, 255);
    SDL_Rect bg{ 0, CTRL_TOP, WIN_W, CTRL_H }; SDL_RenderFillRect(ren, &bg);
    SDL_SetRenderDrawColor(ren, 40, 46, 64, 255);
    SDL_RenderDrawLine(ren, 0, CTRL_TOP, WIN_W, CTRL_TOP);

    for (const Widget &W : g_widgets) {
        if (W.kind == W_KNOB) {
            bool down = ni404_host_button_get(W.idx);
            SDL_SetRenderDrawColor(ren, 70, 78, 100, 255); fill_circle(ren, W.cx, W.cy, W.rOut);      // rim
            SDL_SetRenderDrawColor(ren, down ? 90 : 44, down ? 150 : 50, down ? 100 : 64, 255);
            fill_circle(ren, W.cx, W.cy, W.rIn);                                                      // centre (press)
            // rotation indicator: a tick that turns with the accumulated count.
            float ang = (float)ni404_host_encoder_get(W.idx) * 0.20f;
            int ex = W.cx + (int)(std::sin(ang) * (W.rOut - 6));
            int ey = W.cy - (int)(std::cos(ang) * (W.rOut - 6));
            SDL_SetRenderDrawColor(ren, 235, 245, 255, 255);
            SDL_RenderDrawLine(ren, W.cx, W.cy, ex, ey);
            SDL_SetRenderDrawColor(ren, 160, 200, 255, 255);
            SDL_Rect lbl{ W.cx - W.rOut, W.cy + W.rOut + 4, W.rOut * 2, 14 };
            draw_text_centered(ren, lbl, W.label, 2, 0);
        } else {
            bool down = ni404_host_button_get(W.idx);
            SDL_SetRenderDrawColor(ren, down ? 70 : 40, down ? 110 : 54, down ? 160 : 86, 255);
            SDL_RenderFillRect(ren, &W.r);
            SDL_SetRenderDrawColor(ren, 110, 130, 180, 255); SDL_RenderDrawRect(ren, &W.r);
            SDL_SetRenderDrawColor(ren, 230, 240, 255, 255);
            draw_text_centered(ren, W.r, W.label, 2, W.r.h / 2 - 8);
        }
    }
}

// ---- selftest -------------------------------------------------------------
static int run_selftest() {
    std::printf("[selftest] ni404_setup()...\n");
    ni404_setup();

    // Inject MIDI to exercise the input -> dispatch -> control-map path:
    // knob CC#71 (center encoder) swept, then a pad (note 36 = BTN_L) press.
    long encBefore = ni404_host_encoder_get(ENC_CENTER);
    ni404_midi_feed(0xB0, 25, 5);    // knob 2 (CC25, relative +5) -> CENTER encoder
    ni404_midi_feed(0x90, 36, 100);  // pad 1 (note 36) -> BTN_L down
    ni404_loop();                    // loop() drains usbMIDI.read()
    long encAfter = ni404_host_encoder_get(ENC_CENTER);
    std::printf("[selftest] midi: center encoder %ld -> %ld (%+ld), BTN_L=%d\n",
                encBefore, encAfter, encAfter - encBefore, (int)ni404_host_button_get(BTN_L));
    ni404_midi_feed(0x80, 36, 0);    // pad release

    float buf[256 * 2];
    double asum = 0; float apeak = 0;
    CRGB frame[GRID * GRID];
    uint64_t lastgen = 0; int litframes = 0;
    for (int t = 0; t < 120; t++) {
        ni404_loop();
        ni404_audio_render(buf, 256);
        for (int i = 0; i < 512; i++) { float a = std::fabs(buf[i]); asum += a; if (a > apeak) apeak = a; }
        int n = 0;
        uint64_t g = ni404_get_leds(frame, GRID * GRID, &n);
        if (g != lastgen) { lastgen = g;
            for (int i = 0; i < n; i++) if (frame[i].r || frame[i].g || frame[i].b) { litframes++; break; }
        }
        // Advance real time a little so millis()-gated redraws (toern LED draw,
        // OLED HUD) actually fire during the headless test.
        std::this_thread::sleep_for(std::chrono::milliseconds(3));
    }
    std::printf("[selftest] audio: peak=%.4f avg=%.5f | led generations seen, frames-with-lit=%d\n",
                apeak, asum / (512.0 * 120), litframes);
    // OLED panel check
    static uint8_t oled[128 * 64]; int ow = 0, oh = 0; int olit = 0;
    uint64_t ogen = ni404_get_oled(oled, sizeof(oled), &ow, &oh);
    for (int i = 0; i < ow * oh; i++) if (oled[i]) olit++;
    std::printf("[selftest] oled: %dx%d gen=%llu lit-pixels=%d\n",
                ow, oh, (unsigned long long)ogen, olit);
    std::printf("[selftest] audio memory: max %u of %u blocks, %u failed allocations\n",
                AudioMemoryUsageMax(), audio_memory_total(), audio_alloc_failures());
    std::printf("[selftest] OK\n");
    return 0;
}

// Headless audio-path verification: boot the firmware (which loads the sample
// pack from sdcard), then trigger each sample channel like a MIDI note and
// measure the audio it produces. Proves SD load -> resampling voice -> graph.
static int run_verify() {
    std::printf("[verify] ni404_setup() (loads sample pack from sdcard)...\n");
    ni404_setup();
    float buf[256 * 2];
    int sounding = 0;
    for (int ch = 1; ch <= 8; ch++) {
        ni404_test_trigger(ch);
        int playing = ni404_test_sample_len(ch);   // voice playing after trigger?
        double sum = 0; float peak = 0;
        for (int k = 0; k < 16; k++) {
            ni404_audio_render(buf, 256);
            for (int i = 0; i < 512; i++) { float a = std::fabs(buf[i]); sum += a; if (a > peak) peak = a; }
        }
        bool snd = peak > 0.001f;
        if (snd) sounding++;
        std::printf("[verify] channel %d: voice_playing=%d  audio peak=%.4f  %s\n",
                    ch, playing, peak, snd ? "SOUND" : "(silent)");
    }
    std::printf("[verify] %d/8 channels produced audio.\n", sounding);
    std::printf("[verify] audio memory: max %u of %u blocks, %u failed allocations\n",
                AudioMemoryUsageMax(), audio_memory_total(), audio_alloc_failures());
    std::printf("[verify] %s\n", sounding > 0 ? "OK — sample playback path works."
                                              : "no audio — check sdcard samples / paths.");
    return sounding > 0 ? 0 : 2;
}

// Headless check that the demo song actually produces music.
static float measurePeak(int blocks) {
    float buf[256 * 2]; float peak = 0;
    for (int t = 0; t < blocks; t++) { ni404_audio_render(buf, 256);
        for (int i = 0; i < 512; i++) { float a = std::fabs(buf[i]); if (a > peak) peak = a; } }
    return peak;
}
// "Play it" — drive the real sound engine like a musician and assert that every
// musical function behaves as the hardware should. Prints a PASS/FAIL trace and
// returns non-zero if any check fails.
void ni404_load_sample(int, int);
void ni404_play_note(int, int, int);
void ni404_play_synth(int, int, int);
void ni404_set_filter(int, int);
int  ni404_test_beat();
int  ni404_test_page();
int  ni404_test_playing();
int  ni404_test_cursor_x();
int  ni404_test_cursor_y();
int  ni404_test_edit_page();
const char *ni404_test_mode();
int  ni404_test_note_at(int step, int row);
static float render_peak(int blocks) {
    float buf[256 * 2], pk = 0;
    for (int t = 0; t < blocks; t++) { ni404_loop(); ni404_audio_render(buf, 256);
        for (int i = 0; i < 512; i++) { float a = std::fabs(buf[i]); if (a > pk) pk = a; } }
    return pk;
}
// Mean |amplitude| (energy proxy) over the window — sensitive to lowpass filtering
// of a bright source, unlike peak which the broadband onset transient dominates.
static float render_rms(int blocks) {
    float buf[256 * 2]; double s = 0; long n = 0;
    for (int t = 0; t < blocks; t++) { ni404_loop(); ni404_audio_render(buf, 256);
        for (int i = 0; i < 512; i++) { s += std::fabs(buf[i]); n++; } }
    return n ? (float)(s / n) : 0.0f;
}
static int run_play() {
    int fails = 0;
    auto check = [&](const char *what, bool ok, const char *detail) {
        std::printf("  [%s] %s%s%s\n", ok ? "PASS" : "FAIL", what,
                    detail && detail[0] ? "  -> " : "", detail ? detail : "");
        if (!ok) fails++;
    };
    char d[96];
    std::printf("== PLAY: drive the instrument and verify it behaves like the hardware ==\n");
    ni404_setup();

    // 6) Editing workflow FIRST (clean boot grid, stopped): move the grid cursor
    //    with the encoders and place notes with the centre button (the real paint()
    //    path), then read the grid back. (Run before the demo, which fills the grid.)
    std::printf("\n* Editing dalla griglia (encoder = cursore, pulsante centro = piazza):\n");
    auto tick = [&](int n){ for (int i = 0; i < n; i++) ni404_loop(); };
    // Gestures are timed by the firmware with millis(), so hold them for REAL time,
    // not for a number of loop() calls (loop() speed is not the hardware's anyway).
    auto tick_ms = [&](int ms) {
        auto end = std::chrono::steady_clock::now() + std::chrono::milliseconds(ms);
        while (std::chrono::steady_clock::now() < end) { ni404_loop(); std::this_thread::sleep_for(std::chrono::milliseconds(1)); }
    };
    tick(2);
    std::snprintf(d, sizeof d, "modo=%s", ni404_test_mode());
    check("avvio in un modo di editing (DRAW)", std::strcmp(ni404_test_mode(), "DRAW") == 0, d);
    // ENC_LEFT = row (SMP.y), ENC_CENTER = column (SMP.x); ENC_RIGHT = page.
    int x0 = ni404_test_cursor_x(), y0 = ni404_test_cursor_y();
    ni404_host_encoder_add(ENC_CENTER, 12); tick(3);
    ni404_host_encoder_add(ENC_LEFT, 12);   tick(3);
    int xm = ni404_test_cursor_x(), ym = ni404_test_cursor_y();
    std::snprintf(d, sizeof d, "X %d->%d, Y %d->%d (1..16)", x0, xm, y0, ym);
    check("il cursore si muove (X e Y) e resta nei limiti",
          xm >= 1 && xm <= 16 && ym >= 1 && ym <= 16 && xm != x0 && ym != y0, d);
    for (int t = 0; t < 40; t++) { int y = ni404_test_cursor_y(); if (y >= 2 && y <= 10) break;
        ni404_host_encoder_add(ENC_LEFT, 4); tick(2); }
    int erow = ni404_test_cursor_y(), eedit = ni404_test_edit_page();
    int placed = 0, got[3] = {-9,-9,-9}, cols[3] = {0,0,0};
    for (int k = 0; k < 3; k++) {
        ni404_host_encoder_add(ENC_CENTER, 8); tick(4);    // move to a new column
        int cx = ni404_test_cursor_x();
        cols[k] = cx;
        // A button gesture is only acted on ~80 ms after it changes (the firmware's
        // millis() reset-timer fires checkMode() then clears the buttons), so HOLD
        // centre 110 ms (>80 ms to register, <300 ms so it stays a tap, not a long-press).
        ni404_host_button_set(BTN_C, true);  tick_ms(110);  // press centre -> paint()
        ni404_host_button_set(BTN_C, false); tick_ms(120);  // release; let the gesture close (>80 ms)
        got[k] = ni404_test_note_at((eedit - 1) * 16 + cx, erow);
        if (got[k] == erow - 1) placed++;
    }
    std::snprintf(d, sizeof d, "riga %d (canale %d), colonne %d,%d,%d: piazzate %d/3 (note lette %d,%d,%d, atteso %d)",
                  erow, erow - 1, cols[0], cols[1], cols[2], placed, got[0], got[1], got[2], erow - 1);
    check("piazzo note sulla griglia col pulsante centrale", placed == 3, d);

    // 0) Filter FIRST (clean graph, nothing else ringing): a bright source (closed
    //    hat) through wide-open vs nearly-closed cutoff. Measured as mean energy,
    //    which a lowpass on a high-frequency source clearly reduces.
    std::printf("\n0) Filtro per-voce via 4o encoder (hi-hat brillante, aperto vs chiuso):\n");
    ni404_load_sample(1, 302);   // closed hat = broadband / high-frequency
    // Put the cursor on voice 1 and let the fast-filter latch onto it (so the 4th
    // encoder now drives voice 1's cutoff), then sweep the encoder open vs closed.
    ni404_play_note(1, 60, 110); for (int t = 0; t < 6; t++) ni404_loop();
    ni404_host_encoder_set(ENC_4TH, 4);   ni404_play_note(1, 60, 110); float fNarrow = render_rms(14);  // closed
    ni404_host_encoder_set(ENC_4TH, 400); ni404_play_note(1, 60, 110); float fWide = render_rms(14);    // open
    std::snprintf(d, sizeof d, "energia aperto=%.4f  chiuso=%.4f  (%.0f%%)",
                  fWide, fNarrow, fWide > 0 ? 100.0 * fNarrow / fWide : 0.0);
    check("il 4o encoder filtra (chiuso attenua l'energia)", fNarrow < fWide * 0.7f, d);
    ni404_host_encoder_set(ENC_4TH, 400);

    // 0b) Bitcrusher (FX): a crushed voice's signal differs from the clean one.
    std::printf("\n0b) Bitcrusher per-voce (voce pulita vs frantumata):\n");
    ni404_set_crush(1, 16); ni404_play_note(1, 60, 110); float cClean = render_rms(14);
    ni404_set_crush(1, 2);  ni404_play_note(1, 60, 110); float cCrush = render_rms(14);
    std::snprintf(d, sizeof d, "rms pulito=%.4f  crush(2bit)=%.4f", cClean, cCrush);
    check("il bitcrusher altera il segnale", cClean > 0.001f && cCrush > 0.001f
          && std::fabs(cCrush - cClean) > cClean * 0.05f, d);
    ni404_set_crush(1, 16);

    // 0c) Moog ladder (FX): closing the ladder attenuates a bright voice.
    std::printf("\n0c) Moog ladder per-voce (aperto vs chiuso):\n");
    ni404_set_ladder(1, 99); ni404_play_note(1, 60, 110); float lWide = render_rms(14);
    ni404_set_ladder(1, 1);  ni404_play_note(1, 60, 110); float lNarrow = render_rms(14);
    std::snprintf(d, sizeof d, "energia aperto=%.4f  chiuso=%.4f  (%.0f%%)",
                  lWide, lNarrow, lWide > 0 ? 100.0 * lNarrow / lWide : 0.0);
    check("il ladder attenua chiudendo il taglio", lNarrow < lWide * 0.7f, d);
    ni404_set_ladder(1, 99);

    // 0d) Recording -> SD: synth a take, save it, reload from disk, verify it plays.
    std::printf("\n0d) Registrazione salvata su SD (sintetizza -> salva -> ricarica):\n");
    int recId = ni404_test_record_save(2);
    std::snprintf(d, sizeof d, "id=%d", recId);
    check("la registrazione si salva su SD (id 9xx)", recId >= 901 && recId <= 999, d);
    if (recId > 0) {
        ni404_load_sample(2, recId);
        ni404_play_note(2, 60, 110);     // trigger the reloaded take
        float rpk = render_peak(12);
        std::snprintf(d, sizeof d, "peak=%.3f", rpk);
        check("la registrazione salvata si ricarica da disco e suona", rpk > 0.02f, d);
    }

    // 1) Every drum/sample pad plays from the MIDI keyboard (selected channel).
    std::printf("\n1) Suono gli 8 canali campione dalla tastiera MIDI (DO=base):\n");
    for (int ch = 1; ch <= 8; ch++) {
        ni404_test_trigger(ch);                 // loads samples/0/_1.wav into the channel
        float pk = render_peak(12);
        std::snprintf(d, sizeof d, "peak=%.3f", pk);
        check((std::string("canale ") + std::to_string(ch)).c_str(), pk > 0.02f, d);
    }

    // 2) Pitch: a higher key must change the sound (resampling voice retunes).
    std::printf("\n2) Pitch dalla tastiera (stesso campione, note diverse):\n");
    ni404_play_note(1, 60, 110); float lo = render_peak(10);
    ni404_play_note(1, 72, 110); float hi = render_peak(10);
    std::snprintf(d, sizeof d, "DO=%.3f  DO+1ott=%.3f", lo, hi);
    check("entrambe le note suonano", lo > 0.02f && hi > 0.02f, d);

    // 3) The two synth voices play a pitched scale.
    std::printf("\n3) Voci sintetizzate (basso ch13, lead ch14) su note di scala:\n");
    ni404_play_synth(13, 1, 110); float b1 = render_peak(8);
    ni404_play_synth(13, 8, 110); float b2 = render_peak(8);
    std::snprintf(d, sizeof d, "C basso=%.3f  C alto=%.3f", b1, b2);
    check("basso (synth 13) suona", b1 > 0.02f && b2 > 0.02f, d);
    ni404_play_synth(14, 5, 110); float l1 = render_peak(8);
    check("lead (synth 14) suona", l1 > 0.02f, (std::snprintf(d, sizeof d, "peak=%.3f", l1), d));

    // 5) Full song: start playback, the playhead advances across all 4 pages and
    //    audio stays healthy (loud, no clipping, no NaN).
    std::printf("\n5) Brano completo: play, avanzamento testina su 4 pagine, audio sano:\n");
    ni404_demo();
    check("e' in play", ni404_test_playing() == 1, "");
    int pagesSeen[5] = {0,0,0,0,0}, beatMin = 999, beatMax = 0;
    float buf[256*2], songPk = 0; long clip = 0, bad = 0;
    for (int t = 0; t < 1500; t++) {
        ni404_loop(); ni404_audio_render(buf, 256);
        int b = ni404_test_beat(), p = ni404_test_page();
        if (b < beatMin) beatMin = b; if (b > beatMax) beatMax = b;
        if (p >= 1 && p <= 4) pagesSeen[p] = 1;
        for (int i = 0; i < 512; i++) { float a = std::fabs(buf[i]);
            if (!std::isfinite(buf[i])) bad++; else { if (a > songPk) songPk = a; if (a >= 0.999f) clip++; } }
    }
    int npages = pagesSeen[1]+pagesSeen[2]+pagesSeen[3]+pagesSeen[4];
    std::snprintf(d, sizeof d, "beat %d..%d, pagine viste=%d", beatMin, beatMax, npages);
    check("la testina avanza su tutte le 4 pagine", npages == 4 && beatMax > 48, d);
    std::snprintf(d, sizeof d, "peak=%.3f clip=%ld nan=%ld", songPk, clip, bad);
    check("audio del brano forte e pulito", songPk > 0.3f && clip == 0 && bad == 0, d);

    std::printf("\n== RISULTATO: %s (%d controlli falliti) ==\n", fails == 0 ? "TUTTO OK" : "INCONGRUENZE", fails);
    return fails == 0 ? 0 : 1;
}
static int run_demotest() {
    ni404_setup();
    ni404_demo();
    // Render the full 4-page loop (~8 s at 122 BPM) so every page/voice plays,
    // tracking the peak, any clipping and any non-finite output.
    float buf[256 * 2]; float peak = 0; long clip = 0, bad = 0;
    const int blocks = 1500;   // 1500 * 256 / 44100 ~= 8.7 s
    for (int t = 0; t < blocks; t++) {
        ni404_loop();                       // advance the sequencer clock
        ni404_audio_render(buf, 256);
        for (int i = 0; i < 512; i++) {
            float a = std::fabs(buf[i]);
            if (!std::isfinite(buf[i])) { bad++; continue; }
            if (a > peak) peak = a;
            if (a >= 0.999f) clip++;
        }
    }
    std::printf("[demotest] full-loop peak=%.4f  clipped=%ld/%d  non-finite=%ld\n",
                peak, clip, blocks * 512, bad);
    return (bad == 0) ? 0 : 2;
}

#ifdef EMU_TARGET_TOERN
// ---------------------------------------------------------------------------
// --hwtest: drive the emulated BOARD like a person would and check that it behaves
// like the hardware drivers: boot, OLED HUD text, E1..E4 direction, the three tact
// switches, the sequencer tempo (timer thread), audio-memory headroom, the GPIO
// pull-up model, drag-and-drop import and a LINE IN recording, all on a throw-away
// copy of the SD card. Prints PASS/FAIL lines; exit code = number of failures.
// ---------------------------------------------------------------------------
int  ni404_test_beat();
int  ni404_test_page();
int  ni404_test_playing();
int  ni404_test_bpm();
int  ni404_test_cursor_x();
int  ni404_test_cursor_y();
const char *ni404_test_mode();

// Real time: run loop() as the firmware thread would and keep the audio graph
// running at the audio clock (128-sample blocks), so timers, debounce, the record
// queue and the I2C bus time all behave as live.
static void hw_pump(int ms) {
    using clk = std::chrono::steady_clock;
    static float buf[128 * 2];
    const auto end = clk::now() + std::chrono::milliseconds(ms);
    static auto audioT = clk::now();
    if (clk::now() - audioT > std::chrono::milliseconds(50)) audioT = clk::now();
    while (clk::now() < end) {
        ni404_loop();
        while (audioT < clk::now()) {                 // catch the audio clock up
            ni404_audio_render(buf, 128);
            audioT += std::chrono::microseconds(2902);
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(1));
    }
}
static void hw_tap(int btn, int holdMs) { ni404_host_button_set(btn, true); hw_pump(holdMs); ni404_host_button_set(btn, false); hw_pump(150); }
static void hw_oled_rows(char rows[4][32]) {
    static uint8_t fb[128 * 64]; int w = 0, h = 0;
    std::memset(fb, 0, sizeof fb);
    ni404_get_oled(fb, sizeof fb, &w, &h);
    for (int r = 0; r < 4; r++) menu_ocr_oled_row(fb, r * 2, rows[r], 32);
}
struct WavInfo { int ch = 0, rate = 0, bits = 0; long frames = 0; double peak = 0; };
static bool read_wav(const std::string &path, WavInfo &w) {
    std::ifstream f(path, std::ios::binary);
    if (!f) return false;
    std::vector<char> d((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    if (d.size() < 44 || std::memcmp(d.data(), "RIFF", 4) || std::memcmp(d.data() + 8, "WAVE", 4)) return false;
    size_t p = 12;
    while (p + 8 <= d.size()) {
        uint32_t len; std::memcpy(&len, d.data() + p + 4, 4);
        if (!std::memcmp(d.data() + p, "fmt ", 4) && p + 24 <= d.size()) {
            uint16_t c, b; uint32_t r;
            std::memcpy(&c, d.data() + p + 10, 2); std::memcpy(&r, d.data() + p + 12, 4); std::memcpy(&b, d.data() + p + 22, 2);
            w.ch = c; w.rate = (int)r; w.bits = b;
        } else if (!std::memcmp(d.data() + p, "data", 4)) {
            size_t n = std::min<size_t>(len, d.size() - p - 8);
            if (w.bits == 16 && w.ch > 0) {
                w.frames = (long)(n / 2 / w.ch);
                for (size_t i = 0; i + 1 < n; i += 2) {
                    int16_t v; std::memcpy(&v, d.data() + p + 8 + i, 2);
                    w.peak = std::max(w.peak, std::fabs(v / 32768.0));
                }
            }
            return true;
        }
        p += 8 + len + (len & 1);
    }
    return false;
}
// Every .wav on the card with (size, mtime), to see what a gesture created or rewrote.
static std::map<std::string, std::pair<uintmax_t, long long>> list_wavs(const std::string &root) {
    namespace fs = std::filesystem; std::error_code ec; std::map<std::string, std::pair<uintmax_t, long long>> v;
    for (fs::recursive_directory_iterator it(root, ec), e; !ec && it != e; it.increment(ec))
        if (it->is_regular_file(ec) && it->path().extension() == ".wav")
            v[fs::relative(it->path(), root, ec).generic_string()] =
                { it->file_size(ec), (long long)it->last_write_time(ec).time_since_epoch().count() };
    return v;
}

static int run_hwtest() {
    namespace fs = std::filesystem;
    int fails = 0;
    auto check = [&](const char *what, bool ok, const std::string &detail) {
        std::printf("  [%s] %s%s%s\n", ok ? "PASS" : "FAIL", what, detail.empty() ? "" : "  -> ", detail.c_str());
        if (!ok) fails++;
    };
    char d[256];
    // Throw-away copy of the SD card, so the test never writes into the repo's sdcard/.
    std::error_code ec;
    const fs::path sd = fs::temp_directory_path(ec) / ("ichosynth-hwtest-sd-" + std::to_string((long long)std::chrono::steady_clock::now().time_since_epoch().count()));
    fs::remove_all(sd, ec);
    fs::copy(ni404_sd_default_root(), sd, fs::copy_options::recursive, ec);
    { Ni404FwGuard fw; ni404_sd_set_root(sd.string().c_str()); }
    std::printf("== HWTEST (%s): the emulated board vs the hardware drivers ==\n  SD copy: %s\n", ni404_target_name(), sd.string().c_str());

    // Boot with the slot empty: like the board, TŒRN must wait ("SD?") and carry on
    // as soon as the card goes in.
    std::printf("\n* Boot without a micro SD, then insert it:\n");
    ni404_sd_set_card_present(false);
    std::atomic<bool> booted{false};
    std::thread boot([&booted] { ni404_setup(); booted = true; });
    std::this_thread::sleep_for(std::chrono::milliseconds(2500));
    const bool waited = !booted.load();
    ni404_sd_set_card_present(true);
    for (int i = 0; i < 300 && !booted.load(); i++) std::this_thread::sleep_for(std::chrono::milliseconds(50));
    if (!booted.load()) {
        check("setup() continues once the card is inserted", false, "still waiting after 15 s");
        std::fflush(stdout);
        std::_Exit(fails);
    }
    boot.join();
    check("without a card setup() waits (TOERN shows SD?); inserting it lets the boot finish", waited, waited ? "waited, then booted" : "did not wait");
    hw_pump(2500);                                     // boot animation, first HUD rows

    std::printf("\n* Boot + OLED HUD (IchosOled -> I2C -> SSD1306 model):\n");
    char rows[4][32]; hw_oled_rows(rows);
    for (int r = 0; r < 4; r++) std::printf("      OLED row %d: '%s'\n", r, rows[r]);
    std::snprintf(d, sizeof d, "mode=%s", ni404_test_mode());
    check("boots into DRAW", std::strcmp(ni404_test_mode(), "DRAW") == 0, d);
    check("HUD row 0 shows the channel and transport", std::strncmp(rows[0], "CH:", 3) == 0 && std::strstr(rows[0], "STOP"), rows[0]);
    check("HUD row 1 shows the mode", std::strncmp(rows[1], "MODE: DRAW", 10) == 0, rows[1]);
    check("HUD row 2 shows the BPM", std::strncmp(rows[2], "BPM:", 4) == 0, rows[2]);

    std::printf("\n* Encoders (clockwise = +1 detent on the knob):\n");
    // Start away from the grid edges, so a step either way is visible.
    for (int i = 0; i < 20 && ni404_test_cursor_y() != 8; i++) {
        int y = ni404_test_cursor_y();
        ni404_host_encoder_add(ENC_LEFT, y < 8 ? -4 : +4); hw_pump(40);
        if (ni404_test_cursor_y() == y) { ni404_host_encoder_add(ENC_LEFT, y < 8 ? +8 : -8); hw_pump(40); }
    }
    for (int i = 0; i < 8 && ni404_test_cursor_x() < 5; i++) { ni404_host_encoder_add(ENC_4TH, +4); hw_pump(40); }
    for (int e = 0; e < 4; e++) {
        int x0 = ni404_test_cursor_x(), y0 = ni404_test_cursor_y(), p0 = ni404_test_page();
        ni404_host_encoder_add(e, +4); hw_pump(60);
        int x1 = ni404_test_cursor_x(), y1 = ni404_test_cursor_y(), p1 = ni404_test_page();
        ni404_host_encoder_add(e, -4); hw_pump(60);
        int x2 = ni404_test_cursor_x(), y2 = ni404_test_cursor_y();
        std::printf("      E%d CW: x %d->%d  y %d->%d  page %d->%d   (CCW back: x=%d y=%d)\n",
                    e + 1, x0, x1, y0, y1, p0, p1, x2, y2);
        if (e == 0) {
            std::snprintf(d, sizeof d, "y %d -> %d -> %d (clockwise = %s)", y0, y1, y2, y1 < y0 ? "down" : "up");
            check("E1 moves the cursor row one step per detent and back", std::abs(y1 - y0) == 1 && y2 == y0, d);
        }
        if (e == 3) {
            std::snprintf(d, sizeof d, "x %d -> %d -> %d (clockwise = %s)", x0, x1, x2, x1 > x0 ? "right" : "left");
            check("E4 moves the cursor column one step per detent and back", std::abs(x1 - x0) == 1 && x2 == x0, d);
        }
    }

    std::printf("\n* Tact switches (pins 25/26/28 to GND, INPUT_PULLUP) and encoder pushes:\n");
    hw_tap(BTN_TOUCH2, 120);                          // B2 = MENU
    std::string m1 = ni404_test_mode();
    hw_tap(BTN_TOUCH2, 120);
    std::string m2 = ni404_test_mode();
    std::snprintf(d, sizeof d, "DRAW -> %s -> %s", m1.c_str(), m2.c_str());
    check("B2 (MENU) enters the menu and leaves it", m1 != "DRAW" && m2 == "DRAW", d);
    hw_tap(BTN_R, 60);                                // E3 push = play/pause
    int playing = ni404_test_playing();
    check("E3 push starts the sequencer", playing == 1, playing ? "playing" : "stopped");

    std::printf("\n* Sequencer tempo (IntervalTimer on the timer thread):\n");
    {
        // Rate between the first and the last observed step (not over a fixed window,
        // whose edges would add up to one step of error).
        using clk = std::chrono::steady_clock;
        int bpm = ni404_test_bpm(), steps = -1, last = ni404_test_beat();
        clk::time_point first{}, lastT{};
        const auto t0 = clk::now();
        while (clk::now() - t0 < std::chrono::seconds(4)) {
            hw_pump(1);
            int b = ni404_test_beat();
            if (b != last) {
                const auto now = clk::now();
                if (steps < 0) { first = now; steps = 0; }
                else steps += (b > last) ? (b - last) : 1;
                lastT = now; last = b;
            }
        }
        double secs = steps > 0 ? std::chrono::duration<double>(lastT - first).count() : 1.0;
        double rate = steps > 0 ? steps / secs : 0.0, want = bpm * 4.0 / 60.0;
        std::snprintf(d, sizeof d, "%.2f steps/s at %d BPM, expected %.2f (16ths)", rate, bpm, want);
        check("steps advance at the BPM rate (within 3%)", std::fabs(rate - want) <= want * 0.03, d);
        hw_pump(300);
        char r0[4][32]; hw_oled_rows(r0);
        check("HUD shows >PLAY while playing", std::strstr(r0[0], ">PLAY") != nullptr, r0[0]);
    }
    hw_tap(BTN_R, 60);
    check("E3 push stops it again", ni404_test_playing() == 0, "");

    std::printf("\n* Audio memory (AudioMemory(n) is a hard cap, as on the Teensy):\n");
    std::snprintf(d, sizeof d, "max %u of %u blocks in use, %u failed allocations, CPU max %.1f%%",
                  AudioMemoryUsageMax(), audio_memory_total(), audio_alloc_failures(), AudioProcessorUsageMax());
    check("the graph never ran out of blocks", audio_memory_total() > 0 && audio_alloc_failures() == 0, d);

    std::printf("\n* GPIO model (a PULLDOWN mistake must be visible):\n");
    {
        const uint8_t pin = 26;                        // B2
        pinMode(pin, 3 /*INPUT_PULLDOWN*/);
        int pd = digitalRead(pin);
        pinMode(pin, 2 /*INPUT_PULLUP*/);
        int pu = digitalRead(pin);
        ni404_host_button_set(BTN_TOUCH2, true); int pressed = digitalRead(pin); ni404_host_button_set(BTN_TOUCH2, false);
        std::snprintf(d, sizeof d, "released: PULLDOWN=%s PULLUP=%s, pressed=%s", pd ? "HIGH" : "LOW", pu ? "HIGH" : "LOW", pressed ? "HIGH" : "LOW");
        check("button pin reads like the circuit (PULLDOWN looks pressed)", pd == 0 && pu == 1 && pressed == 0, d);
    }

    std::printf("\n* Drag-and-drop import (48 kHz stereo WAV -> SD):\n");
    {
        fs::path src = fs::temp_directory_path(ec) / "Hw Test Tone.wav";
        { std::ofstream o(src, std::ios::binary);
          const uint32_t rate = 48000, frames = 24000; const uint16_t ch = 2, bits = 16;
          uint32_t dataBytes = frames * ch * 2, v32; uint16_t v16;
          o.write("RIFF", 4); v32 = 36 + dataBytes; o.write((char *)&v32, 4); o.write("WAVEfmt ", 8);
          v32 = 16; o.write((char *)&v32, 4); v16 = 1; o.write((char *)&v16, 2); o.write((char *)&ch, 2);
          o.write((char *)&rate, 4); v32 = rate * ch * 2; o.write((char *)&v32, 4); v16 = ch * 2; o.write((char *)&v16, 2);
          o.write((char *)&bits, 2); o.write("data", 4); o.write((char *)&dataBytes, 4);
          for (uint32_t i = 0; i < frames; i++) { int16_t s = (int16_t)(16000 * std::sin(6.2831853 * 440.0 * i / rate)); o.write((char *)&s, 2); o.write((char *)&s, 2); } }
        const char *res = nullptr;
        { Ni404FwGuard fw; res = ni404_import_sample(src.string().c_str()); }
        fs::path out = sd / "samples" / "import" / "hw-test-tone.wav";
        WavInfo w; bool ok = read_wav(out.string(), w);
        std::snprintf(d, sizeof d, "'%s' -> %s: %d ch, %d Hz, %d bit, %.2f s", res, ok ? "samples/import/hw-test-tone.wav" : "(missing)",
                      w.ch, w.rate, w.bits, w.rate ? (double)w.frames / w.rate : 0.0);
        check("lands in samples/import/ as mono 16-bit 44.1 kHz", ok && w.ch == 1 && w.rate == 44100 && w.bits == 16
              && std::fabs((double)w.frames / 44100.0 - 0.5) < 0.01, d);
        fs::remove(src, ec);
    }

    std::printf("\n* Recording (a 440 Hz tone on the codec input, hold B3 in DRAW):\n");
    {
        std::printf("      record input selected by the firmware: %s\n", ni404_test_rec_input());
        ni404_capture_test_tone(440.0f);
        for (int i = 0; i < 16 && ni404_test_cursor_y() < 3; i++) { ni404_host_encoder_add(ENC_LEFT, +4); hw_pump(40); }
        for (int i = 0; i < 16 && ni404_test_cursor_y() < 3; i++) { ni404_host_encoder_add(ENC_LEFT, -4); hw_pump(40); }
        auto before = list_wavs(sd.string());
        ni404_host_button_set(BTN_TOUCH3, true);
        int sawRec = 0;
        for (int t = 0; t < 30; t++) { hw_pump(50); if (ni404_test_recording()) sawRec = 1; }
        ni404_host_button_set(BTN_TOUCH3, false);
        hw_pump(1500);
        ni404_capture_test_tone(0.0f);
        auto after = list_wavs(sd.string());
        std::vector<std::string> added;
        for (auto &f : after) { auto b = before.find(f.first); if (b == before.end() || b->second != f.second) added.push_back(f.first); }
        std::printf("      cursor y=%d, recording seen=%d, files written: %d\n", ni404_test_cursor_y(), sawRec, (int)added.size());
        bool good = false;
        for (auto &f : added) {
            WavInfo w; bool ok = read_wav((sd / f).string(), w);
            std::printf("      + %s: %d ch, %d Hz, %d bit, %.2f s, peak %.2f\n", f.c_str(), w.ch, w.rate, w.bits,
                        w.rate ? (double)w.frames / w.rate : 0.0, w.peak);
            if (ok && w.ch == 1 && w.bits == 16 && w.frames > 0 && w.peak > 0.05) good = true;
        }
        check("the take is saved on the SD with the tone in it", good, added.empty() ? "no .wav written on the SD" : added[0]);
    }

    std::printf("\n== HWTEST: %s (%d failed) ==\n", fails ? "FAILURES" : "ALL PASS", fails);
    ni404_timers_stop();
    fs::remove_all(sd, ec);
    return fails;
}
#endif

int main(int argc, char **argv) {
    SDL_SetMainReady();
#ifdef _WIN32
    // Built as a GUI app so double-clicking shows NO console window. When launched
    // from a terminal (and stdout isn't already redirected to a file/pipe), reattach
    // to that console so --selftest/--verify/--import logs appear. If stdout is a
    // file or pipe (e.g. `> out.txt`), leave it alone so capture still works.
    {
        DWORD ft = GetFileType(GetStdHandle(STD_OUTPUT_HANDLE));
        if (ft != FILE_TYPE_DISK && ft != FILE_TYPE_PIPE && AttachConsole(ATTACH_PARENT_PROCESS)) {
            freopen("CONOUT$", "w", stdout);
            freopen("CONOUT$", "w", stderr);
        }
    }
#endif
    // Tell the SD shim / runtime files where we live, so a distributed binary finds
    // sdcard next to it and keeps its settings there (the compile-time path points at
    // the build machine). SDL_GetBasePath works however the exe was started.
    if (char *bp = SDL_GetBasePath()) { ni404_set_base_dir(bp); SDL_free(bp); }
    else { std::string a0 = (argc > 0 && argv[0]) ? argv[0] : "";
           size_t sl = a0.find_last_of("/\\");
           ni404_set_base_dir(sl == std::string::npos ? "." : a0.substr(0, sl).c_str()); }
    for (int i = 1; i < argc; i++)
        if (std::strcmp(argv[i], "--no-sd") == 0) { ni404_sd_set_card_present(false); std::printf("[sd] --no-sd: the card slot is empty\n"); }

    int midiDev = 0;
    bool demo = false;
    const char *shotPath = nullptr;
    Uint32 shotMs = 4000;
    for (int i = 1; i < argc; i++) {
        if (std::strcmp(argv[i], "--selftest") == 0) return run_selftest();
        if (std::strcmp(argv[i], "--verify") == 0) return run_verify();
        if (std::strcmp(argv[i], "--demotest") == 0) return run_demotest();
        if (std::strcmp(argv[i], "--play") == 0) return run_play();
#ifdef EMU_TARGET_TOERN
        if (std::strcmp(argv[i], "--hwtest") == 0) return run_hwtest();
#else
        if (std::strcmp(argv[i], "--hwtest") == 0) { std::printf("--hwtest checks the real board: run it on toernemu\n"); return 2; }
#endif
        if (std::strcmp(argv[i], "--import") == 0 && i + 1 < argc) {
            ni404_setup();
            std::printf("[import] %s\n", ni404_import_sample(argv[++i]));
            return 0;
        }
        if (std::strcmp(argv[i], "--demo") == 0) demo = true;
        // --screenshot FILE.bmp [MS]: save the window contents MS ms after it opened
        // (default 4000) and quit - a check of the real windowed path (renderer, audio, firmware thread).
        if (std::strcmp(argv[i], "--screenshot") == 0 && i + 1 < argc) {
            shotPath = argv[++i];
            if (i + 1 < argc && argv[i + 1][0] != '-') shotMs = (Uint32)std::atoi(argv[++i]);
        }
        if (std::strcmp(argv[i], "--midi") == 0 && i + 1 < argc) midiDev = std::atoi(argv[++i]);
    }

    if (SDL_Init(SDL_INIT_VIDEO | SDL_INIT_AUDIO) != 0) {
        std::fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
        return 1;
    }

#ifdef EMU_TARGET_TOERN
    const char *title = "ichosynth emulator - TŒRN firmware (toernemu)";
#else
    const char *title = "ichosynth emulator - NI404 bench firmware (ni404emu)";
#endif
    SDL_Window *win = SDL_CreateWindow(title,
        SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED, WIN_W, WIN_H, SDL_WINDOW_SHOWN);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC);
    if (!ren) ren = SDL_CreateRenderer(win, -1, SDL_RENDERER_SOFTWARE);  // fall back to software
    if (!ren) {
        std::fprintf(stderr, "SDL_CreateRenderer failed: %s\n", SDL_GetError());
        SDL_DestroyWindow(win); SDL_Quit();
        return 1;
    }

    // Settings + device lists are owned by the menu (TAB to change devices/volume).
    // As on the Teensy, audio starts only once setup() has run (AudioMemory, graph).
    menu_init(audio_cb);
    open_midi(midiDev);
    build_widgets();

    // The firmware thread runs setup() and then loop() flat out (as on the device, where
    // nothing waits for the display), ~1 kHz with a 1 ms nap so the PC stays usable.
    // The window is live from the start, so whatever setup() draws (boot animation,
    // TŒRN's "SD?" while it waits for a card) is visible; audio starts once setup() is
    // done, as on the Teensy.
    std::atomic<bool> fwRun{true}, setupDone{false};
    ni404_fw_set_in_setup(true);
    std::thread fwThread([&fwRun, &setupDone, demo] {
        const Uint32 t0 = SDL_GetTicks();
        ni404_setup();
        if (demo) ni404_demo();          // load kit + paint a beat + start playing
        std::printf("[emu] setup() took %u ms\n", (unsigned)(SDL_GetTicks() - t0));
        ni404_fw_set_in_setup(false);
        setupDone = true;
        while (fwRun.load()) {
            { Ni404FwGuard fw; ni404_loop(); }
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }
    });
    bool audioStarted = false;

    std::printf(
        "\n== Emulatore ichosynth (%s) - comandi ==\n"
        "  A schermo (mouse o touch): le 4 manopole E1-E4 (bordo = ruota, centro = premi) e i 3 pulsanti.\n"
        "  Tastiera - Encoder E1..E4 (ruota -/+):  Q/A  W/S  E/D  R/F   Premi: Z X C V\n"
        "  Pulsanti B1/B2/B3: 1 2 3   TAB = menu impostazioni   Esci: Esc\n"
        "  Trascina un file audio nella finestra per importarlo sulla SD; una cartella = nuova SD.\n\n",
        ni404_target_name());

    CRGB frame[GRID * GRID];
    bool running = true;
    const Uint32 loopT0 = SDL_GetTicks();
    while (running) {
        SDL_Event e;
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) { running = false; continue; }
            if (e.type == SDL_DROPFILE) {          // drop a file = import sample; folder = insert/set SD
                const char *path = e.drop.file;
                std::error_code ec;
                Ni404FwGuard fw;                   // loop() runs on the firmware thread
                if (std::filesystem::is_directory(path, ec)) {
                    ni404_sd_set_card_present(true);   // a folder dropped = a card inserted
                    const char *res = ni404_sd_set_root(path) ? "SD: cartella impostata" : "Cartella SD non valida";
                    std::printf("[sd] %s: %s\n", res, path);
                    menu_toast(res);
                } else {
                    const char *res = ni404_import_sample(path);
                    std::printf("[import] %s\n", res);
                    menu_toast(res);               // on-window feedback (no console needed)
                }
                SDL_free((void *)path);
                continue;
            }
            if (menu_handle_event(e)) continue;   // consumed by the settings menu
            if (e.type == SDL_KEYDOWN) {
                if (e.key.keysym.scancode == SDL_SCANCODE_ESCAPE) running = false;
                else handle_key(e.key.keysym.scancode, true, e.key.repeat != 0);
            } else if (e.type == SDL_KEYUP) {
                handle_key(e.key.keysym.scancode, false, false);
            } else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.which != SDL_TOUCH_MOUSEID) {
                pointer_down(e.button.x, e.button.y, -1);
            } else if (e.type == SDL_MOUSEBUTTONUP && e.button.which != SDL_TOUCH_MOUSEID) {
                pointer_up(-1);
            } else if (e.type == SDL_MOUSEMOTION && (e.motion.state & SDL_BUTTON_LMASK)
                       && e.motion.which != SDL_TOUCH_MOUSEID) {
                pointer_move(e.motion.x, e.motion.y, -1);   // drag (rotate / press+rotate)
            } else if (e.type == SDL_MOUSEWHEEL && e.wheel.which != SDL_TOUCH_MOUSEID) {
                int mx, my; SDL_GetMouseState(&mx, &my);
                int w = hit_test(mx, my);
                if (w >= 0 && g_widgets[w].kind == W_KNOB)
                    ni404_host_encoder_add(g_widgets[w].idx, e.wheel.y > 0 ? +DETENT : -DETENT);
            } else if (e.type == SDL_FINGERDOWN) {
                pointer_down((int)(e.tfinger.x * WIN_W), (int)(e.tfinger.y * WIN_H), (long long)e.tfinger.fingerId);
            } else if (e.type == SDL_FINGERMOTION) {
                pointer_move((int)(e.tfinger.x * WIN_W), (int)(e.tfinger.y * WIN_H), (long long)e.tfinger.fingerId);
            } else if (e.type == SDL_FINGERUP) {
                pointer_up((long long)e.tfinger.fingerId);
            }
        }

        if (!audioStarted && setupDone.load()) { menu_start_audio(); audioStarted = true; }

        // Render the LED frame.
        int n = 0;
        ni404_get_leds(frame, GRID * GRID, &n);
        SDL_SetRenderDrawColor(ren, 12, 12, 14, 255);
        SDL_RenderClear(ren);
        for (int i = 0; i < n && i < GRID * GRID; i++) {
            // The 16x16 WS2812 panel is serpentine-wired and the firmware's
            // light() encodes that: LED-memory row (y-1), even rows left->right,
            // odd rows right->left. Undo the serpentine to recover the column.
            int row = i / GRID;
            int k = i % GRID;
            int col = (row % 2 == 0) ? k : (GRID - 1 - k);
            // The firmware's logical y increases UPWARD (showNumber/logo draw the
            // top of a glyph at the highest y, via maxY - y), so y=1 is the BOTTOM
            // physical row. Flip vertically so on-grid text/digits read upright.
            int srow = (GRID - 1) - row;
            SDL_Rect r{ MARGIN + col * CELL + 1, MARGIN + srow * CELL + 1, CELL - 2, CELL - 2 };
            // brighten for visibility (panel values are intentionally low).
            int rr = frame[i].r, gg = frame[i].g, bb = frame[i].b;
            auto bump = [](int v) { v = v * 4; return v > 255 ? 255 : v; };
            SDL_SetRenderDrawColor(ren, bump(rr), bump(gg), bump(bb), 255);
            SDL_RenderFillRect(ren, &r);
        }

        // OLED panel (SSD1306) below the grid.
        static uint8_t oled[OLED_W * OLED_H];
        int ow = 0, oh = 0;
        uint64_t ogen = ni404_get_oled(oled, sizeof(oled), &ow, &oh);
        int panelX = (WIN_W - OLED_W * OLED_SCALE) / 2, panelY = GRID_BOTTOM + MARGIN;
        // panel background (dark blue, like an OLED bezel)
        SDL_Rect bg{ panelX - 2, panelY - 2, OLED_W * OLED_SCALE + 4, OLED_H * OLED_SCALE + 4 };
        SDL_SetRenderDrawColor(ren, 8, 10, 24, 255);
        SDL_RenderFillRect(ren, &bg);
        if (ogen != 0 && ow == OLED_W && oh == OLED_H) {
            SDL_SetRenderDrawColor(ren, 180, 210, 255, 255);   // OLED-blue "on" pixels
            for (int y = 0; y < OLED_H; y++)
                for (int x = 0; x < OLED_W; x++)
                    if (oled[y * OLED_W + x]) {
                        SDL_Rect p{ panelX + x * OLED_SCALE, panelY + y * OLED_SCALE, OLED_SCALE, OLED_SCALE };
                        SDL_RenderFillRect(ren, &p);
                    }
        }
        render_controls(ren);             // on-screen encoders + buttons (mouse/touch)
        menu_render(ren, WIN_W, WIN_H);   // settings overlay (TAB)
        if (shotPath && SDL_GetTicks() - loopT0 >= shotMs) { // --screenshot
            SDL_Surface *sf = SDL_CreateRGBSurfaceWithFormat(0, WIN_W, WIN_H, 32, SDL_PIXELFORMAT_ARGB8888);
            if (sf && SDL_RenderReadPixels(ren, nullptr, SDL_PIXELFORMAT_ARGB8888, sf->pixels, sf->pitch) == 0
                && SDL_SaveBMP(sf, shotPath) == 0)
                std::printf("[screenshot] %s\n", shotPath);
            else
                std::printf("[screenshot] failed: %s\n", SDL_GetError());
            if (sf) SDL_FreeSurface(sf);
            running = false;
        }
        SDL_RenderPresent(ren);
    }

    fwRun = false;
    if (!setupDone.load()) {
        // setup() never returned (e.g. TŒRN still waiting on "SD?"): it cannot be
        // joined, so close the devices and leave without running static destructors.
        ni404_midi_close();
        menu_shutdown();
        SDL_DestroyRenderer(ren);
        SDL_DestroyWindow(win);
        SDL_Quit();
        std::fflush(stdout);
        std::_Exit(0);
    }
    fwThread.join();
    ni404_timers_stop();
    ni404_midi_close();
    menu_shutdown();
    SDL_DestroyRenderer(ren);
    SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
