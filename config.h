/*
 * config.h — NI404 fork hardware & feature configuration
 *
 * Centralizes pin assignments and compile-time feature switches so the fork
 * is easy to customize for hardware variants. All feature toggles default to
 * a value that preserves the original NI404 behavior when the feature is off.
 *
 * Pin map source: _DOCS/wiring.txt (3-4 encoder version 1.x).
 */

#ifndef NI404_CONFIG_H
#define NI404_CONFIG_H

/* ===================== LED MATRIX (FastLED / WS2812Serial) ===================== */
#define DATA_PIN 17  // LED-Matrix DIN
#define NUM_LEDS 256 // 16 x 16 RGB panel

/* ===================== ROTARY ENCODERS (CLK, DT) ===================== */
#define ENC_LEFT_CLK 5  // Left knob CLK
#define ENC_LEFT_DT 22  // Left knob DT
#define ENC_RIGHT_CLK 4 // Right knob CLK
#define ENC_RIGHT_DT 2  // Right knob DT
#define ENC_MIDL_CLK 9  // Middle (center) knob CLK
#define ENC_MIDL_DT 14  // Middle (center) knob DT
#define ENC_MIDR_CLK 32 // 4th knob CLK (upstream NI404 "middle-left" wiring)
#define ENC_MIDR_DT 33  // 4th knob DT

/* ===================== ENCODER PUSH-BUTTONS ===================== */
#define BTN_LEFT 15 // Left knob switch
#define BTN_RIGHT 3 // Right knob switch
#define BTN_MIDL 16 // Middle (center) knob switch
#define BTN_MIDR 41 // 4th knob switch (reuses the old standalone filter-button pin)

/*
 * 4th encoder present?
 * 1 = full 4-encoder build (THIS BUILD): four KY-040 encoders. The 4th (middle-
 *     right) knob is contextual — in DRAW/SINGLE it sweeps the per-voice lowpass
 *     FILTER of the voice under the cursor (TŒRN-style "fast filter": just turn,
 *     no button); in VOLUME/BPM it sets volume; in the sample browser it seeks the
 *     sample end. No standalone filter button needed.
 * 0 = 3-encoder build: three encoders only; the 4th knob's gestures (Play/Pause,
 *     Volume/BPM, Menu, Note-Shift) are remapped onto the three buttons (see the
 *     `!isEncoder4Defined` branches). The per-voice filter control needs the 4th
 *     encoder, so in this fallback the filters just stay open (no live control).
 */
#define HAS_ENCODER4 1

/* ===================== EXTRA PUSHBUTTONS (3 tact switches) ===================== *
 * Three momentary tact switches = the instrument's PLAY / MENU / REC buttons
 * (the role TŒRN assigns to its 3 touch SWITCH_1/2/3). Each: one leg to the pin,
 * the other to GND (INPUT_PULLUP, active LOW — the avdweb Switch default), so an
 * unwired pin safely reads "released". Set BUTTONS3_ENABLED 0 for a board without
 * them. REC is reserved until live recording is ported from TŒRN.
 */
#ifndef BUTTONS3_ENABLED
#define BUTTONS3_ENABLED 1
#endif
#define BTN_SW1 24   // PLAY  (play / pause)
#define BTN_SW2 25   // MENU  (enter / exit menu)
#define BTN_SW3 26   // REC   (hold to record from the audio input)

/* ===================== LIVE RECORDING (mic / line-in) ===================== *
 * Hold the REC button (BTN_SW3) to record from the codec input into the current
 * channel's sample (released = stop, sample is registered and playable). Uses
 * AudioInputI2S + AudioRecordQueue, so it runs on the Teensy and in the emulator
 * (which captures from the selected input device). Set 0 to omit.
 */
#ifndef RECORD_ENABLED
#define RECORD_ENABLED 1
#endif

/* ===================== BITCRUSHER FX (per-voice) ===================== *
 * A per-voice bitcrusher (bit-depth reduction) on the 8 sample voices, inserted
 * in the graph as filterN -> crushN -> mixer. Default = bypass (16 bit), so it's
 * transparent until a voice is crushed. First of the TŒRN effects ported into
 * ichosynth. Set 0 to omit it from the audio graph entirely.
 */
#ifndef BITCRUSH_ENABLED
#define BITCRUSH_ENABLED 1
#endif

/* ===================== OLED STATUS DISPLAY ===================== *
 * SSD1306 0.96" 128x64 over I2C. It shares the Wire bus with the Teensy Audio
 * Shield's SGTL5000 codec (SDA = pin 18, SCL = pin 19). The codec lives at a
 * different I2C address, so no bus conflict — only wire SDA/SCL/3V3/GND.
 *
 * OLED_ENABLED defaults to 0 so a board with no display behaves exactly like
 * the upstream firmware. Set to 1 (or define via build flag) to enable.
 */
#ifndef OLED_ENABLED
#define OLED_ENABLED 0
#endif
#define OLED_I2C_ADDR 0x3C
#define OLED_WIDTH 128
#define OLED_HEIGHT 64
#define OLED_RESET_PIN -1 // -1 = no dedicated reset pin (shared with Teensy)
#define OLED_FPS 15       // max display refresh rate (audio loop is timing-sensitive)

/* ===================== PER-VOICE LOWPASS FILTER (fork) ===================== *
 * Finishes the filter feature the upstream firmware left half-built: every
 * voice already passes through an AudioFilterStateVariable (lowpass output),
 * but stock code never sets its cutoff, leaving the library default (1 kHz!).
 * Mapping mutuated from TOERN (soundpauli, MIT): cutoff 281.25..9000 Hz.
 *
 * Control (TŒRN-style "fast filter"): with HAS_ENCODER4=1, just TURN the 4th
 * encoder in DRAW/SINGLE to sweep the lowpass of the voice under the cursor
 * (row - 1, same indexing as mute) — no button, no hold. The knob auto-syncs to
 * each voice's stored cutoff when the cursor moves. Settings persist per song.
 * (3-encoder build: falls back to a dedicated hold-button — see HAS_ENCODER4=0.)
 *
 * FILTER_ENABLED 1 also opens all filters at boot (9 kHz instead of the
 * accidental 1 kHz default), so the dry sound is brighter than stock. Set to
 * 0 for byte-identical upstream behavior.
 */
#ifndef FILTER_ENABLED
#define FILTER_ENABLED 1
#endif
#define FILTER_MIN_HZ 281.25f  // TOERN 'PASS' lowpass mapping
#define FILTER_MAX_HZ 9000.0f
#define FILTER_RES 0.7f        // neutral resonance

/* ===================== MIDI CLOCK OUT (master sync) ===================== *
 * When enabled, the sequencer emits MIDI realtime Clock/Start/Stop/Continue so
 * external gear can slave to the NI404. Defaults to 0 to preserve original
 * behavior (NI404 acts only as a clock slave). It never generates clock while
 * the device is itself slaved to incoming external MIDI clock.
 */
#ifndef MIDI_CLOCK_OUT_ENABLED
#define MIDI_CLOCK_OUT_ENABLED 0
#endif
// If incoming external MIDI clock pulses arrive within this window, the NI404
// stays a slave and does not generate its own clock.
#define EXTERNAL_CLOCK_TIMEOUT_MS 750

#endif // NI404_CONFIG_H
