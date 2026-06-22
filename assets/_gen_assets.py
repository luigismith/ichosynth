#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate the explanatory SVG infographics for the ichosynth manuals.
Pure stdlib, deterministic output. Run:  python assets/_gen_assets.py
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
FONT = "'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','Consolas','Courier New',monospace"

# ---- design tokens -------------------------------------------------------
BG      = "#0d1117"
PANEL   = "#161b22"
INK     = "#e6edf3"
SUB     = "#9aa4b2"
LINE    = "#30363d"
GREEN   = "#2ea44f"
ORANGE  = "#FF8A1A"
RED      = "#E03030"
GREY     = "#8a8f98"
DATA     = "#36C24A"
DATA2    = "#9A57E8"

VOICES = [
    (1,  "#E83A3A", "rosso",      "voce campione"),
    (2,  "#3A6BE8", "blu",        "voce campione"),
    (3,  "#E8D23A", "giallo",     "voce campione"),
    (4,  "#36C24A", "verde",      "voce campione"),
    (5,  "#E83AA6", "magenta",    "voce campione"),
    (6,  "#A6E03A", "verde-lime", "voce campione"),
    (7,  "#FF7A1A", "arancione",  "voce campione"),
    (8,  "#2AD4B8", "turchese",   "voce campione"),
    (13, "#9A57E8", "viola",      "synth (sawtooth)"),
    (14, "#E6E6E6", "bianco",     "synth (square)"),
]


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def text(x, y, s, size=14, fill=INK, anchor="start", weight="400",
         family=FONT, spacing=None, opacity=None):
    a = f' text-anchor="{anchor}"'
    w = f' font-weight="{weight}"'
    ls = f' letter-spacing="{spacing}"' if spacing else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return (f'<text x="{x}" y="{y}" font-family="{family}" font-size="{size}"'
            f' fill="{fill}"{a}{w}{ls}{op}>{esc(s)}</text>')


def rrect(x, y, w, h, rx, fill, stroke=None, sw=1.5, opacity=None, dash=None):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" fill="{fill}"{s}{d}{op}/>'


def line(x1, y1, x2, y2, stroke, sw=2, dash=None, cap="round", opacity=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" stroke-width="{sw}" stroke-linecap="{cap}"{d}{op}/>'


def circle(cx, cy, r, fill, stroke=None, sw=1.5, opacity=None):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    op = f' opacity="{opacity}"' if opacity is not None else ""
    return f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{fill}"{s}{op}/>'


def header(w, title, sub):
    o = [rrect(0, 0, w, 999, 0, BG)]
    o.append(text(28, 40, title, size=22, weight="700"))
    o.append(text(28, 64, sub, size=13.5, fill=SUB))
    o.append(line(28, 78, w - 28, 78, LINE, 1))
    return o


def svg(w, h, body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
            f'width="{w}" height="{h}" role="img">\n' + "\n".join(body) + "\n</svg>\n")


def write(name, content):
    p = os.path.join(HERE, name)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote", p, f"({len(content)} bytes)")


# =========================================================================
# 1) GRID CONCEPT
# =========================================================================
def gen_grid():
    W, H = 600, 548
    cell, gap = 22, 2
    step = cell + gap
    gx, gy = 150, 128
    N = 16
    o = header(W, "La griglia 16×16 = il tuo foglio musicale",
               "Righe = voci (colori) · Colonne = step · la testina suona colonna per colonna")

    notes = {
        0: [0, 4, 8, 12], 1: [4, 12], 2: [0, 2, 4, 6, 8, 10, 12, 14],
        3: [7, 15], 4: [2, 10], 5: [0, 6, 11], 6: [3, 9, 13],
        7: [5, 14], 12: [1, 8, 12], 13: [4, 11],
    }
    rowcol = {0: "#E83A3A", 1: "#3A6BE8", 2: "#E8D23A", 3: "#36C24A",
              4: "#E83AA6", 5: "#A6E03A", 6: "#FF7A1A", 7: "#2AD4B8",
              12: "#9A57E8", 13: "#E6E6E6"}
    playhead = 6

    # panel behind grid
    o.append(rrect(gx - 10, gy - 10, N * step + 18, N * step + 18, 10, PANEL, LINE, 1))

    # playhead column highlight
    px = gx + playhead * step - 1
    o.append(rrect(px, gy - 6, cell + 2, N * step + 8, 5, "#ffffff", opacity=0.13))
    # playhead marker triangle on top of the column
    pcx = px + (cell + 2) / 2
    o.append(f'<polygon points="{pcx-7},{gy-14} {pcx+7},{gy-14} {pcx},{gy-5}" fill="#ffffff"/>')

    # cells
    for r in range(N):
        for c in range(N):
            x = gx + c * step
            y = gy + r * step
            if r in notes and c in notes[r]:
                col = rowcol[r]
                o.append(rrect(x - 1, y - 1, cell + 2, cell + 2, 5, col, opacity=0.25))  # glow
                o.append(rrect(x, y, cell, cell, 4, col))
            else:
                o.append(rrect(x, y, cell, cell, 4, "#1b2230", LINE, 1))

    # cursor (pulsing dot) on an empty cell row3 col1
    cx = gx + 1 * step + cell / 2
    cy = gy + 9 * step + cell / 2
    o.append(circle(cx, cy, 9, "#ffffff", opacity=0.18))
    o.append(circle(cx, cy, 4.5, "#ffffff"))

    # axis: STEP arrow on top
    ay = gy - 30
    o.append(line(gx, ay, gx + N * step - gap, ay, SUB, 1.5))
    o.append(f'<polygon points="{gx+N*step-gap},{ay} {gx+N*step-gap-8},{ay-4} {gx+N*step-gap-8},{ay+4}" fill="{SUB}"/>')
    o.append(text(gx, ay - 6, "STEP (1 → 16)", size=12, fill=SUB))

    # axis: VOCI arrow on left
    o.append(line(gx - 26, gy, gx - 26, gy + N * step - gap, SUB, 1.5))
    o.append(f'<polygon points="{gx-26},{gy+N*step-gap} {gx-30},{gy+N*step-gap-8} {gx-22},{gy+N*step-gap-8}" fill="{SUB}"/>')
    o.append(f'<text x="{gx-36}" y="{gy+N*step/2}" font-family="{FONT}" font-size="12" fill="{SUB}" text-anchor="middle" transform="rotate(-90 {gx-36} {gy+N*step/2})">VOCI (8 campioni + synth)</text>')

    # bottom legend
    ly = gy + N * step + 24
    o.append(rrect(gx, ly, 14, 14, 4, "#E83A3A"))
    o.append(text(gx + 22, ly + 12, "nota (voce)", size=12.5, fill=SUB))
    o.append(rrect(gx + 142, ly, 14, 14, 4, "#1b2230", LINE, 1))
    o.append(text(gx + 164, ly + 12, "step vuoto", size=12.5, fill=SUB))
    o.append(circle(gx + 276, ly + 7, 5, "#ffffff"))
    o.append(text(gx + 288, ly + 12, "cursore", size=12.5, fill=SUB))
    o.append(rrect(gx + 354, ly, 14, 14, 4, "#ffffff", opacity=0.5))
    o.append(text(gx + 376, ly + 12, "testina ▼", size=12.5, fill=SUB))
    write("grid-concept.svg", svg(W, H, o))


# =========================================================================
# 2) ENCODERS
# =========================================================================
def gen_encoders():
    W, H = 760, 470
    o = header(W, "I comandi: 4 encoder + 3 pulsanti",
               "4 manopole (gira e premi) + 3 tact switch. Lo stato si legge sull'OLED.")

    knobs = [
        ("E1", "SINISTRA", "Y / canale", "#3A6BE8"),
        ("E2", "CENTRO-SX", "pagina / nota", "#36C24A"),
        ("E3", "CENTRO-DX", "filtro / valore", "#E8D23A"),
        ("E4", "DESTRA", "X / colonna", "#E83AA6"),
    ]
    n = len(knobs)
    colw = (W - 56) / n
    cy = 168
    r = 44
    for i, (tag, name, turn, col) in enumerate(knobs):
        cx = 28 + colw * i + colw / 2
        # rotation arc + arrows
        o.append(f'<path d="M {cx-60} {cy-6} A 60 60 0 0 1 {cx+60} {cy-6}" fill="none" stroke="{SUB}" stroke-width="1.5" opacity="0.7"/>')
        o.append(f'<polygon points="{cx+60},{cy-6} {cx+53},{cy-12} {cx+54},{cy-2}" fill="{SUB}"/>')
        o.append(f'<polygon points="{cx-60},{cy-6} {cx-54},{cy-12} {cx-53},{cy-2}" fill="{SUB}"/>')
        o.append(text(cx, cy - 66, "gira + premi", size=11, fill=SUB, anchor="middle"))
        # knob body
        o.append(circle(cx, cy, r + 6, PANEL, LINE, 1.5))
        o.append(circle(cx, cy, r, "#222a35", col, 2.5))
        o.append(circle(cx, cy, r - 12, "#2c3543"))
        # indicator notch
        o.append(line(cx, cy - r + 6, cx, cy - r + 18, col, 3))
        # push center
        o.append(circle(cx, cy, 10, col, opacity=0.25))
        o.append(circle(cx, cy, 5, col))
        # labels
        o.append(text(cx, cy + r + 24, tag + " · " + name, size=12.5, fill=INK, anchor="middle", weight="700"))
        o.append(text(cx, cy + r + 42, turn, size=11, fill=SUB, anchor="middle"))

    # 3 buttons row
    btns = [("B1", "PLAY", "play · SINGLE", "#36C24A"),
            ("B2", "MENU", "menu · tieni = FX", "#E8D23A"),
            ("B3", "REC", "rec · tieni = count-in", "#E83A3A")]
    by = cy + r + 64
    bw = 200
    bgap = (W - 56 - 3 * bw) / 2
    for i, (tag, name, act, col) in enumerate(btns):
        bx = 28 + i * (bw + bgap)
        o.append(rrect(bx, by, bw, 40, 9, PANEL, col, 2))
        o.append(text(bx + 16, by + 25, tag + " · " + name, size=13, fill=INK, weight="700"))
        o.append(text(bx + bw - 12, by + 25, act, size=10.5, fill=SUB, anchor="end"))

    # OLED note
    oy = by + 56
    o.append(rrect(28, oy, W - 56, 34, 8, "#10212e", GREEN, 1.5))
    o.append(text(W / 2, oy + 21,
                  "OLED: canale · modo · trasporto (PLAY/REC/STOP) · BPM · volume · pagina",
                  size=11.5, fill=INK, anchor="middle"))
    write("encoders.svg", svg(W, H, o))


# =========================================================================
# 3) VOICE COLORS
# =========================================================================
def gen_voices():
    W = 560
    rows = len(VOICES)
    rowh = 34
    top = 100
    H = top + rows * rowh + 24
    o = header(W, "Legenda colori delle voci",
               "Ogni riga della griglia è una voce, identificata da un colore (da colors.h).")
    for i, (num, col, name, role) in enumerate(VOICES):
        y = top + i * rowh
        o.append(rrect(28, y, W - 56, rowh - 8, 7, PANEL, LINE, 1))
        o.append(rrect(38, y + 5, 16, rowh - 18, 4, col,
                       stroke="#000000" if col == "#E6E6E6" else None, sw=1))
        o.append(text(70, y + 17, f"Voce {num}", size=13, fill=INK, weight="700"))
        o.append(text(168, y + 17, name, size=13, fill=INK))
        o.append(text(300, y + 17, role, size=12, fill=SUB))
    write("voice-colors.svg", svg(W, H, o))


# =========================================================================
# 4) WIRING MAP
# =========================================================================
def gen_wiring():
    W, H = 900, 700
    o = header(W, "Mappa di cablaggio (tutti i pin del Teensy)",
               "I numeri sono pin GPIO del Teensy 4.1. GND sempre in comune.")

    # Teensy center
    tx, ty, tw, th = 350, 270, 200, 210
    o.append(rrect(tx, ty, tw, th, 14, "#10212e", "#1f6feb", 2))
    o.append(text(tx + tw / 2, ty + 28, "Teensy 4.1", size=17, fill=INK, anchor="middle", weight="700"))
    o.append(text(tx + tw / 2, ty + 48, "+ 16 MB PSRAM", size=11.5, fill=SUB, anchor="middle"))
    o.append(rrect(tx + 30, ty + 64, tw - 60, 26, 6, "#0d1117", "#1f6feb", 1))
    o.append(text(tx + tw / 2, ty + 81, "Audio Shield (impilata)", size=11, fill=INK, anchor="middle"))
    o.append(text(tx + tw / 2, ty + 150, "ichosynth · firmware TŒRN", size=10.5, fill=SUB, anchor="middle"))

    def node(x, y, w, h, title, sub, accent, dash=None):
        o.append(rrect(x, y, w, h, 10, PANEL, accent, 2, dash=dash))
        o.append(text(x + w / 2, y + 22, title, size=13.5, fill=INK, anchor="middle", weight="700"))
        if sub:
            o.append(text(x + w / 2, y + 40, sub, size=11, fill=SUB, anchor="middle"))

    def conn(x1, y1, x2, y2, color, label, lx=None, ly=None):
        o.append(line(x1, y1, x2, y2, color, 2.5))
        if label:
            mx = lx if lx is not None else (x1 + x2) / 2
            my = ly if ly is not None else (y1 + y2) / 2
            tw2 = 8 + len(label) * 6.4
            o.append(rrect(mx - tw2 / 2, my - 11, tw2, 18, 5, BG, color, 1))
            o.append(text(mx, my + 2, label, size=10.5, fill=INK, anchor="middle", family=MONO))

    # LED matrix (top)
    node(365, 110, 170, 64, "Matrice LED 16×16", "WS2812B · 256 LED", "#E83A3A")
    conn(450, 174, 440, 270, DATA, "DIN 17", 490, 218)
    conn(420, 174, 380, 270, RED, "5V", 378, 218)

    # Encoders + buttons (left) — 4 encoders, collision-free pins
    encs = [
        ("E1 SINISTRO", "5 / 22 / 15", "#3A6BE8", 100),
        ("E2 CENTRALE", "32 / 33 / 41", "#36C24A", 188),
        ("E3 CENTRALE", "9 / 14 / 16", "#E8D23A", 276),
        ("E4 DESTRO", "37 / 38 / 39", "#E83AA6", 364),
    ]
    for name, pins, col, y in encs:
        node(40, y, 210, 64, name, "CLK / DT / SW", col)
        o.append(text(145, y + 56, pins, size=12, fill=INK, anchor="middle", family=MONO))
        conn(250, y + 32, tx, min(max(y + 32, ty + 20), ty + th - 20), col, None)
    o.append(text(297, 258, "CLK·DT·SW + 3V3 + GND", size=10.5, fill=SUB, anchor="middle"))

    # 3 buttons node (bottom-left)
    node(40, 470, 210, 78, "3 pulsanti (tact switch)", "B1 PLAY · B2 MENU · B3 REC", "#FF8A1A")
    o.append(text(145, 528, "25 / 26 / 28", size=12, fill=INK, anchor="middle", family=MONO))
    o.append(text(145, 542, "un piedino al pin, l'altro a GND", size=9.5, fill=SUB, anchor="middle"))
    conn(250, 500, tx, ty + th - 16, "#FFB454", None)

    # Audio shield power note (right top)
    node(650, 270, 200, 70, "Teensy Audio Shield", "SGTL5000 · Line In/Out + cuffie", "#2AD4B8")
    conn(650, 305, tx + tw, 320, GREY, "I2S+I2C", 610, 290)
    o.append(text(750, 325, "7·8·18·19·20·21·23", size=10.5, fill=SUB, anchor="middle", family=MONO))

    # OLED right bottom — now standard, solid green
    node(650, 400, 200, 70, "OLED SSD1306", "0x3C · 128×64 · 3V3", GREEN)
    o.append(text(750, 455, "condivide I²C col codec", size=9.5, fill=SUB, anchor="middle"))
    conn(650, 425, tx + tw, 380, DATA2, "SDA 18", 618, 408)
    conn(650, 443, tx + tw, 400, DATA2, "SCL 19", 620, 446)

    # legend
    ly = H - 40
    items = [("5V", RED), ("3V3", ORANGE), ("GND", GREY), ("dati", DATA),
             ("I2C/OLED", DATA2), ("pulsanti", "#FFB454")]
    lx = 40
    o.append(text(lx, ly - 16, "Legenda cavi:", size=12, fill=SUB, weight="600"))
    for lab, col in items:
        o.append(line(lx, ly, lx + 26, ly, col, 3))
        o.append(text(lx + 32, ly + 4, lab, size=11.5, fill=INK))
        lx += 32 + 12 + len(lab) * 7 + 22
    write("wiring-map.svg", svg(W, H, o))


# =========================================================================
# 5) SD STRUCTURE
# =========================================================================
def gen_sd():
    W, H = 660, 500
    o = header(W, "Struttura della micro SD (TŒRN)",
               "Samplepack <pack>/1-8.wav + libreria browser samples/<cat>/<nome>.wav")

    def folder(x, y, w, label, accent="#FF8A1A"):
        o.append(f'<path d="M{x} {y+8} q0 -8 8 -8 h22 l8 8 h{w-46} q8 0 8 8 v22 q0 8 -8 8 h{-(w-16)} q-8 0 -8 -8 z" fill="{PANEL}" stroke="{accent}" stroke-width="1.5"/>')
        o.append(text(x + 16, y + 25, label, size=12, fill=INK, weight="600", family=MONO))

    def file(x, y, w, label, col=INK):
        o.append(rrect(x, y, w, 24, 5, "#1b2230", LINE, 1))
        o.append(text(x + 10, y + 16, label, size=11, fill=col, family=MONO))

    def elbow(x, y1, y2, x2):
        o.append(line(x, y1, x, y2, LINE, 1.5))
        o.append(line(x, y2, x2, y2, LINE, 1.5))

    # SD root
    o.append(rrect(28, 110, 150, 56, 8, "#10212e", "#1f6feb", 1.5))
    o.append(text(103, 134, "microSD", size=13.5, fill=INK, anchor="middle", weight="700"))
    o.append(text(103, 152, "FAT32", size=11, fill=SUB, anchor="middle"))

    bx = 210
    # --- samplepacks: <pack>/1.wav .. 8.wav ---
    o.append(text(bx, 100, "Samplepack — 8 voci per cartella (caricati interi):", size=11, fill=SUB))
    packs = [("0/", "kit di fabbrica", 110, "#36C24A"),
             ("1/", "808", 178, "#36C24A"),
             ("…  99/", "fino a 100 pack", 246, "#36C24A")]
    for name, note, y, ac in packs:
        folder(bx, y, 110, name, accent=ac)
        elbow(190, 138, y + 18, bx)
        file(bx + 130, y, 130, "1.wav … 8.wav")
        o.append(line(bx + 110, y + 18, bx + 130, y + 12, LINE, 1))
        o.append(text(bx + 270, y + 16, "← " + note, size=10.5, fill=SUB))

    # --- browser library: samples/<cat>/<name>.wav ---
    o.append(text(bx, 300, "Libreria del browser (SET_WAV) — nomi liberi:", size=11, fill=SUB))
    folder(bx, 310, 110, "samples/", accent="#E8D23A")
    elbow(190, 138, 328, bx)
    cats = [("kick/", 310), ("snare/", 354), ("hat/", 398)]
    for name, y in cats:
        folder(bx + 130, y, 100, name, accent="#E8D23A")
        elbow(bx + 90, 328, y + 18, bx + 130)
        file(bx + 240, y, 150, "<nome>.wav")
        o.append(line(bx + 230, y + 18, bx + 240, y + 12, LINE, 1))

    # --- songs + autosave (root) ---
    file(bx, 452, 140, "1.txt … 999.txt")
    o.append(text(bx + 150, 468, "← le tue song", size=10.5, fill=SUB))
    file(bx + 290, 452, 140, "autosaved.txt")
    o.append(text(bx + 290, 446, "autosalvataggio:", size=10.5, fill=SUB))

    o.append(text(W / 2, H - 14, "Tutti i WAV: mono · 16-bit · 44100 Hz",
                  size=11, fill=SUB, anchor="middle"))
    write("sd-structure.svg", svg(W, H, o))


# =========================================================================
# shared flow helpers (local equivalents of the Mermaid diagrams)
# =========================================================================
import math


def _box(x, y, w, h, title, accent, sub=None, fill=PANEL, dash=None):
    p = [rrect(x, y, w, h, 9, fill, accent, 2, dash=dash)]
    if sub:
        p.append(text(x + w / 2, y + h / 2 - 2, title, 12.5, INK, "middle", "700"))
        p.append(text(x + w / 2, y + h / 2 + 15, sub, 10.5, SUB, "middle"))
    else:
        p.append(text(x + w / 2, y + h / 2 + 4.5, title, 12.5, INK, "middle", "700"))
    return p


def _arrow(x1, y1, x2, y2, color=GREY, label=None):
    ang = math.atan2(y2 - y1, x2 - x1)
    hx, hy = x2 - 9 * math.cos(ang), y2 - 9 * math.sin(ang)
    p = [line(x1, y1, hx, hy, color, 2)]
    a1 = ang + math.radians(150)
    a2 = ang - math.radians(150)
    p.append(f'<polygon points="{x2:.1f},{y2:.1f} {x2+10*math.cos(a1):.1f},{y2+10*math.sin(a1):.1f} {x2+10*math.cos(a2):.1f},{y2+10*math.sin(a2):.1f}" fill="{color}"/>')
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        tw = 9 + len(label) * 6.2
        p.append(rrect(mx - tw / 2, my - 10, tw, 18, 5, BG, color, 1))
        p.append(text(mx, my + 3, label, 10.5, INK, "middle"))
    return p


# =========================================================================
# 6) MIDI CLOCK master/slave
# =========================================================================
def gen_midi():
    W, H = 560, 360
    o = header(W, "MIDI clock: master o slave?",
               "ichosynth fa da master, oppure segue un clock MIDI esterno se presente.")
    o += _box(230, 104, 100, 46, "Premi Play", "#1f6feb")
    o += _box(170, 196, 220, 52, "Clock esterno", "#d29922", sub="ricevuto negli ultimi 750 ms?")
    o += _arrow(280, 150, 280, 196, GREY)
    o += _box(40, 300, 200, 48, "Resta SLAVE", "#3b82f6", sub="segue il clock esterno")
    o += _box(320, 300, 210, 48, "Diventa MASTER", GREEN, sub="invia Start + Clock 24 PPQN")
    o += _arrow(220, 248, 140, 300, "#3b82f6", "Sì")
    o += _arrow(340, 248, 420, 300, GREEN, "No")
    write("midi-clock.svg", svg(W, H, o))


# =========================================================================
# 7) MODES MAP (state machine)
# =========================================================================
def gen_modes():
    # Per-mode table: what each of the 4 encoders does. From _DOCS/MAPPA_CONTROLLI.md §5.
    cols = ["", "E1 ruota", "E2 ruota", "E3 ruota", "E4 ruota"]
    rows = [
        ("DRAW",     "Y / nota",  "pagina",      "filtro rapido", "X / colonna", "#e6edf3"),
        ("SINGLE",   "canale",    "nota (pitch)", "—",            "X / colonna", "#3A6BE8"),
        ("FILTER",   "slider 1",  "slider 2",    "slider 3",      "slider 4",    "#00FFFF"),
        ("MENU",     "—",         "valore",      "valore",        "naviga pagine", "#36C24A"),
        ("VELOCITY", "velocity",  "probabilità", "volume canale", "condizione",  "#E83AA6"),
        ("SONG",     "—",         "pattern",     "—",             "posizione",   "#E8D23A"),
    ]
    W = 860
    x0, y0 = 28, 100
    cw = [120, 168, 168, 168, 168]
    rh = 46
    H = y0 + (len(rows) + 1) * rh + 96
    o = header(W, "Mappa delle modalità — cosa fa ogni encoder",
               "I 4 encoder cambiano funzione col modo. I 3 pulsanti restano costanti.")

    # header row
    cx = x0
    for j, c in enumerate(cols):
        o.append(rrect(cx, y0, cw[j], rh, 7, "#10212e", "#1f6feb", 1))
        o.append(text(cx + cw[j] / 2, y0 + rh / 2 + 4, c, size=12.5, fill=INK,
                      anchor="middle", weight="700"))
        cx += cw[j]
    # data rows
    for i, row in enumerate(rows):
        name, e1, e2, e3, e4, col = row
        ry = y0 + (i + 1) * rh
        cx = x0
        cells = [name, e1, e2, e3, e4]
        for j, val in enumerate(cells):
            fill = PANEL if j else "#1b2230"
            o.append(rrect(cx, ry, cw[j], rh, 7, fill, LINE, 1))
            if j == 0:
                o.append(rrect(cx + 8, ry + 9, 6, rh - 18, 3, col))
                o.append(text(cx + 22, ry + rh / 2 + 4, val, size=12.5, fill=INK, weight="700"))
            else:
                o.append(text(cx + cw[j] / 2, ry + rh / 2 + 4, val, size=11.5,
                              fill=SUB if val == "—" else INK, anchor="middle"))
            cx += cw[j]

    # buttons strip
    by = y0 + (len(rows) + 1) * rh + 18
    o.append(text(x0, by - 4, "I 3 pulsanti (sempre attivi):", size=12, fill=SUB, weight="600"))
    btns = [("B1 PLAY", "play/pausa · SINGLE · esci", "#36C24A"),
            ("B2 MENU", "menu · tieni = FX MODE", "#E8D23A"),
            ("B3 REC", "rec · tap-tempo · tieni = count-in", "#E83A3A")]
    bw = (W - 56 - 2 * 16) / 3
    for i, (t, s, c) in enumerate(btns):
        bx = x0 + i * (bw + 16)
        o.append(rrect(bx, by + 6, bw, 46, 8, PANEL, c, 2))
        o.append(text(bx + 14, by + 26, t, size=12.5, fill=INK, weight="700"))
        o.append(text(bx + 14, by + 43, s, size=10, fill=SUB))
    write("modes-map.svg", svg(W, H, o))


# =========================================================================
# 8) ASSEMBLY FLOW
# =========================================================================
def gen_assembly():
    steps = [
        ("1 · Teensy", "PSRAM + header", "#1f6feb"),
        ("2 · Audio", "scheda audio", "#2AD4B8"),
        ("3 · Matrice", "LED 16×16", "#E83A3A"),
        ("4 · Encoder", "×4", "#E8D23A"),
        ("5 · Pulsanti", "×3", "#FF8A1A"),
        ("6 · OLED", "I²C", GREEN),
        ("7 · Check", "multimetro", "#9A57E8"),
        ("✅ Pronto", "firmware", GREEN),
    ]
    bw, bh, gap = 100, 56, 20
    W = 28 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    H = 170
    o = header(W, "Montaggio: i passi", "Dal Teensy nudo al dispositivo pronto per il firmware.")
    x = 28
    y = 92
    for i, (t, s, c) in enumerate(steps):
        o += _box(x, y, bw, bh, t, c, sub=s)
        if i < len(steps) - 1:
            o += _arrow(x + bw, y + bh / 2, x + bw + gap, y + bh / 2, GREY)
        x += bw + gap
    write("assembly-flow.svg", svg(W, H, o))


# =========================================================================
# 9) FLASH FLOW
# =========================================================================
def gen_flash():
    steps = [
        ("arduino-cli", "+ core teensy:avr", "#1f6feb"),
        ("build_toern.py", "compila (-O1)", "#2AD4B8"),
        ("toern.hex", "in teensy/firmware/", GREEN),
        ("Flash ▶", "GUI (_FLASHER) o CLI", "#E83A3A"),
    ]
    bw, bh, gap = 150, 56, 26
    W = 28 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    H = 170
    o = header(W, "Caricare il firmware: la sequenza",
               "Un comando compila il vero TŒRN e produce l'.hex da flashare.")
    x = 28
    y = 92
    for i, (t, s, c) in enumerate(steps):
        o += _box(x, y, bw, bh, t, c, sub=s)
        if i < len(steps) - 1:
            o += _arrow(x + bw, y + bh / 2, x + bw + gap, y + bh / 2, GREY)
        x += bw + gap
    write("flash-flow.svg", svg(W, H, o))


# =========================================================================
# 10) AUDIO I/O — Line In/Out 6.35mm + headphone
# =========================================================================
def gen_audio_io():
    W, H = 780, 380
    o = header(W, "Audio I/O: Line In/Out 6.35mm + cuffie",
               "I jack si collegano ai pad LINE IN / LINE OUT dell'Audio Shield (non ai GPIO).")

    # Audio Shield (left)
    sx, sy, sw, sh = 48, 116, 210, 196
    o.append(rrect(sx, sy, sw, sh, 12, "#10212e", "#2AD4B8", 2))
    o.append(text(sx + sw / 2, sy + 26, "Teensy Audio Shield", size=13.5, fill=INK, anchor="middle", weight="700"))
    o.append(text(sx + sw / 2, sy + 44, "SGTL5000", size=11, fill=SUB, anchor="middle"))

    # pads (right edge of the shield) -> jacks (right side)
    jx, jw = 520, 210
    rows = [
        ("LINE IN  L", "Line IN (mono)", GREEN, "tip → LINE IN L",  "in"),
        ("LINE OUT L", "Line OUT  L",    "#E83AA6", "tip → LINE OUT L", "out"),
        ("LINE OUT R", "Line OUT  R",    "#E83AA6", "tip → LINE OUT R", "out"),
        ("HP (su scheda)", "Cuffie 3.5mm", "#E8D23A", "stereo · monitor", "hp"),
    ]
    y = sy + 70
    dy = 40
    for pad, jack, col, lab, kind in rows:
        # pad chip on the shield edge
        o.append(rrect(sx + sw - 92, y - 13, 84, 24, 5, "#0d1117", col, 1))
        o.append(text(sx + sw - 50, y + 3, pad, size=9.5, fill=INK, anchor="middle", family=MONO))
        # jack box
        o.append(rrect(jx, y - 17, jw, 32, 7, PANEL, col, 1.5))
        o.append(circle(jx + 18, y - 1, 7, "#0d1117", col, 1.5))
        o.append(text(jx + 34, y + 3, jack, size=11.5, fill=INK, weight="700"))
        tw = 8 + len(lab) * 6
        # connector line + label
        if kind == "hp":
            o.append(text(jx + jw - 8, y + 3, "(integrato)", size=9.5, fill=SUB, anchor="end"))
            o.append(line(sx + sw - 8, y, jx, y, col, 1.5, dash="4 3"))
        else:
            o.append(line(sx + sw - 8, y, jx, y, col, 2))
            ar = "→" if kind == "out" else "←"
            o.append(text((sx + sw - 8 + jx) / 2, y - 6, ar, size=13, fill=col, anchor="middle"))
        y += dy

    # notes
    ny = sy + sh + 26
    o.append(text(48, ny, "Tutti i 6.35mm sono TS mono: tip = segnale, sleeve = GND (massa in comune).",
                  size=11.5, fill=SUB))
    o.append(text(48, ny + 20, "Line Out è stereo su due jack (L + R). Line In è mono: TŒRN campiona il canale L.",
                  size=11.5, fill=SUB))
    o.append(text(48, ny + 40, "Ingresso di default = LINE IN (registrazione). Nessuna modifica al firmware.",
                  size=11.5, fill=SUB))
    write("audio-io.svg", svg(W, H, o))


def gen_ichos():
    steps = [
        ("Ascolto", "i fondamenti", "#1f6feb"),
        ("Field recording", "i suoni dei luoghi", "#2AD4B8"),
        ("ichosynth", "lo costruisci · Teensy", GREEN),
        ("Performance", "elettroacustica", "#FF7A1A"),
        ("Documentario", "Vicoli Corti, 2026", "#9A57E8"),
    ]
    bw, bh, gap = 152, 60, 24
    W = 28 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    H = 280
    o = header(W, "ICHOS 2026 — Taranto",
               "Workshop di sound ecology di Francesco Giannico — l'ichosynth e' lo strumento che i partecipanti costruiscono.")
    x = 28
    y = 100
    for i, (t, s, c) in enumerate(steps):
        dash = "6 4" if t == "ichosynth" else None
        o += _box(x, y, bw, bh, t, c, sub=s, dash=dash)
        if i < len(steps) - 1:
            o += _arrow(x + bw, y + bh / 2, x + bw + gap, y + bh / 2, GREY)
        x += bw + gap

    sy = 206
    o.append(text(28, sy - 8, "I luoghi \"marginali\" del field recording:", size=12, fill=SUB, weight="600"))
    sites = [
        ("Circummarpiccolo", "ex itticoltura abbandonata"),
        ("Fiume Galeso", "ex stabilimenti balneari"),
        ("Punta Pizzone", "sito neolitico"),
    ]
    sx = 28
    for nm, desc in sites:
        wsite = 22 + max(len(nm), len(desc)) * 6.8
        o.append(rrect(sx, sy, wsite, 44, 8, PANEL, "#E83AA6", 1.5))
        o.append(text(sx + 12, sy + 19, nm, size=12, fill=INK, weight="700"))
        o.append(text(sx + 12, sy + 35, desc, size=10, fill=SUB))
        sx += wsite + 16
    write("ichos-project.svg", svg(W, H, o))


if __name__ == "__main__":
    gen_ichos()
    gen_grid()
    gen_encoders()
    gen_voices()
    gen_wiring()
    gen_sd()
    gen_midi()
    gen_modes()
    gen_assembly()
    gen_flash()
    gen_audio_io()
    print("done.")
