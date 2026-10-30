// i2cEncoderLibV2.h — DROP-IN replacement for the Duppa I2C RGB encoder library,
// backed by plain KY-040 mechanical encoders on the Teensy 4.1 GPIO. It exposes the
// same API the TŒRN firmware calls, so TŒRN runs UNCHANGED on hand-soldered hardware
// (4 KY-040 with push) instead of 4 expensive I2C RGB encoders.
//
//   - rotation -> the Encoder library (quadrature, 4 counts/detent)
//   - push     -> the encoder's switch pin (INPUT_PULLUP, active LOW)
//   - RGB ring -> no hardware ring; writeRGBCode() is remembered (readRGBCode()) so an
//                 OLED HUD can show the colour-coded state instead.
//
// Encoders are matched in CONSTRUCTION ORDER (TŒRN builds exactly 4) onto a fixed pin
// table — left to right, the NI404 1.x hand-wiring. Override ICHOS_ENC_PINS to remap.
#ifndef ICHOS_I2CENCODERLIBV2_H
#define ICHOS_I2CENCODERLIBV2_H

#include <Arduino.h>
#include <Encoder.h>

#ifndef ICHOS_ENC_PINS
// {CLK, DT, SW} for the 4 KY-040, left -> right (see _DOCS/wiring.txt).
// All pins avoid TŒRN's hard-coded GPIO (2/3/4 switches, 17 matrix, 24 strip,
// 27 INT, 30/36 LED power, 40 batt) and the Audio Shield (6/7/8/10-13/18-21/23).
#define ICHOS_ENC_PINS { {5, 22, 15}, {32, 33, 41}, {9, 14, 16}, {37, 38, 39} }
#endif
#ifndef ICHOS_ENC_DEBOUNCE_MS
#define ICHOS_ENC_DEBOUNCE_MS 8
#endif
#ifndef ICHOS_ENC_COUNTS_PER_DETENT
#define ICHOS_ENC_COUNTS_PER_DETENT 4     // most KY-040; set 2 if one click moves 2 steps
#endif

class i2cEncoderLibV2 {
public:
  // Config/status constants — TŒRN uses them scoped (i2cEncoderLibV2::DIRE_LEFT).
  static const int WRAP_ENABLE = 0x01, WRAP_DISABLE = 0x00;
  static const int DIRE_LEFT = 0x02, DIRE_RIGHT = 0x00;
  static const int IPUP_ENABLE = 0x04, IPUP_DISABLE = 0x00;
  static const int RMOD_X1 = 0x00, RMOD_X2 = 0x10, RMOD_X4 = 0x20;
  static const int RGB_ENCODER = 0x08, STD_ENCODER = 0x00;
  static const int EEPROM_BANK1 = 0x00, INT_DATA = 0x00, CLK_STRECH_ENABLE = 0x00;
  static const int PUSHR = 0x01, PUSHP = 0x02, PUSHD = 0x04;
  static const int RINC = 0x08, RDEC = 0x10, RMAX = 0x20, RMIN = 0x40, INT_2 = 0x80;

  typedef void (*Callback)(i2cEncoderLibV2 *);
  Callback onButtonPush = nullptr, onButtonRelease = nullptr, onButtonDoublePush = nullptr;
  Callback onIncrement = nullptr, onDecrement = nullptr, onChange = nullptr;
  Callback onMax = nullptr, onMin = nullptr, onMinMax = nullptr, onFadeProcess = nullptr;

  explicit i2cEncoderLibV2(uint8_t address) : addr(address), slot(nextSlot()) {}

  // TŒRN calls begin() again on E1 every time it enters/leaves SET_WAV or FILTER (only
  // to flip the direction), so the Encoder object is created once and then kept.
  void begin(uint32_t conf = 0) {
    static const uint8_t P[4][3] = ICHOS_ENC_PINS;
    if (!enc && slot >= 0 && slot < 4) {
      clkPin = P[slot][0]; dtPin = P[slot][1]; swPin = P[slot][2];
      enc = new Encoder(clkPin, dtPin);
      pinMode(swPin, INPUT_PULLUP);
      delayMicroseconds(100);            // let the pull-up settle before the first sample
      lastRaw = enc->read();
      rawBtn = lastBtn = false;          // start released: no fake release on the first loop
      btnSince = millis();
    }
    reverse = (conf & DIRE_LEFT) != 0;   // honor the firmware's per-encoder direction
  }

  void reset() { if (enc) { enc->write(0); lastRaw = 0; } counter = 0; }
  void autoconfigInterrupt() {}
  void writeInterruptConfig(uint8_t) {}
  void writeCounter(int32_t v) { counter = v; }
  void writeMax(int32_t v) { vmax = v; }
  void writeMin(int32_t v) { vmin = v; }
  void writeStep(int32_t v) { step = v ? v : 1; }
  void writeAntibouncingPeriod(uint8_t) {}
  void writeDoublePushPeriod(uint8_t) {}     // double-push is disabled by TŒRN anyway
  void writeGammaRLED(uint8_t) {}
  void writeFadeRGB(uint8_t) {}
  void writeRGBCode(uint32_t code) { rgb = code; }
  void writeRGBCode(uint8_t r, uint8_t g, uint8_t b) { rgb = ((uint32_t)r << 16) | ((uint32_t)g << 8) | b; }

  int32_t readCounterInt() { return counter; }
  int32_t readCounterByte() { return counter; }
  uint32_t readRGBCode() { return rgb; }
  uint8_t id() { return addr; }

  // Poll the encoder + button, update the clamped counter, fire callbacks.
  bool updateStatus() {
    bool any = false;
    if (!enc) return false;
    long raw = enc->read();
    long det = (raw - lastRaw) / ICHOS_ENC_COUNTS_PER_DETENT;   // quadrature counts per click
    if (det != 0) {
      lastRaw += det * ICHOS_ENC_COUNTS_PER_DETENT;
      if (reverse) det = -det;
      int32_t before = counter;
      counter += det * step;
      if (counter > vmax) counter = vmax;
      if (counter < vmin) counter = vmin;
      if (counter != before) {
        any = true;
        if (counter > before && onIncrement) onIncrement(this);
        if (counter < before && onDecrement) onDecrement(this);
        if (onChange) onChange(this);
        if (counter == vmax && onMax) onMax(this);
        if (counter == vmin && onMin) onMin(this);
      }
    }
    // Push switch (INPUT_PULLUP: pressed = LOW), debounced: a level change is accepted
    // only after ICHOS_ENC_DEBOUNCE_MS of stability, so contact bounce can't turn one
    // click into two.
    const bool r = (digitalRead(swPin) == LOW);
    const uint32_t t = millis();
    if (r != rawBtn) { rawBtn = r; btnSince = t; }
    else if (r != lastBtn && t - btnSince >= ICHOS_ENC_DEBOUNCE_MS) {
      lastBtn = r;
      if (r && onButtonPush) onButtonPush(this);
      if (!r && onButtonRelease) onButtonRelease(this);
      any = true;
    }
    return any;
  }
  // Duppa's readStatus() just returns the last status byte, with no I/O and no
  // callbacks. TŒRN only calls it from its stuck-button watchdog (toern.ino, "likely
  // stuck"), which reads bit 0x08 as "button really held": report exactly that.
  uint8_t readStatus() { return lastBtn ? 0x08 : 0x00; }
  bool readStatus(uint8_t flag) { return (readStatus() & flag) != 0; }
  void readEncoder8(uint8_t) {}

private:
  uint8_t addr; int slot;
  Encoder *enc = nullptr;
  uint8_t clkPin = 0, dtPin = 0, swPin = 0;
  long lastRaw = 0;
  bool lastBtn = false, rawBtn = false, reverse = false;
  uint32_t btnSince = 0;
  int32_t counter = 0, vmax = (1 << 30), vmin = -(1 << 30), step = 1;
  uint32_t rgb = 0;
  static int nextSlot() { static int n = 0; int s = n; if (n < 3) n++; return s; }
};

#endif // ICHOS_I2CENCODERLIBV2_H
