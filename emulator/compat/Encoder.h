// Encoder.h — desktop shim for the Teensy Encoder library. Each physical knob is
// mapped (by its CLK pin from config.h) to a host encoder slot the SDL frontend
// drives. read() returns quadrature counts at 4 counts per detent, exactly like
// the hardware (the firmware divides by 4 / maps over max*4).
#ifndef NI404_COMPAT_ENCODER_H
#define NI404_COMPAT_ENCODER_H

#include "config.h"
#include "ni404_host.h"

class Encoder {
public:
    Encoder(int clkPin, int /*dtPin*/) : slot(slotForPin(clkPin)) {}
    long read() { return ni404_host_encoder_get(slot); }
    void write(long value) { ni404_host_encoder_set(slot, value); }

private:
    int slot;
    static int slotForPin(int clk) {
        if (clk == ENC_LEFT_CLK)  return ENC_LEFT;
        if (clk == ENC_RIGHT_CLK) return ENC_RIGHT;
        if (clk == ENC_MIDL_CLK)  return ENC_CENTER;
        return ENC_4TH;
    }
};

#endif // NI404_COMPAT_ENCODER_H
