// Arduino.h — desktop compatibility shim for the Teensy/Arduino core API used
// by the NI404 firmware. Goal: let the unmodified firmware compile and run on
// Windows/macOS. Only what the firmware actually uses is implemented; it is
// kept deliberately small and dependency-free.
#ifndef NI404_COMPAT_ARDUINO_H
#define NI404_COMPAT_ARDUINO_H

#include <cstdint>
#include <cstring>
#include <cstdio>
#include <cstdlib>
#include <cmath>
#include <math.h>
#include <string>
#include <algorithm>
#include <type_traits>

// Make the firmware's sprintf() calls memory-safe. The sketch has spots where a
// value can exceed the destination buffer (e.g. showNumber's `char buf[4]` with
// an out-of-range count from an off-by-one read) — harmless on the Teensy but a
// fatal stack smash on desktop. Every sprintf target in the firmware is a local
// char array, so sizeof() yields the real capacity and snprintf truncates safely
// without changing correct behavior.
#define sprintf(buf, ...) snprintf((buf), sizeof(buf), __VA_ARGS__)

// ---- Teensy memory qualifiers: no-ops on desktop -------------------------
#define EXTMEM
#define DMAMEM
#define PROGMEM
#define FASTRUN
#define FLASHMEM
#define PSTR(s) (s)
#define F(s) (s)
typedef const char *__FlashStringHelper_ptr;

// ---- Basic Arduino constants / GPIO (stubbed — no real pins) --------------
#define HIGH 0x1
#define LOW  0x0
#define INPUT          0x0
#define OUTPUT         0x1
#define INPUT_PULLUP   0x2
#define INPUT_PULLDOWN 0x3
#define LSBFIRST 0
#define MSBFIRST 1
#define CHANGE  4
#define FALLING 2
#define RISING  3
#define BUILTIN_SDCARD 254

// Analog pin aliases (Teensy 4.1). Values are nominal; analogRead is stubbed.
enum {
    A0 = 14, A1, A2, A3, A4, A5, A6, A7, A8, A9, A10, A11,
    A12, A13, A14, A15, A16, A17, A18, A19, A20, A21, A22, A23
};

typedef uint8_t byte;
typedef bool boolean;

inline void pinMode(uint8_t, uint8_t) {}
inline void digitalWrite(uint8_t, uint8_t) {}
inline int  digitalRead(uint8_t) { return LOW; }
inline int  analogRead(uint8_t) { return 0; }
inline void analogWrite(uint8_t, int) {}
inline void analogReadResolution(unsigned) {}
inline void attachInterrupt(uint8_t, void (*)(), int) {}
inline void detachInterrupt(uint8_t) {}
inline uint8_t digitalPinToInterrupt(uint8_t p) { return p; }
inline void interrupts() {}
inline void noInterrupts() {}
inline void __disable_irq() {}
inline void __enable_irq() {}

// Teensy NVIC / interrupt-priority helpers — no-ops on desktop.
#define IRQ_SOFTWARE 0
#define IRQ_LPUART8  1
#define IRQ_USB1     2
#define NVIC_SET_PRIORITY(irq, prio) ((void)0)
#define NVIC_GET_PRIORITY(irq) (0)
#define NVIC_ENABLE_IRQ(irq) ((void)0)
#define NVIC_DISABLE_IRQ(irq) ((void)0)
inline void attachInterruptVector(int, void (*)()) {}

// dtostrf: float -> string (AVR libc helper).
inline char *dtostrf(double val, int width, unsigned int prec, char *out) {
    char fmt[16], tmp[64];
    std::snprintf(fmt, sizeof(fmt), "%%%d.%uf", width, prec);
    std::snprintf(tmp, sizeof(tmp), fmt, val);
    std::strcpy(out, tmp);
    return out;
}

// ---- Time -----------------------------------------------------------------
// Defined in host_io.cpp so the whole program shares one monotonic clock.
unsigned long millis();
unsigned long micros();
void delay(unsigned long ms);
void delayMicroseconds(unsigned long us);
inline void yield() {}

// ---- Math helpers ---------------------------------------------------------
// NOTE: Arduino normally defines min/max/abs/round as function-like MACROS.
// Those collide violently with the C++ standard library (<chrono>, <limits>,
// numeric_limits<>::min(), std::chrono::round, etc). Since this shim leans on
// the STL, we provide them as real functions instead — and leave abs()/round()
// to <cmath>/<math.h>, which already overload them for every arithmetic type.
#ifdef min
#undef min
#endif
#ifdef max
#undef max
#endif
#ifdef constrain
#undef constrain
#endif

template <class T> inline T arduino_min(T a, T b) { return a < b ? a : b; }
template <class T> inline T arduino_max(T a, T b) { return a > b ? a : b; }
template <class A, class B>
inline typename std::common_type<A, B>::type min(A a, B b) { return a < b ? a : b; }
template <class A, class B>
inline typename std::common_type<A, B>::type max(A a, B b) { return a > b ? a : b; }
#define constrain(amt, low, high) ((amt) < (low) ? (low) : ((amt) > (high) ? (high) : (amt)))
#define sq(x) ((x) * (x))
#define radians(deg) ((deg) * 0.0174532925)
#define degrees(rad) ((rad) * 57.2957786)
#define bitRead(value, bit) (((value) >> (bit)) & 0x01)
#define bitSet(value, bit) ((value) |= (1UL << (bit)))
#define bitClear(value, bit) ((value) &= ~(1UL << (bit)))
#define lowByte(w) ((uint8_t)((w) & 0xff))
#define highByte(w) ((uint8_t)((w) >> 8))

inline long map(long x, long in_min, long in_max, long out_min, long out_max) {
    if (in_max == in_min) return out_min;
    return (x - in_min) * (out_max - out_min) / (in_max - in_min) + out_min;
}

inline long random(long howbig) { return howbig > 0 ? (long)(::rand() % howbig) : 0; }
inline long random(long howsmall, long howbig) {
    return howsmall >= howbig ? howsmall : howsmall + random(howbig - howsmall);
}
inline void randomSeed(unsigned long seed) { ::srand((unsigned)seed); }

// ---- Arduino String (wraps std::string) -----------------------------------
class String {
public:
    std::string s;

    String() {}
    String(const char *c) : s(c ? c : "") {}
    String(const std::string &str) : s(str) {}
    String(char c) { s = std::string(1, c); }
    String(const String &o) : s(o.s) {}
    String(int v, int base = 10) { setNum((long)v, base); }
    String(unsigned int v, int base = 10) { setNum((unsigned long)v, base); }
    String(long v, int base = 10) { setNum(v, base); }
    String(unsigned long v, int base = 10) { setNum(v, base); }
    String(float v, int decimals = 2) { setFloat(v, decimals); }
    String(double v, int decimals = 2) { setFloat(v, decimals); }

    void setNum(long v, int base) {
        char buf[34];
        if (base == 10) std::snprintf(buf, sizeof(buf), "%ld", v);
        else if (base == 16) std::snprintf(buf, sizeof(buf), "%lx", v);
        else if (base == 2) { // binary
            std::string b; unsigned long u = (unsigned long)v;
            if (u == 0) b = "0";
            while (u) { b = char('0' + (u & 1)) + b; u >>= 1; }
            s = b; return;
        } else std::snprintf(buf, sizeof(buf), "%ld", v);
        s = buf;
    }
    void setNum(unsigned long v, int base) {
        char buf[34];
        if (base == 16) std::snprintf(buf, sizeof(buf), "%lx", v);
        else std::snprintf(buf, sizeof(buf), "%lu", v);
        s = buf;
    }
    void setFloat(double v, int decimals) {
        char buf[48];
        std::snprintf(buf, sizeof(buf), "%.*f", decimals, v);
        s = buf;
    }

    const char *c_str() const { return s.c_str(); }
    unsigned int length() const { return (unsigned int)s.size(); }
    char charAt(unsigned int i) const { return i < s.size() ? s[i] : 0; }
    char operator[](unsigned int i) const { return charAt(i); }
    char &operator[](unsigned int i) { return s[i]; }

    String &operator=(const String &o) { s = o.s; return *this; }
    String &operator=(const char *c) { s = c ? c : ""; return *this; }

    String &operator+=(const String &o) { s += o.s; return *this; }
    String &operator+=(const char *c) { if (c) s += c; return *this; }
    String &operator+=(char c) { s += c; return *this; }
    String &operator+=(int v) { s += String(v).s; return *this; }
    String &operator+=(unsigned int v) { s += String(v).s; return *this; }
    String &operator+=(long v) { s += String(v).s; return *this; }
    String &operator+=(unsigned long v) { s += String(v).s; return *this; }

    bool concat(const String &o) { s += o.s; return true; }
    bool concat(char c) { s += c; return true; }
    bool concat(int v) { s += String(v).s; return true; }

    bool equals(const String &o) const { return s == o.s; }
    bool equals(const char *c) const { return s == (c ? c : ""); }
    bool operator==(const String &o) const { return s == o.s; }
    bool operator==(const char *c) const { return s == (c ? c : ""); }
    bool operator!=(const String &o) const { return s != o.s; }
    bool operator!=(const char *c) const { return s != (c ? c : ""); }
    bool operator<(const String &o) const { return s < o.s; }
    bool operator>(const String &o) const { return s > o.s; }
    bool operator<=(const String &o) const { return s <= o.s; }
    bool operator>=(const String &o) const { return s >= o.s; }

    int indexOf(char c) const { auto p = s.find(c); return p == std::string::npos ? -1 : (int)p; }
    int indexOf(char c, unsigned int from) const { auto p = s.find(c, from); return p == std::string::npos ? -1 : (int)p; }
    int indexOf(const String &v) const { auto p = s.find(v.s); return p == std::string::npos ? -1 : (int)p; }
    int lastIndexOf(char c) const { auto p = s.rfind(c); return p == std::string::npos ? -1 : (int)p; }

    String substring(unsigned int from) const { return from <= s.size() ? String(s.substr(from)) : String(); }
    String substring(unsigned int from, unsigned int to) const {
        if (from > s.size()) return String();
        if (to > s.size()) to = (unsigned int)s.size();
        if (to < from) return String();
        return String(s.substr(from, to - from));
    }

    bool startsWith(const String &p) const { return s.rfind(p.s, 0) == 0; }
    bool endsWith(const String &p) const {
        return p.s.size() <= s.size() && s.compare(s.size() - p.s.size(), p.s.size(), p.s) == 0;
    }

    void remove(unsigned int index) { if (index < s.size()) s.erase(index); }
    void remove(unsigned int index, unsigned int count) { if (index < s.size()) s.erase(index, count); }
    void trim() {
        size_t b = s.find_first_not_of(" \t\r\n");
        size_t e = s.find_last_not_of(" \t\r\n");
        if (b == std::string::npos) s.clear();
        else s = s.substr(b, e - b + 1);
    }
    void toUpperCase() { for (auto &c : s) c = (char)toupper((unsigned char)c); }
    void toLowerCase() { for (auto &c : s) c = (char)tolower((unsigned char)c); }
    void toCharArray(char *buf, unsigned int bufsize) const {
        unsigned int n = arduino_min((unsigned int)s.size(), bufsize ? bufsize - 1 : 0);
        std::memcpy(buf, s.data(), n); buf[n] = 0;
    }

    long toInt() const { return std::strtol(s.c_str(), nullptr, 10); }
    float toFloat() const { return std::strtof(s.c_str(), nullptr); }
    double toDouble() const { return std::strtod(s.c_str(), nullptr); }
};

inline String operator+(const String &a, const String &b) { String r(a); r += b; return r; }
inline String operator+(const String &a, const char *b) { String r(a); r += b; return r; }
inline String operator+(const char *a, const String &b) { String r(a); r += b; return r; }
inline String operator+(const String &a, char b) { String r(a); r += b; return r; }
inline String operator+(const String &a, int b) { String r(a); r += String(b); return r; }
inline String operator+(const String &a, unsigned int b) { String r(a); r += String(b); return r; }
inline String operator+(const String &a, long b) { String r(a); r += String(b); return r; }
inline String operator+(const String &a, unsigned long b) { String r(a); r += String(b); return r; }

// ---- Print / Serial -------------------------------------------------------
#define DEC 10
#define HEX 16
#define OCT 8
#define BIN 2

// CrashReport: on desktop there is never a stored crash. `if (CrashReport)` ->
// false, so printing it never executes — but it must still compile.
struct CrashReportClass {
    explicit operator bool() const { return false; }
};
extern CrashReportClass CrashReport;

// Print routes everything through the virtual write(), so subclasses that
// override write() (HardwareSerial -> stdout, Adafruit_GFX -> framebuffer,
// File -> disk) all work correctly.
class Print {
public:
    virtual size_t write(uint8_t) { return 1; }
    virtual size_t write(const uint8_t *buf, size_t n) { size_t c = 0; for (size_t i = 0; i < n; i++) c += write(buf[i]); return c; }
    size_t write(const char *s) { return s ? write((const uint8_t *)s, std::strlen(s)) : 0; }

    size_t print(const char *s) { return s ? write((const uint8_t *)s, std::strlen(s)) : 0; }
    size_t print(const String &s) { return write((const uint8_t *)s.c_str(), s.length()); }
    size_t print(char c) { return write((uint8_t)c); }
    size_t print(int v, int base = DEC) { return printNum((long)v, base); }
    size_t print(unsigned int v, int base = DEC) { return printNum((unsigned long)v, base); }
    size_t print(long v, int base = DEC) { return printNum(v, base); }
    size_t print(unsigned long v, int base = DEC) { return printNum(v, base); }
    size_t print(double v, int dig = 2) { char b[48]; int n = std::snprintf(b, sizeof b, "%.*f", dig, v); return write((const uint8_t *)b, n < 0 ? 0 : n); }
    size_t print(const CrashReportClass &) { return 0; }

    size_t println() { return write((uint8_t)'\n'); }
    size_t println(const char *s) { return print(s) + println(); }
    size_t println(const String &s) { return print(s) + println(); }
    size_t println(char c) { return print(c) + println(); }
    size_t println(int v, int base = DEC) { return print(v, base) + println(); }
    size_t println(unsigned int v, int base = DEC) { return print(v, base) + println(); }
    size_t println(long v, int base = DEC) { return print(v, base) + println(); }
    size_t println(unsigned long v, int base = DEC) { return print(v, base) + println(); }
    size_t println(double v, int dig = 2) { return print(v, dig) + println(); }

    template <class... A> size_t printf(const char *fmt, A... a) {
        char b[256]; int n = std::snprintf(b, sizeof b, fmt, a...);
        if (n < 0) return 0; if (n > (int)sizeof b - 1) n = sizeof b - 1;
        return write((const uint8_t *)b, n);
    }

private:
    size_t printNum(long v, int base) {
        char b[34];
        if (base == 16) std::snprintf(b, sizeof b, "%lx", v);
        else if (base == 8) std::snprintf(b, sizeof b, "%lo", v);
        else if (base == 2) {
            std::string s; unsigned long u = (unsigned long)v; if (!u) s = "0";
            while (u) { s = char('0' + (u & 1)) + s; u >>= 1; }
            return write((const uint8_t *)s.c_str(), s.size());
        } else std::snprintf(b, sizeof b, "%ld", v);
        return write((const uint8_t *)b, std::strlen(b));
    }
    size_t printNum(unsigned long v, int base) {
        char b[34];
        if (base == 16) std::snprintf(b, sizeof b, "%lx", v);
        else if (base == 8) std::snprintf(b, sizeof b, "%lo", v);
        else if (base == 2) {
            std::string s; if (!v) s = "0";
            while (v) { s = char('0' + (v & 1)) + s; v >>= 1; }
            return write((const uint8_t *)s.c_str(), s.size());
        } else std::snprintf(b, sizeof b, "%lu", v);
        return write((const uint8_t *)b, std::strlen(b));
    }
};

class HardwareSerial : public Print {
public:
    void begin(unsigned long) {}
    void end() {}
    operator bool() const { return true; }
    int available() { return 0; }
    int availableForWrite() { return 64; }
    int read() { return -1; }
    int peek() { return -1; }
    size_t readBytes(char *, size_t) { return 0; }
    size_t readBytes(uint8_t *, size_t) { return 0; }
    void flush() { std::fflush(stdout); }
    void clear() {}
    void addMemoryForRead(void *, size_t) {}
    void addMemoryForWrite(void *, size_t) {}
    // Route serial output to stdout.
    size_t write(uint8_t b) override { std::fputc(b, stdout); return 1; }
    size_t write(const uint8_t *buf, size_t n) override { return std::fwrite(buf, 1, n, stdout); }
    using Print::write;
};

extern HardwareSerial Serial;
// Teensy has Serial1..Serial8 (hardware UARTs). TŒRN uses Serial8 for TRS MIDI.
extern HardwareSerial Serial1, Serial2, Serial3, Serial4, Serial5, Serial6, Serial7, Serial8;

// Teensy core globals the firmware uses WITHOUT an explicit include (the Teensy
// core provides them implicitly): elapsedMillis, IntervalTimer and usbMIDI.
#include "elapsedMillis.h"
#include "IntervalTimer.h"
#include "usb_midi.h"

#endif // NI404_COMPAT_ARDUINO_H
