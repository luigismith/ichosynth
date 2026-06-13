// Wire.h — desktop stub for the Teensy/Arduino I2C library. The emulator has no
// real I2C bus (the OLED and RGB encoders are emulated elsewhere), so this just
// satisfies the API: begin/clock/transmission/read are no-ops returning success.
#ifndef NI404_COMPAT_WIRE_H
#define NI404_COMPAT_WIRE_H

#include <cstdint>
#include <cstddef>

class TwoWire {
public:
    void begin() {}
    void begin(uint8_t) {}
    void end() {}
    void setClock(uint32_t) {}
    void setSDA(uint8_t) {}
    void setSCL(uint8_t) {}
    void beginTransmission(uint8_t) {}
    uint8_t endTransmission(uint8_t = 1) { return 0; }   // 0 = success
    size_t write(uint8_t) { return 1; }
    size_t write(const uint8_t *, size_t n) { return n; }
    uint8_t requestFrom(uint8_t, uint8_t) { return 0; }
    int available() { return 0; }
    int read() { return -1; }
    int peek() { return -1; }
    void onReceive(void (*)(int)) {}
    void onRequest(void (*)()) {}
};

extern TwoWire Wire, Wire1, Wire2;

#endif // NI404_COMPAT_WIRE_H
