/*
 * display.h — NI404 fork: optional SSD1306 0.96" 128x64 OLED status HUD.
 *
 * The OLED talks I2C on the SAME Wire bus as the Teensy Audio Shield's SGTL5000
 * codec (SDA = pin 18, SCL = pin 19). The codec answers on a different I2C
 * address, so the two coexist on one bus — only SDA/SCL/3V3/GND are wired.
 *
 * Everything here is compiled out when OLED_ENABLED == 0 (the default), so a
 * board with no display behaves exactly like the upstream firmware and does not
 * even need the Adafruit libraries installed.
 *
 * Performance: the audio loop is timing-sensitive (it relies on delay(5)).
 * Pushing a full 1KB framebuffer over I2C is comparatively slow, so updates are
 * (a) throttled to OLED_FPS and (b) skipped entirely unless a displayed value
 * actually changed (dirty check). The playhead position is intentionally NOT
 * part of the HUD so playback does not trigger constant I2C traffic.
 */

#ifndef NI404_DISPLAY_H
#define NI404_DISPLAY_H

#include "config.h"

#if OLED_ENABLED

#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

static Adafruit_SSD1306 oled(OLED_WIDTH, OLED_HEIGHT, &Wire, OLED_RESET_PIN);

static bool oledReady = false;
static unsigned long oledLastDraw = 0;

// Snapshot of the last rendered state, for dirty checking.
static String oledLastMode = "";
static int oledLastBpm = -1;
static int oledLastVol = -1;
static int oledLastVel = -1;
static int oledLastPage = -1;
static int oledLastLastPage = -1;
static int oledLastPlaying = -1;

inline void oledInit() {
  // Call AFTER the audio codec is enabled: the codec has already brought up the
  // shared Wire bus. begin() returns false if no panel answers at the address,
  // in which case the firmware simply runs without a HUD.
  if (oled.begin(SSD1306_SWITCHCAPVCC, OLED_I2C_ADDR)) {
    oledReady = true;
    oled.clearDisplay();
    oled.setTextColor(SSD1306_WHITE);
    oled.cp437(true);
    oled.setTextSize(2);
    oled.setCursor(0, 0);
    oled.println(F("NI404"));
    oled.setTextSize(1);
    oled.setCursor(0, 24);
    oled.println(F("fork - status HUD"));
    oled.display();
  }
}

inline void oledRenderStatus(const char *modeName, int bpm, int vol, int vel,
                             int page, int lastPageVal, bool playing) {
  if (!oledReady) return;

  const unsigned long now = millis();
  if (now - oledLastDraw < (unsigned long)(1000 / OLED_FPS)) return;

  const bool dirty =
    (oledLastMode != modeName) || (oledLastBpm != bpm) ||
    (oledLastVol != vol) || (oledLastVel != vel) ||
    (oledLastPage != page) || (oledLastLastPage != lastPageVal) ||
    (oledLastPlaying != (int)playing);
  if (!dirty) return;

  oledLastDraw = now;
  oledLastMode = modeName;
  oledLastBpm = bpm;
  oledLastVol = vol;
  oledLastVel = vel;
  oledLastPage = page;
  oledLastLastPage = lastPageVal;
  oledLastPlaying = (int)playing;

  oled.clearDisplay();

  // Mode name (top-left, large).
  oled.setTextSize(2);
  oled.setCursor(0, 0);
  oled.print(modeName);

  // Transport state (top-right, small).
  oled.setTextSize(1);
  oled.setCursor(OLED_WIDTH - 30, 0);
  oled.print(playing ? F(">PLAY") : F("STOP"));

  // BPM (large).
  oled.setTextSize(2);
  oled.setCursor(0, 20);
  oled.print(F("BPM "));
  oled.print(bpm);

  // Volume / velocity.
  oled.setTextSize(1);
  oled.setCursor(0, 42);
  oled.print(F("Vol:"));
  oled.print(vol);
  oled.print(F("  Vel:"));
  oled.print(vel);

  // Page / last page.
  oled.setCursor(0, 54);
  oled.print(F("Page:"));
  oled.print(page);
  oled.print(F("/"));
  oled.print(lastPageVal);

  oled.display();
}

#else // OLED_ENABLED == 0 : no-op stubs, zero runtime cost.

inline void oledInit() {}
inline void oledRenderStatus(const char *, int, int, int, int, int, bool) {}

#endif // OLED_ENABLED
#endif // NI404_DISPLAY_H
