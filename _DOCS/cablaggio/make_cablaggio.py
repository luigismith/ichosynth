"""Guida grafica al cablaggio di ichosynth -> _DOCS/CABLAGGIO.html + CABLAGGIO.pdf

    python _DOCS/cablaggio/make_cablaggio.py

Illustrazioni vettoriali dei componenti veri (Teensy 4.1 con la piedinatura reale,
KY-040, OLED SSD1306, tact switch, matrice WS2812B, jack 6,35, morsetti a leva) e una
tavola per componente: "questo piedino va su quel pin".

I numeri dei pin NON sono scritti a mano: vengono letti dai driver del firmware
(teensy/libraries/i2cEncoderLibV2 e FastTouch) e dai sorgenti TŒRN, quindi la guida
non può divergere dal codice. La piedinatura del Teensy 4.1 è quella della scheda PJRC.
La stessa impaginazione viene inserita anche in _CASE/MONTAGGIO.pdf (pages()).
"""
import html
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
OUT = REPO / "_DOCS"

# --- verità dal codice ------------------------------------------------------------------------
def _macro(path, name):
    text = (REPO / path).read_text(encoding="utf-8", errors="replace")
    m = re.search(rf"#define\s+{name}\s+(.+)", text)
    if not m:
        raise SystemExit(f"{name} non trovato in {path}")
    return [int(v) for v in re.findall(r"\d+", m.group(1))]


ENC_PINS = _macro("teensy/libraries/i2cEncoderLibV2/i2cEncoderLibV2.h", "ICHOS_ENC_PINS")
BTN_PINS = _macro("teensy/libraries/FastTouch/FastTouch.h", "ICHOS_BTN_PINS")
LED_PIN = _macro("emulator/toern-src/toern.ino", "DATA_PIN")[0]
assert len(ENC_PINS) == 12 and len(BTN_PINS) == 3
ENC = {f"E{i + 1}": dict(zip(("CLK", "DT", "SW"), ENC_PINS[3 * i:3 * i + 3])) for i in range(4)}
BTN = dict(zip(("PLAY", "MENU", "REC"), BTN_PINS))
SDA, SCL = 18, 19                       # Wire (I2C0) del Teensy 4.1, condiviso con il codec

# piedinatura Teensy 4.1 (vista da sopra, USB in alto) — scheda PJRC card11a rev4
LEFT = ["GND"] + [str(i) for i in range(13)] + ["3.3V"] + [str(i) for i in range(24, 33)]
RIGHT = ["VIN", "GND", "3.3V"] + [str(i) for i in range(23, 12, -1)] + ["GND"] + [str(i) for i in range(41, 32, -1)]
UNDER_AUDIO = 14                        # le prime 14 posizioni di ogni lato stanno sotto la scheda audio

# colori dei fili (gli encoder hanno il colore della loro manopola)
C5V, C3V, CGND = "#E5484D", "#F59E0B", "#24292f"
ENC_COL = {"E1": "#3A6BE8", "E2": "#2DA44E", "E3": "#C9A400", "E4": "#E83AA6"}
BTN_COL, I2C_COL, LED_COL, LIN_COL = "#FF8A1A", "#8957E5", "#1A9E8F", "#57606a"
ORANGE, INK, SUB, BG = "#FF8A1A", "#1f2328", "#57606a", "#0d1117"
VOICE = ["#E83A3A", "#3A6BE8", "#E8D23A", "#36C24A", "#E83AA6", "#A6E03A", "#FF7A1A", "#2AD4B8"]
FONT = "'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "Consolas, 'JetBrains Mono', monospace"

# posizione fisica degli encoder sul pannello del case (dal generatore del case)
sys.path.insert(0, str(REPO / "_CASE"))
try:
    import build_case as _bc                                        # noqa: E402
    PANEL_POS = {k: v for k, v in _bc.ENCODERS.items()}
except Exception:                                                   # guida usabile anche senza il case
    PANEL_POS = {"E2": (0, 1), "E3": (1, 1), "E1": (0, 0), "E4": (1, 0)}


def pin_side(pin):
    """('sinistro'|'destro', posizione 1-based dall'alto, sotto la scheda audio?)"""
    p = str(pin)
    if p in LEFT:
        i = LEFT.index(p)
        return "sinistro", i + 1, i < UNDER_AUDIO
    i = RIGHT.index(p)
    return "destro", i + 1, i < UNDER_AUDIO


# --- primitive SVG ------------------------------------------------------------------------
def e(s):
    return html.escape(str(s))


def svg(w, h, body, cls=""):
    return (f'<svg class="{cls}" viewBox="0 0 {w} {h}" xmlns="http://www.w3.org/2000/svg" '
            f'font-family="{FONT}">{body}</svg>')


def rect(x, y, w, h, fill, stroke="none", sw=1, rx=0, extra=""):
    return f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" {extra}/>'


def circ(x, y, r, fill, stroke="none", sw=1):
    return f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'


def txt(x, y, s, size=12, fill=INK, anchor="start", weight="400", family=None, extra=""):
    fam = f' font-family="{family}"' if family else ""
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'font-weight="{weight}"{fam} {extra}>{e(s)}</text>')


def line(x1, y1, x2, y2, col, w=2, dash=None, cap="round"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    return f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="{w}" stroke-linecap="{cap}"{d}/>'


def path(d, col, w=2, fill="none", extra=""):
    return f'<path d="{d}" stroke="{col}" stroke-width="{w}" fill="{fill}" stroke-linecap="round" stroke-linejoin="round" {extra}/>'


def pill(x, y, s, col, size=12, anchor="start", dark_text=False):
    w = 8 + len(s) * size * 0.6
    x0 = x if anchor == "start" else (x - w if anchor == "end" else x - w / 2)
    tc = INK if dark_text else "#fff"
    return (rect(x0, y - size * 0.95, w, size * 1.45, col, rx=size * 0.7) +
            txt(x0 + w / 2, y + size * 0.1, s, size, tc, "middle", "700"))


# --- illustrazioni dei componenti ------------------------------------------------------------
def teensy_svg(marks, audio=True, sw=820, label_all=True):
    """Teensy 4.1 vista da sopra (USB in alto) con la piedinatura vera.
    marks: {pin: (colore, etichetta)} per i pin usati."""
    S = 9.0                                   # px per mm
    bw, bh = 17.78 * S, 61.0 * S
    bx, by = (sw - bw) / 2, 34
    o = []
    # scheda
    o.append(rect(bx, by, bw, bh, "#2a7a46", "#1d5a33", 2, rx=6))
    o.append(rect(bx + bw / 2 - 3.9 * S, by - 1.2 * S, 7.8 * S, 5.6 * S, "#c8ccd2", "#8b939c", 1.5, rx=3))   # micro-USB
    o.append(txt(bx + bw / 2, by - 1.8 * S, "USB", 12, SUB, "middle", "700"))
    o.append(rect(bx + bw / 2 - 5 * S, by + 24 * S, 10 * S, 10 * S, "#15171a", rx=3))                       # i.MX RT1062
    o.append(txt(bx + bw / 2, by + 29.6 * S, "i.MX RT", 11, "#9aa4b2", "middle"))
    o.append(rect(bx + bw / 2 - 5.5 * S, by + bh - 12 * S, 11 * S, 11.5 * S, "#d0d4da", "#9aa1aa", 1.5, rx=2))  # slot micro SD
    o.append(txt(bx + bw / 2, by + bh - 5.4 * S, "micro SD", 11, INK, "middle", "700"))
    o.append(txt(bx + bw / 2, by + 44 * S, "Teensy 4.1", 14, "#e6f4ea", "middle", "700"))
    if audio:                                 # zona coperta dalla scheda audio impilata
        h = UNDER_AUDIO * 2.54 * S + 0.6 * S
        o.append(rect(bx - 2, by + 0.2 * S, bw + 4, h, "#ffffff", "#2AD4B8", 2.5, rx=5,
                      extra='fill-opacity="0.18" stroke-dasharray="7 5"'))
        o.append(txt(bx + bw / 2, by + h - 1.4 * S, "sotto la", 10.5, "#e6f4ea", "middle", "700"))
        o.append(txt(bx + bw / 2, by + h + 0.2 * S, "scheda audio", 10.5, "#e6f4ea", "middle", "700"))
    for side, pins in (("L", LEFT), ("R", RIGHT)):
        px = bx + 1.27 * S if side == "L" else bx + bw - 1.27 * S
        for i, p in enumerate(pins):
            py = by + (1.27 + 2.54 * i) * S
            m = marks.get(p) if p not in ("GND", "3.3V", "VIN") else marks.get(f"{p}@{side}{i}")
            pwr = p in ("GND", "3.3V", "VIN")
            o.append(circ(px, py, 1.0 * S, "#d4a64a", "#8a6a1f", 1))
            o.append(circ(px, py, 0.45 * S, "#2a7a46"))
            lx = bx - 16 if side == "L" else bx + bw + 16
            anc = "end" if side == "L" else "start"
            col_txt = {"GND": CGND, "3.3V": C3V, "VIN": C5V}.get(p, SUB)
            if m:
                c, lab = m
                o.append(circ(px, py, 1.55 * S, "none", c, 3.2))
                o.append(line(px + (-1.55 if side == "L" else 1.55) * S, py, lx + (6 if side == "L" else -6), py, c, 2.2))
                name = txt(lx, py + 4.5, p, 13, col_txt if pwr else INK, anc, "800", MONO)
                o.append(name)
                off = 9 + len(p) * 8.2
                o.append(pill(lx - off if side == "L" else lx + off, py + 4.5, lab, c, 11.5, anc))
            elif label_all:
                o.append(txt(lx, py + 4.5, p, 12, col_txt if pwr else "#8c959f", anc, "700" if pwr else "400", MONO))
    return svg(sw, by + bh + 26, "".join(o), "ill")


def ky040_svg(enc, col, w=300):
    """Modulo KY-040 visto da sopra: encoder EC11, 5 pin in basso con le scritte del PCB."""
    S = 8.0
    pw, ph = 18.5 * S, 26 * S
    x0, y0 = (w - pw) / 2, 18
    o = [rect(x0, y0, pw, ph, "#15171a", "#2b2f36", 2, rx=5)]
    cx, cy = x0 + pw / 2, y0 + 10.5 * S
    o.append(rect(cx - 6 * S, cy - 6 * S, 12 * S, 12 * S, "#b9bec6", "#7d848d", 1.5, rx=2))
    o.append(circ(cx, cy, 3.6 * S, "#d6dae0", "#7d848d", 1.5))
    o.append(circ(cx, cy, 3.0 * S, col, "#00000033", 1))
    o.append(rect(cx - 0.35 * S, cy - 2.6 * S, 0.7 * S, 1.6 * S, "#ffffff", rx=1))
    o.append(txt(cx, y0 - 4, enc, 15, col, "middle", "800"))
    names = ["CLK", "DT", "SW", "+", "GND"]
    pinx = [cx + (k - 2) * 2.54 * S for k in range(5)]
    py = y0 + ph - 2.2 * S
    for k, n in enumerate(names):
        o.append(txt(pinx[k], py - 1.7 * S, n, 10.5, "#e6edf3", "middle", "700", MONO))
        o.append(rect(pinx[k] - 0.5 * S, py - 0.5 * S, 1.0 * S, 1.0 * S, "#d4a64a", rx=1))
        o.append(rect(pinx[k] - 0.32 * S, py, 0.64 * S, 5.5 * S, "#d4a64a"))
    wc = [col, col, col, C3V, CGND]
    for k in range(5):
        o.append(line(pinx[k], py + 5.5 * S, pinx[k], py + 9.5 * S, wc[k], 4))
    return svg(w, py + 9.8 * S, "".join(o), "ill")


def oled_svg(w=300):
    S = 7.5
    pw, ph = 27.3 * S, 27.8 * S
    x0, y0 = (w - pw) / 2, 10
    o = [rect(x0, y0, pw, ph, "#1f4fa8", "#163b80", 2, rx=5)]
    o.append(rect(x0 + 0.3 * S, y0 + 6 * S, pw - 0.6 * S, 15.5 * S, "#050608", "#30363d", 1, rx=2))
    o.append(rect(x0 + 2.8 * S, y0 + 8.2 * S, pw - 5.6 * S, 10.9 * S, "#0b1020", rx=1))
    for k, s in enumerate(("CH:1        >PLAY", "MODE: DRAW", "BPM:  120")):
        o.append(txt(x0 + 3.4 * S, y0 + 11.4 * S + k * 3.1 * S, s, 10, "#cfe9ff", family=MONO))
    names = ["GND", "VCC", "SCL", "SDA"]
    pinx = [x0 + pw / 2 + (k - 1.5) * 2.54 * S for k in range(4)]
    for k, n in enumerate(names):
        o.append(circ(pinx[k], y0 + 2.2 * S, 0.8 * S, "#d4a64a"))
        o.append(txt(pinx[k], y0 + 4.9 * S, n, 9.5, "#e6edf3", "middle", "700", MONO))
    for k, c in enumerate((CGND, C3V, I2C_COL, I2C_COL)):
        o.append(line(pinx[k], y0 + 2.2 * S, pinx[k], y0 - 9, c, 4))
    return svg(w, ph + 22, "".join(o), "ill")


def switch_svg(w=230):
    S = 14.0
    x0, y0 = (w - 6 * S) / 2, 40
    o = []
    legs = [(-1, -1), (1, -1), (-1, 1), (1, 1)]
    cxy = (x0 + 3 * S, y0 + 3 * S)
    for sx, sy in legs:
        lx, ly = cxy[0] + sx * 3.25 * S, cxy[1] + sy * 2.25 * S
        o.append(rect(lx - 0.35 * S, ly - 0.25 * S, 0.7 * S, 0.5 * S, "#c8ccd2", "#8b939c", 1))
    o.append(rect(x0, y0, 6 * S, 6 * S, "#16181d", rx=4))
    o.append(rect(x0 + 0.4 * S, y0 + 0.4 * S, 5.2 * S, 5.2 * S, "#b9bec6", rx=3))
    o.append(circ(*cxy, 1.75 * S, "#1d1f24"))
    # diagonale: alto-sinistra -> pin, basso-destra -> GND
    a = (cxy[0] - 3.6 * S, cxy[1] - 2.25 * S)
    b = (cxy[0] + 3.6 * S, cxy[1] + 2.25 * S)
    o.append(path(f"M{a[0]:.0f},{a[1]:.0f} q -26,0 -40,-28", BTN_COL, 4))
    o.append(path(f"M{b[0]:.0f},{b[1]:.0f} q 26,0 40,28", CGND, 4))
    o.append(line(a[0] + 8, a[1] + 6, b[0] - 8, b[1] - 6, "#ffffffcc", 1.5, "4 4"))
    o.append(pill(a[0] - 40, a[1] - 34, "al pin", BTN_COL, 11, "middle"))
    o.append(pill(b[0] + 40, b[1] + 44, "GND", CGND, 11, "middle"))
    return svg(w, y0 + 6 * S + 90, "".join(o), "ill")


def matrix_svg(w=360):
    o = [rect(20, 20, 300, 230, "#f3f1ec", "#d0ccc2", 2, rx=6)]
    for r in range(9):
        for c in range(12):
            x, y = 40 + c * 24, 36 + r * 24
            col = VOICE[(r + c) % 8] if (r * 7 + c * 3) % 11 == 0 else "#ffffff"
            o.append(rect(x, y, 13, 13, col, "#c9c4b8", 1, rx=2))
    o.append(rect(26, 232, 120, 22, "#ffffff", ORANGE, 2, rx=4))
    o.append(txt(86, 247, "DIN  →  (ingresso)", 11.5, ORANGE, "middle", "800"))
    for k, (c, lab) in enumerate(((C5V, "5V  rosso"), ("#e8e8e8", "GND  bianco"), ("#2DA44E", "DIN  verde"))):
        y = 262 + k * 12
        o.append(path(f"M{40 + k * 14},{252} C {40 + k * 14},{y + 20} {200},{y + 6} {250},{y + 6}", c if c != "#e8e8e8" else "#b5b5b5", 5))
        o.append(txt(258, y + 10, lab, 12, INK, "start", "700"))
    return svg(w, 310, "".join(o), "ill")


def jack_svg(w=330):
    o = [rect(40, 60, 70, 46, "#2b2e33", rx=4), rect(110, 70, 34, 26, "#c8ccd2", "#8b939c", 1.5, rx=2)]
    for k in range(6):
        o.append(line(114 + k * 5, 70, 114 + k * 5, 96, "#9aa1aa", 1.2))
    o.append(rect(144, 64, 8, 38, "#9aa1aa", rx=1))
    o.append(txt(150, 54, "dado fuori dal case", 11, SUB, "middle"))
    o.append(rect(52, 106, 8, 30, "#d4a64a", rx=2))      # linguetta punta
    o.append(rect(86, 106, 8, 30, "#d4a64a", rx=2))      # linguetta massa
    o.append(path("M56,136 C 56,170 120,176 170,176", LIN_COL, 4))
    o.append(path("M90,136 C 90,160 120,196 170,196", CGND, 4))
    o.append(pill(178, 180, "T punta → LINE IN L", LIN_COL, 11.5))
    o.append(pill(178, 200, "S massa → GND", CGND, 11.5))
    o.append(txt(75, 34, "jack mono 6,35 mm", 13, INK, "middle", "800"))
    return svg(w, 220, "".join(o), "ill")


def wago_svg(label, col, w=260):
    o = [rect(30, 30, 200, 56, "#d9dde2", "#9aa1aa", 2, rx=8)]
    for k in range(5):
        x = 44 + k * 38
        o.append(rect(x, 22, 24, 30, ORANGE, "#c96a00", 1.5, rx=4))
        o.append(circ(x + 12, 72, 6, "#4b5058"))
    o.append(pill(130, 112, label, col, 13, "middle"))
    return svg(w, 128, "".join(o), "ill")


def stack_svg(w=600):
    """Vista di lato: Teensy + header maschi lunghi + scheda audio, fili saldati in cima."""
    o = []
    x0 = 90
    o.append(rect(x0, 190, 400, 12, "#2a7a46", rx=3)); o.append(txt(x0 + 410, 201, "Teensy 4.1", 13, INK, "start", "700"))
    o.append(rect(x0, 98, 260, 12, "#2a7a46", rx=3)); o.append(txt(x0 + 270, 109, "scheda audio Rev D", 13, INK, "start", "700"))
    o.append(rect(x0, 178, 260, 12, "#1d1f24", rx=2)); o.append(txt(x0 + 270, 190, "plastica dell'header", 11, SUB))
    for k in range(9):
        x = x0 + 14 + k * 28
        o.append(rect(x - 2.5, 72, 5, 140, "#d4a64a"))
    o.append(rect(x0 + 2, 56, 34, 42, "#16181d", rx=4)); o.append(txt(x0 - 6, 70, "jack", 11, SUB, "end"))
    o.append(txt(x0 - 6, 84, "cuffie", 11, SUB, "end"))
    o.append(txt(x0 + 19, 226, "lato USB", 11, SUB, "middle", "700"))
    o.append(line(40, 110, 40, 178, SUB, 1.5)); o.append(line(34, 110, 46, 110, SUB, 1.5)); o.append(line(34, 178, 46, 178, SUB, 1.5))
    o.append(txt(52, 148, "≈11 mm", 12, INK, "start", "700"))
    # fili saldati sulle punte che sporgono sopra la scheda audio
    for k, c in ((3, ENC_COL["E1"]), (5, LED_COL), (7, I2C_COL)):
        x = x0 + 14 + k * 28
        o.append(circ(x, 76, 5, "#b9bec6"))
        o.append(path(f"M{x},{74} C {x},{44} {x + 50},{36} {x + 80},{30}", c, 4))
    o.append(pill(x0 + 300, 22, "saldi i fili sulle punte", ORANGE, 12))
    return svg(w, 236, "".join(o), "ill")


def overview_svg(w=760, h=470):
    """Vista d'insieme: ogni componente con il suo fascio di fili verso il Teensy."""
    o = []
    tx, ty, tw, th = 300, 110, 150, 230
    def bundle(x1, y1, x2, y2, col, n, lab_side="mid"):
        mx = (x1 + x2) / 2
        o.append(path(f"M{x1},{y1} C {mx},{y1} {mx},{y2} {x2},{y2}", col, 7, extra='stroke-opacity="0.9"'))
        o.append(pill(mx, (y1 + y2) / 2 + 4, f"{n} fili", col, 10, "middle"))
    # Teensy + scheda audio
    o.append(rect(tx, ty, tw, th, "#2a7a46", "#1d5a33", 2, rx=10))
    o.append(rect(tx - 10, ty - 4, tw + 20, 100, "#1f6b5a", "#2AD4B8", 2, rx=8, extra='fill-opacity="0.92"'))
    o.append(txt(tx + tw / 2, ty + 44, "scheda audio", 13, "#e6f4ea", "middle", "700"))
    o.append(txt(tx + tw / 2, ty + 62, "Rev D", 11, "#bfe6dc", "middle"))
    o.append(txt(tx + tw / 2, ty + 160, "Teensy 4.1", 15, "#e6f4ea", "middle", "800"))
    o.append(rect(tx + tw / 2 - 18, ty - 18, 36, 16, "#c8ccd2", "#8b939c", 1, rx=3))
    o.append(txt(tx + tw / 2, ty - 24, "USB · cuffie", 11, SUB, "middle", "700"))
    # encoder (destra, 2x2 come sul pannello)
    pos = {"E2": (600, 60), "E3": (700, 60), "E1": (600, 160), "E4": (700, 160)}
    for n, (x, y) in pos.items():
        o.append(rect(x - 34, y - 34, 68, 68, "#15171a", rx=8))
        o.append(circ(x, y - 4, 20, ENC_COL[n], "#00000044", 2))
        o.append(txt(x, y + 2, n, 14, "#fff", "middle", "800"))
    bundle(tx + tw, ty + 60, 566, 60, ENC_COL["E2"], 5)
    bundle(tx + tw, ty + 140, 566, 170, ENC_COL["E1"], 5)
    # E3 passa sopra E2, E4 sotto E1 (entrano dall'alto / dal basso del loro modulo)
    o.append(path(f"M{tx + tw},{ty + 30} C 540,{ty + 30} 560,8 650,8 S 700,14 700,26", ENC_COL["E3"], 7))
    o.append(pill(650, 12, "5 fili", ENC_COL["E3"], 10, "middle"))
    o.append(path(f"M{tx + tw},{ty + 115} C 520,{ty + 115} 540,226 650,226 S 700,206 700,194", ENC_COL["E4"], 7))
    o.append(pill(640, 230, "5 fili", ENC_COL["E4"], 10, "middle"))
    # OLED (in alto a destra)
    o.append(rect(560, 250, 120, 74, "#1f4fa8", rx=6)); o.append(rect(566, 266, 108, 46, "#050608", rx=3))
    o.append(txt(620, 294, "OLED", 13, "#cfe9ff", "middle", "700"))
    bundle(tx + tw, ty + 180, 560, 287, I2C_COL, 4)
    # pulsanti (in basso a destra)
    for k, n in enumerate(("PLAY", "MENU", "REC")):
        o.append(rect(560 + k * 64, 360, 52, 40, "#16181d", rx=6)); o.append(circ(586 + k * 64, 376, 9, "#3a3e45"))
        o.append(txt(586 + k * 64, 396, n, 9.5, "#e6edf3", "middle", "700"))
    bundle(tx + tw, ty + 215, 560, 380, BTN_COL, 6)
    # matrice (sinistra)
    o.append(rect(30, 40, 170, 170, "#f3f1ec", "#d0ccc2", 2, rx=6))
    for r in range(8):
        for c in range(8):
            col = VOICE[(r + c) % 8] if (r * 5 + c * 3) % 7 == 0 else "#ffffff"
            o.append(rect(44 + c * 19, 54 + r * 19, 11, 11, col, "#c9c4b8", 1, rx=2))
    bundle(200, 125, tx, ty + 40, LED_COL, 3)
    # jack LINE IN (sinistra in basso)
    o.append(rect(60, 300, 70, 40, "#2b2e33", rx=4)); o.append(rect(130, 308, 26, 24, "#c8ccd2", rx=2))
    o.append(txt(108, 290, "LINE IN", 12, INK, "middle", "800"))
    bundle(156, 320, tx, ty + 70, LIN_COL, 2)
    # morsetti 3V3 / GND (in basso al centro)
    for k, (lab, col) in enumerate((("3V3", C3V), ("GND", CGND))):
        x = 255 + k * 130
        o.append(rect(x, 382, 110, 34, "#d9dde2", "#9aa1aa", 1.5, rx=6))
        for j in range(5):
            o.append(rect(x + 8 + j * 20, 376, 14, 16, ORANGE, "#c96a00", 1, rx=3))
        o.append(pill(x + 55, 432, lab, col, 11, "middle"))
        o.append(path(f"M{x + 55},{382} L {x + 55},{ty + th}", col, 5))
    o.append(txt(w / 2, h - 4, "i fili + e GND di encoder, OLED, pulsanti e jack vanno ai morsetti", 11.5, SUB, "middle"))
    return svg(w, h + 6, "".join(o), "ill ov")


def panel_map_svg(w=230):
    """Dove sta ogni encoder sul pannello del case (vista da sopra)."""
    o = [rect(20, 10, 190, 196, "#2b2e33", rx=10)]
    o.append(rect(70, 22, 90, 26, "#050608", "#30363d", 1, rx=3))
    o.append(txt(115, 40, "OLED", 11, "#9aa4b2", "middle", "700"))
    us = sorted({u for u, _ in PANEL_POS.values()})
    vs = sorted({v for _, v in PANEL_POS.values()}, reverse=True)
    for n, (u, v) in PANEL_POS.items():
        x = 70 + us.index(u) * 90
        y = 80 + vs.index(v) * 62
        o.append(circ(x, y, 22, ENC_COL[n], "#00000055", 2))
        o.append(txt(x, y + 6, n, 16, "#fff", "middle", "800"))
    for k, n in enumerate(("PLAY", "MENU", "REC")):
        o.append(rect(32 + k * 60, 172, 48, 24, "#3a3e45", "#555b63", 1, rx=4))
        o.append(txt(56 + k * 60, 188, n, 10, "#e6edf3", "middle", "700"))
    return svg(w, 216, "".join(o), "ill")


# --- elementi di impaginazione ---------------------------------------------------------------
def where(pin):
    side, pos, under = pin_side(pin)
    s = f"lato {side}, {pos}° dall'alto"
    return s + (" · sopra la scheda audio" if under else "")


def wire_row(comp, comp_pin, color, target, hint):
    return (f'<div class="wr"><span class="cp" style="border-color:{color}">{e(comp)} <b>{e(comp_pin)}</b></span>'
            f'<span class="wl" style="background:{color}"></span>'
            f'<span class="tp"><b>{e(target)}</b><i>{e(hint)}</i></span></div>')


def card(title, body, accent=ORANGE, cls=""):
    return (f'<div class="card {cls}"><div class="ct"><span class="dot" style="background:{accent}"></span>'
            f'{e(title)}</div>{body}</div>')


def note(s, kind="info"):
    ico = {"info": "ℹ️", "warn": "⚠️", "ok": "✅"}[kind]
    return f'<div class="nt {kind}">{ico} {s}</div>'


def page(title, body, n):
    stripe = "".join(f'<i style="background:{c}"></i>' for c in VOICE)
    return (f'<section class="page"><header><div class="brand">ichosynth</div><div class="ttl">{e(title)}</div>'
            f'<div class="pn">{n}</div></header><div class="stripe">{stripe}</div><main>{body}</main></section>')


# --- pagine -----------------------------------------------------------------------------------
def marks_all():
    m = {}
    for n, d in ENC.items():
        for k, p in d.items():
            m[str(p)] = (ENC_COL[n], f"{n} {k}")
    for n, p in BTN.items():
        m[str(p)] = (BTN_COL, n)
    m[str(LED_PIN)] = (LED_COL, "matrice DIN")
    m[str(SDA)] = (I2C_COL, "OLED SDA")
    m[str(SCL)] = (I2C_COL, "OLED SCL")
    m["VIN@R0"] = (C5V, "5V → matrice")
    m["3.3V@L14"] = (C3V, "3V3 → morsetto")
    m["GND@R14"] = (CGND, "GND → morsetto")
    return m


def build_pages(start=1):
    P = []
    n = start

    # 1 · cosa ti serve + regole
    parts = [
        ("Teensy 4.1 + scheda audio Rev D", "il cervello e il suono"),
        ("4 × encoder KY-040", "E1 · E2 · E3 · E4"),
        ("3 × tact switch 6×6", "PLAY · MENU · REC"),
        ("OLED SSD1306 0,96\" I²C", "schermo di stato"),
        ("matrice WS2812B 16×16", "la griglia di LED"),
        ("1 × jack mono 6,35 mm", "LINE IN (registrare)"),
        ("2 × morsetti a leva (es. WAGO 221-415)", "barre 3V3 e GND, senza saldare"),
        ("2 strisce di header maschi lunghi (≥ 15 mm)", "Teensy ↔ scheda audio"),
        ("filo AWG 26 in 6+ colori, stagno, saldatore", "una ventina di fili da 10-15 cm"),
    ]
    lst = "".join(f'<li><b>{e(a)}</b><span>{e(b)}</span></li>' for a, b in parts)
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{e(t)}</span>' for c, t in (
        (C5V, "5V"), (C3V, "3,3 V"), (CGND, "GND (massa)"), (ENC_COL["E1"], "E1"), (ENC_COL["E2"], "E2"),
        (ENC_COL["E3"], "E3"), (ENC_COL["E4"], "E4"), (BTN_COL, "pulsanti"), (I2C_COL, "OLED (I²C)"),
        (LED_COL, "matrice"), (LIN_COL, "LINE IN")))
    rules = (note("<b>Tutte le masse (GND) insieme.</b> Ogni modulo va al morsetto GND, e il morsetto al GND del Teensy.", "warn") +
             note("<b>Encoder e OLED a 3,3 V, mai a 5 V.</b> Solo la matrice LED va a 5 V (pin VIN).", "warn") +
             note("<b>Un filo alla volta</b>: salda, controlla il numero del pin due volte, poi passa al prossimo.", "info") +
             note("Il colore dei fili è un consiglio: aiuta a non sbagliare. Gli encoder hanno il colore della loro manopola.", "info"))
    P.append(page("Cablaggio · cosa serve", f'<div class="g3"><div>{card("Componenti", f"<ul class=parts>{lst}</ul>")}</div>'
                  f'<div class="col">{card("Il quadro d\'insieme", overview_svg())}'
                  f'<div class="g2 tight">{card("Colori dei fili", f"<div class=legend>{legend}</div>")}{card("Tre regole", rules, C5V)}</div></div></div>', n))
    n += 1

    # 2 · la mappa del Teensy
    P.append(page("Cablaggio · il Teensy 4.1", f'<div class="g2 wide">'
                  f'<div class="ill-wrap">{teensy_svg(marks_all(), sw=640)}</div>'
                  f'<div>{card("Come leggere la mappa", note("Il Teensy è visto <b>da sopra</b>, con la presa <b>USB in alto</b>. I numeri sono quelli stampati sulla scheda e sul cartoncino che la accompagna.") + note("I pin <b>colorati</b> sono quelli che usi; gli altri restano liberi.") + note("La zona tratteggiata è coperta dalla <b>scheda audio</b>: quei pin si saldano sulle punte degli header lunghi, sopra la scheda audio (pagina seguente).") + note("Ci sono più pin GND e 3,3 V: usa quelli <b>fuori</b> dalla scheda audio (lato sinistro 15° = 3,3 V, lato destro 15° = GND) per i morsetti.", "ok"))}</div></div>', n))
    n += 1

    # 3 · scheda audio + alimentazione
    stack = card("1 · Impila la scheda audio",
                 f'{stack_svg()}' + note("Salda <b>2 strisce da 14 header maschi lunghi</b> sul Teensy (le prime 14 posizioni di ogni lato, dalla USB in giù), con la plastica appoggiata sul Teensy.") +
                 note("Infila la scheda audio con il <b>jack cuffie dallo stesso lato della USB</b>, a circa 11 mm, e saldala.") +
                 note("Le punte che sporgono sopra la scheda audio sono i pin del Teensy: <b>i fili dei pin sotto la scheda audio si saldano lì</b>.", "ok"))
    power = card("2 · Barre di alimentazione",
                 f'<div class="row2">{wago_svg("3V3", C3V)}{wago_svg("GND", CGND)}</div>' +
                 wire_row("Teensy", "3.3V", C3V, "morsetto 3V3", "lato sinistro, 15° dall'alto") +
                 wire_row("Teensy", "GND", CGND, "morsetto GND", "lato destro, 15° dall'alto") +
                 note("Ai morsetti vanno poi il <b>+</b> e il <b>GND</b> dei 4 encoder e dell'OLED, e il GND dei pulsanti e del jack.") +
                 note("Morsetti a leva: spellare 11 mm, alzare la leva, infilare, abbassare. Niente saldature.", "ok"))
    P.append(page("Cablaggio · scheda audio e alimentazione", f'<div class="g2">{stack}{power}</div>', n))
    n += 1

    # 4 · encoder
    rows = ""
    for name in ("E1", "E2", "E3", "E4"):
        r = "".join(wire_row(name, k, ENC_COL[name], f"pin {p}", where(p)) for k, p in ENC[name].items())
        r += wire_row(name, "+", C3V, "morsetto 3V3", "3,3 V, mai 5 V") + wire_row(name, "GND", CGND, "morsetto GND", "")
        rows += f'<div class="enc"><div class="enc-h" style="color:{ENC_COL[name]}">{name}</div>{r}</div>'
    left = (card("Il modulo KY-040", ky040_svg("E1", ENC_COL["E1"]) +
                 note("Le scritte <b>CLK DT SW + GND</b> sono stampate sul modulo: leggi le tue, l'ordine può cambiare.")) +
            card("Dove sta ogni encoder", panel_map_svg() + note("E1 ed E4 (cursore) in basso, vicino alla mano.")))
    tip = note("Se un encoder gira al contrario, <b>scambia i fili CLK e DT</b> di quell'encoder. Se un click "
               "fa due passi, vedi <code>ICHOS_ENC_COUNTS_PER_DETENT</code> nel driver.", "info")
    P.append(page("Cablaggio · 4 encoder KY-040",
                  f'<div class="g2 enc-g"><div>{left}</div><div class="encs">{rows}<div class="span2">{tip}</div></div></div>', n))
    n += 1

    # 5 · pulsanti + OLED
    btn_rows = "".join(wire_row(k, "gamba", BTN_COL, f"pin {p}", where(p)) + wire_row(k, "gamba opposta", CGND, "morsetto GND", "")
                       for k, p in BTN.items())
    btn = card("3 pulsanti", switch_svg() + note("Usa <b>due gambe in diagonale</b>: così il contatto c'è sempre, in qualunque verso lo monti.") + btn_rows, BTN_COL)
    ol = card("Schermo OLED", oled_svg() +
              wire_row("OLED", "GND", CGND, "morsetto GND", "") + wire_row("OLED", "VCC", C3V, "morsetto 3V3", "3,3 V") +
              wire_row("OLED", "SCL", I2C_COL, f"pin {SCL}", where(SCL)) + wire_row("OLED", "SDA", I2C_COL, f"pin {SDA}", where(SDA)) +
              note("Su alcuni moduli <b>VCC e GND sono invertiti</b>: segui le scritte stampate sul tuo.", "warn") +
              note("L'OLED condivide SDA/SCL con la scheda audio: è normale, hanno indirizzi diversi."), I2C_COL)
    P.append(page("Cablaggio · pulsanti e OLED", f'<div class="g2">{btn}{ol}</div>', n))
    n += 1

    # 6 · matrice + line in
    mx = card("Matrice LED 16×16", matrix_svg() +
              wire_row("matrice", "5V (rosso)", C5V, "pin VIN", "lato destro, 1° in alto · sopra la scheda audio") +
              wire_row("matrice", "GND (bianco)", CGND, "morsetto GND", "") +
              wire_row("matrice", "DIN (verde)", LED_COL, f"pin {LED_PIN}", where(LED_PIN)) +
              note("Usa il connettore dove la freccia <b>entra</b> nella matrice (DIN), non quello d'uscita (DOUT).", "warn") +
              note("I colori dei fili della matrice variano fra i produttori: conta la scritta sul PCB (5V / GND / DIN)."), LED_COL)
    li = card("LINE IN (per registrare)", jack_svg() +
              note("Il pad <b>LINE IN L</b> è sulla scheda audio, vicino alle scritte LINE IN: c'è scritto sul PCB.") +
              note("Le cuffie si collegano al jack 3,5 mm della scheda audio: nessun filo da saldare.", "ok") +
              note("<b>Non montare il potenziometro del volume</b> sulla scheda audio: il suo pad (A1) è il pin 15, usato da E1.", "warn") +
              note("MIDI DIN (facoltativo): pin 34 = IN, 35 = OUT, serve un circuito con optoisolatore."), LIN_COL)
    P.append(page("Cablaggio · matrice e audio", f'<div class="g2">{mx}{li}</div>', n))
    n += 1

    # 7 · controllo finale
    checks = [
        "Ogni filo del Teensy va al numero giusto: confronta con la mappa a pagina 2.",
        "Nessun filo va a 5 V tranne il rosso della matrice (pin VIN).",
        "Tutti i GND arrivano al morsetto GND, e il morsetto al GND del Teensy.",
        "Multimetro in continuità: <b>nessun corto</b> fra 5 V e GND e fra 3,3 V e GND.",
        "Nessuna goccia di stagno fra due pin vicini (guarda con una lente).",
        "Micro-SD nello slot del <b>Teensy</b> (in basso sulla scheda), non in quello della scheda audio.",
        "Poi collega la USB: la matrice si accende e l'OLED mostra CH / MODE / BPM.",
    ]
    ck = "".join(f'<li><span class="box"></span><span>{c}</span></li>' for c in checks)
    summary = "".join(f'<span class="sm" style="border-color:{c}"><b>{e(a)}</b> → {e(b)}</span>' for a, b, c in (
        [(f"{k} {kk}", f"pin {p}", ENC_COL[k]) for k, d in ENC.items() for kk, p in d.items()] +
        [(k, f"pin {p}", BTN_COL) for k, p in BTN.items()] +
        [("OLED SDA", f"pin {SDA}", I2C_COL), ("OLED SCL", f"pin {SCL}", I2C_COL), ("matrice DIN", f"pin {LED_PIN}", LED_COL),
         ("matrice 5V", "VIN", C5V), ("LINE IN", "pad LINE IN L", LIN_COL)]))
    P.append(page("Cablaggio · controllo finale", f'<div class="g2">{card("Prima di accendere", f"<ul class=checks>{ck}</ul>", "#2DA44E")}'
                  f'<div class="col">{card("Tutti i collegamenti", f"<div class=summary>{summary}</div>")}'
                  f'{card("Il quadro d\'insieme", overview_svg())}</div></div>', n))
    n += 1
    return P, n


CSS = f"""
@page {{ size: A4 landscape; margin: 0; }}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: {FONT}; color: {INK}; background: #fff; }}
.page {{ width: 297mm; height: 210mm; page-break-after: always; position: relative; overflow: hidden;
         display: flex; flex-direction: column; }}
header {{ background: {BG}; color: #e6edf3; display: flex; align-items: center; height: 15mm; padding: 0 9mm; }}
.brand {{ font-weight: 800; font-size: 6.5mm; }}
.ttl {{ margin-left: 8mm; font-size: 4.6mm; color: #9aa4b2; text-transform: uppercase; letter-spacing: .1em; }}
.pn {{ margin-left: auto; font-size: 5mm; font-weight: 700; }}
.stripe {{ display: flex; height: 1.6mm; }} .stripe i {{ flex: 1; }}
main {{ flex: 1; padding: 5mm 8mm 6mm; display: flex; flex-direction: column; gap: 3mm; min-height: 0; }}
.g2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; flex: 1; min-height: 0; }}
.g2.wide {{ grid-template-columns: 1.35fr 1fr; }}
.g2.enc-g {{ grid-template-columns: 0.72fr 1.6fr; }}
.g2.tight {{ flex: none; gap: 4mm; }}
.g3 {{ display: grid; grid-template-columns: 0.75fr 1.65fr; gap: 5mm; flex: 1; min-height: 0; }}
.col {{ display: flex; flex-direction: column; min-height: 0; }}
.span2 {{ grid-column: 1 / span 2; }}
.ill.ov {{ max-height: 100mm; }}
.enc-g .ill {{ max-height: 52mm; }}
.card {{ border: .4mm solid #e3e6ea; border-radius: 3.5mm; padding: 3.5mm 4mm; display: flex; flex-direction: column;
         gap: 2mm; min-height: 0; margin-bottom: 3mm; }}
.ct {{ font-weight: 800; font-size: 4.6mm; display: flex; align-items: center; gap: 2mm; }}
.dot {{ width: 3.4mm; height: 3.4mm; border-radius: 50%; display: inline-block; }}
.ill {{ width: 100%; height: auto; max-height: 72mm; }}
.ill-wrap .ill {{ max-height: 182mm; }}
.row2 {{ display: flex; gap: 3mm; }} .row2 .ill {{ max-height: 26mm; }}
.nt {{ font-size: 3.35mm; line-height: 1.35; padding: 1.4mm 2.4mm; border-radius: 2mm; background: #f3f5f7; }}
.nt.warn {{ background: #fff4e5; }} .nt.ok {{ background: #eaf7ee; }}
.nt code {{ font-family: {MONO}; font-size: 3mm; }}
.wr {{ display: flex; align-items: center; gap: 2mm; font-size: 3.4mm; }}
.cp {{ border: .7mm solid; border-radius: 99px; padding: .4mm 2.4mm; white-space: nowrap; min-width: 26mm; }}
.wl {{ flex: 0 0 11mm; height: 1.4mm; border-radius: 1mm; }}
.tp {{ display: flex; flex-direction: column; line-height: 1.15; }}
.tp b {{ font-family: {MONO}; font-size: 3.8mm; }} .tp i {{ font-style: normal; color: {SUB}; font-size: 2.8mm; }}
.encs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 3mm 5mm; align-content: start; }}
.enc {{ border: .4mm solid #e3e6ea; border-radius: 3mm; padding: 2mm 3mm; display: flex; flex-direction: column; gap: 1.2mm; }}
.enc-h {{ font-weight: 900; font-size: 5.5mm; }}
.enc .wr {{ font-size: 3.1mm; }} .enc .cp {{ min-width: 18mm; }}
ul.parts {{ list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 1.6mm; }}
ul.parts li {{ display: flex; flex-direction: column; font-size: 3.8mm; border-left: 1.2mm solid {ORANGE}; padding-left: 2.5mm; }}
ul.parts li span {{ color: {SUB}; font-size: 3.1mm; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 2mm 4mm; }}
.lg {{ display: inline-flex; align-items: center; gap: 1.5mm; font-size: 3.5mm; font-weight: 600; }}
.lg i {{ width: 9mm; height: 2mm; border-radius: 1mm; display: inline-block; }}
ul.checks {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2.4mm; font-size: 3.8mm; }}
ul.checks li {{ display: flex; gap: 2.5mm; align-items: flex-start; }}
.box {{ flex: 0 0 4.5mm; height: 4.5mm; border: .5mm solid {INK}; border-radius: 1mm; margin-top: .3mm; }}
.summary {{ display: flex; flex-wrap: wrap; gap: 1.6mm; }}
.sm {{ border: .6mm solid; border-radius: 99px; padding: .5mm 2.4mm; font-size: 3.2mm; white-space: nowrap; }}
"""


def html_doc(pages, title="ichosynth · cablaggio"):
    return (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><title>{e(title)}</title>'
            f'<style>{CSS}</style></head><body>{"".join(pages)}</body></html>')


CHROME = ["C:/Program Files/Google/Chrome/Application/chrome.exe",
          "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
          "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Microsoft/Edge/Application/msedge.exe"]


def to_pdf(html_path):
    chrome = next((p for p in CHROME if Path(p).exists()), None)
    if not chrome:
        print("Chrome/Edge non trovato: PDF non generato (l'HTML è pronto)")
        return None
    pdf = html_path.with_suffix(".pdf")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf}", html_path.as_uri()], check=True, capture_output=True, timeout=180)
    return pdf


def export_assets():
    """Le stesse illustrazioni come SVG autonomi in assets/ (sfondo bianco), per i manuali .md."""
    items = {
        "ill-teensy-pinout": teensy_svg(marks_all(), sw=640),
        "ill-overview": overview_svg(),
        "ill-stack": stack_svg(),
        "ill-ky040": ky040_svg("E1", ENC_COL["E1"]),
        "ill-oled": oled_svg(),
        "ill-switch": switch_svg(),
        "ill-matrix": matrix_svg(),
        "ill-linein": jack_svg(),
        "ill-power": svg(540, 128, wago_svg("3V3", C3V).split(">", 1)[1].rsplit("</svg>", 1)[0] +
                         '<g transform="translate(270,0)">' +
                         wago_svg("GND", CGND).split(">", 1)[1].rsplit("</svg>", 1)[0] + "</g>", "ill"),
        "ill-panel-map": panel_map_svg(),
    }
    for name, s in items.items():
        vb = re.search(r'viewBox="0 0 ([\d.]+) ([\d.]+)"', s)
        w, h = vb.group(1), vb.group(2)
        s = s.replace("<svg ", f'<svg width="{w}" height="{h}" ', 1)
        s = s.replace(">", f'><rect width="{w}" height="{h}" fill="#ffffff"/>', 1)
        (REPO / "assets" / f"{name}.svg").write_text(s + "\n", encoding="utf-8")
    print("illustrazioni ->", ", ".join(f"assets/{n}.svg" for n in items))


def main():
    export_assets()
    pages, _ = build_pages(1)
    out = OUT / "CABLAGGIO.html"
    out.write_text(html_doc(pages), encoding="utf-8")
    pdf = to_pdf(out)
    print("scritto", out.relative_to(REPO), "e", pdf.relative_to(REPO) if pdf else "(niente PDF)")


if __name__ == "__main__":
    main()
