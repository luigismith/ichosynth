// IchosOled.h — tiny text HUD for the TŒRN port, on a 128x64 I2C OLED.
//
// TŒRN shows state through the colour of its encoder RGB rings; our KY-040 build has
// no rings, so this puts that state on an OLED instead (see _DOCS/MAPPA_CONTROLLI.md §6).
//
// Why a separate library and not a .ino glued into the sketch: Arduino concatenates
// every .ino into ONE translation unit, and TŒRN's is already so large that adding a
// graphics library to it crashes the Teensy gcc (exit 0xffffffff). Keeping the OLED
// code in its own .cpp compiles it separately, and using U8x8 (text-only, no 1KB
// framebuffer) keeps it light — TŒRN leaves only ~700 bytes of RAM1 free.
//
// This header pulls in NO graphics headers, so including it from the giant sketch TU
// costs nothing. The sketch passes plain scalars in; all rendering happens in the .cpp.
#ifndef ICHOS_OLED_H
#define ICHOS_OLED_H

// Bring up the panel. Call once at the end of setup() (Wire is up by then).
void ichosOledBegin();

// Refresh the HUD from the current state. Safe to call every loop(): it self-throttles
// and only pushes pixels when a shown value actually changed.
//   ch    current channel (was the E1/E4 ring colour)
//   vol   master volume
//   bpm   tempo
//   page  current pattern page
//   mode  mode name ("DRAW", "SINGLE", "FILTERMODE", ...)
//   play  transport running
//   rec   recording
void ichosOledRender(int ch, int vol, int bpm, int page,
                     const char *mode, bool play, bool rec);

#endif // ICHOS_OLED_H
