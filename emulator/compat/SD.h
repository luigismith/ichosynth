// SD.h — desktop shim for the Teensy SD library, backed by a real folder on disk
// (the repo's sdcard/ by default; see SDClass::resolve_root). Implements the File
// operations the firmwares use: read()/read(buf,n), write(b)/write(buf,n), seek, size,
// available, peek, close; and SD.begin/open/exists/mkdir/remove/rmdir/rename.
//
// Hardware-faithful details:
//  * The virtual card sits in the Teensy 4.1's BUILT-IN slot: SD.begin(BUILTIN_SDCARD)
//    finds it, SD.begin(10) (the Audio board's SPI slot) does not — a build that forgot
//    the INT_SD patch shows "no SD" here as it would on our board.
//  * --no-sd (ni404_sd_set_card_present(false)) simulates an empty slot: begin() fails
//    and every file operation fails.
//  * FILE_WRITE is O_RDWR | O_CREAT | O_AT_END like SdFat: it APPENDS to an existing
//    file (TŒRN removes files before rewriting them); O_TRUNC truncates.
//  * Paths are taken literally from the card root. (The legacy NI404 bench build alone
//    keeps a "samples/" alias for its old card layout: EMU_SD_LEGACY_SAMPLES_ALIAS.)
#ifndef NI404_COMPAT_SD_H
#define NI404_COMPAT_SD_H

#include "Arduino.h"     // String
#include <cstdio>
#include <cstdint>
#include <cstdlib>       // getenv
#include <string>
#include <filesystem>
#include <mutex>

// File open flags (SdFat-style; also accept Arduino FILE_READ/FILE_WRITE).
#define O_READ   0x00
#define O_RDONLY 0x00
#define O_WRITE  0x01
#define O_WRONLY 0x01
#define O_RDWR   0x02
#define O_AT_END 0x04
#define O_APPEND 0x08
#define O_CREAT  0x10
#define O_TRUNC  0x20
#define O_EXCL   0x40
#define O_SYNC   0x80
#define FILE_READ  O_READ
#define FILE_WRITE (O_RDWR | O_CREAT | O_AT_END)
#define FILE_WRITE_BEGIN (O_RDWR | O_CREAT)

#ifndef NI404_SDCARD_PATH
#define NI404_SDCARD_PATH "sdcard"
#endif

class File : public Print {
public:
    File() {}
    File(FILE *f, long sz, const std::string &nm = "", bool writable = false)
        : fp(f), _size(sz), _writable(writable), _name(nm) {}
    // Directory variant.
    File(const std::string &dirPath, const std::string &nm, bool /*dir*/)
        : _isdir(true), _name(nm), _dirpath(dirPath) {
        std::error_code ec;
        diriter = std::filesystem::directory_iterator(dirPath, ec);
    }

    explicit operator bool() const { return fp != nullptr || _isdir; }

    int read() { if (!fp) return -1; int c = std::fgetc(fp); return c == EOF ? -1 : c; }
    int read(void *buf, size_t n) { if (!fp) return -1; return (int)std::fread(buf, 1, n, fp); }
    int peek() { if (!fp) return -1; int c = std::fgetc(fp); if (c != EOF) std::ungetc(c, fp); return c == EOF ? -1 : c; }

    size_t write(uint8_t b) override { if (!fp) return 0; return std::fputc(b, fp) == EOF ? 0 : 1; }
    size_t write(const uint8_t *buf, size_t n) override { if (!fp) return 0; return std::fwrite(buf, 1, n, fp); }
    size_t write(const char *buf, size_t n) { return write((const uint8_t *)buf, n); }
    using Print::write;

    bool seek(long pos) { if (!fp) return false; return std::fseek(fp, pos, SEEK_SET) == 0; }
    long position() { return fp ? std::ftell(fp) : 0; }
    long size() {
        if (!fp || !_writable) return _size;
        long c = std::ftell(fp); std::fseek(fp, 0, SEEK_END); long e = std::ftell(fp); std::fseek(fp, c, SEEK_SET);
        return e;
    }
    int available() { if (!fp) return 0; long c = std::ftell(fp); return (int)(size() - c); }
    void flush() { if (fp) std::fflush(fp); }
    void close() { if (fp) { std::fclose(fp); fp = nullptr; } }

    bool isDirectory() { return _isdir; }
    const char *name() { return _name.c_str(); }
    void rewindDirectory() {
        std::error_code ec;
        diriter = std::filesystem::directory_iterator(_dirpath, ec);
    }
    File openNextFile(int /*mode*/ = O_READ) {
        if (!_isdir) return File();
        std::error_code ec;
        static const std::filesystem::directory_iterator end;
        while (diriter != end) {
            auto entry = *diriter;
            ++diriter;
            std::string full = entry.path().string();
            std::string base = entry.path().filename().string();
            if (entry.is_directory(ec)) return File(full, base, true);
            FILE *f = std::fopen(full.c_str(), "rb");
            if (!f) continue;
            std::fseek(f, 0, SEEK_END); long sz = std::ftell(f); std::fseek(f, 0, SEEK_SET);
            return File(f, sz, base);
        }
        return File();
    }

private:
    FILE *fp = nullptr;
    long _size = 0;
    bool _writable = false;
    bool _isdir = false;
    std::string _name, _dirpath;
    std::filesystem::directory_iterator diriter;
};

// Optional base directory (the executable's folder), set by the frontend from
// argv[0]; lets a distributed binary find an sdcard sitting next to it.
const char *ni404_base_dir();

// Card presence (host_io.cpp): false = --no-sd, an empty slot.
bool ni404_sd_card_present();

class SDClass {
public:
    // The card is in the Teensy 4.1 built-in slot (see the header comment).
    bool begin(int csPin = BUILTIN_SDCARD) {
        mounted = ni404_sd_card_present() && csPin == BUILTIN_SDCARD;
        if (mounted) { std::lock_guard<std::mutex> lk(rootMtx); if (!rootSet) root = resolve_root(); }
        return mounted;
    }
    bool cardPresent() const { return ni404_sd_card_present(); }

    // Emulator-only: inspect / change the folder backing the virtual SD card. An
    // explicitly chosen folder survives later SD.begin() calls (TŒRN calls it again).
    // (The window thread may change it while the firmware thread uses the card.)
    std::string getRoot() const { std::lock_guard<std::mutex> lk(rootMtx); return root; }
    void setRoot(const std::string &r) { std::lock_guard<std::mutex> lk(rootMtx); root = r; rootSet = true; }

    // Find the SD-card folder at RUNTIME so the binary is portable (the baked
    // compile-time path points at the build machine and is only the last resort).
    // Order: $NI404_SDCARD, then sdcard next to the exe / a couple levels up from
    // it, then the same relative to the working directory, then the baked default.
    static std::string resolve_root() {
        namespace fs = std::filesystem;
        std::error_code ec;
        if (const char *e = std::getenv("NI404_SDCARD"))
            if (e[0] && fs::exists(e, ec)) return e;
        const char *rel[] = { "sdcard", "../sdcard", "../../sdcard", "../../../sdcard" };
        std::string b = ni404_base_dir() ? ni404_base_dir() : "";
        if (!b.empty())
            for (const char *r : rel) { fs::path p = fs::path(b) / r; if (fs::exists(p, ec)) return p.string(); }
        for (const char *r : rel) if (fs::exists(r, ec)) return r;
        return NI404_SDCARD_PATH;
    }

    File open(const char *path, int mode = FILE_READ) {
        if (!ready()) return File();
        bool writing = (mode & (O_WRITE | O_RDWR | O_CREAT | O_TRUNC | O_APPEND | O_AT_END)) != 0;
        std::string full = resolve(path, writing);
        std::string base = full.substr(full.find_last_of("/\\") + 1);
        std::error_code ec;
        if (std::filesystem::is_directory(full, ec))
            return writing ? File() : File(full, base, true);
        if (!writing) {
            FILE *f = std::fopen(full.c_str(), "rb");
            if (!f) return File();
            std::fseek(f, 0, SEEK_END); long sz = std::ftell(f); std::fseek(f, 0, SEEK_SET);
            return File(f, sz, base);
        }
        const bool exists = std::filesystem::exists(full, ec);
        if (!exists && !(mode & O_CREAT)) return File();
        if (exists && (mode & O_CREAT) && (mode & O_EXCL)) return File();
        FILE *f = nullptr;
        if (mode & O_APPEND) f = std::fopen(full.c_str(), "ab+");
        else if (!exists || (mode & O_TRUNC)) f = std::fopen(full.c_str(), "wb+");
        else f = std::fopen(full.c_str(), "rb+");
        if (!f) return File();
        if (mode & (O_AT_END | O_APPEND)) std::fseek(f, 0, SEEK_END);
        return File(f, 0, base, true);
    }
    File open(const String &path, int mode = FILE_READ) { return open(path.c_str(), mode); }

    bool exists(const char *path) {
        if (!ready()) return false;
        std::error_code ec;
        return std::filesystem::exists(resolve(path, false), ec);
    }
    bool exists(const String &path) { return exists(path.c_str()); }

    bool mkdir(const char *path) {
        if (!ready()) return false;
        std::error_code ec;
        std::filesystem::create_directories(join(getRoot(), path), ec);
        return !ec;
    }
    bool mkdir(const String &path) { return mkdir(path.c_str()); }

    bool remove(const char *path) {
        if (!ready()) return false;
        std::error_code ec;
        return std::filesystem::remove(resolve(path, false), ec);
    }
    bool remove(const String &path) { return remove(path.c_str()); }

    bool rmdir(const char *path) {
        if (!ready()) return false;
        std::error_code ec;
        return std::filesystem::remove(join(getRoot(), path), ec);
    }
    bool rmdir(const String &path) { return rmdir(path.c_str()); }

    bool rename(const char *from, const char *to) {
        if (!ready()) return false;
        std::error_code ec;
        std::filesystem::rename(resolve(from, false), resolve(to, true), ec);
        return !ec;
    }
    bool rename(const String &from, const String &to) { return rename(from.c_str(), to.c_str()); }

private:
    std::string root = NI404_SDCARD_PATH;
    mutable std::mutex rootMtx;
    bool rootSet = false, mounted = false;

    // Like SdFat, nothing works before a successful begin(), or with no card.
    bool ready() const { return mounted && ni404_sd_card_present(); }

    static std::string join(const std::string &a, const std::string &b) {
        if (a.empty()) return b;
        if (a.back() == '/' || a.back() == '\\') return a + b;
        return a + "/" + b;
    }
    std::string resolve(const char *path, bool forWrite) {
        std::string p = path ? path : "";
        while (!p.empty() && p[0] == '/') p.erase(0, 1);   // "/x" and "x" are the same file
#ifdef EMU_SD_PRIVATE_SUFFIX
        // Legacy bench only: its root-level *.txt saves (autosaved.txt, <n>.txt) use a
        // different struct layout from TŒRN's, so they get their own names on the shared
        // card instead of corrupting each other.
        if (p.find('/') == std::string::npos && p.size() > 4 && p.compare(p.size() - 4, 4, ".txt") == 0)
            p.insert(p.size() - 4, EMU_SD_PRIVATE_SUFFIX);
#endif
        const std::string root = getRoot();
        std::string direct = join(root, p);
#ifdef EMU_SD_LEGACY_SAMPLES_ALIAS
        // Legacy bench only: its firmware addresses "samples/<folder>/_<n>.wav" while
        // older cards hold "<folder>/_<n>.wav" at the root.
        std::error_code ec;
        if (!forWrite && !std::filesystem::exists(direct, ec)) {
            const std::string pre = "samples/";
            if (p.rfind(pre, 0) == 0) {
                std::string alt = join(root, p.substr(pre.size()));
                if (std::filesystem::exists(alt, ec)) return alt;
            }
        }
#else
        (void)forWrite;
#endif
        return direct;
    }
};

extern SDClass SD;

#endif // NI404_COMPAT_SD_H
