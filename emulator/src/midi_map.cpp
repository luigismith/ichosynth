// midi_map.cpp — controller mapping: translate incoming MIDI from a hardware
// controller into NI404/toern host controls (4 encoders + buttons), so a MIDI
// controller can DRIVE the emulator.
//
// Because different controllers (and even different MPK Mini revisions: mk2/mk3/
// mk4/Plus) send DIFFERENT CC numbers for their knobs, the mapping is:
//   * configurable at runtime via `midi-map.txt` next to the exe (no rebuild), and
//   * monitored: every incoming CC/Note is printed to the console, so you can see
//     exactly what your controller sends and set the right numbers.
//
// Defaults (MPK Mini mk3-style): knobs K1..K4 = CC 70,71,72,73 -> the 4 encoders;
// pads (Bank A notes 36..43) -> buttons + grid stepping; keys -> played by the
// firmware. Edit midi-map.txt to match YOUR controller (see what the monitor prints).
#include "ni404_host.h"
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdlib>

// Knob k -> encoder slot.
static const int KNOB_ENC[4] = { ENC_LEFT, ENC_CENTER, ENC_RIGHT, ENC_4TH };
// Configurable CC numbers for the 4 knobs and notes for the 8 pads.
// Defaults match the Akai MPK Mini IV (mk4): knobs are RELATIVE encoders on
// CC 24..27; pads send notes 36..43. (mk3/Plus: set knobmode=absolute, knobs=70..73.)
static int knobCC[4]  = { 24, 25, 26, 27 };
static int padNote[8] = { 36, 37, 38, 39, 40, 41, 42, 43 };
static bool  g_relative = true;      // knobs are relative encoders (mk4) vs absolute pots
static bool  g_monitor = true;       // log incoming MIDI (console + midi-log.txt)
static int   g_noteVel = 110;        // fixed velocity for played notes/pads (0 = use real velocity)
static bool  g_loaded  = false;
static FILE *g_log     = nullptr;    // midi-log.txt (visible even when double-clicked)

static const long DETENT = 4;        // one firmware detent = 4 quadrature counts
static int  ccLast[128];
static bool ccSeen[128];

static void loadConfig() {
    if (g_loaded) return;
    g_loaded = true;
    FILE *f = std::fopen("midi-map.txt", "r");
    if (!f) {
        // Write a self-documenting default so the user can edit it next to the exe.
        if ((f = std::fopen("midi-map.txt", "w"))) {
            std::fprintf(f,
                "# NI404/toern emulator - MIDI controller map. Edit and restart.\n"
                "# Defaults are for the Akai MPK Mini IV (mk4).\n"
                "# Watch midi-log.txt while turning knobs/hitting pads to find your numbers.\n"
                "# The 4 knob CC numbers (K1,K2,K3,K4) -> the 4 encoders:\n"
                "knobs=24,25,26,27\n"
                "# Knob type: 'relative' for endless encoders (mk4), 'absolute' for pots (mk3/Plus 70-73).\n"
                "knobmode=relative\n"
                "# The 8 pad note numbers (Pad1..Pad8):\n"
                "pads=36,37,38,39,40,41,42,43\n"
                "# Fixed velocity for keys/pads that play a sample (pads act like buttons):\n"
                "# 1..127 = always use that velocity; 0 = velocity-sensitive (real dynamics).\n"
                "notevelocity=110\n"
                "# Log incoming MIDI to console + midi-log.txt (1=on, 0=off):\n"
                "monitor=1\n");
            std::fclose(f);
        }
        return;
    }
    char line[160];
    while (std::fgets(line, sizeof line, f)) {
        if (line[0] == '#' || line[0] == '\n') continue;
        if (!std::strncmp(line, "knobs=", 6))
            std::sscanf(line + 6, "%d,%d,%d,%d", &knobCC[0], &knobCC[1], &knobCC[2], &knobCC[3]);
        else if (!std::strncmp(line, "pads=", 5))
            std::sscanf(line + 5, "%d,%d,%d,%d,%d,%d,%d,%d", &padNote[0], &padNote[1],
                        &padNote[2], &padNote[3], &padNote[4], &padNote[5], &padNote[6], &padNote[7]);
        else if (!std::strncmp(line, "knobmode=", 9))
            g_relative = (std::strstr(line + 9, "rel") != nullptr);
        else if (!std::strncmp(line, "notevelocity=", 13))
            g_noteVel = std::atoi(line + 13);
        else if (!std::strncmp(line, "monitor=", 8))
            g_monitor = std::atoi(line + 8) != 0;
    }
    std::fclose(f);
    if (g_monitor) g_log = std::fopen("midi-log.txt", "w");  // truncate at startup
}

// Fixed velocity for keys/pads that play a sample (pads behave like buttons).
// Returns the configured velocity (1..127), or `incoming` if velocity-sensitive
// mode is selected (notevelocity=0). usb_midi.h applies this to every note-on.
uint8_t ni404_note_velocity(uint8_t incoming) {
    loadConfig();
    if (g_noteVel <= 0) return incoming;
    return (uint8_t)(g_noteVel > 127 ? 127 : g_noteVel);
}

bool ni404_midi_control(uint8_t status, uint8_t d1, uint8_t d2) {
    loadConfig();
    uint8_t type = status & 0xF0;

    if (g_monitor) {
        char msg[64] = {0};
        if (type == 0xB0)
            std::snprintf(msg, sizeof msg, "CC   ch=%d  #%d = %d", (status & 0x0F) + 1, d1, d2);
        else if (type == 0x90 && d2 > 0)
            std::snprintf(msg, sizeof msg, "Note ch=%d  %d vel=%d", (status & 0x0F) + 1, d1, d2);
        if (msg[0]) {
            std::printf("[midi] %s\n", msg); std::fflush(stdout);
            if (g_log) { std::fprintf(g_log, "%s\n", msg); std::fflush(g_log); }
        }
    }

    // ---- Control Change: knob -> encoder --------------------------------
    if (type == 0xB0) {
        for (int k = 0; k < 4; k++) {
            if (d1 != knobCC[k]) continue;
            int enc = KNOB_ENC[k];
            int delta;
            if (g_relative) {
                // Relative/endless encoder: 1..63 = +N (CW), 65..127 = -N (CCW,
                // two's complement: 127 = -1), 0/64 = no move.
                delta = (d2 == 0) ? 0 : (d2 < 64 ? d2 : d2 - 128);
            } else {
                // Absolute pot: derive motion from the change in value.
                if (!ccSeen[d1]) { ccSeen[d1] = true; ccLast[d1] = d2; return true; }
                delta = (int)d2 - ccLast[d1];
                ccLast[d1] = d2;
            }
            if (delta) ni404_host_encoder_add(enc, (long)delta * DETENT);
            return true;
        }
        return false;   // unmapped CC -> let the firmware's CC handler (if any) see it
    }

    // ---- Pads: notes -> buttons / grid stepping ----------------------------
    if (type == 0x90 || type == 0x80) {
        bool on = (type == 0x90 && d2 > 0);
        for (int p = 0; p < 8; p++) {
            if (d1 != padNote[p]) continue;
            switch (p) {
                // Pads 1-4 = the PUSH of the 4 encoders (knob N turns encoder N,
                // pad N presses it) -> coherent 1:1 with the 4 knobs.
                case 0: ni404_host_button_set(BTN_L, on); return true;   // encoder 1 push
                case 1: ni404_host_button_set(BTN_C, on); return true;   // encoder 2 push
                case 2: ni404_host_button_set(BTN_R, on); return true;   // encoder 3 push
                case 3: ni404_host_button_set(BTN_4, on); return true;   // encoder 4 push
                // Pads 5-8 = grid navigation (and NI404 filter on pad 8-hold via keyboard B).
                case 4: if (on) ni404_host_encoder_add(ENC_LEFT, +DETENT); return true;   // Y+
                case 5: if (on) ni404_host_encoder_add(ENC_LEFT, -DETENT); return true;   // Y-
                case 6: if (on) ni404_host_encoder_add(ENC_RIGHT, +DETENT); return true;  // X+
                case 7: if (on) ni404_host_encoder_add(ENC_RIGHT, -DETENT); return true;  // X-
            }
        }
        return false;   // not a pad -> keybed note, played by the firmware
    }
    return false;
}
