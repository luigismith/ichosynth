// host_os.cpp — the few OS calls the emulator core needs, kept in their own
// translation unit because <windows.h> clashes with the Arduino macros
// (INPUT, boolean, ...) that every firmware-facing file includes.
#ifdef _WIN32
#define NOMINMAX
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <mmsystem.h>
#endif

// 1 ms timer/sleep granularity while the emulator runs (Windows defaults to 15.6 ms,
// far too coarse for a sequencer timer).
void ni404_os_fine_timers(bool on) {
#ifdef _WIN32
    if (on) timeBeginPeriod(1); else timeEndPeriod(1);
#else
    (void)on;
#endif
}

// The IntervalTimer thread stands in for an ISR: let it preempt the firmware thread.
void ni404_os_raise_thread_priority() {
#ifdef _WIN32
    SetThreadPriority(GetCurrentThread(), THREAD_PRIORITY_ABOVE_NORMAL);
#endif
}
