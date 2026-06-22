#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the local ichosynth design-system library for claude.ai/design.

Generates self-contained HTML preview cards under design/ — each starts with a
`<!-- @dsCard group="..." -->` marker (first line) so the Claude Design pane indexes
it. Diagram cards inline the existing assets/*.svg so they render standalone.

Run:  python design/_build_design.py
Then the cards are pushed to a Claude Design project via the DesignSync tool.
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(HERE, "..", "assets")

# ---- ichosynth design tokens (kept in sync with assets/_gen_assets.py) ----
BG, PANEL, INK, SUB, LINE = "#0d1117", "#161b22", "#e6edf3", "#9aa4b2", "#30363d"
FONT = "'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "'JetBrains Mono','Consolas','Courier New',monospace"

FOUNDATION_COLORS = [
    ("Background", BG), ("Panel", PANEL), ("Ink (testo)", INK),
    ("Sub (testo 2)", SUB), ("Line / bordo", LINE), ("Accent green", "#2ea44f"),
]
ENCODER_COLORS = [("E1 sinistra", "#3A6BE8"), ("E2", "#36C24A"),
                  ("E3", "#E8D23A"), ("E4 destra", "#E83AA6"), ("Pulsanti", "#FF8A1A")]
VOICE_COLORS = [
    ("Voce 1", "#E83A3A"), ("Voce 2", "#3A6BE8"), ("Voce 3", "#E8D23A"),
    ("Voce 4", "#36C24A"), ("Voce 5", "#E83AA6"), ("Voce 6", "#A6E03A"),
    ("Voce 7", "#FF7A1A"), ("Voce 8", "#2AD4B8"),
    ("Synth viola", "#9A57E8"), ("Synth bianco", "#E6E6E6"),
]

# (filename without ext, card title, group)
DIAGRAMS = [
    ("wiring-map", "Mappa di cablaggio", "Diagrammi"),
    ("audio-io", "Audio I/O (jack 6.35mm)", "Diagrammi"),
    ("encoders", "Comandi: 4 encoder + 3 pulsanti", "Diagrammi"),
    ("modes-map", "Mappa delle modalità", "Diagrammi"),
    ("grid-concept", "La griglia 16×16", "Diagrammi"),
    ("voice-colors", "Colori delle voci", "Diagrammi"),
    ("sd-structure", "Struttura micro SD", "Diagrammi"),
    ("assembly-flow", "Flusso di montaggio", "Diagrammi"),
    ("flash-flow", "Flusso di flash", "Diagrammi"),
    ("midi-clock", "MIDI clock master/slave", "Diagrammi"),
    ("ichos-project", "Progetto ICHOS 2026", "Diagrammi"),
]

PAGE_CSS = f"""*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:{BG};color:{INK};font-family:{FONT}}}
.wrap{{padding:24px}}
.h{{font-size:13px;color:{SUB};text-transform:uppercase;letter-spacing:.08em;margin-bottom:14px}}
.title{{font-size:22px;font-weight:700;margin-bottom:4px}}
.mono{{font-family:{MONO}}}"""


def card(group, body, title=None, name=None, subtitle=None):
    """Return an HTML preview file. First line MUST be the @dsCard marker."""
    attrs = f'group="{group}"'
    if name:
        attrs += f' name="{name}"'
    if subtitle:
        attrs += f' subtitle="{subtitle}"'
    head = (f'<!-- @dsCard {attrs} -->\n<!doctype html><html lang="it"><head>'
            f'<meta charset="utf-8"><style>{PAGE_CSS}</style></head>'
            f'<body><div class="wrap">')
    t = f'<div class="title">{title}</div>' if title else ""
    return head + t + body + "</div></body></html>\n"


def write(rel, content):
    p = os.path.join(HERE, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    print("wrote design/" + rel)


def swatches(items, big=False):
    cells = []
    for nm, hx in items:
        sz = 88 if big else 60
        border = f"border:1px solid {LINE};" if hx in (BG, PANEL, "#E6E6E6") else ""
        cells.append(
            f'<div style="display:flex;flex-direction:column;gap:6px">'
            f'<div style="width:{sz}px;height:{sz}px;border-radius:10px;background:{hx};{border}"></div>'
            f'<div style="font-size:12px;font-weight:600">{nm}</div>'
            f'<div class="mono" style="font-size:11px;color:{SUB}">{hx}</div></div>')
    return ('<div style="display:flex;flex-wrap:wrap;gap:18px">' + "".join(cells) + "</div>")


def build_colors():
    body = ('<div class="h">Base</div>' + swatches(FOUNDATION_COLORS, big=True)
            + '<div class="h" style="margin-top:24px">Encoder &amp; pulsanti</div>'
            + swatches(ENCODER_COLORS)
            + '<div class="h" style="margin-top:24px">Voci (righe della griglia)</div>'
            + swatches(VOICE_COLORS))
    write("foundations/colors.html",
          card("Foundations", body, "Palette colori", "Palette colori",
               "Tema scuro + accenti encoder/voci"))


def build_typography():
    body = f"""
<div style="font-size:36px;font-weight:700">ichosynth</div>
<div style="font-size:20px;font-weight:700;margin-top:18px">Titolo sezione (Segoe UI 700)</div>
<div style="font-size:14px;color:{SUB};margin-top:2px">Sottotitolo / didascalia (Segoe UI, {SUB})</div>
<p style="font-size:13.5px;line-height:1.55;margin-top:14px;max-width:560px">
Testo corrente. Il sistema usa <b>Segoe UI</b> per l'interfaccia e la documentazione,
con un grigio tenue per le note secondarie.</p>
<div class="h" style="margin-top:24px">Monospace — pin e codice</div>
<div class="mono" style="font-size:15px">E1 5 / 22 / 15 &nbsp; E4 37 / 38 / 39 &nbsp; pulsanti 25 / 26 / 28</div>
<div class="mono" style="font-size:13px;color:{SUB};margin-top:6px">python teensy/build_toern.py → toern.hex</div>
"""
    write("foundations/typography.html",
          card("Foundations", body, "Tipografia", "Tipografia",
               "Segoe UI + JetBrains Mono"))


def build_logo():
    body = f"""
<div style="display:flex;align-items:center;justify-content:center;height:240px;
            background:{PANEL};border:1px solid {LINE};border-radius:14px;flex-direction:column;gap:10px">
  <div style="font-size:44px;font-weight:700">🎛️ ichosynth</div>
  <div style="font-size:16px;color:{SUB}">un TŒRN su hardware DIY · Teensy 4.1</div>
</div>"""
    write("brand/logo.html",
          card("Brand", body, "Logo / Lockup", "Logo / Lockup", "Titolo + tagline"))


def build_badges():
    defs = [
        ("License", "MIT", "#2ea44f"), ("Platform", "Teensy 4.1", "#ee6611"),
        ("Build", "4 enc + 3 btn + OLED", "#FF8A1A"),
        ("Runs", "TŒRN · SP_", "#8957e5"), ("ICHOS 2026", "Taranto", "#E83AA6"),
    ]
    pills = []
    for lab, val, col in defs:
        pills.append(
            f'<span style="display:inline-flex;font-family:{FONT};font-size:12px;'
            f'border-radius:5px;overflow:hidden;margin:0 8px 10px 0">'
            f'<span style="background:#3a3f44;color:#fff;padding:5px 9px">{lab}</span>'
            f'<span style="background:{col};color:#fff;padding:5px 9px">{val}</span></span>')
    body = '<div style="display:flex;flex-wrap:wrap">' + "".join(pills) + "</div>"
    write("brand/badges.html",
          card("Brand", body, "Badge", "Badge", "Stile shields.io"))


def inline_svg(name):
    with open(os.path.join(ASSETS, name + ".svg"), "r", encoding="utf-8") as f:
        s = f.read()
    # make it scale to the card width
    return s.replace("<svg ", '<svg style="max-width:100%;height:auto;display:block" ', 1)


def build_diagrams():
    for name, title, group in DIAGRAMS:
        body = (f'<div style="background:{BG};border:1px solid {LINE};border-radius:12px;'
                f'padding:10px">{inline_svg(name)}</div>')
        write(f"diagrams/{name}.html",
              card(group, body, title, title, "assets/" + name + ".svg"))


if __name__ == "__main__":
    build_colors()
    build_typography()
    build_logo()
    build_badges()
    build_diagrams()
    print("done.")
