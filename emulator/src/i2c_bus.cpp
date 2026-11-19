// i2c_bus.cpp — the emulator's I2C bus (compat/Wire.h) and the SSD1306 OLED on it.
//
// The SSD1306 model decodes the byte stream exactly as the controller does: a control
// byte per transaction (Co / D-C# bits), the fundamental / addressing / hardware-config
// commands with their argument bytes, and GDDRAM writes in page, horizontal or vertical
// addressing mode. The panel image is then derived from GDDRAM + the configuration
// (display on, charge pump, segment remap, COM scan direction, start line, offset,
// multiplex, inverse, entire-on) and published to the window's OLED view. So the view
// shows what the real 0.96" module would show for the bytes the firmware sent: an init
// missing the charge pump or 0xAF stays dark, a wrong remap is mirrored, and so on.
#include "Wire.h"
#include "Arduino.h"   // delayMicroseconds
#include <cstdlib>
#include <cstring>

void ni404_publish_oled(const uint8_t *fb, int w, int h);   // host_io.cpp

namespace {

class Ssd1306 : public Ni404I2cDevice {
public:
    Ssd1306() { std::memset(ram, 0, sizeof ram); }

    void i2cWrite(const uint8_t *d, size_t n) override {
        size_t i = 0;
        bool changed = false;
        while (i < n) {
            const uint8_t ctrl = d[i++];
            const bool co = (ctrl & 0x80) != 0;     // continuation: one byte, then a new control byte
            const bool data = (ctrl & 0x40) != 0;   // D/C#
            if (co) {
                if (i >= n) break;
                changed |= data ? dataByte(d[i++]) : cmdByte(d[i++]);
            } else {
                while (i < n) changed |= data ? dataByte(d[i++]) : cmdByte(d[i++]);
            }
        }
        if (changed) publish();
    }

private:
    uint8_t ram[8][128];
    // configuration (power-on reset values from the datasheet)
    bool on = false, pump = false, invert = false, entireOn = false;
    bool segRemap = false, comRemap = false;
    uint8_t mux = 63, offset = 0, startLine = 0, memMode = 2;   // 2 = page addressing
    uint8_t col = 0, page = 0, colStart = 0, colEnd = 127, pageStart = 0, pageEnd = 7;
    // multi-byte command parser
    uint8_t pend = 0, need = 0, args[6] = {}, nargs = 0;

    bool dataByte(uint8_t v) {
        ram[page & 7][col & 127] = v;
        if (memMode == 2) {                       // page mode: column wraps within the page
            col = (uint8_t)((col + 1) & 127);
        } else if (memMode == 0) {                // horizontal
            if (col >= colEnd) { col = colStart; page = (page >= pageEnd) ? pageStart : (uint8_t)(page + 1); }
            else col++;
        } else {                                  // vertical
            if (page >= pageEnd) { page = pageStart; col = (col >= colEnd) ? colStart : (uint8_t)(col + 1); }
            else page++;
        }
        return true;
    }

    bool cmdByte(uint8_t c) {
        if (need) {                               // collecting arguments of `pend`
            args[nargs++] = c;
            if (--need) return false;
            return applyArgs();
        }
        switch (c) {
            case 0x81: case 0x20: case 0xA8: case 0xD3: case 0xD5: case 0xD9:
            case 0xDA: case 0xDB: case 0x8D: case 0xAD:
                return begin(c, 1);
            case 0x21: case 0x22: case 0xA3: return begin(c, 2);
            case 0x29: case 0x2A: return begin(c, 5);
            case 0x26: case 0x27: return begin(c, 6);
            case 0xAE: on = false; return true;
            case 0xAF: on = true; return true;
            case 0xA0: segRemap = false; return true;
            case 0xA1: segRemap = true; return true;
            case 0xC0: comRemap = false; return true;
            case 0xC8: comRemap = true; return true;
            case 0xA4: entireOn = false; return true;
            case 0xA5: entireOn = true; return true;
            case 0xA6: invert = false; return true;
            case 0xA7: invert = true; return true;
            case 0x2E: case 0x2F: case 0xE3: return false;   // scroll off/on, NOP
            default: break;
        }
        if (c >= 0x40 && c <= 0x7F) { startLine = c & 0x3F; return true; }
        if (c >= 0xB0 && c <= 0xB7) { page = c & 7; return false; }
        if (c <= 0x0F) { col = (uint8_t)((col & 0xF0) | (c & 0x0F)); return false; }
        if (c >= 0x10 && c <= 0x1F) { col = (uint8_t)((col & 0x0F) | ((c & 0x07) << 4)); return false; }
        return false;                             // unknown: ignored, as the chip does
    }
    bool begin(uint8_t c, uint8_t n) { pend = c; need = n; nargs = 0; return false; }
    bool applyArgs() {
        switch (pend) {
            case 0x20: memMode = args[0] & 3; return false;
            case 0x21: colStart = args[0] & 127; colEnd = args[1] & 127; col = colStart; return false;
            case 0x22: pageStart = args[0] & 7; pageEnd = args[1] & 7; page = pageStart; return false;
            case 0xA8: mux = args[0] & 63; return true;
            case 0xD3: offset = args[0] & 63; return true;
            case 0x8D: pump = (args[0] & 0x04) != 0; return true;
            default: return false;                // contrast, timing, scroll: no visible effect here
        }
    }

    // Build the visible 128x64 image. The common 0.96" modules mount the glass rotated
    // 180 degrees from the controller's native scan, which is why every driver (Adafruit,
    // U8g2, IchosOled) sends 0xA1 (segment remap) + 0xC8 (COM scan reversed): with both
    // set, RAM column 0 / page 0 appear at the top left. Without them the image is
    // mirrored, as on the real module. Start line and display offset shift it vertically.
    void publish() {
        static uint8_t fb[128 * 64];
        const bool lit = on && pump;
        for (int y = 0; y < 64; y++) {
            int com = comRemap ? y : (mux - y);                 // which COM line is at panel row y
            if (com < 0 || y > mux) {                           // rows beyond the multiplex ratio stay dark
                std::memset(fb + y * 128, 0, 128);
                continue;
            }
            int row = (com + startLine + offset) & 63;          // RAM row driven on that COM line
            for (int x = 0; x < 128; x++) {
                int seg = segRemap ? x : (127 - x);
                int bit = (ram[row >> 3][seg] >> (row & 7)) & 1;
                if (entireOn) bit = 1;
                if (invert) bit ^= 1;
                fb[y * 128 + x] = (uint8_t)(lit && bit);
            }
        }
        ni404_publish_oled(fb, 128, 64);
    }
};

Ssd1306 *g_oled = nullptr;

void attach_default_devices() {
    static bool done = false;
    if (done) return;
    done = true;
    // ICHOS_EMU_NO_OLED=1 simulates an unplugged/missing OLED: nothing ACKs at 0x3C.
    const char *e = std::getenv("ICHOS_EMU_NO_OLED");
    if (e && e[0] && e[0] != '0') return;
    g_oled = new Ssd1306();
    Wire.attach(0x3C, g_oled);
}

} // namespace

uint8_t TwoWire::endTransmission(uint8_t /*sendStop*/) {
    attach_default_devices();
    if (!inTx) return 4;
    inTx = false;
    // Bus time: address byte + payload, 9 clocks each (8 bits + ACK), plus START/STOP.
    busDebtUs += (double)(txLen + 1) * 9.0 * 1e6 / (double)clockHz + 10.0 * 1e6 / (double)clockHz;
    if (busDebtUs >= 1000.0) { delayMicroseconds((unsigned long)busDebtUs); busDebtUs = 0; }
    Ni404I2cDevice *dev = devices[txAddr & 127];
    if (!dev) return 2;                              // address NACK
    if (txLen) dev->i2cWrite(txBuf, txLen);
    return 0;
}
