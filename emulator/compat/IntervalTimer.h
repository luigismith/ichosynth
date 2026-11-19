// IntervalTimer.h — desktop shim for Teensy's IntervalTimer.
//
// On the device the callback runs from a hardware timer ISR, independently of loop().
// Here every timer registers itself with the emulator's timer thread (host_io.cpp),
// which wakes on each deadline and runs due callbacks under the interrupt lock
// (emu_irq.h) — so the sequencer keeps time even while loop() is busy, the window is
// redrawing or the PC is slow, instead of only advancing once per video frame.
//
// Semantics follow the Teensy core:
//   begin(fn, us)  (re)starts the timer: first call one period after begin().
//   update(us)     changes the period from the NEXT interval on (the current one
//                  completes at the old period).
//   end()          stops it.
// If the host falls far behind (thread starved for many periods), at most a few
// overdue calls are made and the schedule is then re-anchored to "now", instead of
// firing a burst every wake-up for ever after.
#ifndef NI404_COMPAT_INTERVALTIMER_H
#define NI404_COMPAT_INTERVALTIMER_H

#include "Arduino.h"   // micros()
#include "emu_irq.h"

class IntervalTimer;
void ni404_register_timer(IntervalTimer *t);
void ni404_timers_wake();   // a timer changed: re-evaluate the next deadline now

class IntervalTimer {
public:
    IntervalTimer() {}

    // Templated time arg so any numeric type (unsigned int/long/double) the
    // firmware passes resolves unambiguously.
    template <class T> bool begin(void (*func)(), T microseconds) {
        {
            std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
            fn = func;
            interval = pending = (unsigned long)microseconds;
            last = micros();
            running = (interval > 0 && fn);
            if (!registered) { ni404_register_timer(this); registered = true; }
        }
        ni404_timers_wake();
        return true;
    }
    template <class T> void update(T microseconds) {
        std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
        pending = (unsigned long)microseconds;   // takes effect after the current period
    }

    void end() {
        std::lock_guard<std::recursive_mutex> lk(ni404_irq_lock());
        running = false;
    }
    void priority(uint8_t) {}

    // ---- timer thread side (called with the interrupt lock held) ----
    // Run every call that is due at `now`; returns micros until the next one is due
    // (or a large value if stopped).
    long service(unsigned long now) {
        if (!running || !fn || interval == 0) return 1L << 30;
        int calls = 0;
        while ((long)(now - last) >= (long)interval) {
            if (++calls > MAX_CATCHUP) { last = now; break; }   // re-anchor after a stall
            last += interval;
            interval = pending ? pending : interval;
            fn();
            if (!running) return 1L << 30;                       // fn() may end() us
        }
        return (long)(last + interval - now);
    }

private:
    static const int MAX_CATCHUP = 4;
    void (*fn)() = nullptr;
    unsigned long interval = 0, pending = 0, last = 0;
    bool running = false, registered = false;
};

#endif // NI404_COMPAT_INTERVALTIMER_H
