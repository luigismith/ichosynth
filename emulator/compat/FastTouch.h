// FastTouch.h — desktop shim for the FastTouch library. fastTouchRead(pin)
// returns a capacitance reading on the device; here the 3 TŒRN touch switches
// (SWITCH_1=pin2, SWITCH_2=pin3, SWITCH_3=pin4) map to host "touch" buttons, so
// they can be driven from the keyboard/MIDI. Returns a value above any sane
// threshold when touched, 0 otherwise.
#ifndef NI404_COMPAT_FASTTOUCH_H
#define NI404_COMPAT_FASTTOUCH_H

#include "ni404_host.h"

// Host button slots used for the three touch switches (above the 5 used by the
// encoders/filter button).
enum { TOUCH_SLOT_1 = 5, TOUCH_SLOT_2 = 6, TOUCH_SLOT_3 = 7 };

inline int fastTouchRead(int pin) {
    int slot;
    switch (pin) {
        case 2:  slot = TOUCH_SLOT_1; break;   // SWITCH_1
        case 3:  slot = TOUCH_SLOT_2; break;   // SWITCH_2
        case 4:  slot = TOUCH_SLOT_3; break;   // SWITCH_3
        default: return 0;
    }
    return ni404_host_button_get(slot) ? 100 : 0;
}

#endif // NI404_COMPAT_FASTTOUCH_H
