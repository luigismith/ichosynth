// firmware_toern.cpp — integrates the REAL TŒRN firmware into the emulator,
// the same way firmware.cpp integrates NI404. The Arduino IDE concatenates all
// .ino files in the sketch folder (main first, then the rest); we replicate that
// by including them in order into this one translation unit, preceded by the
// auto-generated prototypes.
#include "ni404_host.h"
#include "IntervalTimer.h"
#include "toern_prototypes.h"

#include "toern.ino"
#include "toern_fileoperations.ino"
#include "toern_filter.ino"
#include "toern_filterUI.ino"
#include "toern_helpers.ino"
#include "toern_leds.ino"
#include "toern_menu.ino"
#include "toern_midi.ino"
#include "toern_parameters.ino"
#include "toern_sample.ino"
#include "toern_synths.ino"
#include "toern_ui.ino"

// ---- OLED HUD for toern --------------------------------------------------
// toern itself is LED-matrix-only, but the user wants their SSD1306 HUD too.
// Drive a self-contained OLED that mirrors toern's mode / BPM / volume / page,
// using only fields known to exist (currentMode->name, SMP.bpm/vol, lastPage).
#include "Adafruit_SSD1306.h"
static Adafruit_SSD1306 toern_oled(128, 64, &Wire, -1);

static void toern_oled_update() {
    static unsigned long last = 0;
    unsigned long now = millis();
    if (now - last < 66) return;   // ~15 fps
    last = now;
    toern_oled.clearDisplay();
    toern_oled.setTextColor(SSD1306_WHITE);
    toern_oled.setTextSize(2);
    toern_oled.setCursor(0, 0);
    toern_oled.print(currentMode ? currentMode->name.c_str() : "TOERN");
    toern_oled.setTextSize(2);
    toern_oled.setCursor(0, 24);
    toern_oled.print("BPM ");
    toern_oled.print((int)SMP.bpm);
    toern_oled.setTextSize(1);
    toern_oled.setCursor(0, 50);
    toern_oled.print("Page:");
    toern_oled.print((int)lastPage);
    toern_oled.display();
}

void ni404_setup() { setup(); toern_oled.begin(); }
void ni404_loop()  { loop(); ni404_pump_timers(); toern_oled_update(); }

// Verification hooks are NI404-specific; not used by the toern build.
void ni404_test_trigger(int) {}
int  ni404_test_sample_len(int) { return 0; }
void ni404_demo() {}   // demo song is implemented for the NI404 build (ni404emu)
// "play it" hooks are NI404-specific; no-op stubs keep the toern target linking.
void ni404_load_sample(int, int) {}
void ni404_play_note(int, int, int) {}
void ni404_play_synth(int, int, int) {}
void ni404_set_filter(int, int) {}
int  ni404_test_beat()    { return 0; }
int  ni404_test_page()    { return 0; }
int  ni404_test_playing() { return 0; }
int  ni404_test_bpm()     { return 0; }
int  ni404_test_cursor_x()  { return 0; }
int  ni404_test_cursor_y()  { return 0; }
int  ni404_test_edit_page() { return 0; }
const char *ni404_test_mode() { return ""; }
int  ni404_test_note_at(int, int) { return 0; }

// Drag-and-drop sample loader (toern build): convert the dropped WAV to the kit
// format and install it on the virtual SD under folder 9 (_900.._999). toern's
// channel model differs from NI404, so here we only add it to the library; pick
// it from toern's own sample browser.
#include "sample_import.h"
#include <filesystem>
#include <string>
#include <cctype>
#ifndef NI404_SDCARD_PATH
#define NI404_SDCARD_PATH "_SDCARD"
#endif
const char *ni404_import_sample(const char *srcPath) {
    static char status[96];
    namespace fs = std::filesystem;
    std::string s = srcPath ? srcPath : "", low = s;
    for (char &ch : low) ch = (char)std::tolower((unsigned char)ch);
    if (low.size() < 4 || low.substr(low.size() - 4) != ".wav") {
        std::snprintf(status, sizeof status, "Not a .wav file"); return status;
    }
    std::error_code ec;
    fs::path dir = fs::path(NI404_SDCARD_PATH) / "9";
    fs::create_directories(dir, ec);
    int id = 0;
    for (int slot = 1; slot <= 99; slot++)
        if (!fs::exists(dir / ("_" + std::to_string(900 + slot) + ".wav"))) { id = 900 + slot; break; }
    if (id == 0) { std::snprintf(status, sizeof status, "Import folder full (901-999)"); return status; }
    fs::path dst = dir / ("_" + std::to_string(id) + ".wav");
    char err[64] = {0};
    if (!ni404_wav_to_kit(srcPath, dst.string().c_str(), err, sizeof err)) {
        std::snprintf(status, sizeof status, "Import failed: %s", err); return status;
    }
    std::snprintf(status, sizeof status, "Imported _%d into folder 9", id);
    return status;
}
