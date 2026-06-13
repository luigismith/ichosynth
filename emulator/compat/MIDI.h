// MIDI.h — desktop shim for the Arduino MIDI Library (FortySevenEffects). TŒRN
// uses it for the TRS MIDI port on Serial8. We share the SAME real MIDI input
// queue as usbMIDI (see usb_midi.h / midi_in.cpp): MIDI.read() pops a message,
// exposes it via getType()/getData/getChannel(), fires the registered handlers,
// and routes knobs/pads through the controller map.
#ifndef NI404_COMPAT_MIDI_H
#define NI404_COMPAT_MIDI_H

#include <cstdint>
#include "usb_midi.h"     // shared queue + ni404_midi_control

#define MIDI_CHANNEL_OMNI 0
#define MIDI_CHANNEL_OFF  17

namespace midi {
typedef uint8_t Channel;
typedef uint8_t DataByte;
enum MidiType : uint8_t {
    InvalidType           = 0x00,
    NoteOff               = 0x80,
    NoteOn                = 0x90,
    AfterTouchPoly        = 0xA0,
    ControlChange         = 0xB0,
    ProgramChange         = 0xC0,
    AfterTouchChannel     = 0xD0,
    PitchBend             = 0xE0,
    SystemExclusive       = 0xF0,
    TimeCodeQuarterFrame  = 0xF1,
    SongPosition          = 0xF2,
    SongSelect            = 0xF3,
    TuneRequest           = 0xF6,
    Clock                 = 0xF8,
    Start                 = 0xFA,
    Continue              = 0xFB,
    Stop                  = 0xFC,
    ActiveSensing         = 0xFE,
    SystemReset           = 0xFF
};
struct DefaultSettings {
    static const bool     UseRunningStatus = false;
    static const bool     HandleNullVelocityNoteOnAsNoteOff = true;
    static const bool     Use1ByteParsing = true;
    static const unsigned SysExMaxSize = 128;
    static const long     BaudRate = 31250;
};
}

using midi::MidiType;

class MidiInterface {
public:
    void begin(midi::Channel = MIDI_CHANNEL_OMNI) {}

    // Pull one message; dispatch to handlers + controller map. Returns true if a
    // message was available (Arduino-MIDI style polling loop: `while (MIDI.read())`).
    bool read() {
        uint8_t s, d1, d2;
        if (!usbMIDI.poll(s, d1, d2)) return false;
        uint8_t type = s & 0xF0;
        curChannel = (s & 0x0F) + 1;
        if (type < 0xF0) { curType = (midi::MidiType)type; curData1 = d1; curData2 = d2; }
        else { curType = (midi::MidiType)s; curData1 = d1; curData2 = d2; }

        // controller mapping (knobs/pads -> UI)
        if (s >= 0xF0 || type == 0x90 || type == 0x80 || type == 0xB0)
            if (ni404_midi_control(s, d1, d2)) return true;

        switch (type) {
            case 0x90: if (d2 > 0) { if (noteOnCb) noteOnCb(curChannel, d1, d2); }
                       else if (noteOffCb) noteOffCb(curChannel, d1, d2); break;
            case 0x80: if (noteOffCb) noteOffCb(curChannel, d1, d2); break;
            case 0xB0: if (ccCb) ccCb(curChannel, d1, d2); break;
            default:
                switch (s) {
                    case midi::Clock:    if (clockCb) clockCb(); break;
                    case midi::Start:    if (startCb) startCb(); break;
                    case midi::Continue: if (continueCb) continueCb(); break;
                    case midi::Stop:     if (stopCb) stopCb(); break;
                }
        }
        return true;
    }

    midi::MidiType getType() const { return curType; }
    midi::Channel  getChannel() const { return curChannel; }
    midi::DataByte getData1() const { return curData1; }
    midi::DataByte getData2() const { return curData2; }
    midi::DataByte getData() const { return curData1; }

    void setHandleNoteOn(void (*h)(uint8_t, uint8_t, uint8_t)) { noteOnCb = h; }
    void setHandleNoteOff(void (*h)(uint8_t, uint8_t, uint8_t)) { noteOffCb = h; }
    void setHandleControlChange(void (*h)(uint8_t, uint8_t, uint8_t)) { ccCb = h; }
    void setHandleClock(void (*h)()) { clockCb = h; }
    void setHandleStart(void (*h)()) { startCb = h; }
    void setHandleStop(void (*h)()) { stopCb = h; }
    void setHandleContinue(void (*h)()) { continueCb = h; }

    template <class... A> void sendNoteOn(A...) {}
    template <class... A> void sendNoteOff(A...) {}
    template <class... A> void sendControlChange(A...) {}
    template <class... A> void sendRealTime(A...) {}

private:
    midi::MidiType curType = midi::InvalidType;
    midi::Channel  curChannel = 0;
    midi::DataByte curData1 = 0, curData2 = 0;
    void (*noteOnCb)(uint8_t, uint8_t, uint8_t) = nullptr;
    void (*noteOffCb)(uint8_t, uint8_t, uint8_t) = nullptr;
    void (*ccCb)(uint8_t, uint8_t, uint8_t) = nullptr;
    void (*clockCb)() = nullptr, (*startCb)() = nullptr, (*stopCb)() = nullptr, (*continueCb)() = nullptr;
};

// The library's instance-creation macros all just declare a global MidiInterface.
#define MIDI_CREATE_INSTANCE(Type, Serial, Name) MidiInterface Name
#define MIDI_CREATE_CUSTOM_INSTANCE(Type, Serial, Name, Settings) MidiInterface Name
#define MIDI_CREATE_DEFAULT_INSTANCE() MidiInterface MIDI

#endif // NI404_COMPAT_MIDI_H
