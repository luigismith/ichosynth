// menu.cpp — in-window settings overlay. Audio output/input device selection,
// master volume, MIDI device + mapping info, key legend. Toggle with TAB.
// Settings persist to <target>-settings.txt next to the exe (ni404_runtime_path).
// Owns the SDL audio output device, which is opened only after the firmware's
// setup() (menu_start_audio), as the Teensy's audio starts once setup() ran.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include "menu.h"
#include "Adafruit_GFX.h"   // ni404_font5x7
#include "audio_capture.h"  // route the selected input device to the recorder
#include "ni404_host.h"     // SD root get/set, current channel, sample loader
#include <filesystem>
#include <algorithm>
#include <cctype>
#include <SDL.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>
#include <atomic>
#include <chrono>
#include <thread>

// From the audio engine / MIDI backend.
void  ni404_set_master_gain(float g);
float ni404_get_master_gain();
int   ni404_midi_list(std::vector<std::string> *names);

// ---- state ----------------------------------------------------------------
static bool g_open = false;
static int  g_sel = 0;
static SDL_AudioCallback g_cb = nullptr;
static SDL_AudioDeviceID g_adev = 0;

static std::vector<std::string> g_outDevs;   // [0] = "(default)"
static std::vector<std::string> g_inDevs;    // [0] = "(none)"
static int g_outSel = 0, g_inSel = 0;
static std::vector<std::string> g_midiDevs;

// ---- settings persistence -------------------------------------------------
static void settings_save() {
    FILE *f = std::fopen(ni404_runtime_path("settings.txt"), "w");
    if (!f) return;
    std::fprintf(f, "# NI404/toern emulator settings (edited via the in-app menu, TAB)\n");
    std::fprintf(f, "audio_out=%s\n", (g_outSel > 0 && g_outSel < (int)g_outDevs.size()) ? g_outDevs[g_outSel].c_str() : "");
    std::fprintf(f, "audio_in=%s\n", (g_inSel > 0 && g_inSel < (int)g_inDevs.size()) ? g_inDevs[g_inSel].c_str() : "");
    std::fprintf(f, "gain=%.2f\n", ni404_get_master_gain());
    std::fclose(f);
}

// ---- audio device handling ------------------------------------------------
static void enumerate_devices() {
    g_outDevs.clear(); g_outDevs.push_back("(default)");
    int n = SDL_GetNumAudioDevices(0);
    for (int i = 0; i < n; i++) { const char *nm = SDL_GetAudioDeviceName(i, 0); if (nm) g_outDevs.push_back(nm); }
    g_inDevs.clear(); g_inDevs.push_back("(nessuno: default solo in REC)");
    int m = SDL_GetNumAudioDevices(1);
    for (int i = 0; i < m; i++) { const char *nm = SDL_GetAudioDeviceName(i, 1); if (nm) g_inDevs.push_back(nm); }
    g_midiDevs.clear(); ni404_midi_list(&g_midiDevs);
}

// The chosen input device feeds the codec input (AudioInputI2S) all the time, so the
// firmware's input meter / monitoring work as on the board; "(nessuno)" opens the
// system default input only while a recording runs.
static void apply_input() {
    const bool chosen = g_inSel > 0 && g_inSel < (int)g_inDevs.size();
    ni404_capture_set_device(chosen ? g_inDevs[g_inSel].c_str() : "");
    ni404_capture_set_always(chosen);
}

// No usable output device (none plugged, remote/locked session): the Teensy's audio
// graph runs regardless (input meter, record queue, sequencer-driven envelopes), so a
// "null" audio clock keeps calling the render callback at the audio rate and drops the
// samples. Stopped as soon as a real device opens.
static std::atomic<bool> g_nullRun{false};
static std::thread g_nullThread;
static void null_audio(bool on) {
    if (on == g_nullRun.load()) return;
    if (!on) { g_nullRun = false; if (g_nullThread.joinable()) g_nullThread.join(); return; }
    g_nullRun = true;
    g_nullThread = std::thread([] {
        static float buf[256 * 2];
        auto next = std::chrono::steady_clock::now();
        while (g_nullRun.load()) {
            g_cb(nullptr, reinterpret_cast<Uint8 *>(buf), (int)sizeof buf);
            next += std::chrono::microseconds(5805);          // 256 frames at 44.1 kHz
            std::this_thread::sleep_until(next);
        }
    });
    std::printf("[menu] no audio output: running the audio graph on a silent clock\n");
}

static void open_output() {
    null_audio(false);
    if (g_adev) { SDL_CloseAudioDevice(g_adev); g_adev = 0; }
    SDL_AudioSpec want, have; SDL_zero(want);
    want.freq = 44100; want.format = AUDIO_F32SYS; want.channels = 2; want.samples = 256; want.callback = g_cb;
    const char *name = (g_outSel > 0 && g_outSel < (int)g_outDevs.size()) ? g_outDevs[g_outSel].c_str() : nullptr;
    g_adev = SDL_OpenAudioDevice(name, 0, &want, &have, 0);
    if (g_adev) SDL_PauseAudioDevice(g_adev, 0);
    else {
        std::fprintf(stderr, "[menu] failed to open audio device '%s': %s\n", name ? name : "(default)", SDL_GetError());
        null_audio(true);
    }
}

void menu_init(SDL_AudioCallback cb) {
    g_cb = cb;
    enumerate_devices();
    // Load settings.
    float gain = 2.0f; std::string outName, inName;
    if (FILE *f = std::fopen(ni404_runtime_path("settings.txt"), "r")) {
        char line[256];
        while (std::fgets(line, sizeof line, f)) {
            if (line[0] == '#') continue;
            char *nl = std::strpbrk(line, "\r\n"); if (nl) *nl = 0;
            if (!std::strncmp(line, "audio_out=", 10)) outName = line + 10;
            else if (!std::strncmp(line, "audio_in=", 9)) inName = line + 9;
            else if (!std::strncmp(line, "gain=", 5)) gain = (float)std::atof(line + 5);
        }
        std::fclose(f);
    }
    for (int i = 0; i < (int)g_outDevs.size(); i++) if (g_outDevs[i] == outName) g_outSel = i;
    for (int i = 0; i < (int)g_inDevs.size(); i++) if (g_inDevs[i] == inName) g_inSel = i;
    ni404_set_master_gain(gain);
    apply_input();
}

void menu_start_audio() { open_output(); }

void menu_shutdown() {
    null_audio(false);
    if (g_adev) { SDL_CloseAudioDevice(g_adev); g_adev = 0; }
    ni404_capture_shutdown();
}

bool menu_is_open() { return g_open; }

// ---- SD card folder + sample browser --------------------------------------
static bool g_browse = false;
static int  g_bsel = 0, g_btop = 0;
static std::vector<int> g_bids;
static std::vector<std::string> g_blabels;

// Scan the SD folder for sample files (_<n>.wav) and list them sorted by id.
static void browser_scan() {
    namespace fs = std::filesystem;
    g_bids.clear(); g_blabels.clear();
    std::error_code ec;
    std::string root = ni404_sd_root() ? ni404_sd_root() : "";
    fs::recursive_directory_iterator it(root, fs::directory_options::skip_permission_denied, ec), end;
    for (; !ec && it != end; it.increment(ec)) {
        if (!it->is_regular_file(ec)) continue;
        std::string name = it->path().filename().string();
        if (name.size() < 6 || name[0] != '_') continue;
        std::string lo = name; for (char &c : lo) c = (char)std::tolower((unsigned char)c);
        if (lo.compare(lo.size() - 4, 4, ".wav") != 0) continue;
        std::string num = name.substr(1, name.size() - 5);
        bool digits = !num.empty();
        for (char c : num) if (!std::isdigit((unsigned char)c)) digits = false;
        if (!digits) continue;
        g_bids.push_back(std::atoi(num.c_str()));
        g_blabels.push_back(name);
    }
    std::vector<int> idx(g_bids.size());
    for (size_t i = 0; i < idx.size(); i++) idx[i] = (int)i;
    std::sort(idx.begin(), idx.end(), [&](int a, int b) { return g_bids[a] < g_bids[b]; });
    std::vector<int> sid; std::vector<std::string> sl;
    for (int i : idx) { sid.push_back(g_bids[i]); sl.push_back(g_blabels[i]); }
    g_bids.swap(sid); g_blabels.swap(sl);
    g_bsel = 0; g_btop = 0;
}

static void open_sd_folder() {
    namespace fs = std::filesystem; std::error_code ec;
    std::string s = fs::absolute(ni404_sd_root() ? ni404_sd_root() : ".", ec).string();
    for (char &c : s) if (c == '\\') c = '/';
    std::string url = "file:///" + s;
    SDL_OpenURL(url.c_str());
}

// ---- menu items -----------------------------------------------------------
enum { IT_OUT = 0, IT_GAIN, IT_IN, IT_SD, IT_SD_RESET, IT_BROWSE,
       IT_MIDI, IT_MAP, IT_KEYS, IT_CLOSE, IT_COUNT };

static void adjust(int item, int dir) {
    if (item == IT_OUT) {
        int n = (int)g_outDevs.size(); g_outSel = (g_outSel + dir + n) % n; open_output(); settings_save();
    } else if (item == IT_GAIN) {
        float cur = ni404_get_master_gain();
        float step = cur < 4.0f ? 0.5f : 4.0f;       // finer at low end, coarser high
        float g = cur + dir * step; if (g < 0) g = 0; if (g > 64) g = 64;
        ni404_set_master_gain(g); settings_save();
    } else if (item == IT_IN) {
        int n = (int)g_inDevs.size(); g_inSel = (g_inSel + dir + n) % n; settings_save();
        apply_input();
    }
}

bool menu_handle_event(const SDL_Event &e) {
    if (e.type != SDL_KEYDOWN) return g_open;   // swallow all key events while open
    SDL_Scancode sc = e.key.keysym.scancode;

    // Sample browser sub-screen (entered from the SD section).
    if (g_browse) {
        int n = (int)g_bids.size();
        if (sc == SDL_SCANCODE_TAB || sc == SDL_SCANCODE_ESCAPE) { g_browse = false; return true; }
        if (sc == SDL_SCANCODE_UP)   { if (g_bsel > 0) g_bsel--; return true; }
        if (sc == SDL_SCANCODE_DOWN) { if (g_bsel < n - 1) g_bsel++; return true; }
        if (sc == SDL_SCANCODE_RETURN && n > 0) {
            Ni404FwGuard fw;                          // loop() runs on the firmware thread
            int ch = ni404_current_channel();
            ni404_load_sample(ch, g_bids[g_bsel]);
            char b[80]; std::snprintf(b, sizeof b, "%s -> canale %d", g_blabels[g_bsel].c_str(), ch);
            menu_toast(b);
            return true;
        }
        return true;   // consume everything else while browsing
    }

    if (sc == SDL_SCANCODE_TAB) { g_open = !g_open; return true; }
    if (!g_open) return false;
    switch (sc) {
        case SDL_SCANCODE_ESCAPE: g_open = false; return true;
        case SDL_SCANCODE_UP:     g_sel = (g_sel + IT_COUNT - 1) % IT_COUNT; return true;
        case SDL_SCANCODE_DOWN:   g_sel = (g_sel + 1) % IT_COUNT; return true;
        case SDL_SCANCODE_LEFT:   adjust(g_sel, -1); return true;
        case SDL_SCANCODE_RIGHT:  adjust(g_sel, +1); return true;
        case SDL_SCANCODE_RETURN:
            if (g_sel == IT_CLOSE) g_open = false;
            else if (g_sel == IT_MAP) enumerate_devices();
            else if (g_sel == IT_SD) open_sd_folder();
            else if (g_sel == IT_SD_RESET) { Ni404FwGuard fw; ni404_sd_set_card_present(true); ni404_sd_set_root(ni404_sd_default_root()); menu_toast("SD ripristinata"); }
#ifdef EMU_TARGET_TOERN
            else if (g_sel == IT_BROWSE) menu_toast("TOERN: campioni da SET_WAV; trascina un file -> samples/import");
#else
            else if (g_sel == IT_BROWSE) { browser_scan(); g_browse = true; }
#endif
            else adjust(g_sel, +1);
            return true;
        default: return true;   // consume everything else while open
    }
}

// ---- text rendering (5x7 font) --------------------------------------------
static void drawChar(SDL_Renderer *r, int x, int y, char c, int s) {
    if (c < 0x20 || c > 0x7E) c = '?';
    const uint8_t *g = ni404_font5x7[c - 0x20];
    for (int col = 0; col < 5; col++) {
        uint8_t line = g[col];
        for (int row = 0; row < 8; row++) if (line & (1 << row)) {
            SDL_Rect p{ x + col * s, y + row * s, s, s }; SDL_RenderFillRect(r, &p);
        }
    }
}
static void drawText(SDL_Renderer *r, int x, int y, const char *t, int s) {
    for (; *t; t++) { drawChar(r, x, y, *t, s); x += 6 * s; }
}

// Read back one 8-pixel text row of the OLED view (the 128x64 panel image) as text:
// 21 cells of 6 px, each matched to the nearest 5x7 glyph. Lets the headless tests
// check what the firmware's HUD actually put on the panel.
// Copy of firmware/libraries/IchosOled's glyphs (ASCII 0x20..0x5F): the HUD's own font,
// so its text reads back exactly (a few letters differ from the GFX font, e.g. W).
static const uint8_t k_ichos_font[] = {
  0x00,0x00,0x00,0x00,0x00, 0x00,0x00,0x5F,0x00,0x00, 0x00,0x07,0x00,0x07,0x00,
  0x14,0x7F,0x14,0x7F,0x14, 0x24,0x2A,0x7F,0x2A,0x12, 0x23,0x13,0x08,0x64,0x62,
  0x36,0x49,0x55,0x22,0x50, 0x00,0x05,0x03,0x00,0x00, 0x00,0x1C,0x22,0x41,0x00,
  0x00,0x41,0x22,0x1C,0x00, 0x14,0x08,0x3E,0x08,0x14, 0x08,0x08,0x3E,0x08,0x08,
  0x00,0x50,0x30,0x00,0x00, 0x08,0x08,0x08,0x08,0x08, 0x00,0x60,0x60,0x00,0x00,
  0x20,0x10,0x08,0x04,0x02, 0x3E,0x51,0x49,0x45,0x3E, 0x00,0x42,0x7F,0x40,0x00,
  0x42,0x61,0x51,0x49,0x46, 0x21,0x41,0x45,0x4B,0x31, 0x18,0x14,0x12,0x7F,0x10,
  0x27,0x45,0x45,0x45,0x39, 0x3C,0x4A,0x49,0x49,0x30, 0x01,0x71,0x09,0x05,0x03,
  0x36,0x49,0x49,0x49,0x36, 0x06,0x49,0x49,0x29,0x1E, 0x00,0x36,0x36,0x00,0x00,
  0x00,0x56,0x36,0x00,0x00, 0x00,0x08,0x14,0x22,0x41, 0x14,0x14,0x14,0x14,0x14,
  0x41,0x22,0x14,0x08,0x00, 0x02,0x01,0x51,0x09,0x06, 0x32,0x49,0x79,0x41,0x3E,
  0x7E,0x11,0x11,0x11,0x7E, 0x7F,0x49,0x49,0x49,0x36, 0x3E,0x41,0x41,0x41,0x22,
  0x7F,0x41,0x41,0x22,0x1C, 0x7F,0x49,0x49,0x49,0x41, 0x7F,0x09,0x09,0x09,0x01,
  0x3E,0x41,0x49,0x49,0x7A, 0x7F,0x08,0x08,0x08,0x7F, 0x00,0x41,0x7F,0x41,0x00,
  0x20,0x40,0x41,0x3F,0x01, 0x7F,0x08,0x14,0x22,0x41, 0x7F,0x40,0x40,0x40,0x40,
  0x7F,0x02,0x0C,0x02,0x7F, 0x7F,0x04,0x08,0x10,0x7F, 0x3E,0x41,0x41,0x41,0x3E,
  0x7F,0x09,0x09,0x09,0x06, 0x3E,0x41,0x51,0x21,0x5E, 0x7F,0x09,0x19,0x29,0x46,
  0x46,0x49,0x49,0x49,0x31, 0x01,0x01,0x7F,0x01,0x01, 0x3F,0x40,0x40,0x40,0x3F,
  0x1F,0x20,0x40,0x20,0x1F, 0x3F,0x40,0x38,0x40,0x3F, 0x63,0x14,0x08,0x14,0x63,
  0x07,0x08,0x70,0x08,0x07, 0x61,0x51,0x49,0x45,0x43, 0x00,0x7F,0x41,0x41,0x00,
  0x02,0x04,0x08,0x10,0x20, 0x00,0x41,0x41,0x7F,0x00, 0x04,0x02,0x01,0x02,0x04,
  0x40,0x40,0x40,0x40,0x40,
};
int menu_ocr_oled_row(const uint8_t *fb, int page, char *out, int outlen) {
    int n = 0;
    for (int cell = 0; cell < 21 && n < outlen - 1; cell++) {
        uint8_t cols[5];
        for (int c = 0; c < 5; c++) {
            uint8_t v = 0;
            for (int b = 0; b < 8; b++) if (fb[(page * 8 + b) * 128 + cell * 6 + c]) v |= (uint8_t)(1 << b);
            cols[c] = v;
        }
        int best = 0, bestd = 1 << 30;
        for (int g = 0; g < 0x60 - 0x20; g++) {              // the HUD font first
            int d = 0;
            for (int c = 0; c < 5; c++) d += __builtin_popcount((unsigned)(cols[c] ^ k_ichos_font[g * 5 + c]));
            if (d < bestd) { bestd = d; best = g; }
        }
        for (int g = 0; g < 0x7F - 0x20 && bestd; g++) {      // then lowercase etc.
            int d = 0;
            for (int c = 0; c < 5; c++) d += __builtin_popcount((unsigned)(cols[c] ^ ni404_font5x7[g][c]));
            if (d < bestd) { bestd = d; best = g; }
        }
        out[n++] = (char)(0x20 + best);
    }
    while (n > 0 && out[n - 1] == ' ') n--;
    out[n] = 0;
    return n;
}

// Public wrapper (declared in menu.h) so the frontend can draw labels with the
// same font. Caller sets the draw color beforehand.
void emu_draw_text(SDL_Renderer *r, int x, int y, const char *t, int s) { drawText(r, x, y, t, s); }

// ---- transient toast notification -----------------------------------------
static std::string g_toast;
static Uint32 g_toastUntil = 0;
void menu_toast(const char *msg) {
    g_toast = msg ? msg : "";
    g_toastUntil = SDL_GetTicks() + 4000;   // visible ~4 s
}
static void render_toast(SDL_Renderer *ren, int winW) {
    if (g_toast.empty() || SDL_GetTicks() > g_toastUntil) return;
    int s = 2, pad = 8, tw = (int)g_toast.size() * 6 * s, bw = tw + pad * 2, bh = 8 * s + pad * 2;
    int x = (winW - bw) / 2; if (x < 4) x = 4;
    SDL_SetRenderDrawBlendMode(ren, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(ren, 20, 80, 40, 235); SDL_Rect bg{ x, 8, bw, bh }; SDL_RenderFillRect(ren, &bg);
    SDL_SetRenderDrawColor(ren, 120, 230, 160, 255); SDL_RenderDrawRect(ren, &bg);
    SDL_SetRenderDrawColor(ren, 230, 255, 240, 255);
    drawText(ren, x + pad, 8 + pad, g_toast.c_str(), s);
}

void menu_render(SDL_Renderer *ren, int winW, int winH) {
    render_toast(ren, winW);   // toast shows whether or not the menu is open
    if (!g_open) return;
    // dim background
    SDL_SetRenderDrawBlendMode(ren, SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(ren, 0, 0, 0, 200);
    SDL_Rect full{ 0, 0, winW, winH }; SDL_RenderFillRect(ren, &full);
    // panel
    int px = 30, py = 30, pw = winW - 60, ph = winH - 60;
    SDL_SetRenderDrawColor(ren, 20, 24, 36, 255); SDL_Rect panel{ px, py, pw, ph }; SDL_RenderFillRect(ren, &panel);
    SDL_SetRenderDrawColor(ren, 90, 120, 200, 255); SDL_RenderDrawRect(ren, &panel);

    // ---- sample browser sub-screen ----
    if (g_browse) {
        SDL_SetRenderDrawColor(ren, 200, 220, 255, 255);
        emu_draw_text(ren, px + 16, py + 16, "SFOGLIA CAMPIONI", 2);
        SDL_SetRenderDrawColor(ren, 130, 150, 190, 255);
        char hh[96]; std::snprintf(hh, sizeof hh, "canale %d - Invio carica, Esc/TAB esci", ni404_current_channel());
        emu_draw_text(ren, px + 16, py + 16 + 22, hh, 1);
        const int listY = py + 56, rowH = 18, visible = (ph - 70) / rowH;
        int n = (int)g_bids.size();
        if (g_bsel < g_btop) g_btop = g_bsel;
        if (g_bsel >= g_btop + visible) g_btop = g_bsel - visible + 1;
        if (n == 0) {
            SDL_SetRenderDrawColor(ren, 200, 200, 210, 255);
            emu_draw_text(ren, px + 16, listY, "(nessun campione _N.wav trovato)", 1);
            return;
        }
        for (int i = 0; i < visible && g_btop + i < n; i++) {
            int idx = g_btop + i; bool seld = (idx == g_bsel); int ry = listY + i * rowH;
            if (seld) { SDL_SetRenderDrawColor(ren, 40, 60, 110, 255); SDL_Rect hl{ px + 10, ry - 2, pw - 20, rowH }; SDL_RenderFillRect(ren, &hl); }
            SDL_SetRenderDrawColor(ren, seld ? 255 : 190, seld ? 255 : 200, 255, 255);
            char line[96]; std::snprintf(line, sizeof line, "%s %s", seld ? ">" : " ", g_blabels[idx].c_str());
            emu_draw_text(ren, px + 16, ry, line, 2);
        }
        return;
    }

    const int x = px + 16, panelRight = px + pw - 10;
    int y = py + 16;
    // Header: title (big) + a hint line (small) so neither runs off a 512px window.
    SDL_SetRenderDrawColor(ren, 200, 220, 255, 255);
    drawText(ren, x, y, "IMPOSTAZIONI", 2); y += 8 * 2 + 6;
    SDL_SetRenderDrawColor(ren, 130, 150, 190, 255);
    drawText(ren, x, y, "TAB chiude - su/giu scegli - sin/des cambia", 1); y += 8 + 12;

    const int s = 2, lh = 8 * s + 10;
    // The value column sits to the right of the (short) labels; values are drawn
    // small and truncated so a long device name never spills past the panel.
    const int valX = x + 15 * 6 * s;                 // after ~15 big-font chars
    const int maxValChars = (panelRight - valX) / 6; // small font = 6px/char
    auto fit = [&](std::string v, int lim) -> std::string {
        if ((int)v.size() > lim && lim > 3) v = v.substr(0, lim - 2) + "..";
        return v;
    };

    char buf[256];
    struct Row { const char *label; std::string val; bool adj; };
    Row rows[IT_COUNT];
    rows[IT_OUT]  = { "Uscita audio", g_outDevs.empty() ? "(nessuna)" : g_outDevs[g_outSel], true };
    std::snprintf(buf, sizeof buf, "%.1fx", ni404_get_master_gain());
    rows[IT_GAIN] = { "Volume", buf, true };
    rows[IT_IN]   = { "Ingresso audio", g_inDevs.empty() ? "(nessuno)" : g_inDevs[g_inSel], true };
    rows[IT_SD]      = { "Cartella SD", ni404_sd_root() ? ni404_sd_root() : "(?)", false };
    rows[IT_SD_RESET]= { "Ripristina SD", "trascina una cartella per cambiarla", false };
#ifdef EMU_TARGET_TOERN
    rows[IT_BROWSE]  = { "Campioni SD", "sul synth: SET_WAV (samples/<cartella>/)", false };
#else
    rows[IT_BROWSE]  = { "Campioni SD", "Invio = sfoglia/carica", false };
#endif
    { std::string m; for (size_t i = 0; i < g_midiDevs.size(); i++) { if (i) m += ", "; m += g_midiDevs[i]; }
      rows[IT_MIDI] = { "MIDI in", m.empty() ? "(nessuno)" : m, false }; }
    std::string mapName = std::string(ni404_target_name()) + "-midi-map.txt";
    rows[IT_MAP]  = { "Mappa MIDI", "CC24-27 -> encoder; vedi " + mapName, false };
    rows[IT_KEYS] = { "Tasti", "QAWSED RF=enc ZXCV=premi 1/2/3=puls", false };
    rows[IT_CLOSE]= { "Chiudi", "trascina audio=campione, cartella=SD", false };

    for (int i = 0; i < IT_COUNT; i++) {
        bool selrow = (i == g_sel);
        if (selrow) { SDL_SetRenderDrawColor(ren, 40, 60, 110, 255); SDL_Rect hl{ x - 6, y - 3, pw - 32, lh }; SDL_RenderFillRect(ren, &hl); }
        SDL_SetRenderDrawColor(ren, selrow ? 255 : 180, selrow ? 255 : 200, 255, 255);
        std::snprintf(buf, sizeof buf, "%s%s", selrow ? ">" : " ", rows[i].label);
        drawText(ren, x, y, buf, s);
        std::string val = rows[i].adj ? ("< " + fit(rows[i].val, maxValChars - 4) + " >") : fit(rows[i].val, maxValChars);
        drawText(ren, valX, y + (8 * s - 8) / 2, val.c_str(), 1);
        y += lh;
    }
}
