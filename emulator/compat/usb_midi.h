// usb_midi.h — desktop shim for Teensy's usbMIDI, backed by a REAL MIDI input
// device (see src/midi_in.cpp). Incoming messages are queued by the MIDI backend
// thread via ni404_midi_feed() and dispatched on the main thread from read() to
// the handlers the firmware registered (handleNoteOn/Clock/Start/Stop/...), so a
// plugged-in controller plays & records and external clock syncs — exactly like
// on the device. Control-Change (and any mapped notes) are additionally routed
// to the controller-mapping layer (src/midi_map.cpp) to drive the UI.
#ifndef NI404_COMPAT_USB_MIDI_H
#define NI404_COMPAT_USB_MIDI_H

#include <cstdint>
#include <vector>
#include <mutex>

// Defined in src/midi_map.cpp: translate a raw MIDI message into NI404 host
// controls (encoders/buttons). Returns true if it consumed the message (so it is
// NOT also forwarded to the firmware's note handler).
bool ni404_midi_control(uint8_t status, uint8_t d1, uint8_t d2);

// Defined in src/midi_map.cpp: maps an incoming note-on velocity to the velocity
// the firmware should use. Lets pads/keys behave like fixed-velocity buttons
// (configurable via notevelocity= in midi-map.txt; 0 = real velocity).
uint8_t ni404_note_velocity(uint8_t incoming);

class usb_midi_class {
public:
    static const uint8_t Clock = 0xF8;
    static const uint8_t Start = 0xFA;
    static const uint8_t Continue = 0xFB;
    static const uint8_t Stop = 0xFC;
    static const uint8_t ActiveSensing = 0xFE;
    static const uint8_t SystemReset = 0xFF;

    typedef void (*note_handler)(uint8_t, uint8_t, uint8_t);
    typedef void (*rt_handler)();
    typedef void (*u16_handler)(uint16_t);
    typedef void (*u8_handler)(uint8_t);

    void setHandleNoteOn(note_handler h) { noteOnCb = h; }
    void setHandleNoteOff(note_handler h) { noteOffCb = h; }
    void setHandleControlChange(void (*h)(uint8_t, uint8_t, uint8_t)) { ccCb = h; }
    void setHandleClock(rt_handler h) { clockCb = h; }
    void setHandleStart(rt_handler h) { startCb = h; }
    void setHandleStop(rt_handler h) { stopCb = h; }
    void setHandleContinue(rt_handler h) { continueCb = h; }
    void setHandleSongPosition(u16_handler h) { songPosCb = h; }
    void setHandleTimeCodeQuarterFrame(u8_handler h) { tcqfCb = h; }

    // Backend thread pushes raw messages here.
    void enqueue(uint8_t s, uint8_t d1, uint8_t d2) {
        std::lock_guard<std::mutex> lk(mtx);
        // Controllers that mirror keys/pads onto several MIDI ports (e.g. the MPK
        // mini IV) would deliver each NOTE twice now that we merge all ports.
        // Drop a note identical to the immediately-preceding message. (CC is never
        // deduped: relative-encoder streams legitimately repeat the same value.)
        uint8_t t = s & 0xF0;
        if ((t == 0x90 || t == 0x80) && s == lastS && d1 == lastD1 && d2 == lastD2) return;
        lastS = s; lastD1 = d1; lastD2 = d2;
        q.push_back({ s, d1, d2 });
    }
    // Pop one raw message (used by the MIDI.h shim, which shares this queue).
    bool poll(uint8_t &s, uint8_t &d1, uint8_t &d2) {
        std::lock_guard<std::mutex> lk(mtx);
        if (q.empty()) return false;
        Msg m = q.front();
        q.erase(q.begin());
        s = m.s; d1 = m.d1; d2 = m.d2;
        return true;
    }

    // Called by the firmware's loop(); drains and dispatches all pending messages.
    bool read() {
        std::vector<Msg> local;
        { std::lock_guard<std::mutex> lk(mtx); local.swap(q); }
        for (const Msg &m : local) dispatch(m.s, m.d1, m.d2);
        return !local.empty();
    }
    int read(int) { return read() ? 1 : 0; }

    template <class... A> void sendNoteOn(A...) {}
    template <class... A> void sendNoteOff(A...) {}
    template <class... A> void sendControlChange(A...) {}
    template <class... A> void sendRealTime(A...) {}
    void send_now() {}

private:
    struct Msg { uint8_t s, d1, d2; };
    std::vector<Msg> q;
    std::mutex mtx;
    uint8_t lastS = 0, lastD1 = 0, lastD2 = 0;   // for multi-port NOTE de-dup

    note_handler noteOnCb = nullptr, noteOffCb = nullptr;
    void (*ccCb)(uint8_t, uint8_t, uint8_t) = nullptr;
    rt_handler clockCb = nullptr, startCb = nullptr, stopCb = nullptr, continueCb = nullptr;
    u16_handler songPosCb = nullptr;
    u8_handler tcqfCb = nullptr;

    void dispatch(uint8_t s, uint8_t d1, uint8_t d2) {
        uint8_t type = s & 0xF0;
        uint8_t ch = (s & 0x0F) + 1;
        // Controller mapping first (knobs/pads -> UI). If it consumes the message
        // we don't also treat it as a played note.
        if (s >= 0xF0 || type == 0x90 || type == 0x80 || type == 0xB0) {
            if (ni404_midi_control(s, d1, d2)) return;
        }
        switch (type) {
            case 0x90:
                if (d2 > 0) { if (noteOnCb) noteOnCb(ch, d1, ni404_note_velocity(d2)); }
                else { if (noteOffCb) noteOffCb(ch, d1, d2); }
                break;
            case 0x80: if (noteOffCb) noteOffCb(ch, d1, d2); break;
            case 0xB0: if (ccCb) ccCb(ch, d1, d2); break;
            case 0xE0: break;  // pitch bend (unused)
            default:
                switch (s) {
                    case Clock: if (clockCb) clockCb(); break;
                    case Start: if (startCb) startCb(); break;
                    case Continue: if (continueCb) continueCb(); break;
                    case Stop: if (stopCb) stopCb(); break;
                    case 0xF2: if (songPosCb) songPosCb((uint16_t)(d1 | (d2 << 7))); break;
                    case 0xF1: if (tcqfCb) tcqfCb(d1); break;
                    default: break;
                }
        }
    }
};

extern usb_midi_class usbMIDI;

// Backend -> queue (defined in src/midi_in.cpp via usbMIDI.enqueue).
void ni404_midi_feed(uint8_t status, uint8_t d1, uint8_t d2);

#endif // NI404_COMPAT_USB_MIDI_H
