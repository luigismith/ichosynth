// SD.h — desktop shim for the Teensy SD library, backed by a real folder on disk
// (NI404_SDCARD_PATH, the repo's ../_SDCARD). Implements the File operations the
// NI404 firmware uses: read()/read(buf,n), write(b)/write(buf,n), seek, size,
// available, peek, close; and SD.begin/open/exists/mkdir/remove.
#ifndef NI404_COMPAT_SD_H
#define NI404_COMPAT_SD_H

#include "Arduino.h"     // String
#include <cstdio>
#include <cstdint>
#include <cstdlib>       // getenv
#include <string>
#include <filesystem>

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
#define FILE_WRITE (O_WRITE | O_CREAT)

#ifndef NI404_SDCARD_PATH
#define NI404_SDCARD_PATH "_SDCARD"
#endif

class File : public Print {
public:
    File() {}
    File(FILE *f, long sz, const std::string &nm = "") : fp(f), _size(sz), _name(nm) {}
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
    long size() { return _size; }
    int available() { if (!fp) return 0; long c = std::ftell(fp); return (int)(_size - c); }
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
    bool _isdir = false;
    std::string _name, _dirpath;
    std::filesystem::directory_iterator diriter;
};

// Optional base directory (the executable's folder), set by the frontend from
// argv[0]; lets a distributed binary find an _SDCARD sitting next to it.
const char *ni404_base_dir();

class SDClass {
public:
    bool begin(int = 0) { root = resolve_root(); return true; }

    // Emulator-only: inspect / change the folder backing the virtual SD card.
    std::string getRoot() const { return root; }
    void setRoot(const std::string &r) { root = r; }

    // Find the SD-card folder at RUNTIME so the binary is portable (the baked
    // compile-time path points at the build machine and is only the last resort).
    // Order: $NI404_SDCARD, then _SDCARD next to the exe / a couple levels up from
    // it, then the same relative to the working directory, then the baked default.
    static std::string resolve_root() {
        namespace fs = std::filesystem;
        std::error_code ec;
        if (const char *e = std::getenv("NI404_SDCARD"))
            if (e[0] && fs::exists(e, ec)) return e;
        const char *rel[] = { "_SDCARD", "../_SDCARD", "../../_SDCARD", "../../../_SDCARD" };
        std::string b = ni404_base_dir() ? ni404_base_dir() : "";
        if (!b.empty())
            for (const char *r : rel) { fs::path p = fs::path(b) / r; if (fs::exists(p, ec)) return p.string(); }
        for (const char *r : rel) if (fs::exists(r, ec)) return r;
        return NI404_SDCARD_PATH;
    }

    File open(const char *path, int mode = FILE_READ) {
        bool writing = (mode & (O_WRITE | O_RDWR | O_CREAT | O_TRUNC | O_APPEND | O_AT_END)) != 0;
        std::string full = resolve(path, writing);
        std::string base = full.substr(full.find_last_of("/\\") + 1);
        // Directory?
        std::error_code ec;
        if (!writing && std::filesystem::is_directory(full, ec))
            return File(full, base, true);
        const char *m = writing ? ((mode & (O_APPEND | O_AT_END)) ? "ab+" : "wb+") : "rb";
        FILE *f = std::fopen(full.c_str(), m);
        if (!f) return File();
        long sz = 0;
        if (!writing) { std::fseek(f, 0, SEEK_END); sz = std::ftell(f); std::fseek(f, 0, SEEK_SET); }
        return File(f, sz, base);
    }
    File open(const String &path, int mode = FILE_READ) { return open(path.c_str(), mode); }

    bool exists(const char *path) {
        std::string full = resolve(path, false);
        return std::filesystem::exists(full);
    }
    bool exists(const String &path) { return exists(path.c_str()); }

    bool mkdir(const char *path) {
        std::error_code ec;
        std::filesystem::create_directories(join(root, path), ec);
        return !ec;
    }
    bool mkdir(const String &path) { return mkdir(path.c_str()); }

    bool remove(const char *path) {
        std::error_code ec;
        return std::filesystem::remove(resolve(path, false), ec);
    }
    bool remove(const String &path) { return remove(path.c_str()); }

    bool rmdir(const char *path) {
        std::error_code ec;
        return std::filesystem::remove(join(root, path), ec);
    }
    bool rmdir(const String &path) { return rmdir(path.c_str()); }

    bool rename(const char *from, const char *to) {
        std::error_code ec;
        std::filesystem::rename(resolve(from, false), join(root, to), ec);
        return !ec;
    }
    bool rename(const String &from, const String &to) { return rename(from.c_str(), to.c_str()); }

private:
    std::string root = NI404_SDCARD_PATH;

    static std::string join(const std::string &a, const std::string &b) {
        if (a.empty()) return b;
        if (!a.empty() && (a.back() == '/' || a.back() == '\\')) return a + b;
        return a + "/" + b;
    }
    // Resolve a device path to a real file. The firmware addresses samples as
    // "samples/<folder>/_<n>.wav"; the repo's _SDCARD holds "<folder>/_<n>.wav"
    // at its root, so if "samples/..." is not found we retry with that prefix
    // stripped.
    std::string resolve(const char *path, bool forWrite) {
        std::string p = path ? path : "";
        std::string direct = join(root, p);
        if (forWrite || std::filesystem::exists(direct)) return direct;
        const std::string pre = "samples/";
        if (p.rfind(pre, 0) == 0) {
            std::string alt = join(root, p.substr(pre.size()));
            if (std::filesystem::exists(alt)) return alt;
        }
        return direct;
    }
};

extern SDClass SD;

#endif // NI404_COMPAT_SD_H
