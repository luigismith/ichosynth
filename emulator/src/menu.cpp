// menu.cpp — in-window settings overlay. Audio output/input device selection,
// master volume, MIDI device + mapping info, key legend. Toggle with TAB.
// Settings persist to settings.txt next to the exe. Owns the SDL audio device.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include "menu.h"
#include "Adafruit_GFX.h"   // ni404_font5x7
#include <SDL.h>
#include <cstdio>
#include <cstring>
#include <cstdlib>
#include <string>
#include <vector>

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
    FILE *f = std::fopen("settings.txt", "w");
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
    g_inDevs.clear(); g_inDevs.push_back("(none)");
    int m = SDL_GetNumAudioDevices(1);
    for (int i = 0; i < m; i++) { const char *nm = SDL_GetAudioDeviceName(i, 1); if (nm) g_inDevs.push_back(nm); }
    g_midiDevs.clear(); ni404_midi_list(&g_midiDevs);
}

static void open_output() {
    if (g_adev) { SDL_CloseAudioDevice(g_adev); g_adev = 0; }
    SDL_AudioSpec want, have; SDL_zero(want);
    want.freq = 44100; want.format = AUDIO_F32SYS; want.channels = 2; want.samples = 256; want.callback = g_cb;
    const char *name = (g_outSel > 0 && g_outSel < (int)g_outDevs.size()) ? g_outDevs[g_outSel].c_str() : nullptr;
    g_adev = SDL_OpenAudioDevice(name, 0, &want, &have, 0);
    if (g_adev) SDL_PauseAudioDevice(g_adev, 0);
    else std::fprintf(stderr, "[menu] failed to open audio device '%s': %s\n", name ? name : "(default)", SDL_GetError());
}

void menu_init(SDL_AudioCallback cb) {
    g_cb = cb;
    enumerate_devices();
    // Load settings.
    float gain = 2.0f; std::string outName, inName;
    if (FILE *f = std::fopen("settings.txt", "r")) {
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
    open_output();
}

void menu_shutdown() {
    if (g_adev) { SDL_CloseAudioDevice(g_adev); g_adev = 0; }
}

bool menu_is_open() { return g_open; }

// ---- menu items -----------------------------------------------------------
enum { IT_OUT = 0, IT_GAIN, IT_IN, IT_MIDI, IT_MAP, IT_KEYS, IT_CLOSE, IT_COUNT };

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
    }
}

bool menu_handle_event(const SDL_Event &e) {
    if (e.type != SDL_KEYDOWN) return g_open;   // swallow all key events while open
    SDL_Scancode sc = e.key.keysym.scancode;
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
            else if (g_sel == IT_MAP) { /* reload happens in firmware lazily; just re-enumerate */ enumerate_devices(); }
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

    int s = 2, lh = 8 * s + 8, x = px + 16, y = py + 16;
    SDL_SetRenderDrawColor(ren, 200, 220, 255, 255);
    drawText(ren, x, y, "IMPOSTAZIONI  (TAB chiude, su/giu scegli, sin/des cambia)", s); y += lh + 6;

    char buf[256];
    struct Row { const char *label; std::string val; };
    Row rows[IT_COUNT];
    rows[IT_OUT]  = { "Uscita audio ", g_outDevs.empty() ? "(nessuna)" : g_outDevs[g_outSel] };
    std::snprintf(buf, sizeof buf, "%.1fx", ni404_get_master_gain());
    rows[IT_GAIN] = { "Volume master", buf };
    rows[IT_IN]   = { "Ingresso audio", g_inDevs.empty() ? "(nessuno)" : g_inDevs[g_inSel] };
    { std::string m; for (size_t i = 0; i < g_midiDevs.size(); i++) { if (i) m += ", "; m += g_midiDevs[i]; }
      rows[IT_MIDI] = { "Ingresso MIDI", m.empty() ? "(nessuno)" : m }; }
    rows[IT_MAP]  = { "Mappa MIDI   ", "manopole CC24-27 (rel) -> 4 encoder; pad 36-43 (vedi midi-map.txt)" };
    rows[IT_KEYS] = { "Tastiera     ", "Q/A W/S E/D R/F=encoder  Z X C V=premi  B=filtro  1/2/3=touch" };
    rows[IT_CLOSE]= { "Chiudi       ", "trascina un .wav nella finestra per caricare un campione" };

    for (int i = 0; i < IT_COUNT; i++) {
        bool selrow = (i == g_sel);
        if (selrow) { SDL_SetRenderDrawColor(ren, 40, 60, 110, 255); SDL_Rect hl{ x - 6, y - 3, pw - 32, lh }; SDL_RenderFillRect(ren, &hl); }
        SDL_SetRenderDrawColor(ren, selrow ? 255 : 180, selrow ? 255 : 200, 255, 255);
        std::snprintf(buf, sizeof buf, "%s %s %s", selrow ? ">" : " ", rows[i].label,
                      (i == IT_OUT || i == IT_GAIN || i == IT_IN) ? "<" : " ");
        drawText(ren, x, y, buf, s);
        drawText(ren, x + 26 * 6 * s, y, rows[i].val.c_str(), 1);   // value in smaller font, fits more
        y += lh;
    }
}
