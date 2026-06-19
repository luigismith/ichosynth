// FastTouch.h — DROP-IN replacement for the FastTouch capacitive-touch library,
// backed by 3 plain momentary pushbuttons on the Teensy 4.1 (the Teensy 4.x has no
// native cap-touch). TŒRN reads its 3 touch switches with fastTouchRead(pin); here
// each maps to a pushbutton (INPUT_PULLUP, active LOW) and returns a value above the
// firmware's touch threshold (45) when pressed.
//
// TŒRN's SWITCH_1/2/3 default to pins 2/3/4, which collide with our encoder wiring,
// so they must be redefined to ICHOS_BTN_PINS (the 3 tact switches) in the sketch.
#ifndef ICHOS_FASTTOUCH_H
#define ICHOS_FASTTOUCH_H

#include <Arduino.h>

#ifndef ICHOS_BTN_PINS
// the 3 tact switches (PLAY/MENU/REC roles). 24 is TŒRN's 2nd LED strip and 27 is its
// INT pin, so the buttons sit on 25/26/28; build_toern.py remaps SWITCH_1/2/3 to match.
#define ICHOS_BTN_PINS { 25, 26, 28 }
#endif

inline int fastTouchRead(int pin) {
  static const uint8_t B[3] = ICHOS_BTN_PINS;
  static bool inited = false;
  if (!inited) { for (int i = 0; i < 3; i++) pinMode(B[i], INPUT_PULLUP); inited = true; }
  // Map the firmware's touch pins (whatever they are) to our 3 buttons in order.
  for (int i = 0; i < 3; i++)
    if (pin == B[i]) return (digitalRead(B[i]) == LOW) ? 100 : 0;
  return 0;
}

#endif // ICHOS_FASTTOUCH_H
