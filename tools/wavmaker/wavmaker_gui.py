#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ichosynth / TŒRN — WAV Maker (GUI)
==================================
Friendly graphical converter that turns any WAV into the format the TŒRN
firmware loads — MONO / 16-bit / 44100 Hz — and writes it where the firmware
reads it.

The firmware has TWO sample systems, so the app has two modes:

  • Samplepack  — a numbered folder <pack>/ with 8 voices 1.wav .. 8.wav,
                  loaded as a set at boot / via the pack selector.
  • Libreria    — free WAV files under samples/<categoria>/<nome>.wav, browsed
                  voice-by-voice in SET_WAV (names are kept, just tidied; the
                  firmware shows names <= 64 chars and <= 256 WAVs per folder).

Features:
- pick individual files or a whole folder; see each file's current format and
  its destination before converting
- prepare an SD card: scan it (detect packs + browser library), and on Windows
  format it FAT32 / create the samples/ folder. Formatting is offered ONLY for
  removable SD media (never fixed / system disks), re-checks the card right
  before formatting and shows disk number, model, size and partitions.
- progress bar + log; conversion runs off the UI thread; every source is
  converted before any destination is overwritten (safe voice reordering)
- band-limited resampling (windowed-sinc); 16-bit mono 44.1k files pass bit-exact

Pure standard library — the WAV converter is hand-rolled (no ffmpeg, no audioop),
so it works on any Python 3.8+ including 3.13/3.14 where audioop was removed.
SD scan/format on Windows shell out to PowerShell.

Run:  python wavmaker_gui.py      (or launch the bundled wavmaker.exe)
"""
import array
import math
import operator
import os
import re
import sys
import json
import struct
import shutil
import subprocess
import threading
import queue
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_VERSION = "2.0"
APP_AUTHOR = "Luigi Massari (luigismith)"
REPO_URL = "https://github.com/luigismith/ichosynth"

TARGET_CH, TARGET_WIDTH, TARGET_RATE = 1, 2, 44100

# voices in a samplepack (labels are cosmetic; the firmware just loads 1..8)
VOICE_LABELS = ["KICK", "SNARE", "HAT ch.", "HAT ap.", "CLAP", "TOM", "PERC", "PERC"]
MAX_VOICES = 8
MAX_PACK = 99
# suggested browser categories (the user can type any name)
CATEGORIES = ["kick", "snare", "hat", "clap", "tom", "perc", "fx", "bass", "synth", "loop"]

# ------- ichosynth palette -------
BG = "#0d1117"
PANEL = "#161b22"
INK = "#e6edf3"
SUB = "#9aa4b2"
LINE = "#30363d"
ACCENT = "#2ea44f"
ACCENT2 = "#1f6feb"
WARN = "#d29922"
RED = "#e5534b"
ROW_OK = "#16241b"

SD_BROWSER_DIR = "samples"
FORMAT_LABEL = "ICHOSYNTH"
IS_WIN = sys.platform.startswith("win")
_FS_OK = ("FAT", "FAT16", "FAT32", "EXFAT")


# =========================================================================
# audio core — pure-python WAV decode/encode (mono / 16-bit / 44100 Hz)
# =========================================================================
def _parse_fmt(b):
    """Return (tag, channels, rate, bits, data_bytes) or None."""
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        return None
    tag = ch = rate = bits = None
    data_bytes = 0
    for cid, body in _iter_chunks(b):
        if cid == b"fmt ":
            tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:
                tag = struct.unpack("<H", body[24:26])[0]
        elif cid == b"data":
            data_bytes = len(body)
    if tag is None:
        return None
    return tag, ch, rate, bits, data_bytes


def read_format(path):
    """Return (channels, sampwidth_bytes, rate, nframes, tag) or None."""
    try:
        with open(path, "rb") as f:
            head = f.read(1 << 20)  # 1 MB is plenty for the header chunks
        info = _parse_fmt(head)
        if not info:
            # data chunk may be beyond the first MB; re-read fully for size only
            with open(path, "rb") as f:
                info = _parse_fmt(f.read())
        if not info:
            return None
        tag, ch, rate, bits, dbytes = info
        # if data was truncated in the 1MB read, get the true size from file
        nbytes = max(1, (bits // 8) * ch)
        # use on-disk size as a robust frame estimate when header was partial
        try:
            full = os.path.getsize(path)
            est_data = max(dbytes, full - 44)
        except OSError:
            est_data = dbytes
        nframes = est_data // nbytes
        return ch, bits // 8, rate, nframes, tag
    except Exception:
        return None


def is_target(fmt):
    return fmt is not None and fmt[0] == TARGET_CH and fmt[1] == TARGET_WIDTH and fmt[2] == TARGET_RATE


def fmt_label(fmt):
    if fmt is None:
        return "non leggibile"
    ch, width, rate, nframes, tag = fmt
    chl = {1: "mono", 2: "stereo"}.get(ch, f"{ch}ch")
    kind = "float" if tag == 3 else "PCM"
    secs = nframes / rate if rate else 0
    return f"{chl} · {width*8}-bit {kind} · {rate} Hz · {secs:0.1f}s"


# --------------------------------------------------------------------------
# pure-python WAV codec  (mono / 16-bit / 44100 Hz output)
# NB: the same block lives in wavmaker.py, wavmaker_gui.py and build_samples.py
#     (each script stays standalone) — keep the three copies identical.
# --------------------------------------------------------------------------
def _iter_chunks(b):
    pos, n = 12, len(b)
    while pos + 8 <= n:
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        yield cid, b[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)          # chunks are word-aligned


def wav_info(b):
    """RIFF/WAVE bytes -> (tag, channels, rate, bits, data_bytes). Raises ValueError."""
    if b[:4] != b"RIFF" or b[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    fmt = data = None
    for cid, body in _iter_chunks(b):
        if cid == b"fmt ":
            if len(body) < 16:
                raise ValueError("fmt chunk troppo corto")
            tag, ch, rate, _br, _ba, bits = struct.unpack("<HHIIHH", body[:16])
            if tag == 0xFFFE and len(body) >= 26:    # WAVE_FORMAT_EXTENSIBLE
                tag = struct.unpack("<H", body[24:26])[0]   # real format from GUID
            fmt = (tag, ch, rate, bits)
        elif cid == b"data":
            data = body
    if not fmt or data is None:
        raise ValueError("missing fmt/data chunk")
    tag, ch, rate, bits = fmt
    if ch == 0 or rate == 0 or bits == 0 or bits % 8:
        raise ValueError("bad fmt (ch=%d rate=%d bits=%d)" % (ch, rate, bits))
    return tag, ch, rate, bits, data


def _samples(data, tag, bits):
    """Interleaved sample bytes -> list of floats in -1..1 (all channels)."""
    if tag == 1 and bits == 8:                 # unsigned 8-bit
        return [(v - 128) / 128.0 for v in data]
    if tag == 1 and bits == 24:
        n = len(data) // 3
        out = [0.0] * n
        for i in range(n):
            o = i * 3
            v = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
            out[i] = (v - 0x1000000 if v & 0x800000 else v) / 8388608.0
        return out
    if tag == 1 and bits in (16, 32):
        code = "h" if bits == 16 else ("i" if array.array("i").itemsize == 4 else "l")
        scale = 1.0 / (32768.0 if bits == 16 else 2147483648.0)
    elif tag == 3 and bits in (32, 64):        # IEEE float
        code = "f" if bits == 32 else "d"
        scale = 1.0
    elif tag in (1, 3):
        raise ValueError("%s bits %d" % ("pcm" if tag == 1 else "float", bits))
    else:
        raise ValueError("format tag %d" % tag)
    a = array.array(code)
    a.frombytes(data[:len(data) - len(data) % a.itemsize])
    if sys.byteorder != "little":
        a.byteswap()
    if scale == 1.0:
        return [v if v == v else 0.0 for v in a]      # NaN -> 0
    return [v * scale for v in a]


def decode_wav(b):
    """Arbitrary PCM/float WAV bytes -> (rate, [mono floats in -1..1])."""
    tag, ch, rate, bits, data = wav_info(b)
    s = _samples(data, tag, bits)
    if ch == 1:
        return rate, s
    nframes = len(s) // ch
    inv = 1.0 / ch
    cols = [s[c:nframes * ch:ch] for c in range(ch)]
    return rate, [sum(fr) * inv for fr in zip(*cols)]


# band-limited resampler: polyphase windowed-sinc (Kaiser), low-pass at
# 0.45 * min(fs_in, fs_out) so nothing above the new Nyquist folds back.
_RS_CUT = 0.45          # cutoff, fraction of the lower sample rate
_RS_ZEROS = 24          # sinc zero-crossings per side
_RS_BETA = 8.6          # Kaiser beta (~-85 dB stopband)
_RS_MAX_PHASES = 1024   # odd rate ratios: phase quantised to 1/1024 sample


def _bessel_i0(x):
    s = term = 1.0
    y = x * x / 4.0
    k = 1
    while term > 1e-12 * s:
        term *= y / (k * k)
        s += term
        k += 1
    return s


def resample(mono, src_rate, dst_rate):
    if src_rate == dst_rate or not mono:
        return mono
    g = math.gcd(int(src_rate), int(dst_rate))
    up, down = int(dst_rate) // g, int(src_rate) // g
    out_n = max(1, int(round(len(mono) * dst_rate / src_rate)))
    fc = _RS_CUT * min(src_rate, dst_rate) / src_rate      # cycles / input sample
    half = _RS_ZEROS / (2.0 * fc)                           # kernel half-width
    taps = int(math.ceil(half))
    width = 2 * taps
    i0b = _bessel_i0(_RS_BETA)
    nph = up if up <= _RS_MAX_PHASES else _RS_MAX_PHASES
    cache = {}

    def kernel(q):
        frac = q / nph
        c = []
        for j in range(-taps + 1, taps + 1):
            d = frac - j                     # distance input sample -> output point
            u = d / half
            if abs(u) >= 1.0:
                c.append(0.0)
                continue
            x = 2.0 * fc * d
            sinc = 1.0 if x == 0.0 else math.sin(math.pi * x) / (math.pi * x)
            c.append(2.0 * fc * sinc * _bessel_i0(_RS_BETA * math.sqrt(1.0 - u * u)) / i0b)
        tot = sum(c)
        return [v / tot for v in c]           # unity gain at DC for every phase

    xp = [0.0] * taps + list(mono) + [0.0] * (taps + 2)
    out = [0.0] * out_n
    mul = operator.mul
    for n in range(out_n):
        k, r = divmod(n * down, up)
        if nph == up:
            q = r
        else:
            q = int(round(r * nph / up))
            if q == nph:
                k, q = k + 1, 0
        c = cache.get(q)
        if c is None:
            c = cache[q] = kernel(q)
        out[n] = sum(map(mul, c, xp[k + 1:k + 1 + width]))
    return out


def _wav_header(nbytes):
    return (b"RIFF" + struct.pack("<I", 36 + nbytes) + b"WAVE"
            + b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, TARGET_RATE, TARGET_RATE * 2, 2, 16)
            + b"data" + struct.pack("<I", nbytes))


def encode_wav_mono16(mono):
    # symmetric scaling (decode /32768, encode *32768 clipped to int16): a 16-bit
    # source survives decode -> encode bit-exact, so re-converting is lossless
    pcm = array.array("h", [0]) * len(mono)
    for i, v in enumerate(mono):
        x = v * 32768.0
        if x >= 32767.0:
            pcm[i] = 32767
        elif x <= -32768.0:
            pcm[i] = -32768
        elif x == x:                           # NaN -> 0
            pcm[i] = int(round(x))
    if sys.byteorder != "little":
        pcm.byteswap()
    raw = pcm.tobytes()
    return _wav_header(len(raw)) + raw


def convert_bytes(raw):
    """Any WAV -> mono/16-bit/44100 WAV bytes (44-byte header)."""
    tag, ch, rate, bits, data = wav_info(raw)
    if tag == 1 and ch == 1 and bits == 16 and rate == TARGET_RATE:
        pcm = bytes(data[:len(data) & ~1])     # already the target: samples untouched
        return _wav_header(len(pcm)) + pcm
    rate, mono = decode_wav(raw)
    return encode_wav_mono16(resample(mono, rate, TARGET_RATE))


def convert_file(src, dst):
    """Convert src WAV to mono/16-bit/44100, write to dst (atomic)."""
    tmp = stage_convert(src, dst)
    os.replace(tmp, dst)


def _tmp_path(dst):
    return dst + ".ichotmp"


def stage_convert(src, dst):
    """Convert src into a temp file next to dst and return its path.

    Batches convert EVERY source first and only then move the temp files over
    the destinations, so a destination that is also a later source (e.g. voices
    swapped inside a pack already on the SD) is never read after being overwritten.
    """
    with open(src, "rb") as f:
        out = convert_bytes(f.read())
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    tmp = _tmp_path(dst)
    try:
        with open(tmp, "wb") as f:
            f.write(out)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return tmp


def same_path(a, b):
    """True if a and b name the same file (case-insensitive on Windows)."""
    try:
        if os.path.exists(a) and os.path.exists(b):
            return os.path.samefile(a, b)
    except OSError:
        pass
    return os.path.normcase(os.path.abspath(a)) == os.path.normcase(os.path.abspath(b))


# firmware limits of the sample browser (SET_WAV), from the TŒRN listing:
# names are copied into SAMPLE_BROWSER_NAME_MAX (65) buffers and at most
# BROWSE_MAX_TMP (256) WAVs per folder are listed.
BROWSER_NAME_MAX = 60      # full name incl. ".wav" (margin below the 64 kept)
BROWSER_MAX_FILES = 256
CATEGORY_MAX = 32


def sanitize_name(basename, suffix=""):
    """Turn a source filename into a tidy browser name (keeps it readable, <= 60 chars)."""
    name = os.path.splitext(os.path.basename(basename))[0]
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-._")
    room = BROWSER_NAME_MAX - len(".wav") - len(suffix)
    name = (name or "sample")[:room].rstrip("-._") or "sample"
    return name + suffix + ".wav"


def sanitize_category(cat):
    """Category -> ONE safe folder name under samples/ (no '/', '\\', '..', leading dots)."""
    c = (cat or "").strip().lower()
    c = re.sub(r"[^a-z0-9_-]+", "-", c)
    c = re.sub(r"-{2,}", "-", c).strip("-_")[:CATEGORY_MAX].strip("-_")
    return c or "perc"


def browser_names(paths):
    """Destination names for a batch: sanitised, de-duplicated (case-insensitive)."""
    seen, out = set(), []
    for p in paths:
        nm, n = sanitize_name(p), 1
        while nm.lower() in seen:
            n += 1
            nm = sanitize_name(p, f"-{n}")
        seen.add(nm.lower())
        out.append(nm)
    return out


# =========================================================================
# SD card helpers (scan / structure / format) — Windows-focused
# =========================================================================
def human_size(n):
    if n is None:
        return "?"
    n = float(n)
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or u == "TB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} TB"


def _ps(script, timeout=120):
    if not IS_WIN:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            startupinfo=si, creationflags=0x08000000)
    except Exception:
        return None


def drive_letter_of(path):
    if not path:
        return None
    drv = os.path.splitdrive(os.path.abspath(path))[0]
    if len(drv) >= 2 and drv[1] == ":":
        return drv[0].upper()
    return None


def _ps_json(script, timeout=60):
    r = _ps(script, timeout=timeout)
    if not r or r.returncode != 0 or not (r.stdout or "").strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


# FAT32: Windows' Format-Volume refuses volumes above 32 GB
FAT32_MAX = 32 * 1024 ** 3
# bus types of a real SD/MMC slot; a USB card reader shows "USB" and is accepted
# only when Windows reports the volume as Removable (USB HDD/SSD are "Fixed")
_SD_BUS = ("SD", "MMC")


def volume_info(path):
    """Volume + physical-disk facts for the drive holding `path` (Windows: PowerShell)."""
    info = {"letter": drive_letter_of(path), "fs": None, "drive_type": None,
            "size": None, "free": None, "label": None, "serial": None,
            "removable": None, "system": False, "readable": False,
            "disk_number": None, "disk_model": None, "disk_size": None,
            "bus_type": None, "disk_system": None, "partitions": None, "part_list": []}
    sysdrive = os.environ.get("SystemDrive", "C:")[0].upper()
    if info["letter"] and info["letter"] == sysdrive:
        info["system"] = True
    root = (info["letter"] + ":\\") if info["letter"] else path
    try:
        u = shutil.disk_usage(root)
        info["size"], info["free"] = u.total, u.free
        info["readable"] = True
    except Exception:
        info["readable"] = False
    if IS_WIN and info["letter"]:
        L = info["letter"]
        d = _ps_json(
            "$ErrorActionPreference='SilentlyContinue'; "
            f"$v = Get-Volume -DriveLetter {L}; "
            f"$p = Get-Partition -DriveLetter {L}; "
            "$d = $null; if ($p) { $d = $p | Get-Disk }; "
            f"$ld = Get-CimInstance Win32_LogicalDisk | Where-Object {{ $_.DeviceID -eq '{L}:' }}; "
            "$parts = @(); if ($d) { $parts = @(Get-Partition -DiskNumber $d.Number | ForEach-Object { "
            "[pscustomobject]@{ Letter = $(if ([string]$_.DriveLetter -match '^[A-Za-z]$') { [string]$_.DriveLetter } else { '' }); "
            "Size = $_.Size; Type = [string]$_.Type } }) }; "
            "[pscustomobject]@{ "
            "FileSystemType = [string]$v.FileSystemType; DriveType = [string]$v.DriveType; "
            "Size = $v.Size; SizeRemaining = $v.SizeRemaining; FileSystemLabel = [string]$v.FileSystemLabel; "
            "Serial = [string]$ld.VolumeSerialNumber; "
            "DiskNumber = $d.Number; DiskModel = [string]$d.FriendlyName; DiskSize = $d.Size; "
            "BusType = [string]$d.BusType; IsSystem = [bool]($d.IsSystem -or $d.IsBoot); "
            "Partitions = $d.NumberOfPartitions; PartList = $parts "
            "} | ConvertTo-Json -Compress -Depth 4")
        if isinstance(d, dict):
            info["fs"] = d.get("FileSystemType") or None
            info["drive_type"] = d.get("DriveType") or None
            dt = str(info["drive_type"] or "").lower()
            info["removable"] = (dt == "removable") if dt else None
            if d.get("Size"):
                info["size"] = int(d["Size"])
            if d.get("SizeRemaining") is not None:
                info["free"] = int(d["SizeRemaining"])
            info["label"] = d.get("FileSystemLabel") or None
            info["serial"] = d.get("Serial") or None
            if d.get("DiskNumber") is not None:
                info["disk_number"] = int(d["DiskNumber"])
                info["disk_model"] = d.get("DiskModel") or None
                info["disk_size"] = int(d["DiskSize"]) if d.get("DiskSize") else None
                info["bus_type"] = d.get("BusType") or None
                info["disk_system"] = bool(d.get("IsSystem"))
                info["partitions"] = d.get("Partitions")
                pl = d.get("PartList") or []
                info["part_list"] = pl if isinstance(pl, list) else [pl]
    return info


def is_sd_media(info):
    """True only for removable SD media: Removable volume, or a disk on an SD/MMC bus."""
    if not info or not info.get("letter"):
        return False
    bus = str(info.get("bus_type") or "").upper()
    return info.get("removable") is True or bus in _SD_BUS


def format_block_reason(info, deep=False):
    """None if formatting `info` is allowed, else the (Italian) reason it is refused."""
    if not IS_WIN:
        return "La formattazione automatica è disponibile solo su Windows."
    if not info or not info.get("letter"):
        return "Indica una scheda SD con lettera di unità (es. E:\\)."
    letter = info["letter"]
    sysdrive = os.environ.get("SystemDrive", "C:")[0].upper()
    if letter == sysdrive or info.get("system") or info.get("disk_system"):
        return f"L'unità {letter}: è sul disco di SISTEMA/avvio. Non verrà mai formattata."
    if info.get("disk_number") is None:
        return f"Non riesco a identificare il disco fisico di {letter}: (Get-Disk): formattazione bloccata."
    if not is_sd_media(info):
        return (f"L'unità {letter}: non è una scheda SD rimovibile "
                f"(tipo: {info.get('drive_type') or '?'}, bus: {info.get('bus_type') or '?'}). "
                "Per sicurezza qui si formattano solo schede SD.")
    size = info.get("disk_size") if deep else (info.get("size") or info.get("disk_size"))
    if size and size > FAT32_MAX:
        return (f"La scheda è da {human_size(size)}: Windows non crea FAT32 oltre 32 GB. "
                "Usa una scheda ≤ 32 GB (o formatta exFAT manualmente da Esplora risorse).")
    if deep and (info.get("partitions") or 0) > 1:
        return (f"Il disco {info['disk_number']} ha {info['partitions']} partizioni: la ripulitura "
                "completa le cancellerebbe tutte. Bloccata per sicurezza.")
    return None


def same_volume(a, b):
    """Has the card changed between two volume_info() snapshots?"""
    keys = ("letter", "size", "label", "serial", "disk_number", "disk_model", "disk_size")
    return all(a.get(k) == b.get(k) for k in keys)


def fs_is_compatible(fs):
    return bool(fs) and fs.upper() in _FS_OK


def scan_sd_layout(root):
    """Inspect a card root for TŒRN content.

    Returns: packs {pack_num: voice_count}, browser_files int,
             browser_cats {category: count}, next_pack int.
    """
    res = {"packs": {}, "browser_files": 0, "browser_cats": {}, "next_pack": 1}
    try:
        for name in os.listdir(root):
            full = os.path.join(root, name)
            if os.path.isdir(full) and name.isdigit() and 0 <= int(name) <= MAX_PACK:
                voices = 0
                for v in range(1, MAX_VOICES + 1):
                    if os.path.isfile(os.path.join(full, f"{v}.wav")):
                        voices += 1
                res["packs"][int(name)] = voices
    except Exception:
        pass
    # next free pack number (skip 0, which is the factory/default pack)
    n = 1
    while n in res["packs"] and n <= MAX_PACK:
        n += 1
    res["next_pack"] = n
    # browser library
    sdir = os.path.join(root, SD_BROWSER_DIR)
    if os.path.isdir(sdir):
        for dirpath, _dirs, files in os.walk(sdir):
            wavs = [f for f in files if f.lower().endswith(".wav")]
            if not wavs:
                continue
            res["browser_files"] += len(wavs)
            cat = os.path.relpath(dirpath, sdir).replace("\\", "/")
            if cat == ".":
                cat = "(radice)"
            res["browser_cats"][cat] = res["browser_cats"].get(cat, 0) + len(wavs)
    return res


def ensure_browser_dir(root):
    d = os.path.join(root, SD_BROWSER_DIR)
    created = not os.path.isdir(d)
    os.makedirs(d, exist_ok=True)
    return created


def format_fat32(info, label=FORMAT_LABEL, deep=False):
    """Format the SD described by a FRESH volume_info() snapshot.

    The PowerShell side re-checks the same rules (removable / SD bus, not system,
    same disk number and size, one partition for `deep`) before touching anything.
    Returns (True, new_letter) or (False, message).
    """
    why = format_block_reason(info, deep=deep)
    if why:
        return False, why
    letter = info["letter"]
    dnum = int(info["disk_number"])
    dsize = int(info.get("disk_size") or 0)
    check = (
        "$ErrorActionPreference='Stop'; "
        f"$v = Get-Volume -DriveLetter {letter}; "
        f"$p = Get-Partition -DriveLetter {letter}; "
        "$d = $p | Get-Disk; "
        f"if ($d.Number -ne {dnum} -or $d.Size -ne {dsize}) {{ throw 'ICHO:CHANGED' }}; "
        "if ($d.IsSystem -or $d.IsBoot) { throw 'ICHO:SYSTEM' }; "
        "if (-not ([string]$v.DriveType -eq 'Removable' -or "
        "[string]$d.BusType -eq 'SD' -or [string]$d.BusType -eq 'MMC')) { throw 'ICHO:NOTSD' }; ")
    if not deep:
        action = (f"Format-Volume -DriveLetter {letter} -FileSystem FAT32 "
                  f"-NewFileSystemLabel '{label}' -Force -Confirm:$false | Out-Null; "
                  f"Write-Output 'NEWLETTER={letter}'; ")
    else:
        action = (
            "if ($d.NumberOfPartitions -gt 1) { throw 'ICHO:MULTIPART' }; "
            "Clear-Disk -Number $d.Number -RemoveData -RemoveOEM -Confirm:$false; "
            "Initialize-Disk -Number $d.Number -PartitionStyle MBR -ErrorAction SilentlyContinue | Out-Null; "
            "$np = New-Partition -DiskNumber $d.Number -UseMaximumSize -AssignDriveLetter; "
            "Start-Sleep -Milliseconds 800; "
            "$np = Get-Partition -DiskNumber $d.Number -PartitionNumber $np.PartitionNumber; "
            "Format-Volume -Partition $np -FileSystem FAT32 "
            f"-NewFileSystemLabel '{label}' -Force -Confirm:$false | Out-Null; "
            "$np = Get-Partition -DiskNumber $d.Number -PartitionNumber $np.PartitionNumber; "
            "Write-Output ('NEWLETTER=' + $np.DriveLetter); ")
    # errors are reported as one 'ERR=<message>' line: classify on the exception
    # message only, never on PowerShell's echo of the command line
    script = ("try { " + check + action + "} catch { "
              "Write-Output ('ERR=' + $_.Exception.Message); exit 1 }")
    r = _ps(script, timeout=480 if deep else 300)
    if r is None:
        return False, "Impossibile avviare PowerShell."
    out = r.stdout or ""
    m_err = re.search(r"^ERR=(.*)$", out, re.M)
    m_new = re.search(r"NEWLETTER=([A-Za-z])", out)
    if r.returncode == 0 and not m_err:
        return True, (m_new.group(1).upper() if m_new else letter)
    msg = (m_err.group(1).strip() if m_err else (r.stderr or out or "").strip())
    low = msg.lower()
    if "icho:changed" in low:
        return False, "La scheda è cambiata dopo la scansione: rifai «Scansiona»."
    if "icho:system" in low or "icho:notsd" in low or "icho:multipart" in low:
        return False, "Controllo di sicurezza fallito: il disco non risulta una SD rimovibile a partizione singola."
    if "denied" in low or "negato" in low or "administrator" in low or "amministrat" in low:
        return False, ("Accesso negato: serve eseguire l'app come Amministratore "
                       "(clic destro sull'app → «Esegui come amministratore»).")
    if "write protect" in low or "protetto da scrittura" in low or "read-only" in low or "sola lettura" in low:
        return False, "La scheda è protetta da scrittura (levetta LOCK dell'adattatore SD?)."
    if "in use" in low or "in uso" in low:
        return False, "L'unità è in uso: chiudi le finestre/app che la usano e riprova."
    return False, (msg[:400] if msg else "Formattazione non riuscita.")


# =========================================================================
# GUI
# =========================================================================
class WavMakerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=0)
        self.master = master
        self.items = []
        self.q = queue.Queue()
        self.sdq = queue.Queue()
        self.worker = None
        self.sd_root = None
        self.sd_info = None
        self.sd_scan = None
        self.deduced_pack = 1
        self._sd_inflight = 0
        self._last_out = ""
        self._njobs = 0

        self._build_style()
        self._build_ui()
        self.pack(fill="both", expand=True)
        self._on_mode_change()
        self._log("Pronto. Aggiungi file WAV o una cartella per iniziare.")
        self._log("Scegli la modalità: Samplepack (8 voci) o Libreria browser.", SUB)

    # ---- styling ----
    def _build_style(self):
        self.master.configure(bg=BG)
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=BG, foreground=INK, fieldbackground=PANEL,
                     bordercolor=LINE, lightcolor=PANEL, darkcolor=PANEL)
        st.configure("TFrame", background=BG)
        st.configure("Panel.TFrame", background=PANEL)
        st.configure("TLabel", background=BG, foreground=INK)
        st.configure("Sub.TLabel", background=BG, foreground=SUB)
        st.configure("Panel.TLabel", background=PANEL, foreground=INK)
        st.configure("PanelSub.TLabel", background=PANEL, foreground=SUB)
        st.configure("Title.TLabel", background=BG, foreground=INK, font=("Segoe UI", 17, "bold"))
        st.configure("H2.TLabel", background=BG, foreground=INK, font=("Segoe UI", 10, "bold"))
        st.configure("PanelH2.TLabel", background=PANEL, foreground=INK, font=("Segoe UI", 10, "bold"))
        st.configure("TButton", background=PANEL, foreground=INK, bordercolor=LINE, focuscolor=BG, padding=6)
        st.map("TButton", background=[("active", "#21262d")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#06210f",
                     font=("Segoe UI", 11, "bold"), padding=9)
        st.map("Accent.TButton", background=[("active", "#2bbd5a"), ("disabled", LINE)])
        st.configure("Scan.TButton", background=ACCENT2, foreground="#06122b",
                     font=("Segoe UI", 10, "bold"), padding=7)
        st.map("Scan.TButton", background=[("active", "#3b82f6"), ("disabled", LINE)])
        st.configure("Danger.TButton", background=RED, foreground="#2a0707",
                     font=("Segoe UI", 10, "bold"), padding=7)
        st.map("Danger.TButton", background=[("active", "#f2645b"), ("disabled", LINE)])
        st.configure("Info.TButton", background=PANEL, foreground=ACCENT2, font=("Segoe UI", 13, "bold"), padding=2)
        st.map("Info.TButton", background=[("active", "#21262d")])
        st.configure("TCheckbutton", background=PANEL, foreground=INK)
        st.map("TCheckbutton", background=[("active", PANEL)])
        st.configure("TRadiobutton", background=PANEL, foreground=INK)
        st.map("TRadiobutton", background=[("active", PANEL)])
        st.configure("TEntry", fieldbackground="#0b0f14", foreground=INK)
        st.configure("TSpinbox", fieldbackground="#0b0f14", foreground=INK, arrowsize=14)
        st.configure("TCombobox", fieldbackground="#0b0f14", foreground=INK)
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                     rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background="#0b0f14", foreground=SUB, font=("Segoe UI", 9, "bold"))
        st.map("Treeview", background=[("selected", ACCENT2)])
        st.configure("green.Horizontal.TProgressbar", background=ACCENT, troughcolor="#0b0f14", bordercolor=LINE)

    # ---- layout ----
    def _build_ui(self):
        self.master.title("ichosynth — WAV Maker")
        self.master.minsize(780, 680)

        head = ttk.Frame(self, padding=(18, 14, 18, 6))
        head.pack(fill="x")
        ttk.Button(head, text="ⓘ", width=3, style="Info.TButton", command=self.show_about).pack(side="right", anchor="n")
        titlebox = ttk.Frame(head)
        titlebox.pack(side="left", anchor="w")
        ttk.Label(titlebox, text="🎵  ichosynth — WAV Maker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titlebox, text="Converte i WAV in  mono · 16-bit · 44100 Hz  per il firmware TŒRN",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        # mode selector
        modebar = ttk.Frame(self, style="Panel.TFrame", padding=(12, 8))
        modebar.pack(fill="x", padx=18, pady=(4, 2))
        ttk.Label(modebar, text="Modalità:", style="Panel.TLabel").pack(side="left")
        self.mode_var = tk.StringVar(value="pack")
        ttk.Radiobutton(modebar, text="Samplepack (8 voci → <pack>/1-8.wav)", value="pack",
                        variable=self.mode_var, command=self._on_mode_change).pack(side="left", padx=(12, 0))
        ttk.Radiobutton(modebar, text="Libreria browser (samples/<cat>/<nome>.wav)", value="browser",
                        variable=self.mode_var, command=self._on_mode_change).pack(side="left", padx=(16, 0))

        # toolbar
        bar = ttk.Frame(self, padding=(18, 6, 18, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="➕  Aggiungi file", command=self.add_files).pack(side="left")
        ttk.Button(bar, text="📁  Aggiungi cartella", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(bar, text="🗑  Rimuovi", command=self.remove_selected).pack(side="left")
        ttk.Button(bar, text="Svuota", command=self.clear_all).pack(side="left", padx=6)
        self.up_btn = ttk.Button(bar, text="↑", width=3, command=lambda: self.move_selected(-1))
        self.up_btn.pack(side="left", padx=(12, 0))
        self.down_btn = ttk.Button(bar, text="↓", width=3, command=lambda: self.move_selected(1))
        self.down_btn.pack(side="left", padx=(4, 0))
        self.count_lbl = ttk.Label(bar, text="0 file", style="Sub.TLabel")
        self.count_lbl.pack(side="right")

        # file table
        table = ttk.Frame(self, style="Panel.TFrame", padding=1)
        table.pack(fill="both", expand=True, padx=18, pady=(2, 6))
        cols = ("slot", "file", "fmt", "arrow", "dst")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("slot", text="#")
        self.tree.heading("file", text="FILE")
        self.tree.heading("fmt", text="FORMATO ATTUALE")
        self.tree.heading("arrow", text="")
        self.tree.heading("dst", text="DESTINAZIONE")
        self.tree.column("slot", width=70, anchor="w")
        self.tree.column("file", width=210, anchor="w")
        self.tree.column("fmt", width=210, anchor="w")
        self.tree.column("arrow", width=28, anchor="center")
        self.tree.column("dst", width=180, anchor="w")
        self.tree.tag_configure("ok", background=ROW_OK)
        self.tree.tag_configure("over", foreground=RED)
        vs = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # ---------- SD card panel ----------
        sdp = ttk.Frame(self, style="Panel.TFrame", padding=12)
        sdp.pack(fill="x", padx=18, pady=(0, 6))
        sdp.columnconfigure(1, weight=1)
        ttk.Label(sdp, text="💾  Scheda SD", style="PanelH2.TLabel").grid(row=0, column=0, columnspan=4, sticky="w")
        ttk.Label(sdp, text="Percorso SD", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.sd_path_var = tk.StringVar(value="")
        ttk.Entry(sdp, textvariable=self.sd_path_var).grid(row=1, column=1, sticky="ew", padx=(12, 6), pady=(8, 0))
        ttk.Button(sdp, text="Sfoglia…", command=self.pick_sd).grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.sd_scan_btn = ttk.Button(sdp, text="🔍  Scansiona", style="Scan.TButton", command=self.scan_sd)
        self.sd_scan_btn.grid(row=1, column=3, sticky="e", padx=(6, 0), pady=(8, 0))
        self.sd_status = tk.Label(sdp, text="Indica la cartella della SD (es. E:\\) e premi Scansiona.",
                                  bg=PANEL, fg=SUB, justify="left", anchor="w", font=("Segoe UI", 9), wraplength=680)
        self.sd_status.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))
        actions = ttk.Frame(sdp, style="Panel.TFrame")
        actions.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.sd_btn_struct = ttk.Button(actions, text="📁  Crea cartella samples/", command=self.do_create_structure)
        self.sd_btn_format = ttk.Button(actions, text="⚠  Formatta e prepara (FAT32)",
                                        style="Danger.TButton", command=self.do_format)
        self._show_sd_actions(struct=False, fmt=False)

        # ---------- destination options (mode-specific) ----------
        opt = ttk.Frame(self, style="Panel.TFrame", padding=12)
        opt.pack(fill="x", padx=18, pady=(0, 6))
        opt.columnconfigure(3, weight=1)

        # pack mode controls
        self.pack_lbl = ttk.Label(opt, text="Numero pack (0-99):", style="Panel.TLabel")
        self.pack_var = tk.IntVar(value=1)
        self.pack_sp = ttk.Spinbox(opt, from_=0, to=MAX_PACK, textvariable=self.pack_var, width=6,
                                   command=self._refresh_targets)
        self.pack_sp.bind("<KeyRelease>", lambda e: self._refresh_targets())

        # browser mode controls
        self.cat_lbl = ttk.Label(opt, text="Categoria:", style="Panel.TLabel")
        self.cat_var = tk.StringVar(value="kick")
        self.cat_cb = ttk.Combobox(opt, textvariable=self.cat_var, values=CATEGORIES, width=14)
        self.cat_cb.bind("<KeyRelease>", lambda e: self._refresh_targets())
        self.cat_cb.bind("<<ComboboxSelected>>", lambda e: self._refresh_targets())

        # common: write to local folder instead of the SD
        self.local_mode_var = tk.BooleanVar(value=False)
        self.local_chk = ttk.Checkbutton(opt, text="Scrivi in una cartella locale invece che sulla SD",
                                         variable=self.local_mode_var, command=self._on_dest_change)
        self.out_var = tk.StringVar(value="")
        self.out_entry = ttk.Entry(opt, textvariable=self.out_var)
        self.out_btn = ttk.Button(opt, text="Sfoglia…", command=self.pick_output)
        self.delete_var = tk.BooleanVar(value=False)
        self.delete_chk = ttk.Checkbutton(opt, text="Elimina gli originali dopo la conversione (attenzione!)",
                                         variable=self.delete_var)

        # grid placement
        self.pack_lbl.grid(row=0, column=0, sticky="w")
        self.pack_sp.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.cat_lbl.grid(row=0, column=0, sticky="w")
        self.cat_cb.grid(row=0, column=1, sticky="w", padx=(10, 0))
        self.target_lbl = ttk.Label(opt, text="", style="PanelSub.TLabel", justify="left")
        self.target_lbl.grid(row=1, column=0, columnspan=4, sticky="w", pady=(10, 0))
        self.local_chk.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.out_entry.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 6), pady=(4, 0))
        self.out_btn.grid(row=3, column=3, sticky="w", pady=(4, 0))
        self.delete_chk.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 0))

        # action + progress
        act = ttk.Frame(self, padding=(18, 4, 18, 4))
        act.pack(fill="x")
        self.convert_btn = ttk.Button(act, text="🎶  Converti", style="Accent.TButton", command=self.start_convert)
        self.convert_btn.pack(side="left")
        self.pbar = ttk.Progressbar(act, style="green.Horizontal.TProgressbar", mode="determinate")
        self.pbar.pack(side="left", fill="x", expand=True, padx=12)
        self.status = ttk.Label(act, text="Pronto", style="Sub.TLabel")
        self.status.pack(side="right")

        # log
        logf = ttk.Frame(self, padding=(18, 0, 18, 12))
        logf.pack(fill="both")
        self.log = tk.Text(logf, height=6, bg="#0b0f14", fg=SUB, insertbackground=INK,
                           relief="flat", font=("Consolas", 9), wrap="none")
        self.log.pack(fill="both", expand=True)
        self.log.configure(state="disabled")

    # ---- helpers ----
    def _log(self, msg, color=None):
        self.log.configure(state="normal")
        if color:
            tag = f"c{color}"
            self.log.tag_configure(tag, foreground=color)
            self.log.insert("end", msg + "\n", tag)
        else:
            self.log.insert("end", msg + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _default_output(self):
        if self.items:
            return os.path.dirname(self.items[0]["path"])
        return os.path.join(os.path.expanduser("~"), "Desktop", "ichosynth_sd")

    def _on_mode_change(self):
        pack = self.mode_var.get() == "pack"
        if pack:
            self.pack_lbl.grid()
            self.pack_sp.grid()
            self.cat_lbl.grid_remove()
            self.cat_cb.grid_remove()
            self.tree.heading("slot", text="VOCE")
        else:
            self.pack_lbl.grid_remove()
            self.pack_sp.grid_remove()
            self.cat_lbl.grid()
            self.cat_cb.grid()
            self.tree.heading("slot", text="#")
        self._refresh_targets()

    def _on_dest_change(self):
        st = "normal" if self.local_mode_var.get() else "disabled"
        self.out_entry.configure(state=st)
        self.out_btn.configure(state=st)
        if self.local_mode_var.get() and not self.out_var.get():
            self.out_var.set(self._default_output())
        self._refresh_targets()

    def _dest_root(self):
        """Return (root, mode) where mode is 'sd' | 'local' | 'none'."""
        if self.local_mode_var.get():
            return (self.out_var.get().strip() or self._default_output()), "local"
        if self.sd_root:
            return self.sd_root, "sd"
        return None, "none"

    def _refresh_targets(self):
        root, mode = self._dest_root()
        is_pack = self.mode_var.get() == "pack"
        # header line
        if mode == "none":
            self.target_lbl.configure(text="🎯  Scansiona una SD oppure scegli una cartella locale qui sotto.")
        else:
            where = "sulla SD" if mode == "sd" else f"in  {root}"
            if is_pack:
                try:
                    pk = int(self.pack_var.get())
                except (tk.TclError, ValueError):
                    pk = 0
                note = "  (pack 0 = kit di fabbrica)" if pk == 0 else ""
                self.target_lbl.configure(text=f"🎯  Scrivo {where}  →  {pk}/1.wav … {pk}/8.wav{note}")
            else:
                cat = sanitize_category(self.cat_var.get())
                self.target_lbl.configure(text=f"🎯  Scrivo {where}  →  {SD_BROWSER_DIR}/{cat}/<nome>.wav"
                                               f"  (nomi ≤ {BROWSER_NAME_MAX} caratteri)")
        # per-row destination + slot
        try:
            pk = int(self.pack_var.get())
        except (tk.TclError, ValueError):
            pk = 0
        cat = sanitize_category(self.cat_var.get())
        names = browser_names([it["path"] for it in self.items])
        for i, iid in enumerate(self.tree.get_children()):
            tags = list(self.tree.item(iid, "tags"))
            tags = [t for t in tags if t != "over"]
            if is_pack:
                if i < MAX_VOICES:
                    self.tree.set(iid, "slot", f"{i+1} · {VOICE_LABELS[i]}")
                    self.tree.set(iid, "dst", f"{pk}/{i+1}.wav")
                else:
                    self.tree.set(iid, "slot", "—")
                    self.tree.set(iid, "dst", "(ignorato: max 8)")
                    tags.append("over")
            else:
                self.tree.set(iid, "slot", str(i + 1))
                self.tree.set(iid, "dst", f"{SD_BROWSER_DIR}/{cat}/{names[i]}")
            self.tree.item(iid, tags=tuple(tags))
        self.count_lbl.configure(text=f"{len(self.items)} file")

    def _add_paths(self, paths):
        existing = {it["path"] for it in self.items}
        added = 0
        for p in paths:
            if not p.lower().endswith(".wav") or p in existing:
                continue
            fmt = read_format(p)
            self.items.append({"path": p, "fmt": fmt})
            tags = ("ok",) if is_target(fmt) else ()
            self.tree.insert("", "end", values=("", os.path.basename(p), fmt_label(fmt), "→", ""), tags=tags)
            existing.add(p)
            added += 1
        if added:
            self._refresh_targets()

    # ---- file actions ----
    def add_files(self):
        paths = filedialog.askopenfilenames(title="Scegli i file WAV",
                                            filetypes=[("File WAV", "*.wav"), ("Tutti i file", "*.*")])
        self._add_paths(list(paths))

    def add_folder(self):
        d = filedialog.askdirectory(title="Scegli una cartella con WAV")
        if d:
            self._add_paths([os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(".wav")])

    def remove_selected(self):
        sel = set(self.tree.selection())
        if not sel:
            return
        keep, kept_iids = [], []
        for iid, it in zip(self.tree.get_children(), self.items):
            if iid not in sel:
                keep.append(it)
                kept_iids.append(iid)
        for iid in sel:
            self.tree.delete(iid)
        self.items = keep
        self._refresh_targets()

    def move_selected(self, delta):
        sel = self.tree.selection()
        if len(sel) != 1:
            return
        iids = list(self.tree.get_children())
        i = iids.index(sel[0])
        j = i + delta
        if j < 0 or j >= len(iids):
            return
        self.items[i], self.items[j] = self.items[j], self.items[i]
        # rebuild rows preserving format/tags
        self._rebuild_rows(select_index=j)

    def _rebuild_rows(self, select_index=None):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        new_iids = []
        for it in self.items:
            tags = ("ok",) if is_target(it["fmt"]) else ()
            iid = self.tree.insert("", "end", values=("", os.path.basename(it["path"]),
                                                       fmt_label(it["fmt"]), "→", ""), tags=tags)
            new_iids.append(iid)
        self._refresh_targets()
        if select_index is not None and 0 <= select_index < len(new_iids):
            self.tree.selection_set(new_iids[select_index])

    def clear_all(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items = []
        self._refresh_targets()

    def pick_output(self):
        d = filedialog.askdirectory(title="Cartella di destinazione locale (radice della SD)")
        if d:
            self.out_var.set(d)
            self.local_mode_var.set(True)
            self._on_dest_change()

    # =====================================================================
    # SD card (scan / structure / format)
    # =====================================================================
    def pick_sd(self):
        d = filedialog.askdirectory(title="Scegli la scheda SD (la sua radice, es. E:\\)")
        if d:
            self.sd_path_var.set(d)

    def _run_sd_async(self, fn, on_done):
        self._sd_inflight += 1

        def runner():
            try:
                res = ("ok", fn())
            except Exception as e:
                res = ("err", e)
            self.sdq.put((on_done, res))
        threading.Thread(target=runner, daemon=True).start()
        if self._sd_inflight == 1:
            self.after(80, self._poll_sd)

    def _poll_sd(self):
        try:
            while True:
                on_done, res = self.sdq.get_nowait()
                self._sd_inflight -= 1
                try:
                    on_done(res)
                except Exception as e:
                    self._log(f"  ✗ errore interno: {e}", RED)
        except queue.Empty:
            pass
        if self._sd_inflight > 0:
            self.after(120, self._poll_sd)

    def _sd_busy(self, msg):
        self.sd_scan_btn.configure(state="disabled")
        self.sd_btn_struct.configure(state="disabled")
        self.sd_btn_format.configure(state="disabled")
        self.sd_status.configure(text=msg, fg=SUB)

    def _sd_idle(self):
        self.sd_scan_btn.configure(state="normal")
        self.sd_btn_struct.configure(state="normal")
        self.sd_btn_format.configure(state="normal")

    def _show_sd_actions(self, struct, fmt):
        for w in (self.sd_btn_struct, self.sd_btn_format):
            w.pack_forget()
        if struct:
            self.sd_btn_struct.pack(side="left", padx=(0, 8))
        if fmt:
            self.sd_btn_format.pack(side="left", padx=(0, 8))

    def scan_sd(self):
        path = self.sd_path_var.get().strip()
        if not path:
            messagebox.showinfo("Percorso mancante", "Indica prima la cartella della SD (es. E:\\).")
            return
        self._sd_busy("Scansione in corso…")
        self._log(f"--- scansione SD: {path} ---", ACCENT2)

        def work():
            info = volume_info(path)
            root = (info["letter"] + ":\\") if info["letter"] else path
            scan = scan_sd_layout(root) if os.path.isdir(root) else None
            return root, info, scan
        self._run_sd_async(work, self._after_scan)

    def _after_scan(self, result):
        self._sd_idle()
        kind, payload = result
        if kind == "err":
            self.sd_status.configure(text=f"Errore durante la scansione: {payload}", fg=RED)
            self.sd_info = None          # never format on the basis of a failed scan
            self._show_sd_actions(False, False)
            return
        root, info, scan = payload
        self.sd_info = info
        self.sd_scan = scan
        self._render_sd(root, info, scan)

    def _render_sd(self, root, info, scan):
        letter = info.get("letter")
        fs = info.get("fs")
        head = (f"Unità {letter}:  ·  {info.get('label') or '(senza etichetta)'}  ·  "
                f"{human_size(info.get('size'))} ({human_size(info.get('free'))} liberi)  ·  "
                f"{info.get('drive_type') or '?'}")
        if info.get("disk_number") is not None:
            head += (f"\nDisco {info['disk_number']}: {info.get('disk_model') or '?'}  ·  "
                     f"bus {info.get('bus_type') or '?'}  ·  {human_size(info.get('disk_size'))}  ·  "
                     f"{info.get('partitions') or '?'} partizioni")
        fs_s = fs or "non rilevato"
        readable = info.get("readable")
        compatible = fs_is_compatible(fs) if IS_WIN else readable
        # the format button is offered ONLY for removable SD media (never fixed/system disks)
        fmt_block = format_block_reason(info) if IS_WIN else "non Windows"

        if IS_WIN and (not readable or fs is None or not compatible):
            reason = ("filesystem non rilevato (probabilmente non formattata)"
                      if not fs else f"filesystem «{fs_s}» non compatibile col Teensy")
            if fmt_block is None:
                hint = "Serve formattarla FAT32. Usa «Formatta e prepara»."
            else:
                hint = (f"Formattazione da qui disabilitata: {fmt_block}\n"
                        "Se è davvero la SD del synth, formattala FAT32 da Esplora risorse.")
            self.sd_status.configure(
                text=f"{head}\nFilesystem: {fs_s}\n⚠  {reason}.\n{hint}", fg=WARN)
            self._show_sd_actions(struct=False, fmt=fmt_block is None)
            self._clear_sd_mode()
            self._log(f"  ⚠ SD non pronta: {reason}", WARN)
            return

        packs = scan["packs"] if scan else {}
        nxt = scan["next_pack"] if scan else 1
        if packs:
            pk_desc = ", ".join(f"{p}({v}/8)" for p, v in sorted(packs.items())[:12])
            packline = f"✓  Samplepack presenti: {pk_desc}"
        else:
            packline = "·  Nessun samplepack (verrà creato al primo «Converti»)"
        if scan and scan["browser_files"]:
            cats = ", ".join(f"{c}:{n}" for c, n in sorted(scan["browser_cats"].items())[:8])
            brline = f"✓  Libreria browser: {scan['browser_files']} file ({cats})"
        else:
            brline = "·  Libreria browser vuota"
        self.sd_status.configure(
            text=(f"{head}\nFilesystem: {fs_s}  ✓\n{packline}\n{brline}\n"
                  f"▶  Prossimo pack libero: {nxt}"), fg=ACCENT)
        self._set_sd_mode(root, nxt)
        self._show_sd_actions(struct=True, fmt=fmt_block is None)
        self._log(f"  ✓ SD pronta. Prossimo pack libero: {nxt}", ACCENT)

    def _set_sd_mode(self, root, next_pack):
        self.sd_root = root
        try:
            self.deduced_pack = int(next_pack)
        except Exception:
            self.deduced_pack = 1
        if self.mode_var.get() == "pack":
            self.pack_var.set(self.deduced_pack)
        self.local_mode_var.set(False)
        self._on_dest_change()

    def _clear_sd_mode(self):
        self.sd_root = None
        self._refresh_targets()

    def do_create_structure(self):
        root = self._current_sd_root()
        if not root:
            return
        self._sd_busy("Creazione cartella samples/…")
        self._run_sd_async(lambda: ensure_browser_dir(root), self._after_structure)

    def _after_structure(self, result):
        self._sd_idle()
        kind, payload = result
        if kind == "err":
            messagebox.showerror("Errore", f"Impossibile creare la struttura:\n{payload}")
            return
        self._log("  ✓ cartella samples/ pronta", ACCENT)
        self.scan_sd()

    def _current_sd_root(self):
        path = self.sd_path_var.get().strip()
        letter = drive_letter_of(path)
        if not path:
            messagebox.showinfo("Percorso mancante", "Indica prima la cartella della SD.")
            return None
        return (letter + ":\\") if letter else path

    def do_format(self):
        if not IS_WIN:
            messagebox.showinfo("Solo Windows",
                                "La formattazione automatica è disponibile solo su Windows.\n"
                                "Su macOS/Linux formatta la SD in FAT32 a mano.")
            return
        scanned = self.sd_info
        path = self.sd_path_var.get().strip()
        letter = drive_letter_of(path)
        if not letter:
            messagebox.showerror("Percorso non valido",
                                 "Indica una cartella su una scheda SD con lettera di unità (es. E:\\).")
            return
        if not scanned or scanned.get("letter") != letter:
            messagebox.showinfo("Scansiona prima",
                                f"Premi prima «Scansiona» sull'unità {letter}: — formatto solo la scheda "
                                "appena scansionata.")
            return
        why = format_block_reason(scanned)
        if why:
            messagebox.showerror("Operazione bloccata", why)
            return
        # re-query the volume right now: the card may have been swapped since the scan
        self._sd_busy("Verifico la scheda…")
        self._run_sd_async(lambda: volume_info(path), lambda res: self._format_checked(scanned, res))

    def _format_checked(self, scanned, result):
        self._sd_idle()
        kind, fresh = result
        if kind == "err":
            messagebox.showerror("Operazione bloccata", f"Non riesco a rileggere l'unità:\n{fresh}")
            return
        letter = fresh.get("letter")
        if not same_volume(scanned, fresh):
            self.sd_info = None
            self._show_sd_actions(False, False)
            messagebox.showerror("Scheda cambiata",
                                 f"L'unità {letter}: non è più quella scansionata "
                                 "(dimensione/etichetta/seriale/disco diversi).\nRifai «Scansiona».")
            return
        why = format_block_reason(fresh)
        if why:
            messagebox.showerror("Operazione bloccata", why)
            return
        proceed, deep = self._confirm_format(letter, fresh)
        if not proceed:
            return
        why = format_block_reason(fresh, deep=deep)
        if why:
            messagebox.showerror("Operazione bloccata", why)
            return
        self._sd_busy("Formattazione FAT32 in corso… (non rimuovere la scheda)")
        self._log(f"--- formattazione {letter}: (disco {fresh.get('disk_number')}) in FAT32"
                  f"{' (ripulitura completa)' if deep else ''} ---", WARN)
        self._run_sd_async(lambda: format_fat32(fresh, deep=deep), self._after_format)

    def _confirm_format(self, letter, info):
        win = tk.Toplevel(self.master)
        win.title("Conferma formattazione")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.master)
        result = {"proceed": False, "deep": False}
        frm = ttk.Frame(win, padding=20)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="⚠  Formattazione scheda SD", style="Title.TLabel").pack(anchor="w")
        parts = []
        for p in info.get("part_list") or []:
            if isinstance(p, dict):
                lt = (p.get("Letter") or "").strip()
                parts.append(f"   · {lt + ':' if lt else '(senza lettera)'}  {human_size(p.get('Size'))}"
                             f"  {p.get('Type') or ''}")
        ttk.Label(frm, text=(f"Unità {letter}:  ·  {info.get('label') or '(senza etichetta)'}  ·  "
                             f"{info.get('fs') or 'filesystem ?'}  ·  {human_size(info.get('size'))}  ·  "
                             f"tipo: {info.get('drive_type') or '?'}\n"
                             f"Disco {info.get('disk_number')}: {info.get('disk_model') or '?'}  ·  "
                             f"bus {info.get('bus_type') or '?'}  ·  {human_size(info.get('disk_size'))}\n"
                             f"Partizioni sul disco: {info.get('partitions') or '?'}\n" + "\n".join(parts)),
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(6, 12))
        tk.Label(frm, text=(f"Verranno CANCELLATI TUTTI i dati sull'unità {letter}:\n"
                            "e la scheda sarà formattata FAT32.\nL'operazione è IRREVERSIBILE."),
                 bg=BG, fg=RED, justify="left", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 12))
        deep_var = tk.BooleanVar(value=False)
        deep_block = format_block_reason(info, deep=True)
        ttk.Checkbutton(frm, variable=deep_var,
                        state="disabled" if deep_block else "normal",
                        text=(f"Ripulisci tutto il disco {info.get('disk_number')} (ripartiziona) — avanzato")
                        ).pack(anchor="w")
        if deep_block:
            ttk.Label(frm, text=f"   (non disponibile: {deep_block})", style="Sub.TLabel",
                      wraplength=520, justify="left").pack(anchor="w")
        ack_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, variable=ack_var, text=f"Ho capito: cancella tutto su {letter}:").pack(anchor="w", pady=(8, 14))
        btns = ttk.Frame(frm)
        btns.pack(fill="x")
        go = ttk.Button(btns, text=f"Formatta {letter}:", style="Danger.TButton", state="disabled",
                        command=lambda: (result.update(proceed=True, deep=deep_var.get()), win.destroy()))
        go.pack(side="right")
        ttk.Button(btns, text="Annulla", command=win.destroy).pack(side="right", padx=(0, 8))
        ack_var.trace_add("write", lambda *_: go.configure(state="normal" if ack_var.get() else "disabled"))
        win.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        win.grab_set()
        win.focus_set()
        self.master.wait_window(win)
        return result["proceed"], result["deep"]

    def _after_format(self, result):
        self._sd_idle()
        kind, payload = result
        if kind == "err":
            messagebox.showerror("Formattazione non riuscita", str(payload))
            self.sd_status.configure(text=f"Formattazione non riuscita: {payload}", fg=RED)
            return
        ok, info = payload
        if not ok:
            messagebox.showerror("Formattazione non riuscita", info)
            self.sd_status.configure(text=f"Formattazione non riuscita: {info}", fg=RED)
            self._log(f"  ✗ {info}", RED)
            return
        new_letter = info
        self._log(f"  ✓ formattata. Preparo {new_letter}:\\", ACCENT)
        root = new_letter + ":\\"
        self.sd_path_var.set(root)
        try:
            ensure_browser_dir(root)
        except Exception as e:
            messagebox.showwarning("Struttura", f"Formattata, ma non sono riuscito a creare samples/:\n{e}")
        messagebox.showinfo("Fatto", f"Scheda {new_letter}: formattata FAT32 e pronta.")
        self.scan_sd()

    # ---- about ----
    def show_about(self):
        win = tk.Toplevel(self.master)
        win.title("Informazioni")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.master)
        frm = ttk.Frame(win, padding=22)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="🎵  ichosynth — WAV Maker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frm, text=f"Versione {APP_VERSION}", style="Sub.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Label(frm, text="Sviluppato da", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(frm, text=APP_AUTHOR, style="H2.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(frm, text=("Prepara i campioni per il firmware TŒRN:\n"
                             "li converte in mono · 16-bit · 44100 Hz e li scrive come\n"
                             "samplepack (<pack>/1-8.wav) o nella libreria browser\n"
                             "(samples/<categoria>/<nome>.wav). Prepara anche la SD (FAT32)."),
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(0, 12))
        link = tk.Label(frm, text=REPO_URL.replace("https://", ""), bg=BG, fg=ACCENT2,
                        cursor="hand2", font=("Segoe UI", 9, "underline"))
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))
        ttk.Label(frm, text="Parte del progetto ichosynth · un TŒRN (SP_) su hardware DIY · licenza MIT",
                  style="Sub.TLabel").pack(anchor="w", pady=(12, 16))
        ttk.Button(frm, text="Chiudi", command=win.destroy).pack(anchor="e")
        win.update_idletasks()
        px, py = self.master.winfo_rootx(), self.master.winfo_rooty()
        pw, ph = self.master.winfo_width(), self.master.winfo_height()
        w, h = win.winfo_width(), win.winfo_height()
        win.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 3}")
        win.grab_set()
        win.focus_set()

    # ---- conversion (threaded) ----
    def _build_jobs(self):
        """Return (jobs, base_desc) or (None, error_message)."""
        root, mode = self._dest_root()
        if mode == "none":
            return None, ("Scansiona prima una scheda SD, oppure attiva «Scrivi in una cartella locale».")
        if mode == "local":
            try:
                os.makedirs(root, exist_ok=True)
            except Exception as e:
                return None, f"Cartella non scrivibile:\n{e}"

        jobs = []
        if self.mode_var.get() == "pack":
            try:
                pk = int(self.pack_var.get())
            except (tk.TclError, ValueError):
                return None, "Numero pack non valido."
            if not (0 <= pk <= MAX_PACK):
                return None, "Il numero del pack deve essere tra 0 e 99."
            if len(self.items) > MAX_VOICES:
                if not messagebox.askyesno("Troppi file",
                                           f"Un pack ha 8 voci ma hai {len(self.items)} file.\n"
                                           "Userò solo i primi 8 (le voci 1-8). Procedo?"):
                    return None, "__cancel__"
            dst_dir = os.path.join(root, str(pk))
            for i, it in enumerate(self.items[:MAX_VOICES], start=1):
                jobs.append((it["path"], os.path.join(dst_dir, f"{i}.wav")))
            base_desc = f"{pk}/ (voci 1-{len(jobs)})"
        else:
            cat = sanitize_category(self.cat_var.get())
            dst_dir = os.path.join(root, SD_BROWSER_DIR, cat)
            names = browser_names([it["path"] for it in self.items])
            for it, nm in zip(self.items, names):
                jobs.append((it["path"], os.path.join(dst_dir, nm)))
            base_desc = f"{SD_BROWSER_DIR}/{cat}/"
            # the firmware lists at most 256 WAVs per folder
            try:
                have = {f.lower() for f in os.listdir(dst_dir) if f.lower().endswith(".wav")}
            except OSError:
                have = set()
            total = len(have | {nm.lower() for nm in names})
            if total > BROWSER_MAX_FILES:
                if not messagebox.askyesno(
                        "Troppi file nella cartella",
                        f"{SD_BROWSER_DIR}/{cat}/ avrebbe {total} WAV, ma il firmware ne mostra al "
                        f"massimo {BROWSER_MAX_FILES} per cartella: gli altri non saranno visibili.\n\n"
                        "Meglio dividerli in più categorie. Procedo comunque?", icon="warning"):
                    return None, "__cancel__"
        return jobs, base_desc

    def start_convert(self):
        if not self.items:
            messagebox.showinfo("Niente da fare", "Aggiungi prima qualche file WAV.")
            return
        jobs, info = self._build_jobs()
        if jobs is None:
            if info != "__cancel__":
                messagebox.showinfo("Destinazione", info)
            return
        # warn on overwrite
        existing = [d for _s, d in jobs if os.path.exists(d)]
        if existing:
            if not messagebox.askyesno("Sovrascrivo?",
                                       f"{len(existing)} file esistenti verranno sovrascritti.\nProcedo?"):
                return
        if self.delete_var.get():
            if not messagebox.askyesno("Confermi?", "Eliminerò gli ORIGINALI dopo la conversione.\nProcedo?"):
                return
        delete = self.delete_var.get()
        self._last_out = os.path.dirname(jobs[0][1])
        self._njobs = len(jobs)
        self.convert_btn.configure(state="disabled")
        self.pbar.configure(maximum=len(jobs) + 1, value=0)
        self._log(f"--- conversione di {len(jobs)} file → {info} ---", ACCENT2)
        self.worker = threading.Thread(target=self._worker, args=(jobs, delete), daemon=True)
        self.worker.start()
        self.after(80, self._poll)

    def _worker(self, jobs, delete):
        # phase 1: convert EVERY source into a temp file next to its destination,
        # before any destination is touched (a destination may be a later source,
        # e.g. voices swapped inside a pack that is already on the SD)
        staged, written = [], []
        try:
            for src, dst in jobs:
                name = os.path.basename(src)
                try:
                    staged.append((src, dst, stage_convert(src, dst)))
                except Exception as e:
                    self.q.put(("err", f"  ✗ {name}: {e}"))
                self.q.put(("tick", None))
            # phase 2: move the converted files into place
            for src, dst, tmp in staged:
                try:
                    os.replace(tmp, dst)
                    written.append((src, dst))
                    self.q.put(("ok", f"  ✓ {os.path.basename(src)}  →  {os.path.basename(dst)}"))
                except Exception as e:
                    self.q.put(("err", f"  ✗ {os.path.basename(src)}: {e}"))
        finally:
            for _s, _d, tmp in staged:
                if os.path.exists(tmp):
                    try:
                        os.remove(tmp)
                    except OSError:
                        pass
        # phase 3: delete originals — never a file that is (now) one of the outputs
        if delete:
            outputs = [d for _s, d in written]
            for src, _dst in written:
                if any(same_path(src, d) for d in outputs):
                    continue
                try:
                    os.remove(src)
                except OSError as e:
                    self.q.put(("err", f"  ✗ non ho eliminato {os.path.basename(src)}: {e}"))
        self.q.put(("tick", None))
        self.q.put(("finish", len(written)))

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "tick":
                    self.pbar.configure(value=min(float(self.pbar["value"]) + 1, float(self.pbar["maximum"])))
                elif kind == "ok":
                    self._log(payload, ACCENT)
                elif kind == "err":
                    self._log(payload, RED)
                elif kind == "finish":
                    self.status.configure(text=f"Fatto: {payload}/{self._njobs}")
                    self._log(f"--- completato: {payload} file convertiti ---", ACCENT2)
                    self.convert_btn.configure(state="normal")
                    messagebox.showinfo("Completato", f"{payload} file convertiti in:\n{self._last_out}")
                    return
        except queue.Empty:
            pass
        self.status.configure(text=f"Converto… {min(int(float(self.pbar['value'])), self._njobs)}/{self._njobs}")
        self.after(80, self._poll)


def main():
    root = tk.Tk()
    root.geometry("820x800")
    app = WavMakerApp(root)
    if "--selftest" in sys.argv:
        root.after(300, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
