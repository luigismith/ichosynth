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
    W, H = 760, 384
    o = header(W, "Le manopole (encoder): gira e premi",
               "Ogni manopola si gira (cursore/valori) e si preme (azioni). Versione a 4 encoder.")

    knobs = [
        ("SX", "SINISTRA", "cursore ↑↓", "#3A6BE8",
         ["click → cancella nota", "2× click → modalità Single"]),
        ("C-SX", "CENTRALE-SX", "pagina / BPM", "#36C24A",
         ["push → disegna nota", "hold → disegno continuo"]),
        ("C-DX", "CENTRALE-DX", "filtro / seek", "#FF7A1A",
         ["click → Play / Pausa", "hold → Volume / BPM"]),
        ("DX", "DESTRA", "cursore ←→", "#E83AA6",
         ["click → mute voce", "2× click → velocity"]),
    ]
    n = len(knobs)
    colw = (W - 56) / n
    cy = 168
    r = 46
    for i, (tag, name, turn, col, gestures) in enumerate(knobs):
        cx = 28 + colw * i + colw / 2
        # rotation arc + arrows
        o.append(f'<path d="M {cx-62} {cy-6} A 62 62 0 0 1 {cx+62} {cy-6}" fill="none" stroke="{SUB}" stroke-width="1.5" opacity="0.7"/>')
        o.append(f'<polygon points="{cx+62},{cy-6} {cx+55},{cy-12} {cx+56},{cy-2}" fill="{SUB}"/>')
        o.append(f'<polygon points="{cx-62},{cy-6} {cx-56},{cy-12} {cx-55},{cy-2}" fill="{SUB}"/>')
        o.append(text(cx, cy - 70, "gira", size=11.5, fill=SUB, anchor="middle"))
        # knob body
        o.append(circle(cx, cy, r + 6, PANEL, LINE, 1.5))
        o.append(circle(cx, cy, r, "#222a35", col, 2.5))
        o.append(circle(cx, cy, r - 12, "#2c3543"))
        # indicator notch
        o.append(line(cx, cy - r + 6, cx, cy - r + 18, col, 3))
        # push center
        o.append(circle(cx, cy, 10, col, opacity=0.25))
        o.append(circle(cx, cy, 5, col))
        o.append(text(cx, cy + 4, "", size=10))
        # labels
        o.append(text(cx, cy + r + 26, name, size=13.5, fill=INK, anchor="middle", weight="700"))
        o.append(text(cx, cy + r + 44, turn, size=11.5, fill=SUB, anchor="middle"))
        # gesture chips
        gy = cy + r + 60
        for j, g in enumerate(gestures):
            yy = gy + j * 26
            o.append(rrect(cx - colw / 2 + 18, yy, colw - 36, 21, 6, "#1b2230", LINE, 1))
            o.append(text(cx, yy + 15, g, size=11, fill=INK, anchor="middle"))
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
    W, H = 860, 660
    o = header(W, "Mappa di cablaggio (tutti i pin del Teensy)",
               "I numeri sono pin Teensy 4.1, come in config.h. GND sempre in comune.")

    # Teensy center
    tx, ty, tw, th = 330, 250, 200, 210
    o.append(rrect(tx, ty, tw, th, 14, "#10212e", "#1f6feb", 2))
    o.append(text(tx + tw / 2, ty + 28, "Teensy 4.1", size=17, fill=INK, anchor="middle", weight="700"))
    o.append(text(tx + tw / 2, ty + 48, "+ 16 MB PSRAM", size=11.5, fill=SUB, anchor="middle"))
    o.append(rrect(tx + 30, ty + 64, tw - 60, 26, 6, "#0d1117", "#1f6feb", 1))
    o.append(text(tx + tw / 2, ty + 81, "Audio Shield (impilata)", size=11, fill=INK, anchor="middle"))

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
    node(345, 100, 170, 64, "Matrice LED 16×16", "WS2812B · 256 LED", "#E83A3A")
    conn(430, 164, 420, 250, DATA, "DIN 17", 470, 205)
    conn(400, 164, 360, 250, RED, "5V", 360, 205)

    # Encoders (left)
    encs = [
        ("SINISTRO", "5 / 22 / 15", "#3A6BE8", 96),
        ("CENTRALE-SX", "9 / 14 / 16", "#36C24A", 188),
        ("CENTRALE-DX", "32 / 33 / 41", "#FF7A1A", 280),
        ("DESTRO", "4 / 2 / 3", "#E83AA6", 372),
    ]
    for name, pins, col, y in encs:
        node(40, y, 200, 68, "Encoder " + name, "CLK / DT / SW", col)
        o.append(text(140, y + 58, pins, size=12, fill=INK, anchor="middle", family=MONO))
        conn(240, y + 34, tx, min(max(y + 34, ty + 20), ty + th - 20), col, None)
    o.append(text(285, 232, "CLK·DT·SW + 3V3 + GND", size=10.5, fill=SUB, anchor="middle"))

    # Audio shield power note (right top)
    node(620, 250, 200, 70, "Teensy Audio Shield", "SGTL5000 · jack 3.5mm", "#2AD4B8")
    conn(620, 285, tx + tw, 300, GREY, "I2S+I2C", 590, 270)
    o.append(text(720, 305, "7·8·18·19·20·21·23", size=10.5, fill=SUB, anchor="middle", family=MONO))

    # OLED (fork) right bottom, dashed green
    node(620, 380, 200, 78, "OLED SSD1306", "0x3C · 128×64", GREEN, dash="6 4")
    o.append(rrect(792, 386, 22, 16, 4, GREEN))
    o.append(text(803, 398, "fork", size=10, fill="#0d1117", anchor="middle", weight="700"))
    conn(620, 410, tx + tw, 360, DATA2, "SDA 18", 588, 392)
    conn(620, 428, tx + tw, 380, DATA2, "SCL 19", 590, 430)

    # legend
    ly = H - 40
    items = [("5V", RED), ("3V3", ORANGE), ("GND", GREY), ("dati", DATA), ("I2C/OLED", DATA2)]
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
    W, H = 640, 470
    o = header(W, "Struttura della micro SD",
               "Dove ichosynth cerca campioni, sample-pack e song.")

    def folder(x, y, w, label, accent="#FF8A1A"):
        o.append(f'<path d="M{x} {y+8} q0 -8 8 -8 h22 l8 8 h{w-46} q8 0 8 8 v22 q0 8 -8 8 h{-(w-16)} q-8 0 -8 -8 z" fill="{PANEL}" stroke="{accent}" stroke-width="1.5"/>')
        o.append(text(x + 16, y + 25, label, size=12.5, fill=INK, weight="600", family=MONO))

    def file(x, y, w, label, col=INK):
        o.append(rrect(x, y, w, 24, 5, "#1b2230", LINE, 1))
        o.append(text(x + 10, y + 16, label, size=11, fill=col, family=MONO))

    def elbow(x, y1, y2, x2):
        o.append(line(x, y1, x, y2, LINE, 1.5))
        o.append(line(x, y2, x2, y2, LINE, 1.5))

    # SD root
    o.append(rrect(28, 100, 150, 56, 8, "#10212e", "#1f6feb", 1.5))
    o.append(f'<path d="M40 100 v-0 h12 v0" fill="none"/>')
    o.append(text(103, 124, "microSD", size=13.5, fill=INK, anchor="middle", weight="700"))
    o.append(text(103, 142, "FAT32", size=11, fill=SUB, anchor="middle"))

    bx = 210
    # samples/
    folder(bx, 100, 150, "samples/")
    elbow(190, 128, 128, bx)
    subs = [("0/", ["_1.wav", "_2.wav", "…", "_99.wav"], 152),
            ("1/", ["_100.wav", "…", "_199.wav"], 252),
            ("2/", ["_200.wav", "…"], 332)]
    for name, files, y in subs:
        folder(bx + 60, y, 110, name, accent="#36C24A")
        elbow(bx + 20, 136, y + 18, bx + 60)
        fx = bx + 190
        for k, fn in enumerate(files):
            fy = y + k * 28 - (len(files) - 1) * 14 + 4
            file(fx, fy, 116, fn)
            o.append(line(bx + 170, y + 18, fx, fy + 12, LINE, 1))

    # packs + songs
    folder(bx, 372, 230, "1/ … 99/  →  1.wav … 12.wav", accent="#9A57E8")
    o.append(text(bx, 366, "Sample-pack (gestiti da ichosynth):", size=11, fill=SUB))
    file(bx, 414, 150, "1.txt … 100.txt")
    o.append(text(bx + 160, 430, "← le tue song", size=11, fill=SUB))
    file(bx, 442, 150, "autosaved.txt")
    o.append(text(bx + 160, 458, "← autosalvataggio", size=11, fill=SUB))
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
               "ichosynth genera il proprio clock solo se non ne riceve uno esterno.")
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
    W, H = 740, 560
    o = header(W, "Mappa delle modalità",
               "Da DRAW raggiungi ogni modalità con una combinazione di gesti. Ritorno: click C-SX / rilascia.")
    # DRAW
    o += _box(36, 250, 150, 60, "DRAW", "#e6edf3", sub="schermata principale")
    sat = [
        (320, 94, "Volume / BPM", "#FF7A1A", "hold C-DX", "rilascia"),
        (320, 172, "Velocity", "#E83AA6", "2× click DX", "rilascia"),
        (320, 255, "SINGLE", "#3A6BE8", "2× click SX", "2× click SX"),
        (320, 394, "Sample Pack", "#9A57E8", "hold SX + DX", "click C-SX"),
        (320, 478, "Menu salva/carica", "#2AD4B8", "hold C-DX + C-SX", "click C-SX"),
    ]
    for x, y, name, col, g, _back in sat:
        o += _box(x, y, 190, 54, name, col)
        o += _arrow(186, 280, x, y + 27, col, g)
    # SINGLE children
    children = [
        (560, 178, "Sample Browser", "hold SX + DX"),
        (560, 336, "Note Shift", "hold DX + C-DX"),
    ]
    for x, y, name, g in children:
        o += _box(x, y, 160, 50, name, "#3A6BE8")
        o += _arrow(510, 282, x, y + 25, "#3A6BE8", g)
    write("modes-map.svg", svg(W, H, o))


# =========================================================================
# 8) ASSEMBLY FLOW
# =========================================================================
def gen_assembly():
    steps = [
        ("1 · Teensy", "PSRAM + header", "#1f6feb"),
        ("2 · Audio", "scheda audio", "#2AD4B8"),
        ("3 · Matrice", "LED 16×16", "#E83A3A"),
        ("4 · Encoder", "×3–4", "#E8D23A"),
        ("5 · OLED", "fork (opz.)", GREEN),
        ("6 · Check", "multimetro", "#FF7A1A"),
        ("✅ Pronto", "firmware", GREEN),
    ]
    bw, bh, gap = 104, 56, 22
    W = 28 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    H = 170
    o = header(W, "Montaggio: i 6 passi", "Dal Teensy nudo al dispositivo pronto per il firmware.")
    x = 28
    y = 92
    for i, (t, s, c) in enumerate(steps):
        dash = "6 4" if t.startswith("5") else None
        o += _box(x, y, bw, bh, t, c, sub=s, dash=dash)
        if i < len(steps) - 1:
            o += _arrow(x + bw, y + bh / 2, x + bw + gap, y + bh / 2, GREY)
        x += bw + gap
    write("assembly-flow.svg", svg(W, H, o))


# =========================================================================
# 9) FLASH FLOW
# =========================================================================
def gen_flash():
    steps = [
        ("Arduino IDE", "+ Teensyduino", "#1f6feb"),
        ("Librerie", "FastLED, Audio…", "#2AD4B8"),
        ("ResamplingReader.h", "⚠ sostituisci", "#d29922"),
        ("USB Type", "Serial + MIDI", "#9A57E8"),
        ("config.h", "OLED / MIDI (opz.)", GREEN),
        ("Upload ▶", "carica sul Teensy", "#E83A3A"),
    ]
    bw, bh, gap = 132, 56, 22
    W = 28 * 2 + len(steps) * bw + (len(steps) - 1) * gap
    H = 170
    o = header(W, "Caricare il firmware: la sequenza", "Segui l'ordine; il passo 3 è obbligatorio.")
    x = 28
    y = 92
    for i, (t, s, c) in enumerate(steps):
        o += _box(x, y, bw, bh, t, c, sub=s)
        if i < len(steps) - 1:
            o += _arrow(x + bw, y + bh / 2, x + bw + gap, y + bh / 2, GREY)
        x += bw + gap
    write("flash-flow.svg", svg(W, H, o))


if __name__ == "__main__":
    gen_grid()
    gen_encoders()
    gen_voices()
    gen_wiring()
    gen_sd()
    gen_midi()
    gen_modes()
    gen_assembly()
    gen_flash()
    print("done.")
