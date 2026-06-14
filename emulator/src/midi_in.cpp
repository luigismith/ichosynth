// midi_in.cpp — real MIDI input backend. Opens a hardware MIDI input port and
// feeds incoming messages into the usbMIDI queue (ni404_midi_feed), where the
// firmware's loop() drains them via usbMIDI.read(). Windows uses winmm (no extra
// deps); macOS uses CoreMIDI. ni404_midi_feed is always defined so the rest of
// the program links even without a backend.
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN

#include "usb_midi.h"
#include <cstdio>
#include <string>
#include <vector>

void ni404_midi_close();   // fwd decl (ni404_midi_open calls it)

void ni404_midi_feed(uint8_t status, uint8_t d1, uint8_t d2) {
    usbMIDI.enqueue(status, d1, d2);
}

// ===========================================================================
#if defined(_WIN32)
#include <windows.h>
#include <mmsystem.h>

static std::vector<HMIDIIN> g_handles;

static void CALLBACK midiInProc(HMIDIIN, UINT msg, DWORD_PTR, DWORD_PTR p1, DWORD_PTR) {
    if (msg != MIM_DATA) return;
    DWORD packed = (DWORD)p1;
    uint8_t status = packed & 0xFF, d1 = (packed >> 8) & 0xFF, d2 = (packed >> 16) & 0xFF;
    ni404_midi_feed(status, d1, d2);
}

int ni404_midi_list(std::vector<std::string> *names) {
    UINT n = midiInGetNumDevs();
    for (UINT i = 0; i < n; i++) {
        MIDIINCAPSA caps;
        if (midiInGetDevCapsA(i, &caps, sizeof(caps)) == MMSYSERR_NOERROR) {
            if (names) names->push_back(caps.szPname);
        }
    }
    return (int)n;
}

// Open EVERY MIDI input port and merge them. Controllers like the MPK mini IV
// expose several ports (keys/pads on one, knobs on another — MIDIIN2), so
// opening just one would miss the knobs. `index` is ignored (kept for the API).
bool ni404_midi_open(int /*index*/) {
    ni404_midi_close();
    UINT n = midiInGetNumDevs();
    for (UINT i = 0; i < n; i++) {
        HMIDIIN h;
        if (midiInOpen(&h, i, (DWORD_PTR)midiInProc, 0, CALLBACK_FUNCTION) == MMSYSERR_NOERROR) {
            midiInStart(h);
            g_handles.push_back(h);
        }
    }
    return !g_handles.empty();
}

void ni404_midi_close() {
    for (HMIDIIN h : g_handles) { midiInStop(h); midiInClose(h); }
    g_handles.clear();
}

// ===========================================================================
// CoreMIDI only under Clang: Apple's CoreMIDI/CoreFoundation headers declare
// block (^) APIs that Homebrew GCC cannot parse, and the firmware needs GCC's
// -fpermissive. So a GCC macOS build falls through to the no-MIDI stub below
// (keyboard + audio + drag-drop samples still work); a Clang build keeps CoreMIDI.
#elif defined(__APPLE__) && defined(__clang__)
#include <CoreMIDI/CoreMIDI.h>

static MIDIClientRef g_client = 0;
static MIDIPortRef g_port = 0;

static int midiMsgLen(uint8_t status) {
    if (status >= 0xF8) return 1;                 // realtime
    switch (status & 0xF0) {
        case 0x80: case 0x90: case 0xA0: case 0xB0: case 0xE0: return 3;
        case 0xC0: case 0xD0: return 2;           // program change, channel pressure
        case 0xF0:
            if (status == 0xF1 || status == 0xF3) return 2;   // MTC / song select
            if (status == 0xF2) return 3;                     // song position
            return 1;                                         // F6/F7/...
    }
    return 1;
}

static void midiReadProc(const MIDIPacketList *pktlist, void *, void *) {
    const MIDIPacket *p = &pktlist->packet[0];
    for (unsigned i = 0; i < pktlist->numPackets; i++) {
        UInt16 j = 0;
        while (j < p->length) {
            uint8_t status = p->data[j];
            if (status < 0x80) { j++; continue; }             // stray/running-status data byte
            if (status == 0xF0) {                             // SysEx: skip to 0xF7
                j++; while (j < p->length && p->data[j] != 0xF7) j++;
                if (j < p->length) j++;
                continue;
            }
            int len = midiMsgLen(status);
            uint8_t d1 = (j + 1 < p->length) ? p->data[j + 1] : 0;
            uint8_t d2 = (j + 2 < p->length) ? p->data[j + 2] : 0;
            ni404_midi_feed(status, d1, d2);
            j += len;
        }
        p = MIDIPacketNext(p);
    }
}

int ni404_midi_list(std::vector<std::string> *names) {
    ItemCount n = MIDIGetNumberOfSources();
    for (ItemCount i = 0; i < n; i++) {
        MIDIEndpointRef src = MIDIGetSource(i);
        CFStringRef name = nullptr;
        MIDIObjectGetStringProperty(src, kMIDIPropertyDisplayName, &name);
        char buf[128] = "MIDI";
        if (name) { CFStringGetCString(name, buf, sizeof(buf), kCFStringEncodingUTF8); CFRelease(name); }
        if (names) names->push_back(buf);
    }
    return (int)n;
}

// Connect EVERY MIDI source and merge them (like the Windows backend). The MPK
// mini IV splits keys/pads and knobs across two ports, so opening just one would
// miss the knobs. `index` is ignored (kept for the API).
bool ni404_midi_open(int /*index*/) {
    ItemCount n = MIDIGetNumberOfSources();
    if (n == 0) return false;
    if (!g_client) MIDIClientCreate(CFSTR("NI404"), nullptr, nullptr, &g_client);
    if (!g_port) MIDIInputPortCreate(g_client, CFSTR("NI404 In"), midiReadProc, nullptr, &g_port);
    for (ItemCount i = 0; i < n; i++) MIDIPortConnectSource(g_port, MIDIGetSource(i), nullptr);
    return true;
}

void ni404_midi_close() {}

// ===========================================================================
#else
int  ni404_midi_list(std::vector<std::string> *) { return 0; }
bool ni404_midi_open(int) { return false; }
void ni404_midi_close() {}
#endif
