// Adafruit_SSD1306.h — desktop shim. Emulates the SSD1306 OLED as a 128x64 mono
// framebuffer (1 byte/pixel); display() publishes it to the SDL frontend, which
// draws it as a panel beside the LED grid. This is the display the NI404 fork's
// display.h drives (OLED_ENABLED=1).
#ifndef NI404_COMPAT_ADAFRUIT_SSD1306_H
#define NI404_COMPAT_ADAFRUIT_SSD1306_H

#include "Adafruit_GFX.h"
#include "Wire.h"
#include <cstring>

#define SSD1306_SWITCHCAPVCC 0x02
#define SSD1306_EXTERNALVCC  0x01

// Publish the current OLED frame to the frontend (defined in host_io.cpp).
void ni404_publish_oled(const uint8_t *fb, int w, int h);

class Adafruit_SSD1306 : public Adafruit_GFX {
public:
    Adafruit_SSD1306(int16_t w, int16_t h, TwoWire * = nullptr, int16_t = -1,
                     uint32_t = 0, uint32_t = 0)
        : Adafruit_GFX(w, h) { clearDisplay(); }

    bool begin(uint8_t = SSD1306_SWITCHCAPVCC, uint8_t = 0x3C, bool = true, bool = true) {
        clearDisplay();
        return true;   // always "present" in the emulator
    }
    void clearDisplay() { std::memset(buffer, 0, sizeof(buffer)); }
    void display() { ni404_publish_oled(buffer, width(), height()); }

    void drawPixel(int16_t x, int16_t y, uint16_t color) override {
        if (x < 0 || y < 0 || x >= width() || y >= height()) return;
        uint8_t &px = buffer[(int)y * width() + (int)x];
        if (color == SSD1306_INVERSE) px ^= 1;
        else px = color ? 1 : 0;
    }

    void dim(bool) {}
    void setContrast(uint8_t) {}
    void invertDisplay(bool) {}
    void ssd1306_command(uint8_t) {}
    void startscrollright(uint8_t, uint8_t) {}
    void stopscroll() {}

private:
    uint8_t buffer[128 * 64] = {};
};

#endif // NI404_COMPAT_ADAFRUIT_SSD1306_H
