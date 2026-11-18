// firmware_toern.cpp — runs the REAL ichosynth firmware in the emulator.
//
// "Real" means the very sources that get flashed: CMake stages the pinned TŒRN sketch
// with firmware/build_toern.py --stage-only (pin remap, INPUT_PULLUP buttons, pin-2
// pull-up, SD on the built-in slot, LINE IN default, 2nd LED strip removed, OLED HUD
// glue) and this file compiles that staged sketch. The hardware drivers are the real
// ones too — firmware/libraries/i2cEncoderLibV2 (KY-040), FastTouch (tact switches) and
// IchosOled (SSD1306 HUD, its own translation unit) — running on modelled GPIO
// (compat/Arduino.h) and a modelled I2C bus with an SSD1306 on it (src/i2c_bus.cpp).
//
// The Arduino IDE concatenates all .ino files in the sketch folder (main first, then
// the rest in alphabetical order); we replicate that by including them in order into
// this one translation unit, preceded by the auto-generated prototypes.
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

// ---- the board: which pins the controls are soldered to ----------------------
// Taken from the drivers' own pin tables (ICHOS_ENC_PINS / ICHOS_BTN_PINS), so the
// emulator is wired exactly like the hardware the firmware is built for. Host encoder
// slot i = E(i+1), left to right; host buttons 0-3 = the encoder pushes, 5-7 = the
// three tact switches PLAY / MENU / REC.
static void wire_board() {
    static const uint8_t ENC[4][3] = ICHOS_ENC_PINS;
    static const uint8_t BTN[3] = ICHOS_BTN_PINS;
    for (int i = 0; i < 4; i++) {
        ni404_wire_encoder(i, ENC[i][0], ENC[i][1]);
        ni404_wire_button(BTN_L + i, ENC[i][2]);
    }
    for (int i = 0; i < 3; i++) ni404_wire_button(BTN_TOUCH1 + i, BTN[i]);
}

void ni404_setup() {
    wire_board();
    setup();
    if (ni404_gpio_audit() > 0)
        std::printf("[gpio] some wired pins are configured in a way the real board would not "
                    "tolerate (see WARNING lines above)\n");
}
void ni404_loop() { loop(); }

// Verification hooks are NI404-specific; not used by the toern build.
void ni404_test_trigger(int) {}
int  ni404_test_sample_len(int) { return 0; }
void ni404_demo() {}   // demo song is implemented for the NI404 build (ni404emu)
// "play it" hooks are NI404-specific; no-op stubs keep the toern target linking.
void ni404_load_sample(int, int) {}
void ni404_play_note(int, int, int) {}
void ni404_play_synth(int, int, int) {}
void ni404_set_filter(int, int) {}
void ni404_set_crush(int, int) {}
void ni404_set_ladder(int, int) {}
int  ni404_test_record_save(int) { return 0; }
int  ni404_test_beat()    { return (int)beat; }
int  ni404_test_page()    { return (int)GLOB.page; }
int  ni404_test_playing() { return isNowPlaying ? 1 : 0; }
int  ni404_test_bpm()     { return (int)(SMP.bpm + 0.5f); }
int  ni404_test_cursor_x()  { return (int)GLOB.x; }
int  ni404_test_cursor_y()  { return (int)GLOB.y; }
int  ni404_test_edit_page() { return (int)GLOB.edit; }
const char *ni404_test_mode() { static std::string s; s = currentMode ? currentMode->name.c_str() : ""; return s.c_str(); }
int  ni404_test_note_at(int, int) { return 0; }
int  ni404_test_recording() { return (isRecording || fastRecordActive) ? 1 : 0; }
const char *ni404_test_rec_input() { return recInput == AUDIO_INPUT_MIC ? "MIC" : "LINE IN"; }

// SD-management hooks: root get/set work; the current channel is TŒRN's.
const char *ni404_sd_root() { static std::string s; s = SD.getRoot(); return s.c_str(); }
const char *ni404_sd_default_root() { static std::string s; s = SDClass::resolve_root(); return s.c_str(); }
int  ni404_current_channel() { return (int)GLOB.currentChannel; }
bool ni404_sd_set_root(const char *path) { if (!path || !*path) return false; SD.setRoot(path); return true; }

// ---- drag-and-drop sample import ---------------------------------------------
// TŒRN's sample browser (SET_WAV) lists samples/<folder>/<name>.wav on the card, mono
// 16-bit 44.1 kHz. A dropped file (wav/mp3/flac, any rate/channels) is converted to that
// format and written to samples/import/<name>.wav on the virtual SD — the folder the
// card's own layout uses — so it shows up in SET_WAV exactly as a file copied onto the
// real micro SD would. Names keep [a-z0-9-_], at most 60 characters (the firmware does
// not open longer ones), and never overwrite an existing file.
#include "sample_import.h"
#include <filesystem>
#include <string>
#include <cctype>
#include <cstring>
const char *ni404_import_sample(const char *srcPath) {
    static char status[160];
    namespace fs = std::filesystem;
    std::string s = srcPath ? srcPath : "", low = s;
    for (char &ch : low) ch = (char)std::tolower((unsigned char)ch);
    auto endsWith = [&](const char *e) { size_t n = std::strlen(e);
        return low.size() >= n && low.compare(low.size() - n, n, e) == 0; };
    if (!endsWith(".wav") && !endsWith(".mp3") && !endsWith(".flac")) {
        std::snprintf(status, sizeof status, "Formato non supportato (wav/mp3/flac)"); return status;
    }
    std::string root = SD.getRoot();
    if (root.empty() || !SD.cardPresent()) {
        std::snprintf(status, sizeof status, "Nessuna SD: import impossibile"); return status;
    }
    // Sanitise the file stem into a SET_WAV-friendly name.
    std::string stem = fs::path(s).stem().string(), name;
    for (char ch : stem) {
        unsigned char c = (unsigned char)std::tolower((unsigned char)ch);
        if (std::isalnum(c) || c == '-' || c == '_') name += (char)c;
        else if (c == ' ' || c == '.') name += '-';
    }
    if (name.empty()) name = "import";
    if (name.size() > 52) name.resize(52);     // room for "-NN" + ".wav" within 60
    std::error_code ec;
    fs::path dir = fs::path(root) / "samples" / "import";
    fs::create_directories(dir, ec);
    fs::path dst = dir / (name + ".wav");
    for (int n = 2; fs::exists(dst, ec) && n < 100; n++) dst = dir / (name + "-" + std::to_string(n) + ".wav");
    if (fs::exists(dst, ec)) { std::snprintf(status, sizeof status, "samples/import: nome gia' usato"); return status; }
    char err[64] = {0};
    if (!ni404_wav_to_kit(srcPath, dst.string().c_str(), err, sizeof err)) {
        std::snprintf(status, sizeof status, "Import fallito: %s", err); return status;
    }
    std::snprintf(status, sizeof status, "SD: samples/import/%s (scegli in SET_WAV)", dst.filename().string().c_str());
    return status;
}
