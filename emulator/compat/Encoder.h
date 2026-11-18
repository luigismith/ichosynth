// Encoder.h — desktop shim for the PJRC Encoder library (quadrature on two pins).
//
// The encoder is found through the emulator's VIRTUAL WIRING (ni404_host.h,
// ni404_wire_encoder): each on-screen knob is "soldered" to a CLK/DT pin pair, exactly
// as on the board. Encoder(a, b) reads the knob wired to those pins, 4 counts per
// detent like a KY-040; if the firmware passes the pins swapped (b, a) the count runs
// backwards, as it would on the hardware; if nothing is wired there it never moves.
// The lookup is lazy (first read), so encoders built as static globals work too.
//
// Convention: a clockwise turn of the on-screen knob (keyboard A/S/D/F, wheel up,
// clockwise drag) adds counts on Encoder(CLK, DT).
#ifndef NI404_COMPAT_ENCODER_H
#define NI404_COMPAT_ENCODER_H

#include "Arduino.h"
#include "ni404_host.h"

class Encoder {
public:
    Encoder(uint8_t pinA, uint8_t pinB) : a(pinA), b(pinB) {
        pinMode(a, INPUT_PULLUP);   // the PJRC library enables the pull-ups itself
        pinMode(b, INPUT_PULLUP);
    }
    long read() { resolve(); return pos + (slot < 0 ? 0 : sign * (ni404_host_encoder_get(slot) - hostBase)); }
    void write(long p) {
        resolve();
        pos = p;
        hostBase = slot < 0 ? 0 : ni404_host_encoder_get(slot);
    }

private:
    uint8_t a, b;
    int slot = -2;          // -2 = not looked up yet, -1 = nothing wired to these pins
    long sign = 1, pos = 0, hostBase = 0;
    void resolve() {
        if (slot != -2) return;
        bool reversed = false;
        slot = ni404_wiring_encoder_for(a, b, &reversed);
        sign = reversed ? -1 : 1;
        hostBase = slot < 0 ? 0 : ni404_host_encoder_get(slot);
    }
};

#endif // NI404_COMPAT_ENCODER_H
