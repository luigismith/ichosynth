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
                  voice-by-voice in SET_WAV (names are kept, just tidied).

Features:
- pick individual files or a whole folder; see each file's current format and
  its destination before converting
- prepare an SD card: scan it (detect packs + browser library), and on Windows
  format it FAT32 / create the samples/ folder
- progress bar + log; conversion runs off the UI thread

Pure standard library — the WAV converter is hand-rolled (no ffmpeg, no audioop),
so it works on any Python 3.8+ including 3.13/3.14 where audioop was removed.
SD scan/format on Windows shell out to PowerShell.

Run:  python wavmaker_gui.py      (or launch the bundled wavmaker.exe)
"""
import io
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
def _iter_chunks(b):
    pos, n = 12, len(b)
    while pos + 8 <= n:
        cid = b[pos:pos + 4]
        size = struct.unpack("<I", b[pos + 4:pos + 8])[0]
        yield cid, b[pos + 8:pos + 8 + size]
        pos += 8 + size + (size & 1)


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


def decode_wav(b):
    info = _parse_fmt(b)
    if not info:
        raise ValueError("not a RIFF/WAVE file")
    tag, ch, rate, bits, _db = info
    data = None
    for cid, body in _iter_chunks(b):
        if cid == b"data":
            data = body
    if data is None:
        raise ValueError("missing data chunk")
    nbytes = bits // 8
    frame = nbytes * ch
    if frame == 0:
        raise ValueError("bad fmt")
    nframes = len(data) // frame

    if tag == 3:
        if bits == 32:
            rd = lambda o: struct.unpack_from("<f", data, o)[0]
        elif bits == 64:
            rd = lambda o: struct.unpack_from("<d", data, o)[0]
        else:
            raise ValueError("float bits %d" % bits)
    elif tag == 1:
        if bits == 8:
            rd = lambda o: (data[o] - 128) / 128.0
        elif bits == 16:
            rd = lambda o: struct.unpack_from("<h", data, o)[0] / 32768.0
        elif bits == 24:
            def rd(o):
                v = data[o] | (data[o + 1] << 8) | (data[o + 2] << 16)
                return (v - 0x1000000 if v & 0x800000 else v) / 8388608.0
        elif bits == 32:
            rd = lambda o: struct.unpack_from("<i", data, o)[0] / 2147483648.0
        else:
            raise ValueError("pcm bits %d" % bits)
    else:
        raise ValueError("format tag %d" % tag)

    mono = [0.0] * nframes
    inv = 1.0 / ch
    for i in range(nframes):
        base = i * frame
        acc = 0.0
        for c in range(ch):
            acc += rd(base + c * nbytes)
        mono[i] = acc * inv
    return rate, mono


def resample(mono, src_rate, dst_rate):
    if src_rate == dst_rate or not mono:
        return mono
    out_n = max(1, int(round(len(mono) * dst_rate / src_rate)))
    out = [0.0] * out_n
    step = src_rate / dst_rate
    pos = 0.0
    last = len(mono) - 1
    for i in range(out_n):
        idx = int(pos)
        if idx >= last:
            out[i] = mono[last]
        else:
            frac = pos - idx
            out[i] = mono[idx] * (1.0 - frac) + mono[idx + 1] * frac
        pos += step
    return out


def encode_wav_mono16(mono):
    pcm = bytearray(len(mono) * 2)
    for i, v in enumerate(mono):
        v = 1.0 if v > 1.0 else (-1.0 if v < -1.0 else v)
        struct.pack_into("<h", pcm, i * 2, int(round(v * 32767.0)))
    db = len(pcm)
    o = io.BytesIO()
    o.write(b"RIFF"); o.write(struct.pack("<I", 36 + db)); o.write(b"WAVE")
    o.write(b"fmt "); o.write(struct.pack("<IHHIIHH", 16, 1, 1, TARGET_RATE, TARGET_RATE * 2, 2, 16))
    o.write(b"data"); o.write(struct.pack("<I", db)); o.write(pcm)
    return o.getvalue()


def convert_file(src, dst):
    """Convert src WAV to mono/16-bit/44100, write to dst (atomic)."""
    with open(src, "rb") as f:
        rate, mono = decode_wav(f.read())
    out = encode_wav_mono16(resample(mono, rate, TARGET_RATE))
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    tmp = dst + ".tmp"
    with open(tmp, "wb") as f:
        f.write(out)
    os.replace(tmp, dst)


def sanitize_name(basename):
    """Turn a source filename into a tidy browser name (keeps it readable)."""
    name = os.path.splitext(os.path.basename(basename))[0]
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9._-]+", "-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-._")
    return (name or "sample") + ".wav"


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


def volume_info(path):
    info = {"letter": drive_letter_of(path), "fs": None, "drive_type": None,
            "size": None, "free": None, "label": None,
            "removable": None, "system": False, "readable": False}
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
        r = _ps(f"Get-Volume -DriveLetter {info['letter']} -ErrorAction SilentlyContinue | "
                f"Select-Object FileSystemType,DriveType,Size,SizeRemaining,FileSystemLabel | "
                f"ConvertTo-Json -Compress")
        if r and r.returncode == 0 and r.stdout.strip():
            try:
                d = json.loads(r.stdout)
                info["fs"] = d.get("FileSystemType")
                info["drive_type"] = d.get("DriveType")
                dt = str(d.get("DriveType") or "").lower()
                info["removable"] = (dt == "removable") if dt else None
                if d.get("Size"):
                    info["size"] = int(d["Size"])
                if d.get("SizeRemaining") is not None:
                    info["free"] = int(d["SizeRemaining"])
                info["label"] = d.get("FileSystemLabel")
            except Exception:
                pass
    return info


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


def format_fat32(letter, label=FORMAT_LABEL, deep=False):
    if not IS_WIN:
        return False, "La formattazione automatica è disponibile solo su Windows."
    letter = letter.upper()
    sysdrive = os.environ.get("SystemDrive", "C:")[0].upper()
    if letter == sysdrive:
        return False, "Rifiuto: è l'unità di sistema."
    if not deep:
        r = _ps(f"Format-Volume -DriveLetter {letter} -FileSystem FAT32 "
                f"-NewFileSystemLabel '{label}' -Force -Confirm:$false -ErrorAction Stop", timeout=300)
        new_letter = letter
    else:
        script = (
            f"$ErrorActionPreference='Stop'; "
            f"$p = Get-Partition -DriveLetter {letter}; "
            f"$d = $p | Get-Disk; "
            f"if (-not ($d.BusType -eq 'USB' -or $d.BusType -eq 'SD' -or $d.IsRemovable)) "
            f"{{ throw 'Disco non rimovibile: operazione annullata per sicurezza.' }} "
            f"Clear-Disk -Number $d.Number -RemoveData -RemoveOEM -Confirm:$false; "
            f"Initialize-Disk -Number $d.Number -PartitionStyle MBR -ErrorAction SilentlyContinue | Out-Null; "
            f"$np = New-Partition -DiskNumber $d.Number -UseMaximumSize -AssignDriveLetter; "
            f"Start-Sleep -Milliseconds 800; "
            f"Format-Volume -DriveLetter $np.DriveLetter -FileSystem FAT32 "
            f"-NewFileSystemLabel '{label}' -Force -Confirm:$false | Out-Null; "
            f"Write-Output ('NEWLETTER=' + $np.DriveLetter)")
        r = _ps(script, timeout=480)
        new_letter = letter
    if r is None:
        return False, "Impossibile avviare PowerShell."
    out = (r.stdout or "") + "\n" + (r.stderr or "")
    low = out.lower()
    err = (r.stderr or "").lower()
    ok = (r.returncode == 0 and "exception" not in err and "error" not in err
          and "throw" not in err and "denied" not in low)
    if ok:
        m = re.search(r"NEWLETTER=([A-Za-z])", out)
        if m:
            new_letter = m.group(1).upper()
        return True, new_letter
    if "denied" in low or "administrator" in low or "negato" in low or "amministrat" in low:
        return False, ("Accesso negato: serve eseguire l'app come Amministratore "
                       "(clic destro sull'app → «Esegui come amministratore»).")
    if "fat32" in low and ("too big" in low or "size" in low or "grande" in low or "32" in low):
        return False, ("Windows non crea FAT32 oltre 32 GB. Usa una scheda ≤ 32 GB "
                       "(o formatta exFAT manualmente da Esplora risorse).")
    msg = (r.stderr or r.stdout or "Formattazione non riuscita.").strip()
    return False, msg[:400] if msg else "Formattazione non riuscita."


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
                cat = (self.cat_var.get().strip() or "perc")
                self.target_lbl.configure(text=f"🎯  Scrivo {where}  →  {SD_BROWSER_DIR}/{cat}/<nome>.wav")
        # per-row destination + slot
        try:
            pk = int(self.pack_var.get())
        except (tk.TclError, ValueError):
            pk = 0
        cat = (self.cat_var.get().strip() or "perc")
        seen = {}
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
                nm = sanitize_name(self.items[i]["path"])
                # de-dup within this batch
                key = (cat, nm.lower())
                if key in seen:
                    seen[key] += 1
                    nm = f"{nm[:-4]}-{seen[key]}.wav"
                else:
                    seen[key] = 1
                self.tree.set(iid, "dst", f"{SD_BROWSER_DIR}/{cat}/{nm}")
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
            self._show_sd_actions(False, IS_WIN)
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
        fs_s = fs or "non rilevato"
        readable = info.get("readable")
        compatible = fs_is_compatible(fs) if IS_WIN else readable

        if IS_WIN and (not readable or fs is None or not compatible):
            reason = ("filesystem non rilevato (probabilmente non formattata)"
                      if not fs else f"filesystem «{fs_s}» non compatibile col Teensy")
            self.sd_status.configure(
                text=(f"{head}\nFilesystem: {fs_s}\n⚠  {reason}.\n"
                      f"Serve formattarla FAT32. Usa «Formatta e prepara»."), fg=WARN)
            self._show_sd_actions(struct=False, fmt=True)
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
        self._show_sd_actions(struct=True, fmt=IS_WIN)
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
        info = self.sd_info or volume_info(self.sd_path_var.get())
        letter = info.get("letter")
        if not letter:
            messagebox.showerror("Percorso non valido",
                                 "Indica una cartella su una scheda SD con lettera di unità (es. E:\\).")
            return
        sysdrive = os.environ.get("SystemDrive", "C:")[0].upper()
        if letter == sysdrive or info.get("system"):
            messagebox.showerror("Operazione bloccata",
                                 f"L'unità {letter}: è il disco di SISTEMA. Non verrà mai formattata.")
            return
        if info.get("removable") is False:
            if not messagebox.askyesno(
                    "Unità non rimovibile",
                    f"L'unità {letter}: NON risulta rimovibile (tipo: {info.get('drive_type')}).\n\n"
                    "Formattare un disco fisso interno cancellerebbe dati importanti.\n"
                    "Sei DAVVERO sicuro che sia la SD del synth?", icon="warning"):
                return
        proceed, deep = self._confirm_format(letter, info)
        if not proceed:
            return
        self._sd_busy("Formattazione FAT32 in corso… (non rimuovere la scheda)")
        self._log(f"--- formattazione {letter}: in FAT32{' (ripulitura completa)' if deep else ''} ---", WARN)
        self._run_sd_async(lambda: format_fat32(letter, deep=deep), self._after_format)

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
        ttk.Label(frm, text=(f"Unità {letter}:  ·  {info.get('label') or '(senza etichetta)'}\n"
                             f"{human_size(info.get('size'))}  ·  tipo: {info.get('drive_type') or '?'}"),
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(6, 12))
        tk.Label(frm, text=(f"Verranno CANCELLATI TUTTI i dati sull'unità {letter}:\n"
                            "e la scheda sarà formattata FAT32.\nL'operazione è IRREVERSIBILE."),
                 bg=BG, fg=RED, justify="left", font=("Segoe UI", 9, "bold")).pack(anchor="w", pady=(0, 12))
        deep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, variable=deep_var,
                        text="Ripulisci anche partizioni strane (ripartiziona tutto il disco) — avanzato").pack(anchor="w")
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
            cat = (self.cat_var.get().strip() or "perc")
            cat = re.sub(r"[^a-z0-9._/-]+", "-", cat.lower()).strip("-/") or "perc"
            dst_dir = os.path.join(root, SD_BROWSER_DIR, cat)
            seen = {}
            for it in self.items:
                nm = sanitize_name(it["path"])
                key = nm.lower()
                if key in seen:
                    seen[key] += 1
                    nm = f"{nm[:-4]}-{seen[key]}.wav"
                else:
                    seen[key] = 1
                jobs.append((it["path"], os.path.join(dst_dir, nm)))
            base_desc = f"{SD_BROWSER_DIR}/{cat}/"
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
        self.convert_btn.configure(state="disabled")
        self.pbar.configure(maximum=len(jobs), value=0)
        self._log(f"--- conversione di {len(jobs)} file → {info} ---", ACCENT2)
        self.worker = threading.Thread(target=self._worker, args=(jobs, delete), daemon=True)
        self.worker.start()
        self.after(80, self._poll)

    def _worker(self, jobs, delete):
        done = 0
        for src, dst in jobs:
            name = os.path.basename(src)
            try:
                convert_file(src, dst)
                if delete and os.path.abspath(src) != os.path.abspath(dst):
                    try:
                        os.remove(src)
                    except OSError:
                        pass
                self.q.put(("ok", f"  ✓ {name}  →  {os.path.basename(dst)}"))
                done += 1
            except Exception as e:
                self.q.put(("err", f"  ✗ {name}: {e}"))
            self.q.put(("tick", None))
        self.q.put(("finish", done))

    def _poll(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "tick":
                    self.pbar.step(1)
                elif kind == "ok":
                    self._log(payload, ACCENT)
                elif kind == "err":
                    self._log(payload, RED)
                elif kind == "finish":
                    self.status.configure(text=f"Fatto: {payload}/{len(self.items)}")
                    self._log(f"--- completato: {payload} file convertiti ---", ACCENT2)
                    self.convert_btn.configure(state="normal")
                    messagebox.showinfo("Completato", f"{payload} file convertiti in:\n{self._last_out}")
                    return
        except queue.Empty:
            pass
        self.status.configure(text=f"Converto… {int(self.pbar['value'])}/{len(self.items)}")
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
