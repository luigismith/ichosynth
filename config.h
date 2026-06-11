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
#define ENC_MIDR_CLK 99 // 4th knob — UNUSED in this 3-encoder build (99 = not wired)
#define ENC_MIDR_DT 99  // 4th knob — UNUSED in this 3-encoder build (99 = not wired)

/* ===================== ENCODER PUSH-BUTTONS ===================== */
#define BTN_LEFT 15 // Left knob switch
#define BTN_RIGHT 3 // Right knob switch
#define BTN_MIDL 16 // Middle (center) knob switch
#define BTN_MIDR 99 // 4th knob switch — UNUSED in this 3-encoder build (99 = not wired)

/*
 * 4th encoder present?
 * 0 = 3-encoder build (THIS BUILD): three KY-040 encoders only (LEFT, CENTER,
 *     RIGHT). Volume moves to the LEFT knob, BPM to the CENTER knob, and the
 *     button gestures that upstream put on the 4th knob (Play/Pause, Volume/BPM,
 *     Menu, Note-Shift) are remapped onto the three remaining buttons — see the
 *     `!isEncoder4Defined` branches in checkMode(). Filtering/seeking disabled.
 * 1 = full 4-encoder build (filtering + sample-end seeking + volume on the
 *     middle-right knob). Restore the real ENC_MIDR and BTN_MIDR pins above.
 */
#define HAS_ENCODER4 0

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
 * Control: a plain momentary PUSHBUTTON (to GND) on BTN_FILTER — wired where
 * the 4th encoder's switch would sit. HOLD the button and TURN the CENTER
 * knob to sweep the lowpass of the voice under the cursor (row - 1, same
 * indexing as mute). Release = back to normal. Settings persist per song.
 *
 * FILTER_ENABLED 1 also opens all filters at boot (9 kHz instead of the
 * accidental 1 kHz default), so the dry sound is brighter than stock. Set to
 * 0 for byte-identical upstream behavior (and no button needed).
 */
#ifndef FILTER_ENABLED
#define FILTER_ENABLED 1
#endif
#define BTN_FILTER 41          // momentary pushbutton to GND (4th knob's SW spot)
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
