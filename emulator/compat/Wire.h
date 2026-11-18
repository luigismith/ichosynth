// Wire.h — desktop model of the Teensy I2C library.
//
// Not a stub: transmissions go to virtual I2C devices attached by 7-bit address
// (src/i2c_bus.cpp). The emulator attaches an SSD1306 at 0x3C that decodes the real
// command/data stream into the on-screen OLED view, so the firmware's own OLED driver
// (firmware/libraries/IchosOled) runs unchanged. Like the hardware:
//   * endTransmission() returns 2 (address NACK) when nothing answers at that address;
//   * the transmit buffer holds 32 bytes: write() returns 0 and drops the byte beyond;
//   * a transfer takes bus time (9 clocks per byte at setClock(), 100 kHz by default),
//     charged to the caller in ~1 ms steps, so a slow HUD shows up as a slow loop().
#ifndef NI404_COMPAT_WIRE_H
#define NI404_COMPAT_WIRE_H

#include <cstdint>
#include <cstddef>

// A device on the bus (implemented by the emulator, e.g. the SSD1306 model).
class Ni404I2cDevice {
public:
    virtual ~Ni404I2cDevice() {}
    // One complete write transaction (START, address+W, bytes..., STOP).
    virtual void i2cWrite(const uint8_t *data, size_t len) = 0;
};

class TwoWire {
public:
    static const size_t BUFFER_LENGTH = 32;

    void begin() {}
    void begin(uint8_t) {}
    void end() {}
    void setClock(uint32_t hz) { if (hz) clockHz = hz; }
    void setSDA(uint8_t) {}
    void setSCL(uint8_t) {}
    void beginTransmission(uint8_t address) { txAddr = address; txLen = 0; inTx = true; }
    void beginTransmission(int address) { beginTransmission((uint8_t)address); }
    uint8_t endTransmission(uint8_t sendStop = 1);
    size_t write(uint8_t b) {
        if (!inTx || txLen >= BUFFER_LENGTH) return 0;
        txBuf[txLen++] = b;
        return 1;
    }
    size_t write(const uint8_t *data, size_t n) { size_t c = 0; while (c < n && write(data[c])) c++; return c; }
    uint8_t requestFrom(uint8_t, uint8_t) { return 0; }
    int available() { return 0; }
    int read() { return -1; }
    int peek() { return -1; }
    void onReceive(void (*)(int)) {}
    void onRequest(void (*)()) {}

    // Emulator: attach/detach a device at a 7-bit address.
    void attach(uint8_t address, Ni404I2cDevice *dev) { if (address < 128) devices[address] = dev; }
    uint32_t clock() const { return clockHz; }

private:
    Ni404I2cDevice *devices[128] = {};
    uint8_t txBuf[BUFFER_LENGTH] = {};
    size_t txLen = 0;
    uint8_t txAddr = 0;
    bool inTx = false;
    uint32_t clockHz = 100000;
    double busDebtUs = 0;    // bus time owed by the caller, slept off in ~1 ms steps
};

extern TwoWire Wire, Wire1, Wire2;

#endif // NI404_COMPAT_WIRE_H
