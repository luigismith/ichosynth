#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ichosynth - WAV Maker (GUI)
===========================
Friendly graphical converter that turns any WAV into the format the ichosynth
sampler needs - MONO / 16-bit / 44100 Hz - and names the files _<n>.wav.

- pick individual files or a whole folder
- see each file's current format and its target name before converting
- choose a separate output folder (originals are kept by default)
- progress bar + log; conversion runs off the UI thread

Pure standard library (tkinter + wave + audioop). On Python 3.13+ install the
'audioop-lts' backport so `import audioop` works.

Run:  python wavmaker_gui.py      (or launch the bundled wavmaker.exe)
"""
import os
import sys
import wave
import threading
import queue
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

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
# GUI
# =========================================================================
class WavMakerApp(ttk.Frame):
    def __init__(self, master):
        super().__init__(master, padding=0)
        self.master = master
        self.items = []            # list of dict: path, fmt
        self.q = queue.Queue()
        self.worker = None

        self._build_style()
        self._build_ui()
        self.pack(fill="both", expand=True)
        self._refresh_targets()
        self._log("Pronto. Aggiungi file WAV o una cartella per iniziare.")
        self._log("Suggerimento: le righe verdi sono già nel formato giusto (mono · 16-bit · 44100 Hz).", SUB)

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
        st.configure("TButton", background=PANEL, foreground=INK, bordercolor=LINE,
                     focuscolor=BG, padding=6)
        st.map("TButton", background=[("active", "#21262d")])
        st.configure("Accent.TButton", background=ACCENT, foreground="#06210f",
                     font=("Segoe UI", 11, "bold"), padding=9)
        st.map("Accent.TButton", background=[("active", "#2bbd5a"), ("disabled", LINE)])
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
        self.master.minsize(720, 560)

        # header
        head = ttk.Frame(self, padding=(18, 14, 18, 6))
        head.pack(fill="x")
        ttk.Label(head, text="🎵  ichosynth — WAV Maker", style="Title.TLabel").pack(anchor="w")
        ttk.Label(head, text="Converte i tuoi WAV in  mono · 16-bit · 44100 Hz  e li rinomina _<n>.wav",
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
        self.tree.column("file", width=240, anchor="w")
        self.tree.column("fmt", width=230, anchor="w")
        self.tree.column("arrow", width=28, anchor="center")
        self.tree.column("dst", width=130, anchor="w")
        self.tree.tag_configure("ok", background=ROW_OK)
        vs = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        # options
        opt = ttk.Frame(self, style="Panel.TFrame", padding=12)
        opt.pack(fill="x", padx=18, pady=(0, 6))
        opt.columnconfigure(1, weight=1)

        ttk.Label(opt, text="Numero di partenza", style="Panel.TLabel").grid(row=0, column=0, sticky="w")
        self.start_var = tk.IntVar(value=1)
        sp = ttk.Spinbox(opt, from_=0, to=99999, textvariable=self.start_var, width=8,
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
        folder = start // 100
        self.sd_hint.configure(text=f"→ va in  samples/{folder}/  sulla SD")
        if not self.out_var.get():
            self.out_var.set(self._default_output())
        for i, iid in enumerate(self.tree.get_children()):
            self.tree.set(iid, "dst", f"_{start + i}.wav")
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

    # ---- actions ----
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

    # ---- conversion (threaded) ----
    def start_convert(self):
        if audioop is None:
            messagebox.showerror("audioop mancante",
                                 "Serve il modulo audioop.\nPython 3.13+:  pip install audioop-lts")
            return
        if not self.items:
            messagebox.showinfo("Niente da fare", "Aggiungi prima qualche file WAV.")
            return
        out = self.out_var.get().strip() or self._default_output()
        try:
            os.makedirs(out, exist_ok=True)
        except Exception as e:
            messagebox.showerror("Cartella non valida", f"Impossibile creare:\n{out}\n\n{e}")
            return
        if self.delete_var.get():
            if not messagebox.askyesno("Confermi?",
                                       "Eliminerò gli ORIGINALI dopo la conversione.\nProcedo?"):
                return

        start = int(self.start_var.get())
        delete = self.delete_var.get()
        jobs = [(it["path"], os.path.join(out, f"_{start + i}.wav")) for i, it in enumerate(self.items)]

        self.convert_btn.configure(state="disabled")
        self.pbar.configure(maximum=len(jobs), value=0)
        self._log(f"--- conversione di {len(jobs)} file in: {out} ---", ACCENT2)
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
                                        f"{payload} file convertiti in:\n{self.out_var.get()}")
                    return
        except queue.Empty:
            pass
        self.status.configure(text=f"Converto… {int(self.pbar['value'])}/{len(self.items)}")
        self.after(80, self._poll)


def main():
    root = tk.Tk()
    root.geometry("780x680")
    app = WavMakerApp(root)
    # smoke-test hook: build the window then close immediately
    if "--selftest" in sys.argv:
        root.after(300, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    main()
