// i2cEncoderLibV2.h — desktop shim for the I2C RGB rotary-push encoder library
// (Saimon Duchi). The 4 TŒRN encoders are mapped, in construction order, onto the
// host encoder/button slots the SDL frontend (and MIDI controller) drive. The
// library's clamped counter + callbacks are reproduced; RGB writes are accepted
// (and remembered, so the frontend can colour the on-screen encoders later).
#ifndef NI404_COMPAT_I2CENCODERLIBV2_H
#define NI404_COMPAT_I2CENCODERLIBV2_H

#include <cstdint>
#include "ni404_host.h"

class i2cEncoderLibV2 {
public:
    // Config/status constants — the firmware accesses these SCOPED
    // (i2cEncoderLibV2::INT_DATA), so they must be class members, not macros.
    static const int WRAP_ENABLE = 0x01, WRAP_DISABLE = 0x00;
    static const int DIRE_LEFT = 0x02, DIRE_RIGHT = 0x00;
    static const int IPUP_ENABLE = 0x04, IPUP_DISABLE = 0x00;
    static const int RMOD_X1 = 0x00, RMOD_X2 = 0x10, RMOD_X4 = 0x20;
    static const int RGB_ENCODER = 0x08, STD_ENCODER = 0x00;
    static const int EEPROM_BANK1 = 0x00, INT_DATA = 0x00, CLK_STRECH_ENABLE = 0x00;
    static const int PUSHR = 0x01, PUSHP = 0x02, PUSHD = 0x04;
    static const int RINC = 0x08, RDEC = 0x10, RMAX = 0x20, RMIN = 0x40, INT_2 = 0x80;

    typedef void (*Callback)(i2cEncoderLibV2 *);

    // Public callback members, assigned directly by the firmware.
    Callback onButtonPush = nullptr, onButtonRelease = nullptr, onButtonDoublePush = nullptr;
    Callback onIncrement = nullptr, onDecrement = nullptr, onChange = nullptr;
    Callback onMax = nullptr, onMin = nullptr, onMinMax = nullptr;
    Callback onFadeProcess = nullptr;

    explicit i2cEncoderLibV2(uint8_t address) : addr(address), slot(nextSlot()) {}

    void begin(uint32_t conf = 0) { (void)conf; }
    void reset() { counter = 0; lastHost = ni404_host_encoder_get(slot); }
    void autoconfigInterrupt() {}
    void writeInterruptConfig(uint8_t) {}
    void writeCounter(int32_t v) { counter = v; lastHost = ni404_host_encoder_get(slot); }
    void writeMax(int32_t v) { vmax = v; }
    void writeMin(int32_t v) { vmin = v; }
    void writeStep(int32_t v) { step = v ? v : 1; }
    void writeAntibouncingPeriod(uint8_t) {}
    void writeDoublePushPeriod(uint8_t) {}
    void writeGammaRLED(uint8_t) {}
    void writeFadeRGB(uint8_t) {}
    void writeRGBCode(uint32_t code) { rgb = code; }
    void writeRGBCode(uint8_t r, uint8_t g, uint8_t b) { rgb = ((uint32_t)r << 16) | (g << 8) | b; }

    int32_t readCounterInt() { return counter; }
    int32_t readCounterByte() { return counter; }
    uint32_t readRGBCode() { return rgb; }
    uint8_t id() { return addr; }

    // Read host input, update the clamped counter, fire callbacks.
    bool updateStatus() {
        bool any = false;
        // rotation: host counts are 4 per detent; the library steps by `step`.
        long h = ni404_host_encoder_get(slot);
        long dcount = h - lastHost;
        long detents = dcount / 4;
        if (detents != 0) {
            lastHost += detents * 4;
            int32_t before = counter;
            counter += detents * step;
            if (counter > vmax) counter = vmax;
            if (counter < vmin) counter = vmin;
            if (counter != before) {   // only fire callbacks when the value changed
                any = true;
                if (counter > before && onIncrement) onIncrement(this);
                if (counter < before && onDecrement) onDecrement(this);
                if (onChange) onChange(this);
                // onMax/onMin fire only on the transition that reaches the limit,
                // not on every further detent held against the stop.
                if (counter == vmax && onMax) onMax(this);
                if (counter == vmin && onMin) onMin(this);
            }
        }
        // button
        bool b = ni404_host_button_get(slot);
        if (b && !lastBtn) { if (onButtonPush) onButtonPush(this); any = true; }
        if (!b && lastBtn) { if (onButtonRelease) onButtonRelease(this); any = true; }
        lastBtn = b;
        return any;
    }
    bool readStatus() { return updateStatus(); }
    bool readStatus(uint8_t /*flag*/) { return false; }
    void readEncoder8(uint8_t) {}

private:
    uint8_t addr;
    int slot;
    int32_t counter = 0, vmax = 1 << 30, vmin = -(1 << 30), step = 1;
    long lastHost = 0;
    bool lastBtn = false;
    uint32_t rgb = 0;
    static int nextSlot() { static int n = 0; int s = n; n = (n + 1) & 3; return s; }
};

#endif // NI404_COMPAT_I2CENCODERLIBV2_H
