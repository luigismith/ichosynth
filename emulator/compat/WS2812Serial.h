// WS2812Serial.h — desktop stub. On the Teensy this is the DMA LED driver; the
// firmware only needs the token `WS2812SERIAL` (used as a FastLED chipset
// template argument) and the USE_WS2812SERIAL define to exist.
#ifndef NI404_COMPAT_WS2812SERIAL_H
#define NI404_COMPAT_WS2812SERIAL_H

// FastLED chipset selector token. Kept as an int constant so it can be passed
// as a non-type template argument to FastLED.addLeds<WS2812SERIAL, PIN, ORDER>.
static const int WS2812SERIAL = 1;

#endif // NI404_COMPAT_WS2812SERIAL_H
