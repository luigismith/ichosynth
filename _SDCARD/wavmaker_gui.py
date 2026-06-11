#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ichosynth - WAV Maker (GUI)
===========================
Friendly graphical converter that turns any WAV into the format the ichosynth
sampler needs - MONO / 16-bit / 44100 Hz - and names the files _<n>.wav.

- pick individual files or a whole folder
- see each file's current format and its target name before converting
- prepare an SD card: scan it, understand what's already there, find where to
  continue numbering, and (if needed) format it FAT32 and build the directory
  structure the firmware expects (samples/0..9/_<n>.wav)
- progress bar + log; conversion runs off the UI thread

Pure standard library (tkinter + wave + audioop) for the conversion; SD scan /
format on Windows shell out to PowerShell. On Python 3.13+ install the
'audioop-lts' backport so `import audioop` works.

Run:  python wavmaker_gui.py      (or launch the bundled wavmaker.exe)
"""
import os
import sys
import re
import json
import shutil
import subprocess
import wave
import threading
import queue
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_VERSION = "1.1"
APP_AUTHOR = "Luigi Massari (luigismith)"
REPO_URL = "https://github.com/luigismith/ichosynth"

try:
    import audioop
except ModuleNotFoundError:  # Python 3.13+ without the backport
    audioop = None

TARGET_CH, TARGET_WIDTH, TARGET_RATE = 1, 2, 44100

# ------- ichosynth-ish palette -------
BG      = "#0d1117"
PANEL   = "#161b22"
INK     = "#e6edf3"
SUB     = "#9aa4b2"
LINE    = "#30363d"
ACCENT  = "#2ea44f"
ACCENT2 = "#1f6feb"
WARN    = "#d29922"
RED     = "#e5534b"
ROW_OK  = "#16241b"

# ------- SD structure the firmware reads (authoritative) -------
#   samples/<bank>/_<n>.wav   with   bank = n // 100,   bank in 0..maxFolders
SD_DIRNAME   = "samples"
MAX_BANK     = 9                       # firmware: maxFolders = 9  -> banks 0..9
FORMAT_LABEL = "ICHOSYNTH"
FAT32_MAX    = 32 * 1024 ** 3          # Windows refuses to create FAT32 above ~32 GiB
IS_WIN       = sys.platform.startswith("win")
_WAV_RE      = re.compile(r"^_(\d+)\.wav$", re.IGNORECASE)
_FS_OK       = ("FAT", "FAT16", "FAT32", "EXFAT")   # filesystems the Teensy SdFat can read


# =========================================================================
# audio core
# =========================================================================
def read_format(path):
    """Return (channels, sampwidth, framerate, nframes) or None if unreadable."""
    try:
        with wave.open(path, "rb") as w:
            return w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
    except Exception:
        return None


def is_target(fmt):
    return fmt is not None and fmt[0] == TARGET_CH and fmt[1] == TARGET_WIDTH and fmt[2] == TARGET_RATE


def fmt_label(fmt):
    if fmt is None:
        return "non leggibile"
    ch, width, rate, nframes = fmt
    chl = {1: "mono", 2: "stereo"}.get(ch, f"{ch}ch")
    secs = nframes / rate if rate else 0
    return f"{chl} · {width*8}-bit · {rate} Hz · {secs:0.1f}s"


def convert_file(src, dst):
    """Convert src WAV to mono/16-bit/44100 Hz, write to dst."""
    with wave.open(src, "rb") as w:
        ch = w.getnchannels()
        width = w.getsampwidth()
        rate = w.getframerate()
        frames = w.readframes(w.getnframes())

    if ch > 1:
        frames = audioop.tomono(frames, width, 0.5, 0.5)
    if width != TARGET_WIDTH:
        frames = audioop.lin2lin(frames, width, TARGET_WIDTH)
        width = TARGET_WIDTH
    if rate != TARGET_RATE:
        frames, _ = audioop.ratecv(frames, TARGET_WIDTH, 1, rate, TARGET_RATE, None)

    with wave.open(dst, "wb") as out:
        out.setnchannels(TARGET_CH)
        out.setsampwidth(TARGET_WIDTH)
        out.setframerate(TARGET_RATE)
        out.writeframes(frames)


# =========================================================================
# SD card helpers  (scan / structure / format)  — Windows-focused
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
    """Run a PowerShell command with no visible window. Returns CompletedProcess or None."""
    if not IS_WIN:
        return None
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0  # SW_HIDE
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, timeout=timeout,
            startupinfo=si, creationflags=0x08000000)  # CREATE_NO_WINDOW
    except Exception:
        return None


def drive_letter_of(path):
    """'E:\\samples' -> 'E'  (or None if the path has no drive letter)."""
    if not path:
        return None
    drv = os.path.splitdrive(os.path.abspath(path))[0]
    if len(drv) >= 2 and drv[1] == ":":
        return drv[0].upper()
    return None


def volume_info(path):
    """Inspect the volume that `path` lives on.

    Returns a dict: letter, fs, drive_type, size, free, label, removable, system, readable.
    """
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


def scan_samples(sd_root):
    """Inspect <sd_root>/samples and the card root.

    Returns: structured, banks [(bank,count)], files, max_num, next_num, packs, songs.
    """
    res = {"structured": False, "banks": [], "files": 0, "max_num": 0,
           "next_num": 1, "packs": [], "songs": 0}
    samples = os.path.join(sd_root, SD_DIRNAME)
    if os.path.isdir(samples):
        for b in range(0, MAX_BANK + 1):
            bp = os.path.join(samples, str(b))
            if os.path.isdir(bp):
                cnt = 0
                try:
                    for name in os.listdir(bp):
                        m = _WAV_RE.match(name)
                        if m:
                            n = int(m.group(1))
                            cnt += 1
                            res["files"] += 1
                            if n > res["max_num"]:
                                res["max_num"] = n
                except Exception:
                    pass
                res["banks"].append((b, cnt))
        res["structured"] = len(res["banks"]) > 0
        res["next_num"] = (res["max_num"] + 1) if res["files"] else 1
    # informational: song packs (numeric dirs at root) and pattern files (<n>.txt)
    try:
        for name in os.listdir(sd_root):
            full = os.path.join(sd_root, name)
            if os.path.isdir(full) and name.isdigit():
                res["packs"].append(name)
            elif os.path.isfile(full) and name.lower().endswith(".txt") and name[:-4].isdigit():
                res["songs"] += 1
    except Exception:
        pass
    return res


def create_structure(sd_root, banks=None):
    """mkdir samples/ and samples/<bank>/ for every bank. Returns created paths."""
    if banks is None:
        banks = range(0, MAX_BANK + 1)
    created = []
    samples = os.path.join(sd_root, SD_DIRNAME)
    for d in [samples] + [os.path.join(samples, str(b)) for b in banks]:
        if not os.path.isdir(d):
            os.makedirs(d, exist_ok=True)
            created.append(d)
    return created


def format_fat32(letter, label=FORMAT_LABEL, deep=False):
    """Format the removable volume at `letter` to FAT32.

    Returns (True, new_drive_letter) on success, or (False, error_message).
    `deep=True` wipes ALL partitions on the backing removable disk and rebuilds one.
    """
    if not IS_WIN:
        return False, "La formattazione automatica è disponibile solo su Windows."
    letter = letter.upper()
    sysdrive = os.environ.get("SystemDrive", "C:")[0].upper()
    if letter == sysdrive:
        return False, "Rifiuto: è l'unità di sistema."

    if not deep:
        r = _ps(f"Format-Volume -DriveLetter {letter} -FileSystem FAT32 "
                f"-NewFileSystemLabel '{label}' -Force -Confirm:$false -ErrorAction Stop",
                timeout=300)
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
    # friendly diagnosis of common failures
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
        self.items = []            # list of dict: path, fmt
        self.q = queue.Queue()
        self.sdq = queue.Queue()
        self.worker = None
        self.sd_root = None        # set when an SD has been scanned & chosen as target
        self.sd_info = None        # last volume_info()
        self.sd_scan = None        # last scan_samples()
        self._sd_inflight = 0
        self._last_out = ""

        self._build_style()
        self._build_ui()
        self.pack(fill="both", expand=True)
        self._refresh_targets()
        self._log("Pronto. Aggiungi file WAV o una cartella per iniziare.")
        self._log("Suggerimento: scansiona la SD per preparala e numerare in automatico.", SUB)

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
        st.configure("TButton", background=PANEL, foreground=INK, bordercolor=LINE,
                     focuscolor=BG, padding=6)
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
        st.configure("Info.TButton", background=PANEL, foreground=ACCENT2,
                     font=("Segoe UI", 13, "bold"), padding=2)
        st.map("Info.TButton", background=[("active", "#21262d")])
        st.configure("TCheckbutton", background=PANEL, foreground=INK)
        st.map("TCheckbutton", background=[("active", PANEL)])
        st.configure("TEntry", fieldbackground="#0b0f14", foreground=INK)
        st.configure("TSpinbox", fieldbackground="#0b0f14", foreground=INK, arrowsize=14)
        st.configure("Treeview", background=PANEL, fieldbackground=PANEL, foreground=INK,
                     rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background="#0b0f14", foreground=SUB,
                     font=("Segoe UI", 9, "bold"))
        st.map("Treeview", background=[("selected", ACCENT2)])
        st.configure("green.Horizontal.TProgressbar", background=ACCENT, troughcolor="#0b0f14",
                     bordercolor=LINE)

    # ---- layout ----
    def _build_ui(self):
        self.master.title("ichosynth — WAV Maker")
        self.master.minsize(760, 640)

        # header (title block on the left, info button top-right)
        head = ttk.Frame(self, padding=(18, 14, 18, 6))
        head.pack(fill="x")
        info_btn = ttk.Button(head, text="ⓘ", width=3, style="Info.TButton", command=self.show_about)
        info_btn.pack(side="right", anchor="n")
        titlebox = ttk.Frame(head)
        titlebox.pack(side="left", anchor="w")
        ttk.Label(titlebox, text="🎵  ichosynth — WAV Maker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(titlebox, text="Converte i WAV in  mono · 16-bit · 44100 Hz  e prepara la scheda SD del synth",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        if audioop is None:
            warn = tk.Label(self, text="⚠  Modulo 'audioop' assente (Python 3.13+). Installa:  pip install audioop-lts",
                            bg=WARN, fg="#1a1300", font=("Segoe UI", 9, "bold"))
            warn.pack(fill="x", padx=18, pady=(0, 4))

        # toolbar
        bar = ttk.Frame(self, padding=(18, 6, 18, 6))
        bar.pack(fill="x")
        ttk.Button(bar, text="➕  Aggiungi file", command=self.add_files).pack(side="left")
        ttk.Button(bar, text="📁  Aggiungi cartella", command=self.add_folder).pack(side="left", padx=6)
        ttk.Button(bar, text="🗑  Rimuovi", command=self.remove_selected).pack(side="left")
        ttk.Button(bar, text="Svuota", command=self.clear_all).pack(side="left", padx=6)
        self.count_lbl = ttk.Label(bar, text="0 file", style="Sub.TLabel")
        self.count_lbl.pack(side="right")

        # file table
        table = ttk.Frame(self, style="Panel.TFrame", padding=1)
        table.pack(fill="both", expand=True, padx=18, pady=(2, 6))
        cols = ("file", "fmt", "arrow", "dst")
        self.tree = ttk.Treeview(table, columns=cols, show="headings", selectmode="extended")
        self.tree.heading("file", text="FILE")
        self.tree.heading("fmt", text="FORMATO ATTUALE")
        self.tree.heading("arrow", text="")
        self.tree.heading("dst", text="DESTINAZIONE")
        self.tree.column("file", width=230, anchor="w")
        self.tree.column("fmt", width=210, anchor="w")
        self.tree.column("arrow", width=28, anchor="center")
        self.tree.column("dst", width=190, anchor="w")
        self.tree.tag_configure("ok", background=ROW_OK)
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
        sde = ttk.Entry(sdp, textvariable=self.sd_path_var)
        sde.grid(row=1, column=1, sticky="ew", padx=(12, 6), pady=(8, 0))
        ttk.Button(sdp, text="Sfoglia…", command=self.pick_sd).grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.sd_scan_btn = ttk.Button(sdp, text="🔍  Scansiona", style="Scan.TButton", command=self.scan_sd)
        self.sd_scan_btn.grid(row=1, column=3, sticky="e", padx=(6, 0), pady=(8, 0))

        self.sd_status = tk.Label(sdp, text="Indica la cartella della SD (es. E:\\) e premi Scansiona.",
                                  bg=PANEL, fg=SUB, justify="left", anchor="w",
                                  font=("Segoe UI", 9), wraplength=660)
        self.sd_status.grid(row=2, column=0, columnspan=4, sticky="ew", pady=(10, 0))

        actions = ttk.Frame(sdp, style="Panel.TFrame")
        actions.grid(row=3, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.sd_btn_struct = ttk.Button(actions, text="📁  Crea/completa struttura",
                                        command=self.do_create_structure)
        self.sd_btn_format = ttk.Button(actions, text="⚠  Formatta e prepara (FAT32)",
                                        style="Danger.TButton", command=self.do_format)
        # both start hidden; scan decides what to show
        self._show_sd_actions(struct=False, fmt=False)

        # options
        opt = ttk.Frame(self, style="Panel.TFrame", padding=12)
        opt.pack(fill="x", padx=18, pady=(0, 6))
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Numero di partenza", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self.start_var = tk.IntVar(value=1)
        sp = ttk.Spinbox(opt, from_=0, to=999, textvariable=self.start_var, width=8,
                         command=self._refresh_targets)
        sp.grid(row=0, column=0, sticky="w", padx=(150, 0))
        sp.bind("<KeyRelease>", lambda e: self._refresh_targets())
        self.sd_hint = ttk.Label(opt, text="", style="PanelSub.TLabel")
        self.sd_hint.grid(row=0, column=1, sticky="w", padx=12)

        ttk.Label(opt, text="Cartella di destinazione", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.out_var = tk.StringVar(value="")
        oe = ttk.Entry(opt, textvariable=self.out_var)
        oe.grid(row=1, column=1, sticky="ew", padx=(12, 6), pady=(10, 0))
        ttk.Button(opt, text="Sfoglia…", command=self.pick_output).grid(row=1, column=2, sticky="e", pady=(10, 0))

        self.delete_var = tk.BooleanVar(value=False)
        dc = ttk.Checkbutton(opt, text="Elimina gli originali dopo la conversione (attenzione!)",
                             variable=self.delete_var)
        dc.grid(row=2, column=0, columnspan=3, sticky="w", pady=(10, 0))

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
            return os.path.join(os.path.dirname(self.items[0]["path"]), "wav_convertiti")
        return os.path.join(os.path.expanduser("~"), "Desktop", "wav_convertiti")

    def _refresh_targets(self):
        try:
            start = int(self.start_var.get())
        except (tk.TclError, ValueError):
            start = 0
        if self.sd_root:
            self.sd_hint.configure(text=f"→ scrive in  {SD_DIRNAME}/<bank>/  sulla SD (modalità SD attiva)")
        else:
            folder = start // 100
            self.sd_hint.configure(text=f"→ va in  {SD_DIRNAME}/{folder}/  sulla SD")
            if not self.out_var.get():
                self.out_var.set(self._default_output())
        for i, iid in enumerate(self.tree.get_children()):
            n = start + i
            if self.sd_root:
                self.tree.set(iid, "dst", f"{SD_DIRNAME}/{n // 100}/_{n}.wav")
            else:
                self.tree.set(iid, "dst", f"_{n}.wav")
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
            self.tree.insert("", "end", values=(os.path.basename(p), fmt_label(fmt), "→", ""), tags=tags)
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
            paths = [os.path.join(d, f) for f in sorted(os.listdir(d)) if f.lower().endswith(".wav")]
            self._add_paths(paths)

    def remove_selected(self):
        sel = set(self.tree.selection())
        if not sel:
            return
        keep = []
        for iid, it in zip(self.tree.get_children(), self.items):
            if iid not in sel:
                keep.append(it)
        for iid in sel:
            self.tree.delete(iid)
        self.items = keep
        self._refresh_targets()

    def clear_all(self):
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self.items = []
        self._refresh_targets()

    def pick_output(self):
        d = filedialog.askdirectory(title="Cartella di destinazione")
        if d:
            self.out_var.set(d)
            self._clear_sd_mode("Destinazione manuale scelta: modalità SD disattivata.")

    # =====================================================================
    # SD card  (scan / structure / format)
    # =====================================================================
    def pick_sd(self):
        d = filedialog.askdirectory(title="Scegli la scheda SD (la sua radice, es. E:\\)")
        if d:
            self.sd_path_var.set(d)

    # ---- async plumbing for SD ops (keep UI responsive) ----
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

    # ---- scan ----
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
            scan = scan_samples(root) if os.path.isdir(root) else None
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
        size_s = human_size(info.get("size"))
        free_s = human_size(info.get("free"))
        label = info.get("label") or "(senza etichetta)"
        drive_type = info.get("drive_type") or "?"

        head = f"Unità {letter}:  ·  {label}  ·  {size_s} ({free_s} liberi)  ·  {drive_type}"
        fs_s = fs or "non rilevato"

        # ----- decide verdict -----
        readable = info.get("readable")
        compatible = fs_is_compatible(fs) if IS_WIN else readable

        if IS_WIN and (not readable or fs is None or not compatible):
            # not formatted / incompatible filesystem (e.g. NTFS) / unreadable
            reason = ("filesystem non rilevato (probabilmente non formattata)"
                      if not fs else f"filesystem «{fs_s}» non compatibile col Teensy")
            self.sd_status.configure(
                text=(f"{head}\nFilesystem: {fs_s}\n"
                      f"⚠  {reason}.\n"
                      f"Serve formattarla FAT32 e creare la struttura. Usa «Formatta e prepara»."),
                fg=WARN)
            self._show_sd_actions(struct=False, fmt=True)
            self._clear_sd_mode(log=False)
            self._log(f"  ⚠ SD non pronta: {reason}", WARN)
            return

        # compatible filesystem -> look at the structure
        if scan and scan["structured"]:
            nb = sum(1 for _b, c in scan["banks"])
            nfiles = scan["files"]
            nxt = scan["next_num"]
            extra = ""
            if scan["packs"]:
                extra += f"  ·  pack-canzone: {', '.join(scan['packs'][:8])}"
            if scan["songs"]:
                extra += f"  ·  {scan['songs']} pattern .txt"
            self.sd_status.configure(
                text=(f"{head}\nFilesystem: {fs_s}  ✓\n"
                      f"✓  Struttura presente: {SD_DIRNAME}/ con {nb} bank · {nfiles} campioni"
                      f" (max _{scan['max_num']}){extra}\n"
                      f"▶  Riprendo la numerazione da  _{nxt}  →  {SD_DIRNAME}/{nxt // 100}/"),
                fg=ACCENT)
            self._set_sd_mode(root, nxt)
            self._show_sd_actions(struct=True, fmt=IS_WIN)   # struct = "completa eventuali bank mancanti"
            self._log(f"  ✓ SD pronta. Prossimo numero: _{nxt}", ACCENT)
        else:
            # healthy filesystem but no samples/ structure yet
            self.sd_status.configure(
                text=(f"{head}\nFilesystem: {fs_s}  ✓\n"
                      f"📁  Filesystem ok ma manca la cartella «{SD_DIRNAME}/». "
                      f"Premi «Crea/completa struttura» (non cancella nulla)."),
                fg=INK)
            self._show_sd_actions(struct=True, fmt=IS_WIN)
            self._clear_sd_mode(log=False)
            self._log("  📁 SD sana ma senza struttura: pronta da creare.", SUB)

    def _set_sd_mode(self, root, next_num):
        self.sd_root = root
        self.out_var.set(os.path.join(root, SD_DIRNAME))
        try:
            self.start_var.set(int(next_num))
        except Exception:
            pass
        self._refresh_targets()

    def _clear_sd_mode(self, msg=None, log=True):
        was = self.sd_root is not None
        self.sd_root = None
        self._refresh_targets()
        if msg and log:
            self._log(f"  · {msg}", SUB)
        if was and msg:
            self.sd_status.configure(text=msg, fg=SUB)

    # ---- create structure ----
    def do_create_structure(self):
        root = self._current_sd_root()
        if not root:
            return
        self._sd_busy("Creazione struttura…")
        self._run_sd_async(lambda: create_structure(root), self._after_structure)

    def _after_structure(self, result):
        self._sd_idle()
        kind, payload = result
        if kind == "err":
            messagebox.showerror("Errore", f"Impossibile creare la struttura:\n{payload}")
            return
        created = payload
        self._log(f"  ✓ struttura creata/completata ({len(created)} cartelle nuove)", ACCENT)
        # re-scan to refresh verdict and enter SD mode
        self.scan_sd()

    # ---- format ----
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
                                "Su macOS/Linux formatta la SD in FAT32 a mano, poi usa «Crea struttura».")
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
                    "Sei DAVVERO sicuro che sia la SD del synth?",
                    icon="warning"):
                return

        proceed, deep = self._confirm_format(letter, info)
        if not proceed:
            return

        self._sd_busy("Formattazione FAT32 in corso… (non rimuovere la scheda)")
        self._log(f"--- formattazione {letter}: in FAT32{' (ripulitura completa)' if deep else ''} ---", WARN)
        self._run_sd_async(lambda: format_fat32(letter, deep=deep), self._after_format)

    def _confirm_format(self, letter, info):
        """Modal destructive-confirmation. Returns (proceed, deep)."""
        win = tk.Toplevel(self.master)
        win.title("Conferma formattazione")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.master)
        result = {"proceed": False, "deep": False}

        frm = ttk.Frame(win, padding=20)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="⚠  Formattazione scheda SD", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frm,
                  text=(f"Unità {letter}:  ·  {info.get('label') or '(senza etichetta)'}\n"
                        f"{human_size(info.get('size'))}  ·  tipo: {info.get('drive_type') or '?'}"),
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(6, 12))
        msg = tk.Label(frm,
                       text=("Verranno CANCELLATI TUTTI i dati sull'unità "
                             f"{letter}:\ne creata la struttura ichosynth (FAT32, samples/0..9).\n"
                             "L'operazione è IRREVERSIBILE."),
                       bg=BG, fg=RED, justify="left", font=("Segoe UI", 9, "bold"))
        msg.pack(anchor="w", pady=(0, 12))

        deep_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, variable=deep_var,
                        text="Ripulisci anche partizioni strane (cancella e ripartiziona tutto il disco) — avanzato"
                        ).pack(anchor="w")

        ack_var = tk.BooleanVar(value=False)
        ack = ttk.Checkbutton(frm, variable=ack_var,
                              text=f"Ho capito: cancella tutto su {letter}:")
        ack.pack(anchor="w", pady=(8, 14))

        btns = ttk.Frame(frm)
        btns.pack(fill="x")
        go = ttk.Button(btns, text=f"Formatta {letter}:", style="Danger.TButton",
                        state="disabled",
                        command=lambda: (result.update(proceed=True, deep=deep_var.get()), win.destroy()))
        go.pack(side="right")
        ttk.Button(btns, text="Annulla", command=win.destroy).pack(side="right", padx=(0, 8))

        def _toggle(*_):
            go.configure(state="normal" if ack_var.get() else "disabled")
        ack_var.trace_add("write", _toggle)

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
        self._log(f"  ✓ formattata. Creo la struttura su {new_letter}:\\", ACCENT)
        root = new_letter + ":\\"
        self.sd_path_var.set(root)
        try:
            create_structure(root)
        except Exception as e:
            messagebox.showwarning("Struttura",
                                   f"Formattata, ma non sono riuscito a creare la struttura:\n{e}")
        messagebox.showinfo("Fatto", f"Scheda {new_letter}: formattata FAT32 e pronta.")
        self.scan_sd()

    # ---- about / info ----
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

        ttk.Label(frm, text="Prepara i campioni audio per il sampler ichosynth:\n"
                            "li converte in mono · 16-bit · 44100 Hz, prepara la SD\n"
                            "(scan / struttura / formattazione FAT32) e li nomina _<n>.wav.",
                  style="Sub.TLabel", justify="left").pack(anchor="w", pady=(0, 12))

        link = tk.Label(frm, text=REPO_URL.replace("https://", ""), bg=BG, fg=ACCENT2,
                        cursor="hand2", font=("Segoe UI", 9, "underline"))
        link.pack(anchor="w")
        link.bind("<Button-1>", lambda e: webbrowser.open(REPO_URL))

        ttk.Label(frm, text="Parte del progetto ichosynth · fork di NI404 (SP_) · licenza MIT",
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
    def start_convert(self):
        if audioop is None:
            messagebox.showerror("audioop mancante",
                                 "Serve il modulo audioop.\nPython 3.13+:  pip install audioop-lts")
            return
        if not self.items:
            messagebox.showinfo("Niente da fare", "Aggiungi prima qualche file WAV.")
            return

        start = int(self.start_var.get())
        if self.sd_root:
            base = os.path.join(self.sd_root, SD_DIRNAME)
            jobs = []
            try:
                for i, it in enumerate(self.items):
                    n = start + i
                    bank = os.path.join(base, str(n // 100))
                    os.makedirs(bank, exist_ok=True)
                    jobs.append((it["path"], os.path.join(bank, f"_{n}.wav")))
            except Exception as e:
                messagebox.showerror("SD non scrivibile", f"Impossibile preparare le cartelle sulla SD:\n{e}")
                return
            self._last_out = base
        else:
            out = self.out_var.get().strip() or self._default_output()
            try:
                os.makedirs(out, exist_ok=True)
            except Exception as e:
                messagebox.showerror("Cartella non valida", f"Impossibile creare:\n{out}\n\n{e}")
                return
            jobs = [(it["path"], os.path.join(out, f"_{start + i}.wav")) for i, it in enumerate(self.items)]
            self._last_out = out

        if self.delete_var.get():
            if not messagebox.askyesno("Confermi?",
                                       "Eliminerò gli ORIGINALI dopo la conversione.\nProcedo?"):
                return
        delete = self.delete_var.get()

        self.convert_btn.configure(state="disabled")
        self.pbar.configure(maximum=len(jobs), value=0)
        self._log(f"--- conversione di {len(jobs)} file in: {self._last_out} ---", ACCENT2)
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
                    os.remove(src)
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
                    messagebox.showinfo("Completato",
                                        f"{payload} file convertiti in:\n{self._last_out}")
                    return
        except queue.Empty:
            pass
        self.status.configure(text=f"Converto… {int(self.pbar['value'])}/{len(self.items)}")
        self.after(80, self._poll)


def main():
    root = tk.Tk()
    root.geometry("800x760")
    app = WavMakerApp(root)
    # smoke-test hook: build the window then close immediately
    if "--selftest" in sys.argv:
        root.after(300, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
