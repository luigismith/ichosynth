// elapsedMillis.h — desktop shim for Teensy's elapsedMillis / elapsedMicros.
// These behave like an unsigned long that auto-counts up over time and can be
// reset by assignment (e.g. `t = 0;`). Time source is provided by Arduino.h.
#ifndef NI404_COMPAT_ELAPSEDMILLIS_H
#define NI404_COMPAT_ELAPSEDMILLIS_H

unsigned long millis();
unsigned long micros();

class elapsedMillis {
private:
    unsigned long ms;
public:
    elapsedMillis() { ms = millis(); }
    elapsedMillis(unsigned long val) { ms = millis() - val; }
    elapsedMillis(const elapsedMillis &o) { ms = o.ms; }
    operator unsigned long() const { return millis() - ms; }
    elapsedMillis &operator=(const elapsedMillis &o) { ms = o.ms; return *this; }
    elapsedMillis &operator=(unsigned long val) { ms = millis() - val; return *this; }
    elapsedMillis &operator-=(unsigned long val) { ms += val; return *this; }
    elapsedMillis &operator+=(unsigned long val) { ms -= val; return *this; }
};

class elapsedMicros {
private:
    unsigned long us;
public:
    elapsedMicros() { us = micros(); }
    elapsedMicros(unsigned long val) { us = micros() - val; }
    elapsedMicros(const elapsedMicros &o) { us = o.us; }
    operator unsigned long() const { return micros() - us; }
    elapsedMicros &operator=(const elapsedMicros &o) { us = o.us; return *this; }
    elapsedMicros &operator=(unsigned long val) { us = micros() - val; return *this; }
    elapsedMicros &operator-=(unsigned long val) { us += val; return *this; }
    elapsedMicros &operator+=(unsigned long val) { us -= val; return *this; }
};

#endif // NI404_COMPAT_ELAPSEDMILLIS_H
