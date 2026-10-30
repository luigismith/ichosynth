// IchosOled.cpp — implementation of the TŒRN port's OLED HUD (see IchosOled.h).
//
// A self-contained, minimal SSD1306 text driver. We do NOT use Adafruit_GFX or U8g2
// here on purpose: TŒRN leaves only ~700 bytes of RAM1 free, and those libraries push
// several KB of code into RAM1 (Teensy 4 runs code from ITCM by default), which
// overflows the link. Instead every function below is marked FLASHMEM (stays in flash,
// not ITCM) and the font lives in PROGMEM, so this HUD costs essentially zero RAM1.
//
// 128x64 SSD1306 over I2C on the Wire bus it shares with the Audio Shield's SGTL5000
// codec (SDA=18, SCL=19, different I2C addresses). Page-addressing mode, no framebuffer
// (glyphs are streamed straight to the panel), 5x7 font => 21 chars x 8 rows. The HUD
// uses 4 rows; each is redrawn whole (space-padded) and only when its text changed.
#include "IchosOled.h"

#include <Arduino.h>
#include <Wire.h>
#include <string.h>

#ifndef ICHOS_OLED_ADDR
#define ICHOS_OLED_ADDR 0x3C
#endif
static const int FPS = 12;

// Classic 5x7 glyphs, column-major (LSB = top pixel), ASCII 0x20..0x5F. Mode names and
// numbers are all uppercase, so this 64-glyph range is everything the HUD needs.
static const uint8_t FONT5x7[] PROGMEM = {
  0x00,0x00,0x00,0x00,0x00, 0x00,0x00,0x5F,0x00,0x00, 0x00,0x07,0x00,0x07,0x00, // sp ! "
  0x14,0x7F,0x14,0x7F,0x14, 0x24,0x2A,0x7F,0x2A,0x12, 0x23,0x13,0x08,0x64,0x62, // # $ %
  0x36,0x49,0x55,0x22,0x50, 0x00,0x05,0x03,0x00,0x00, 0x00,0x1C,0x22,0x41,0x00, // & ' (
  0x00,0x41,0x22,0x1C,0x00, 0x14,0x08,0x3E,0x08,0x14, 0x08,0x08,0x3E,0x08,0x08, // ) * +
  0x00,0x50,0x30,0x00,0x00, 0x08,0x08,0x08,0x08,0x08, 0x00,0x60,0x60,0x00,0x00, // , - .
  0x20,0x10,0x08,0x04,0x02, 0x3E,0x51,0x49,0x45,0x3E, 0x00,0x42,0x7F,0x40,0x00, // / 0 1
  0x42,0x61,0x51,0x49,0x46, 0x21,0x41,0x45,0x4B,0x31, 0x18,0x14,0x12,0x7F,0x10, // 2 3 4
  0x27,0x45,0x45,0x45,0x39, 0x3C,0x4A,0x49,0x49,0x30, 0x01,0x71,0x09,0x05,0x03, // 5 6 7
  0x36,0x49,0x49,0x49,0x36, 0x06,0x49,0x49,0x29,0x1E, 0x00,0x36,0x36,0x00,0x00, // 8 9 :
  0x00,0x56,0x36,0x00,0x00, 0x00,0x08,0x14,0x22,0x41, 0x14,0x14,0x14,0x14,0x14, // ; < =
  0x41,0x22,0x14,0x08,0x00, 0x02,0x01,0x51,0x09,0x06, 0x32,0x49,0x79,0x41,0x3E, // > ? @
  0x7E,0x11,0x11,0x11,0x7E, 0x7F,0x49,0x49,0x49,0x36, 0x3E,0x41,0x41,0x41,0x22, // A B C
  0x7F,0x41,0x41,0x22,0x1C, 0x7F,0x49,0x49,0x49,0x41, 0x7F,0x09,0x09,0x09,0x01, // D E F
  0x3E,0x41,0x49,0x49,0x7A, 0x7F,0x08,0x08,0x08,0x7F, 0x00,0x41,0x7F,0x41,0x00, // G H I
  0x20,0x40,0x41,0x3F,0x01, 0x7F,0x08,0x14,0x22,0x41, 0x7F,0x40,0x40,0x40,0x40, // J K L
  0x7F,0x02,0x0C,0x02,0x7F, 0x7F,0x04,0x08,0x10,0x7F, 0x3E,0x41,0x41,0x41,0x3E, // M N O
  0x7F,0x09,0x09,0x09,0x06, 0x3E,0x41,0x51,0x21,0x5E, 0x7F,0x09,0x19,0x29,0x46, // P Q R
  0x46,0x49,0x49,0x49,0x31, 0x01,0x01,0x7F,0x01,0x01, 0x3F,0x40,0x40,0x40,0x3F, // S T U
  0x1F,0x20,0x40,0x20,0x1F, 0x3F,0x40,0x38,0x40,0x3F, 0x63,0x14,0x08,0x14,0x63, // V W X
  0x07,0x08,0x70,0x08,0x07, 0x61,0x51,0x49,0x45,0x43, 0x00,0x7F,0x41,0x41,0x00, // Y Z [
  0x02,0x04,0x08,0x10,0x20, 0x00,0x41,0x41,0x7F,0x00, 0x04,0x02,0x01,0x02,0x04, // \ ] ^
  0x40,0x40,0x40,0x40,0x40,                                                     // _
};

static const uint8_t COLS = 21;           // 21 glyphs x 6 px = 126 px per text row
static const uint8_t ROW_PAGE[4] = {0, 2, 4, 6};
static bool oledOk = false, fastBus = false;
static unsigned long lastDraw = 0;
static char shown[4][COLS + 1];           // what each HUD row currently shows on the panel
static uint8_t nextRow = 0;

FLASHMEM static void cmd(uint8_t c) {
  Wire.beginTransmission(ICHOS_OLED_ADDR);
  Wire.write((uint8_t)0x00);  // Co=0, D/C#=0 -> command stream
  Wire.write(c);
  Wire.endTransmission();
}

// Move the page cursor to (page row 0..7, column 0..127).
FLASHMEM static void setPos(uint8_t page, uint8_t col) {
  cmd(0xB0 | (page & 0x07));
  cmd(0x00 | (col & 0x0F));
  cmd(0x10 | (col >> 4));
}

FLASHMEM static void clearAll() {
  for (uint8_t p = 0; p < 8; p++) {
    setPos(p, 0);
    for (uint8_t c = 0; c < 128; ) {
      Wire.beginTransmission(ICHOS_OLED_ADDR);
      Wire.write((uint8_t)0x40);  // data stream
      for (uint8_t n = 0; n < 16 && c < 128; n++, c++) Wire.write((uint8_t)0x00);
      Wire.endTransmission();
    }
  }
}

// Draw a string at (page, startCol) using the 5x7 font (6px per glyph incl. spacing).
FLASHMEM static void drawStr(uint8_t page, uint8_t startCol, const char *s) {
  setPos(page, startCol);
  uint8_t col = startCol;
  for (; *s && col + 6 <= 128; s++) {
    char ch = *s;
    if (ch < 0x20 || ch > 0x5F) ch = (ch >= 'a' && ch <= 'z') ? ch - 32 : '?';
    if (ch > 0x5F) ch = '?';
    const uint8_t *g = &FONT5x7[(ch - 0x20) * 5];
    Wire.beginTransmission(ICHOS_OLED_ADDR);
    Wire.write((uint8_t)0x40);
    for (uint8_t i = 0; i < 5; i++) Wire.write(pgm_read_byte(g + i));
    Wire.write((uint8_t)0x00);  // 1px gap between glyphs
    Wire.endTransmission();
    col += 6;
  }
}

FLASHMEM void ichosOledBegin() {
  Wire.begin();
  static const uint8_t INIT[] PROGMEM = {
    0xAE, 0xD5, 0x80, 0xA8, 0x3F, 0xD3, 0x00, 0x40, 0x8D, 0x14,
    0x20, 0x02, 0xA1, 0xC8, 0xDA, 0x12, 0x81, 0xCF, 0xD9, 0xF1,
    0xDB, 0x40, 0xA4, 0xA6, 0xAF };
  // Probe: if nothing ACKs at the address, run without a HUD.
  Wire.beginTransmission(ICHOS_OLED_ADDR);
  if (Wire.endTransmission() != 0) { oledOk = false; return; }
  for (uint8_t i = 0; i < sizeof(INIT); i++) cmd(pgm_read_byte(INIT + i));
  oledOk = true;
  clearAll();
  drawStr(0, 0, "TOERN");
  drawStr(2, 0, "KY-040 + OLED PORT");
}

// Tiny formatting helpers (no snprintf: its formatter costs a few hundred bytes of the
// small RAM1 stack). Each appends to a row buffer of COLS chars and returns the new end.
FLASHMEM static uint8_t putStr(char *row, uint8_t at, const char *s) {
  while (*s && at < COLS) row[at++] = *s++;
  return at;
}

FLASHMEM static uint8_t putInt(char *row, uint8_t at, int v) {
  char tmp[12];
  uint8_t n = 0;
  unsigned int u = v < 0 ? (unsigned int)(-(long)v) : (unsigned int)v;
  do { tmp[n++] = (char)('0' + u % 10); u /= 10; } while (u && n < sizeof(tmp));
  if (v < 0 && at < COLS) row[at++] = '-';
  while (n && at < COLS) row[at++] = tmp[--n];
  return at;
}

// Stream one full, space-padded row: overwrites the old text, so no clear is needed.
// Glyphs go out in 30-byte data packets (the Teensy Wire buffer is 32 bytes).
FLASHMEM static void drawRow(uint8_t page, const char *row) {
  setPos(page, 0);
  uint8_t pkt = 0;
  for (uint8_t i = 0; i < COLS; i++) {
    char ch = row[i];
    if (ch >= 'a' && ch <= 'z') ch -= 32;
    if (ch < 0x20 || ch > 0x5F) ch = '?';
    const uint8_t *g = &FONT5x7[(ch - 0x20) * 5];
    if (pkt == 0) { Wire.beginTransmission(ICHOS_OLED_ADDR); Wire.write((uint8_t)0x40); }
    for (uint8_t k = 0; k < 5; k++) Wire.write(pgm_read_byte(g + k));
    Wire.write((uint8_t)0x00);                 // 1 px gap between glyphs
    pkt += 6;
    if (pkt >= 30 || i == COLS - 1) { Wire.endTransmission(); pkt = 0; }
  }
}

FLASHMEM void ichosOledRender(int ch, int vol, int bpm, int page,
                              const char *mode, bool play, bool rec) {
  if (!oledOk) return;
  if (!fastBus) {          // after setup(): the codec is up, both chips handle 400 kHz
    Wire.setClock(400000);
    fastBus = true;
  }
  const unsigned long now = millis();
  if (now - lastDraw < (unsigned long)(1000 / FPS / 4)) return;   // up to 4 rows per frame time
  if (!mode) mode = "";

  char rows[4][COLS + 1];
  for (uint8_t r = 0; r < 4; r++) { memset(rows[r], ' ', COLS); rows[r][COLS] = '\0'; }
  // Row 0: current channel (was the E1/E4 ring colour) + transport, right-aligned.
  uint8_t at = putInt(rows[0], putStr(rows[0], 0, "CH:"), ch);
  const char *t = rec ? "*REC*" : (play ? ">PLAY" : "STOP");
  const uint8_t tl = (uint8_t)strlen(t);
  if (at + 1 + tl <= COLS) putStr(rows[0], COLS - tl, t);
  putStr(rows[1], putStr(rows[1], 0, "MODE: "), mode);
  putInt(rows[2], putStr(rows[2], 0, "BPM:  "), bpm);
  const uint8_t a3 = putInt(rows[3], putStr(rows[3], 0, "VOL:"), vol);
  putInt(rows[3], putStr(rows[3], (uint8_t)(a3 + 2), "PAGE:"), page);

  // Redraw at most one changed row per call, round-robin.
  for (uint8_t k = 0; k < 4; k++) {
    const uint8_t r = (uint8_t)((nextRow + k) % 4);
    if (memcmp(rows[r], shown[r], COLS) != 0) {
      drawRow(ROW_PAGE[r], rows[r]);
      memcpy(shown[r], rows[r], COLS + 1);
      nextRow = (uint8_t)((r + 1) % 4);
      lastDraw = now;
      return;
    }
  }
}
