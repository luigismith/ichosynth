// IntervalTimer.h — desktop shim for Teensy's IntervalTimer. On the device the
// callback runs from a hardware timer ISR; here every timer registers itself and
// is "pumped" from the main loop (ni404_pump_timers(), called each ni404_loop()).
// Supports begin(fn, micros), end(), and update(micros) — all used by the
// firmware's sequencer (playTimer) and MIDI clock (midiClockTimer).
#ifndef NI404_COMPAT_INTERVALTIMER_H
#define NI404_COMPAT_INTERVALTIMER_H

#include "Arduino.h"   // micros()

class IntervalTimer;
void ni404_register_timer(IntervalTimer *t);

class IntervalTimer {
public:
    IntervalTimer() {}

    // Templated time arg so any numeric type (unsigned int/long/double) the
    // firmware passes resolves unambiguously.
    template <class T> bool begin(void (*func)(), T microseconds) {
        fn = func; interval = (unsigned long)microseconds; last = micros();
        running = (interval > 0);
        if (!registered) { ni404_register_timer(this); registered = true; }
        return true;
    }
    template <class T> void update(T microseconds) {
        interval = (unsigned long)microseconds; running = (interval > 0);
    }

    void end() { running = false; }
    void priority(uint8_t) {}

    // Called by ni404_pump_timers().
    void pump() {
        if (!running || !fn || interval == 0) return;
        unsigned long now = micros();
        int guard = 0;
        while ((long)(now - last) >= (long)interval && guard++ < 8) {
            last += interval;
            fn();
        }
    }

private:
    void (*fn)() = nullptr;
    unsigned long interval = 0, last = 0;
    bool running = false, registered = false;
};

// Pump every registered timer (defined in host_io.cpp).
void ni404_pump_timers();

#endif // NI404_COMPAT_INTERVALTIMER_H
