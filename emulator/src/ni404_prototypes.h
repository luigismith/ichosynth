// ni404_prototypes.h — AUTO-GENERATED forward declarations of the firmware's
// functions. The Arduino IDE auto-prototypes every function before compiling;
// when building the raw .ino as C++ we must do the same so functions can call
// each other regardless of definition order. Included by firmware.cpp BEFORE the
// .ino (after the .ino's own Mode/Device types are forward-declared here).
#ifndef NI404_PROTOTYPES_H
#define NI404_PROTOTYPES_H

#include "Arduino.h"     // String, uint*_t
#include "FastLED.h"     // CRGB
#include "Encoder.h"     // Encoder

struct Mode;             // defined in the .ino (line ~138)

void serialprint(...);
void serialprintln(...);
void resetAllFilters();
void allOff();
void FastLEDclear();
void FastLEDshow();
void drawNoSD();
void copyPosValues(Mode *source, Mode *destination);
void setVelocity();
unsigned int filterVoice();
void applyFilter(unsigned int v);
void applyAllFilters();
void drawFilterBar(unsigned int v);
void setup();
void buttonCallbackFunction(void *s);
void checkMode();
void setLastFile();
void getLastFiles();
void shiftNotes();
void tmpMuteAll(bool pressed);
void toggleMute();
void deleteActiveCopy();
void togglePlay(bool &value);
void playNote();
void unpaint();
void paint();
void light(unsigned int x, unsigned int y, CRGB color);
void switchMode(Mode *newMode);
int reverseMapEncoderValue(unsigned int encoderValue, unsigned int minValue, unsigned int maxValue);
float mapAndClampEncoderValue(Encoder &encoder, int min, int max, int id);
void displaySample(unsigned int len);
void checkPositions();
void preloadSample(unsigned int folder, unsigned int sampleID, bool setMaxSampleLength);
void preview(unsigned int PrevSampleRate, unsigned int plen);
void previewSample(unsigned int folder, unsigned int sampleID, bool setMaxSampleLength, bool firstPreview);
void drawLoadingBar(int minval, int maxval, int currentval, CRGB color, CRGB fontColor);
void loadSample(unsigned int packID, unsigned int sampleID);
void loop();
void canvas(bool singleview);
void toggleCopyPaste();
void clearNoteChannel(unsigned int c, unsigned int yStart, unsigned int yEnd, unsigned int channel, bool singleMode);
void clearPage();
void drawBPMScreen();
void updateVolume();
void updateBPM();
void setVolume();
CRGB getCol(unsigned int g);
void drawVolume(unsigned int vol);
void showMenu();
void showSamplePack();
void loadSamplePack(unsigned int pack);
void saveSamplePack(unsigned int pack);
int getFolderNumber(int value);
int getFileNumber(int value);
void showWave();
void showIntro();
void showNumber(unsigned int count, CRGB color, int topY);
void drawVelocity(CRGB color);
void drawBase();
void drawStatus();
void updateLastPage();
void drawPages();
void drawSamples();
void drawTimer(unsigned int timer);
void drawCursor();
void showIcons(String ico, CRGB colors);
void loadWav();
void savePattern(bool autosave);
void autoSave();
void loadPattern(bool autoload);
void autoLoad();
void handleStop();
void handleNoteOn(uint8_t channel, uint8_t pitch, uint8_t velocity);
void handleNoteOff(uint8_t channel, uint8_t pitch, uint8_t velocity);
void handleStart();
void handleTimeCodeQuarterFrame(uint8_t data);
void handleSongPosition(uint16_t beats);
void myClock();
unsigned long midiClockIntervalUs();
bool slavedToExternalClock();
void sendMidiClockPulse();
void midiClockTransport(bool playing);
void midiClockUpdateTempo();

#endif // NI404_PROTOTYPES_H
