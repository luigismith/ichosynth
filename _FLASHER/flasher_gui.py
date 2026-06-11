#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ichosynth - Flasher (GUI)
=========================
One-click flasher for the ichosynth firmware on a Teensy 4.1.

- ships a pre-compiled `ichosynth.hex` (no Arduino/arduino-cli needed to flash)
- detects the Teensy live (running / bootloader / absent)
- reboots the board into the bootloader automatically; if it can't, it asks you
  to press the Teensy PROGRAM button
- streams the flashing progress and tells you when it's done

Flashing backend (auto-detected, in order of preference):
  1. teensy_loader_cli.exe   (standalone, placed next to this app or on PATH)
  2. Teensyduino tools       (teensy_post_compile.exe + the Teensy Loader GUI,
                              installed with the Arduino "teensy" core)

Windows-focused (Teensy detection uses PowerShell). Pure standard library.

Run:  python flasher_gui.py        (or launch the bundled flasher.exe)
"""
import os
import sys
import glob
import time
import shutil
import subprocess
import threading
import queue
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_VERSION = "1.0"
APP_AUTHOR  = "Luigi Massari (luigismith)"
REPO_URL    = "https://github.com/luigismith/ichosynth"
HEX_NAME    = "ichosynth.hex"
BOARD       = "TEENSY41"
TEENSY_DL   = "https://www.pjrc.com/teensy/td_download.html"

IS_WIN = sys.platform.startswith("win")

# ------- ichosynth palette (shared with WAV Maker) -------
BG      = "#0d1117"
PANEL   = "#161b22"
INK     = "#e6edf3"
SUB     = "#9aa4b2"
LINE    = "#30363d"
ACCENT  = "#2ea44f"
ACCENT2 = "#1f6feb"
WARN    = "#d29922"
RED     = "#e5534b"
GREYDOT = "#6e7681"


# =========================================================================
# helpers
# =========================================================================
def app_dir():
    """Folder the app lives in (next to the .exe when frozen, else this file)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def human_size(n):
    if n is None:
        return "?"
    n = float(n)
    for u in ("B", "KB", "MB", "GB"):
        if n < 1024 or u == "GB":
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024
    return f"{n:.1f} GB"


def _ps(script, timeout=20):
    """Run a PowerShell command hidden. Returns CompletedProcess or None."""
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


def _run(cmd, timeout=120):
    """Run an external tool hidden, capturing output. Returns (returncode, text)."""
    si = None
    flags = 0
    if IS_WIN:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        flags = 0x08000000
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           startupinfo=si, creationflags=flags)
        return r.returncode, ((r.stdout or "") + (r.stderr or ""))
    except FileNotFoundError:
        return 127, "tool non trovato"
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except Exception as e:
        return 1, str(e)


def find_backend():
    """Locate a flashing backend. Returns a dict describing it."""
    here = app_dir()
    # 1) standalone teensy_loader_cli (preferred): next to the app or on PATH
    for cand in (os.path.join(here, "teensy_loader_cli.exe"),
                 shutil.which("teensy_loader_cli") or "",
                 shutil.which("teensy_loader_cli.exe") or ""):
        if cand and os.path.isfile(cand):
            return {"kind": "cli", "loader": cand, "reboot": shutil.which("teensy_reboot") or "",
                    "label": "teensy_loader_cli"}
    # 2) Teensyduino tools shipped with the Arduino "teensy" core
    roots = []
    la = os.environ.get("LOCALAPPDATA")
    if la:
        roots.append(os.path.join(la, "Arduino15", "packages", "teensy", "tools", "teensy-tools"))
    # macOS / Linux Arduino locations (best-effort)
    home = os.path.expanduser("~")
    roots += [os.path.join(home, ".arduino15", "packages", "teensy", "tools", "teensy-tools"),
              os.path.join(home, "Library", "Arduino15", "packages", "teensy", "tools", "teensy-tools")]
    pc_name = "teensy_post_compile.exe" if IS_WIN else "teensy_post_compile"
    rb_name = "teensy_reboot.exe" if IS_WIN else "teensy_reboot"
    best = None
    for root in roots:
        for pc in glob.glob(os.path.join(root, "*", pc_name)):
            tools = os.path.dirname(pc)
            ver = os.path.basename(tools)
            if best is None or ver > best[0]:
                best = (ver, tools, pc, os.path.join(tools, rb_name))
    if best:
        ver, tools, pc, rb = best
        return {"kind": "teensyduino", "tools": tools, "post_compile": pc,
                "reboot": rb if os.path.isfile(rb) else "", "version": ver,
                "label": f"Teensyduino {ver}"}
    return {"kind": "none", "label": "nessuno"}


def teensy_state():
    """Return 'run' | 'halfkay' | 'absent' | 'unknown' (Windows only)."""
    if not IS_WIN:
        return "unknown"
    r = _ps("$d = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match 'VID_16C0' }; "
            "if ($d | Where-Object { $_.InstanceId -match 'PID_0478' }) { 'halfkay' } "
            "elseif ($d) { 'run' } else { 'absent' }", timeout=12)
    if r and r.returncode == 0:
        s = (r.stdout or "").strip().lower()
        if s in ("run", "halfkay", "absent"):
            return s
    return "unknown"


def _usb_present(pattern):
    r = _ps(f"[bool](Get-PnpDevice -PresentOnly | Where-Object {{ $_.InstanceId -match '{pattern}' }})", timeout=12)
    return bool(r and "true" in (r.stdout or "").lower())


# =========================================================================
# GUI
# =========================================================================
class FlasherApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=0)
        self.master = master
        self.q = queue.Queue()
        self.flashing = False
        self.backend = find_backend()
        self._last_state = None

        self._build_style()
        self._build_ui()
        self.pack(fill="both", expand=True)

        # default firmware = ichosynth.hex next to the app
        default_hex = os.path.join(app_dir(), HEX_NAME)
        self.fw_var.set(default_hex if os.path.isfile(default_hex) else "")
        self._render_backend()
        self._refresh_fw()
        self._log("Pronto. Collega il Teensy 4.1 e premi «Flash ichosynth».")
        self._poll_teensy()  # start live detection

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
        st.configure("PanelH2.TLabel", background=PANEL, foreground=INK, font=("Segoe UI", 10, "bold"))
        st.configure("Title.TLabel", background=BG, foreground=INK, font=("Segoe UI", 17, "bold"))
        st.configure("H2.TLabel", background=BG, foreground=INK, font=("Segoe UI", 10, "bold"))
        st.configure("TButton", background=PANEL, foreground=INK, bordercolor=LINE, focuscolor=BG, padding=6)
        st.map("TButton", background=[("active", "#21262d")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#06210f",
                     font=("Segoe UI", 13, "bold"), padding=12)
        st.map("Accent.TButton", background=[("active", "#2bbd5a"), ("disabled", LINE)])
        st.configure("Info.TButton", background=PANEL, foreground=ACCENT2, font=("Segoe UI", 13, "bold"), padding=2)
        st.map("Info.TButton", background=[("active", "#21262d")])
        st.configure("TEntry", fieldbackground="#0b0f14", foreground=INK)
        st.configure("green.Horizontal.TProgressbar", background=ACCENT, troughcolor="#0b0f14", bordercolor=LINE)

    # ---- layout ----
    def _build_ui(self):
        self.master.title("ichosynth — Flasher")
        self.master.minsize(640, 540)

        head = ttk.Frame(self, padding=(18, 14, 18, 6))
        head.pack(fill="x")
        ttk.Button(head, text="ⓘ", width=3, style="Info.TButton", command=self.show_about).pack(side="right", anchor="n")
        tb = ttk.Frame(head)
        tb.pack(side="left", anchor="w")
        ttk.Label(tb, text="⚡  ichosynth — Flasher", style="Title.TLabel").pack(anchor="w")
        ttk.Label(tb, text="Carica il firmware ichosynth sul Teensy 4.1 — in un clic",
                  style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        # firmware panel
        fwp = ttk.Frame(self, style="Panel.TFrame", padding=12)
        fwp.pack(fill="x", padx=18, pady=(6, 6))
        fwp.columnconfigure(1, weight=1)
        ttk.Label(fwp, text="🧩  Firmware", style="PanelH2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(fwp, text="File .hex", style="Panel.TLabel").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.fw_var = tk.StringVar(value="")
        fe = ttk.Entry(fwp, textvariable=self.fw_var)
        fe.grid(row=1, column=1, sticky="ew", padx=(12, 6), pady=(8, 0))
        fe.bind("<KeyRelease>", lambda e: self._refresh_fw())
        ttk.Button(fwp, text="Sfoglia…", command=self.pick_fw).grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.fw_info = ttk.Label(fwp, text="", style="PanelSub.TLabel")
        self.fw_info.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # status panel
        stp = ttk.Frame(self, style="Panel.TFrame", padding=12)
        stp.pack(fill="x", padx=18, pady=(0, 6))
        stp.columnconfigure(1, weight=1)
        ttk.Label(stp, text="🔌  Stato", style="PanelH2.TLabel").grid(row=0, column=0, columnspan=3, sticky="w")
        self.dot = tk.Label(stp, text="●", bg=PANEL, fg=GREYDOT, font=("Segoe UI", 12, "bold"))
        self.dot.grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.teensy_lbl = ttk.Label(stp, text="Teensy: rilevamento…", style="Panel.TLabel")
        self.teensy_lbl.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(8, 0))
        ttk.Button(stp, text="Aggiorna", command=self._detect_now).grid(row=1, column=2, sticky="e", pady=(8, 0))
        self.backend_lbl = ttk.Label(stp, text="", style="PanelSub.TLabel")
        self.backend_lbl.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # action
        act = ttk.Frame(self, padding=(18, 6, 18, 2))
        act.pack(fill="x")
        self.flash_btn = ttk.Button(act, text="⚡  Flash ichosynth", style="Accent.TButton", command=self.start_flash)
        self.flash_btn.pack(fill="x")
        prog = ttk.Frame(self, padding=(18, 4, 18, 4))
        prog.pack(fill="x")
        self.pbar = ttk.Progressbar(prog, style="green.Horizontal.TProgressbar", mode="determinate", maximum=100)
        self.pbar.pack(side="left", fill="x", expand=True)
        self.status = ttk.Label(prog, text="Pronto", style="Sub.TLabel")
        self.status.pack(side="right", padx=(12, 0))

        # log
        logf = ttk.Frame(self, padding=(18, 2, 18, 12))
        logf.pack(fill="both", expand=True)
        self.log = tk.Text(logf, height=10, bg="#0b0f14", fg=SUB, insertbackground=INK,
                           relief="flat", font=("Consolas", 9), wrap="word")
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

    def _refresh_fw(self):
        p = self.fw_var.get().strip()
        if p and os.path.isfile(p):
            try:
                sz = os.path.getsize(p)
            except OSError:
                sz = None
            ok = p.lower().endswith(".hex")
            self.fw_info.configure(
                text=f"{'✓' if ok else '⚠'}  {os.path.basename(p)}  ·  {human_size(sz)}"
                     + ("" if ok else "  (non è un .hex)"))
        else:
            self.fw_info.configure(text="⚠  nessun file .hex selezionato")
        self._update_flash_enabled()

    def _render_backend(self):
        b = self.backend
        if b["kind"] == "none":
            self.backend_lbl.configure(
                text="Strumenti di flash: ✗ non trovati. Installa il «Teensy Loader» / Teensyduino "
                     "(pjrc.com) e riapri l'app.", foreground=RED)
        else:
            self.backend_lbl.configure(text=f"Strumenti di flash: ✓ {b['label']}", foreground=SUB)
        self._update_flash_enabled()

    def _update_flash_enabled(self):
        ok = (not self.flashing
              and self.backend["kind"] != "none"
              and bool(self.fw_var.get().strip())
              and os.path.isfile(self.fw_var.get().strip()))
        self.flash_btn.configure(state="normal" if ok else "disabled")

    def pick_fw(self):
        p = filedialog.askopenfilename(title="Scegli il firmware (.hex)",
                                       filetypes=[("Firmware Teensy", "*.hex"), ("Tutti i file", "*.*")])
        if p:
            self.fw_var.set(p)
            self._refresh_fw()

    # ---- live Teensy detection (polled in a thread) ----
    def _poll_teensy(self):
        if IS_WIN:
            threading.Thread(target=lambda: self.q.put(("state", teensy_state())), daemon=True).start()
        self.after(120, self._drain_q)
        self.after(3000, self._poll_teensy)

    def _detect_now(self):
        self._log("· rilevamento Teensy…", SUB)
        if IS_WIN:
            threading.Thread(target=lambda: self.q.put(("state", teensy_state())), daemon=True).start()
            self.after(120, self._drain_q)

    def _set_state(self, state):
        if state == self._last_state:
            return
        self._last_state = state
        if state == "run":
            self.dot.configure(fg=ACCENT)
            self.teensy_lbl.configure(text="Teensy collegato (in esecuzione) — pronto a flashare")
        elif state == "halfkay":
            self.dot.configure(fg=ACCENT2)
            self.teensy_lbl.configure(text="Teensy in modalità bootloader (HalfKay) — pronto")
        elif state == "absent":
            self.dot.configure(fg=GREYDOT)
            self.teensy_lbl.configure(text="Teensy non rilevato — collegalo via USB")
        else:
            self.dot.configure(fg=WARN)
            self.teensy_lbl.configure(text="Stato Teensy non determinabile")

    # ---- flashing ----
    def start_flash(self):
        fw = self.fw_var.get().strip()
        if not fw or not os.path.isfile(fw):
            messagebox.showerror("Firmware mancante", "Seleziona un file .hex valido.")
            return
        if self.backend["kind"] == "none":
            messagebox.showerror("Strumenti mancanti",
                                 "Non ho trovato gli strumenti di flash del Teensy.\n\n"
                                 "Installa il «Teensy Loader» / Teensyduino da:\n" + TEENSY_DL)
            return
        self.flashing = True
        self._update_flash_enabled()
        self.flash_btn.configure(state="disabled")
        self.pbar.configure(mode="indeterminate")
        self.pbar.start(12)
        self.status.configure(text="Flashing…")
        self._log("──────────────────────────────", ACCENT2)
        self._log(f"Flash di {os.path.basename(fw)} su {BOARD}…", ACCENT2)
        threading.Thread(target=self._flash_worker, args=(fw,), daemon=True).start()

    def _flash_worker(self, fw):
        try:
            if self.backend["kind"] == "cli":
                ok, msg = self._flash_cli(fw)
            else:
                ok, msg = self._flash_teensyduino(fw)
        except Exception as e:
            ok, msg = False, f"errore inatteso: {e}"
        self.q.put(("flash_done", (ok, msg)))

    def _emit(self, msg, color=None):
        self.q.put(("log", (msg, color)))

    # backend 1: teensy_loader_cli (clean exit code, streams progress)
    def _flash_cli(self, fw):
        if self.backend.get("reboot"):
            self._emit("· invio reboot nel bootloader…", SUB)
            _run([self.backend["reboot"]], timeout=20)
            time.sleep(1.0)
        self._emit("· scrittura firmware (attendo il Teensy)…", SUB)
        code, out = _run([self.backend["loader"], f"--mcu={BOARD}", "-w", "-v", fw], timeout=180)
        for line in out.splitlines():
            if line.strip():
                self._emit("  " + line.strip())
        if code == 0:
            return True, "Firmware scritto correttamente."
        if "press" in out.lower() and "button" in out.lower():
            return False, "Premi il pulsante PROGRAM sul Teensy e riprova."
        return False, f"teensy_loader_cli ha restituito codice {code}."

    # backend 2: Teensyduino tools (teensy_post_compile launches the Loader GUI)
    def _flash_teensyduino(self, fw):
        tmp = os.path.join(os.environ.get("TEMP", app_dir()), "ichosynth_flash")
        os.makedirs(tmp, exist_ok=True)
        hexpath = os.path.join(tmp, HEX_NAME)
        shutil.copyfile(fw, hexpath)

        pc = self.backend["post_compile"]
        tools = self.backend["tools"]
        self._emit("· avvio Teensy Loader e reboot nel bootloader…", SUB)
        code, out = _run([pc, "-file=" + os.path.splitext(HEX_NAME)[0], "-path=" + tmp,
                          "-tools=" + tools, "-board=" + BOARD, "-reboot"], timeout=40)

        need_button = ("press" in out.lower() and "button" in out.lower())
        if need_button:
            self._emit("⚠  Premi ORA il pulsante PROGRAM sul Teensy.", WARN)

        # watch USB: HalfKay (writing) -> back to RUN (done)
        saw_halfkay = False
        t0 = time.time()
        limit = 90 if need_button else 25
        while time.time() - t0 < limit:
            if _usb_present("VID_16C0&PID_0478"):
                if not saw_halfkay:
                    saw_halfkay = True
                    self._emit("· bootloader rilevato, scrittura in corso…", ACCENT2)
            elif saw_halfkay:
                # left HalfKay -> firmware written and rebooted
                time.sleep(1.2)
                return True, "Firmware scritto e Teensy riavviato."
            time.sleep(0.4)

        if saw_halfkay:
            return True, "Firmware scritto (verifica la board)."
        # never entered the bootloader
        if need_button:
            return False, "Tempo scaduto: il pulsante PROGRAM non è stato premuto."
        return False, ("Non sono riuscito a mettere il Teensy in bootloader. "
                       "Premi il pulsante PROGRAM e riprova.")

    # ---- queue pump ----
    def _drain_q(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "state":
                    self._set_state(payload)
                elif kind == "log":
                    self._log(payload[0], payload[1])
                elif kind == "flash_done":
                    self._finish_flash(*payload)
        except queue.Empty:
            pass

    def _finish_flash(self, ok, msg):
        self.flashing = False
        self.pbar.stop()
        self.pbar.configure(mode="determinate", value=100 if ok else 0)
        if ok:
            self.status.configure(text="Completato ✓")
            self._log("✓  " + msg, ACCENT)
            messagebox.showinfo("Fatto", "Firmware ichosynth caricato sul Teensy.\n\n" + msg)
        else:
            self.status.configure(text="Non riuscito")
            self._log("✗  " + msg, RED)
            messagebox.showerror("Flash non riuscito", msg)
        self._update_flash_enabled()

    # ---- about ----
    def show_about(self):
        win = tk.Toplevel(self.master)
        win.title("Informazioni")
        win.configure(bg=BG)
        win.resizable(False, False)
        win.transient(self.master)
        frm = ttk.Frame(win, padding=22)
        frm.pack(fill="both", expand=True)
        ttk.Label(frm, text="⚡  ichosynth — Flasher", style="Title.TLabel").pack(anchor="w")
        ttk.Label(frm, text=f"Versione {APP_VERSION}", style="Sub.TLabel").pack(anchor="w", pady=(0, 14))
        ttk.Label(frm, text="Sviluppato da", style="Sub.TLabel").pack(anchor="w")
        ttk.Label(frm, text=APP_AUTHOR, style="H2.TLabel").pack(anchor="w", pady=(0, 12))
        ttk.Label(frm, text="Carica il firmware ichosynth sul Teensy 4.1 in un clic:\n"
                            "rileva la board, entra nel bootloader e scrive il .hex.",
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


def main():
    root = tk.Tk()
    root.geometry("680x620")
    app = FlasherApp(root)
    if "--selftest" in sys.argv:
        root.after(400, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
