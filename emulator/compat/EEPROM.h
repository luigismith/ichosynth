// EEPROM.h — desktop shim for the Teensy EEPROM API. Backs a byte array that is
// lazily loaded from / saved to "eeprom.bin" in the working directory, so song
// state and the sample-pack id persist across runs like on the device.
#ifndef NI404_COMPAT_EEPROM_H
#define NI404_COMPAT_EEPROM_H

#include <cstdint>
#include <cstdio>
#include <cstring>

class EEPROMClass {
public:
    static const int SIZE = 4284;  // Teensy 4.1 emulated EEPROM size

    uint8_t read(int addr) { ensure(); return (addr >= 0 && addr < SIZE) ? data[addr] : 0; }
    void write(int addr, uint8_t v) { ensure(); if (addr >= 0 && addr < SIZE) { data[addr] = v; save(); } }
    void update(int addr, uint8_t v) { ensure(); if (addr >= 0 && addr < SIZE && data[addr] != v) { data[addr] = v; save(); } }
    int length() { return SIZE; }

    template <class T> T &get(int addr, T &t) {
        ensure();
        if (addr >= 0 && addr + (int)sizeof(T) <= SIZE) std::memcpy(&t, data + addr, sizeof(T));
        return t;
    }
    template <class T> const T &put(int addr, const T &t) {
        ensure();
        if (addr >= 0 && addr + (int)sizeof(T) <= SIZE) { std::memcpy(data + addr, &t, sizeof(T)); save(); }
        return t;
    }

private:
    uint8_t data[SIZE] = {};
    bool loaded = false;
    const char *path() { return "eeprom.bin"; }
    void ensure() {
        if (loaded) return;
        loaded = true;
        if (FILE *f = std::fopen(path(), "rb")) { std::fread(data, 1, SIZE, f); std::fclose(f); }
    }
    void save() {
        if (FILE *f = std::fopen(path(), "wb")) { std::fwrite(data, 1, SIZE, f); std::fclose(f); }
    }
};

extern EEPROMClass EEPROM;

#endif // NI404_COMPAT_EEPROM_H
