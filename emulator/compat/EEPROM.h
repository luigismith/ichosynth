// EEPROM.h — desktop shim for the Teensy EEPROM API. Backs a byte array that is
// lazily loaded from / saved to "<target>-eeprom.bin" next to the executable
// (ni404_runtime_path), so settings and the sample-pack id persist across runs like on
// the device, and ni404emu / toernemu never read each other's layout. A missing file
// is a factory-fresh Teensy: the emulated EEPROM (flash) reads 0xFF everywhere, which
// is what the firmware's first-boot defaults have to cope with on real hardware.
// (The legacy NI404 bench build sets EMU_EEPROM_ERASED=0x00: that firmware reads its
// sample-pack id from EEPROM and loads nothing from an erased one.)
#ifndef EMU_EEPROM_ERASED
#define EMU_EEPROM_ERASED 0xFF
#endif
#ifndef NI404_COMPAT_EEPROM_H
#define NI404_COMPAT_EEPROM_H

#include <cstdint>
#include <cstdio>
#include <cstring>

const char *ni404_runtime_path(const char *name);   // host_io.cpp

class EEPROMClass {
public:
    static const int SIZE = 4284;  // Teensy 4.1 emulated EEPROM size

    uint8_t read(int addr) { ensure(); return (addr >= 0 && addr < SIZE) ? data[addr] : 0; }
    void write(int addr, uint8_t v) { ensure(); if (addr >= 0 && addr < SIZE) { data[addr] = v; save(addr, 1); } }
    void update(int addr, uint8_t v) { ensure(); if (addr >= 0 && addr < SIZE && data[addr] != v) { data[addr] = v; save(addr, 1); } }
    int length() { return SIZE; }

    template <class T> T &get(int addr, T &t) {
        ensure();
        if (addr >= 0 && addr + (int)sizeof(T) <= SIZE) std::memcpy(&t, data + addr, sizeof(T));
        return t;
    }
    template <class T> const T &put(int addr, const T &t) {
        ensure();
        if (addr >= 0 && addr + (int)sizeof(T) <= SIZE) { std::memcpy(data + addr, &t, sizeof(T)); save(addr, (int)sizeof(T)); }
        return t;
    }

private:
    uint8_t data[SIZE];
    bool loaded = false;
    const char *path() { return ni404_runtime_path("eeprom.bin"); }
    void ensure() {
        if (loaded) return;
        loaded = true;
        std::memset(data, EMU_EEPROM_ERASED, SIZE);   // erased flash
        if (FILE *f = std::fopen(path(), "rb")) { size_t n = std::fread(data, 1, SIZE, f); (void)n; std::fclose(f); }
    }
    // Write-through, but only the bytes that changed: the image file is created whole
    // once, then each write patches its range in place (TŒRN's first boot and CLR RAM
    // write all 4284 bytes one by one; rewriting the whole file each time took seconds).
    FILE *fp = nullptr;
    void save(int addr, int n) {
        if (!fp) {
            fp = std::fopen(path(), "r+b");
            if (fp) { std::fseek(fp, 0, SEEK_END); if (std::ftell(fp) != SIZE) { std::fclose(fp); fp = nullptr; } }
            if (!fp && (fp = std::fopen(path(), "w+b"))) { std::fwrite(data, 1, SIZE, fp); std::fflush(fp); return; }
            if (!fp) return;
        }
        std::fseek(fp, addr, SEEK_SET);
        std::fwrite(data + addr, 1, (size_t)n, fp);
        std::fflush(fp);
    }
};

extern EEPROMClass EEPROM;

#endif // NI404_COMPAT_EEPROM_H
