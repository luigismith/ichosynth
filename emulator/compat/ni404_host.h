// ni404_host.h — the bridge interface between the SDL frontend (main.cpp) and
// the firmware/audio side. The frontend feeds input here; the compat Encoder/
// Switch shims read it; FastLED + the audio sink expose frames/samples back.
#ifndef NI404_HOST_H
#define NI404_HOST_H

#include <cstdint>
struct CRGB;

// Encoder indices (match config.h knobs).
enum { ENC_LEFT = 0, ENC_CENTER = 1, ENC_RIGHT = 2, ENC_4TH = 3, ENC_COUNT = 4 };
// Button indices. 0-3 are the four encoder push-buttons; 4 is the NI404 filter
// button; 5-7 are toern's three touch switches (see FastTouch.h).
enum {
    BTN_L = 0, BTN_C = 1, BTN_R = 2, BTN_4 = 3, BTN_FILT = 4,
    BTN_TOUCH1 = 5, BTN_TOUCH2 = 6, BTN_TOUCH3 = 7, BTN_COUNT = 8
};

// ---- input: frontend writes, compat shims read ----------------------------
void ni404_host_encoder_add(int idx, long delta);   // accumulate detents
long ni404_host_encoder_get(int idx);
void ni404_host_encoder_set(int idx, long value);
void ni404_host_button_set(int idx, bool down);
bool ni404_host_button_get(int idx);

// ---- virtual wiring: which board pins the host controls are soldered to ----
// The firmware glue (firmware*.cpp) declares the board, before setup(): each encoder
// slot on a CLK/DT pin pair, each button slot on a pin (a push button to GND). The
// Encoder shim and digitalRead() then behave like the real circuit (compat/Arduino.h).
void ni404_wire_encoder(int encSlot, int clkPin, int dtPin);
void ni404_wire_button(int btnSlot, int pin);
// Encoder slot wired to (clk, dt); *reversed = the pins were given swapped. -1 = none.
int  ni404_wiring_encoder_for(int clkPin, int dtPin, bool *reversed);
// After setup(): print every wired pin's mode and warn about the ones that would
// misbehave on the board (a button pin left INPUT_PULLDOWN reads "pressed" when
// released; INPUT with no pull floats). Returns the number of warnings.
int  ni404_gpio_audit();
const char *ni404_pin_mode_name(int pin);

// ---- threads ----------------------------------------------------------------
// setup() and then loop() run on their own "firmware" thread; anything else that touches
// firmware state (SD root, sample import, the bench's sample loader) takes this lock
// first. While setup() is still running (it may wait for ever, e.g. TŒRN's "SD?" screen
// until a card is inserted) the guard does not wait: the SD root is safe on its own.
void ni404_fw_lock();
void ni404_fw_unlock();
void ni404_fw_set_in_setup(bool inSetup);
bool ni404_fw_in_setup();
struct Ni404FwGuard {
    bool held;
    Ni404FwGuard() : held(!ni404_fw_in_setup()) { if (held) ni404_fw_lock(); }
    ~Ni404FwGuard() { if (held) ni404_fw_unlock(); }
};
void ni404_timers_stop();      // stop the IntervalTimer thread (at exit)

// ---- runtime files ------------------------------------------------------------
// Path of an emulator runtime file (settings, eeprom, midi map/log): next to the
// executable, prefixed with the target name so ni404emu and toernemu never share
// one ("toernemu-settings.txt", "toernemu-eeprom.bin", ...).
const char *ni404_runtime_path(const char *name);
const char *ni404_target_name();

// ---- output: frontend reads ----------------------------------------------
// Latest LED frame (brightness applied). Returns a generation counter.
uint64_t ni404_get_leds(CRGB *out, int max, int *count);
// Render `frames` interleaved-stereo float frames, driving the audio graph.
void ni404_audio_render(float *out, int frames);

// Latest OLED (SSD1306) frame: 1 byte/pixel, row-major. Returns a generation
// counter (0 = never drawn). out must hold at least maxBytes.
uint64_t ni404_get_oled(uint8_t *out, int maxBytes, int *w, int *h);

// ---- firmware entry points (defined by the .ino via firmware.cpp) ---------
void ni404_setup();
void ni404_loop();

// Tell the SD shim / runtime files where the executable lives, so a distributed
// binary finds the sdcard folder and keeps its settings next to it. Call before
// ni404_setup().
void ni404_set_base_dir(const char *dir);
// Simulate a missing micro SD card (--no-sd): SD.begin() fails like an empty slot.
void ni404_sd_set_card_present(bool present);

// ---- headless verification hooks (firmware.cpp sees the firmware globals) --
void ni404_test_trigger(int channel);    // play channel's sample like a MIDI note
int  ni404_test_sample_len(int channel); // loaded sample length in bytes (0 = none)

// ---- "play it" hooks: drive the real sound engine for verification ---------
void ni404_play_note(int channel, int pitch, int vel);  // sample ch 1..8, pitch 60=base
void ni404_play_synth(int voice, int row, int vel);     // synth 13/14 at pianoFrequencies[row]
void ni404_set_filter(int channel, int knob);           // cutoff knob 1..32
void ni404_set_crush(int channel, int bits);            // bitcrusher bit depth 1..16 (16 = off)
void ni404_set_ladder(int channel, int cutoffKnob);     // Moog ladder cutoff knob 1..32 (max = open)
int  ni404_test_record_save(int channel);               // test: synth a take, save to SD, return id (0=fail)
int  ni404_test_beat();
int  ni404_test_page();
int  ni404_test_playing();
int  ni404_test_bpm();

// ---- demo: load the kit, paint a beat, and start playing -------------------
void ni404_demo();

// ---- SD-card management (emulator): inspect/point the folder backing the SD,
// read the current channel, and load a sample id into a channel (browser). -----
const char *ni404_sd_root();                 // current SD folder path
bool        ni404_sd_set_root(const char *path);  // repoint SD + reload samples
const char *ni404_sd_default_root();         // the auto-resolved default folder
int         ni404_current_channel();         // firmware's current channel (1..8)
// Load sample id (e.g. 302) into a channel (1..8); reuses the firmware loader.
void ni404_load_sample(int channel, int id);

// ---- sample import (drag-and-drop): convert a dropped WAV to the kit format,
// install it on the virtual SD (folder 9 = user imports) and load it into the
// current channel. Returns a short status string (valid until the next call).
const char *ni404_import_sample(const char *srcPath);

#endif // NI404_HOST_H
