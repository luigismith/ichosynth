// FastTouch.h — DROP-IN replacement for the FastTouch capacitive-touch library,
// backed by 3 plain momentary pushbuttons on the Teensy 4.1 (the Teensy 4.x has no
// native cap-touch). TŒRN reads its 3 touch switches with fastTouchRead(pin); here
// each maps to a pushbutton (INPUT_PULLUP, active LOW) and returns a value above the
// firmware's touch threshold (45) when pressed.
//
// build_toern.py remaps TŒRN's SWITCH_1/2/3 onto ICHOS_BTN_PINS. Three things matter
// on real hardware:
//  - TŒRN calls pinMode(SWITCH_n, INPUT_PULLDOWN) in setup() (right for touch pads,
//    wrong for buttons to GND: an open button would read "pressed" and the firmware
//    would hang in INIT MODE). build_toern.py patches those lines, and the pull-up is
//    also re-asserted here on every read, so the buttons work either way.
//  - The very first read (TŒRN checks SWITCH_1 for "CLR RAM", which erases the
//    EEPROM) waits for the freshly enabled pull-up to settle before sampling.
//  - Contacts bounce: a level change counts only after it has been stable for
//    ICHOS_BTN_DEBOUNCE_MS, so one press never becomes two (e.g. Play/Pause, tap tempo).
#ifndef ICHOS_FASTTOUCH_H
#define ICHOS_FASTTOUCH_H

#include <Arduino.h>

#ifndef ICHOS_BTN_PINS
// the 3 tact switches (PLAY/MENU/REC roles). 24 is TŒRN's 2nd LED strip and 27 is its
// INT pin, so the buttons sit on 25/26/28; build_toern.py remaps SWITCH_1/2/3 to match.
#define ICHOS_BTN_PINS { 25, 26, 28 }
#endif
#ifndef ICHOS_BTN_DEBOUNCE_MS
#define ICHOS_BTN_DEBOUNCE_MS 8
#endif

inline int fastTouchRead(int pin) {
  static const uint8_t B[3] = ICHOS_BTN_PINS;
  static bool inited = false;
  static bool state[3], raw[3];
  static uint32_t since[3];
  if (!inited) {
    for (int i = 0; i < 3; i++) pinMode(B[i], INPUT_PULLUP);
    delayMicroseconds(100);                      // let the pull-ups charge the lines
    for (int i = 0; i < 3; i++) { state[i] = raw[i] = (digitalRead(B[i]) == LOW); since[i] = millis(); }
    inited = true;
  }
  for (int i = 0; i < 3; i++) {
    if (pin != B[i]) continue;
    pinMode(B[i], INPUT_PULLUP);                 // undo TŒRN's INPUT_PULLDOWN, if any
    const bool now = (digitalRead(B[i]) == LOW);
    const uint32_t t = millis();
    if (now != raw[i]) { raw[i] = now; since[i] = t; }
    else if (now != state[i] && t - since[i] >= ICHOS_BTN_DEBOUNCE_MS) state[i] = now;
    return state[i] ? 100 : 0;
  }
  return 0;
}

#endif // ICHOS_FASTTOUCH_H
