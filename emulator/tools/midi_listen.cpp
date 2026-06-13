// midi_listen.cpp — winmm MIDI logger. Opens ALL input ports, prints status and
// every CC/NOTE to stdout (tagged with port), line-buffered.
#include <windows.h>
#include <mmsystem.h>
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
void CALLBACK proc(HMIDIIN, UINT msg, DWORD_PTR inst, DWORD_PTR p1, DWORD_PTR) {
    if (msg != MIM_DATA) return;
    DWORD d = (DWORD)p1; uint8_t s = d & 0xFF, a = (d >> 8) & 0xFF, b = (d >> 16) & 0xFF;
    uint8_t t = s & 0xF0; int port = (int)inst;
    if (t == 0xB0) { printf("[%d] CC %d %d\n", port, a, b); fflush(stdout); }
    else if (t == 0x90 && b > 0) { printf("[%d] NOTE %d %d\n", port, a, b); fflush(stdout); }
}
int main(int argc, char** argv) {
    if (argc > 1 && !strcmp(argv[1], "--list")) {
        UINT n = midiInGetNumDevs();
        for (UINT i = 0; i < n; i++) { MIDIINCAPSA c; if (midiInGetDevCapsA(i, &c, sizeof c) == MMSYSERR_NOERROR) printf("[%u] %s\n", i, c.szPname); }
        return 0;
    }
    UINT n = midiInGetNumDevs();
    int opened = 0;
    for (UINT i = 0; i < n; i++) {
        HMIDIIN h;
        MMRESULT res = midiInOpen(&h, i, (DWORD_PTR)proc, (DWORD_PTR)i, CALLBACK_FUNCTION);
        if (res == MMSYSERR_NOERROR) { midiInStart(h); opened++; printf("opened port %u\n", i); }
        else printf("port %u busy (err %u)\n", i, res);
        fflush(stdout);
    }
    printf("READY: %d/%u ports open\n", opened, n); fflush(stdout);
    for (;;) Sleep(200);
}
