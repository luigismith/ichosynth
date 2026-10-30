"""Guida di montaggio grafica del case ichosynth: render + frecce -> HTML -> PDF.

    python _CASE/render/make_guide.py     # -> _CASE/img/*.jpg, _CASE/MONTAGGIO.html, _CASE/MONTAGGIO.pdf

Usa i render di Blender in _CASE/render/out (vedi render.ps1) e i loro .json con le
coordinate in pixel di frecce/etichette. Il PDF lo stampa Chrome/Edge in headless.
"""
import html
import json
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
REPO = CASE.parent
OUT = HERE / "out"
IMG = CASE / "img"
sys.path.insert(0, str(CASE))
sys.path.insert(0, str(REPO / "_DOCS" / "cablaggio"))
import build_case as b                                   # noqa: E402
import make_cablaggio as cab                             # noqa: E402  tavole di cablaggio

ORANGE, INK, SUB, BG = "#FF8A1A", "#1f2328", "#57606a", "#0d1117"
VOICE = ["#E83A3A", "#3A6BE8", "#E8D23A", "#36C24A", "#E83AA6", "#A6E03A", "#FF7A1A", "#2AD4B8"]
CHROME = ["C:/Program Files/Google/Chrome/Application/chrome.exe",
          "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
          "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
          "C:/Program Files/Microsoft/Edge/Application/msedge.exe"]

# --- pittogrammi (SVG semplici, stile istruzioni di montaggio) ----------------------------
ICON = {
    "screwdriver": '<rect x="4" y="20" width="16" height="8" rx="3" fill="#333"/><rect x="20" y="22.5" width="20" height="3" fill="#999"/><path d="M40 22.5 l5 1.5 -5 1.5z" fill="#999"/>',
    "glue": '<rect x="6" y="14" width="22" height="12" rx="3" fill="#333"/><rect x="14" y="26" width="8" height="12" rx="2" fill="#333"/><rect x="28" y="18" width="12" height="4" fill="#bbb"/><path d="M40 18 l5 2 -5 2z" fill="#bbb"/><circle cx="45" cy="30" r="2.5" fill="#f2c94c"/>',
    "solder": '<rect x="4" y="21" width="18" height="6" rx="3" fill="#333"/><rect x="22" y="22.5" width="16" height="3" fill="#bbb"/><path d="M38 22.5 l8 1.5 -8 1.5z" fill="#c0392b"/>',
    "print": '<rect x="8" y="6" width="32" height="6" fill="#333"/><rect x="14" y="12" width="20" height="8" fill="#666"/><path d="M24 20 l-3 5 6 0z" fill="#333"/><rect x="6" y="36" width="36" height="4" fill="#333"/><rect x="16" y="28" width="16" height="8" fill="' + ORANGE + '"/>',
    "nosupport": '<rect x="8" y="30" width="32" height="6" fill="#333"/><rect x="14" y="14" width="20" height="16" fill="#888"/><circle cx="24" cy="24" r="16" fill="none" stroke="#c0392b" stroke-width="3"/><path d="M13 35 L35 13" stroke="#c0392b" stroke-width="3"/>',
    "colorchange": '<rect x="10" y="30" width="28" height="8" fill="#e9e6df" stroke="#999"/><rect x="10" y="14" width="28" height="16" fill="#222"/><path d="M4 30 h40" stroke="' + ORANGE + '" stroke-width="2" stroke-dasharray="3 2"/>',
}


def icon(name, size=46):
    return f'<svg class="ico" viewBox="0 0 48 48" width="{size}" height="{size}">{ICON[name]}</svg>'


def chip(text, ico=None, strong=False):
    i = icon(ico, 30) if ico else ""
    return f'<span class="chip{" strong" if strong else ""}">{i}<b>{html.escape(text)}</b></span>'


# --- immagini + annotazioni ------------------------------------------------------------
def jpg(name, quality=86):
    src, dst = OUT / f"{name}.png", IMG / f"{name}.jpg"
    if src.exists():                       # render nuovo -> JPG ottimizzato (quello che va nel repo)
        Image.open(src).convert("RGB").save(dst, "JPEG", quality=quality, optimize=True, progressive=True)
    elif not dst.exists():
        raise SystemExit(f"manca il render {src} — lancia prima _CASE/render/render.ps1")
    return f"img/{name}.jpg"


def figure(name, cls=""):
    """Immagine con le frecce/etichette sovrapposte in SVG (stesse coordinate in pixel)."""
    src = jpg(name)
    meta = json.loads((OUT / f"{name}.json").read_text(encoding="utf-8"))
    w, h = meta["res"]
    P = meta["points"]
    svg = [f'<svg class="ov" viewBox="0 0 {w} {h}" preserveAspectRatio="xMidYMid meet">',
           f'<defs><marker id="ah" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto">'
           f'<path d="M0 0 L10 5 L0 10z" fill="{ORANGE}"/></marker></defs>']
    sw = max(w, h) / 260
    for a, c in meta["arrows"]:
        (x0, y0), (x1, y1) = P[a], P[c]
        svg.append(f'<line x1="{x0}" y1="{y0}" x2="{x1}" y2="{y1}" stroke="{ORANGE}" stroke-width="{sw:.1f}" '
                   f'stroke-linecap="round" marker-end="url(#ah)"/>')
    fs = max(w, h) / 46
    for key, text, cls_ in meta["labels"]:
        x, y = P[key]
        if cls_.startswith("callout:"):
            ax, ay = P[cls_.split(":", 1)[1]]
            svg.append(f'<line x1="{ax}" y1="{ay}" x2="{x}" y2="{y}" stroke="{INK}" stroke-width="{sw * 0.6:.1f}"/>'
                       f'<circle cx="{ax}" cy="{ay}" r="{sw * 1.6:.1f}" fill="{ORANGE}"/>')
        tw = fs * 0.62 * len(text) + fs * 0.9
        svg.append(f'<rect x="{x - tw / 2:.0f}" y="{y - fs * 0.85:.0f}" width="{tw:.0f}" height="{fs * 1.5:.0f}" '
                   f'rx="{fs * 0.35:.0f}" fill="{INK}"/>'
                   f'<text x="{x:.0f}" y="{y + fs * 0.18:.0f}" font-size="{fs:.0f}" fill="#fff" '
                   f'text-anchor="middle" dominant-baseline="middle" font-weight="700">{html.escape(text)}</text>')
    svg.append("</svg>")
    return f'<div class="fig {cls}"><img src="{src}">{"".join(svg)}</div>'


# --- pagine ---------------------------------------------------------------------------
def page(title, body, n):
    stripe = "".join(f'<i style="background:{c}"></i>' for c in VOICE)
    return (f'<section class="page"><header><div class="brand">ichosynth</div><div class="ttl">{title}</div>'
            f'<div class="pn">{n}</div></header><div class="stripe">{stripe}</div><main>{body}</main></section>')


def step(num, scene_or_html, chips="", note=""):
    fig = scene_or_html if scene_or_html.startswith("<") else figure(scene_or_html)
    return (f'<div class="step"><div class="num">{num}</div>{fig}'
            f'<div class="cap">{chips}{f"<span class=note>{html.escape(note)}</span>" if note else ""}</div></div>')


def build_html():
    IMG.mkdir(exist_ok=True)
    pages = []
    n = 1
    dims = f"{b.W:.0f} × {b.D:.0f} mm · h {b.Z_TOP_M:.0f} / {b.Z_TOP_C:.0f} mm"
    pages.append(
        f'<section class="page cover"><div class="stripe big">{"".join(f"<i style=background:{c}></i>" for c in VOICE)}</div>'
        f'<div class="ctitle"><div class="brand big">ichosynth</div><div class="sub">case stampato in 3D · guida di montaggio</div></div>'
        f'{figure("hero", "hero")}'
        f'<div class="cfoot">{chip("3 pezzi", "print", True)}{chip("2 piatti · Kobra S1")}{chip("0 supporti", "nosupport")}{chip(dims)}</div></section>')
    n += 1

    pages.append(page("Stampa", (
        '<div class="two">'
        f'<div class="col">{figure("plate1")}<div class="cap">{chip("PIATTO 1", strong=True)}{chip("PLA/PETG nero")}{chip("vasca + pannello")}</div></div>'
        f'<div class="col">{figure("plate2")}<div class="cap">{chip("PIATTO 2", strong=True)}{chip("PLA/PETG traslucido")}'
        f'{chip(f"Z {b.DIFF_T:g} mm → nero", "colorchange")}</div></div></div>'
        f'<div class="cap center">{chip("0,2 mm")}{chip("3 perimetri")}{chip("15 %")}{chip("niente supporti", "nosupport")}'
        f'{chip("stl/plate1.stl · stl/window.stl")}</div>'), n))
    n += 1

    items = [("item_matrix", "×1", "matrice WS2812B 16×16"), ("item_teensy", "×1", "Teensy 4.1 + Audio Rev D"),
             ("item_encoder", "×4", "encoder KY-040"), ("item_oled", "×1", "OLED SSD1306 0,96\""),
             ("item_switch", "×3", "tact switch 6×6×4,3"), ("item_jack", "×1", "jack mono 6,35 (LINE IN)"),
             ("item_screw", "×8", "vite M3×8 svasata"), ("item_feet", "×4", "piedini Ø10")]
    grid = "".join(f'<div class="item">{figure(s)}<div class="q">{q}</div><div class="nm">{html.escape(t)}</div></div>'
                   for s, q, t in items)
    tools = f'<div class="tools">{icon("screwdriver", 110)}{icon("solder", 110)}{icon("glue", 110)}</div>'
    pages.append(page("Cosa serve", f'<div class="grid">{grid}</div>'
                      f'<div class="kit">{figure("item_prints")}{tools}</div>', n))
    n += 1

    steps = [
        ("1", "s01_feet", chip("×4") + chip("piedini adesivi")),
        ("2", "s02_jacks", chip("LINE IN") + chip("dado fuori") + chip("≤ 22 × 16 mm")),
        ("3", "s03_teensy", chip("USB + PHONES dal retro") + icon("glue", 40)),
        ("4", f'<div class="fig ovw">{cab.overview_svg()}</div>',
         icon("solder", 40) + chip("cablaggio: le 7 tavole seguenti", strong=True) + chip("anche in _DOCS/CABLAGGIO.pdf")),
        ("5", "s05_matrix", chip("LED in alto") + chip("fili nelle tacche")),
        ("6", "s06_window", chip("M3×8 ×4", "screwdriver")),
        ("7", "s07_switches", chip("2 gambe in diagonale") + chip("fili saldati prima") + icon("glue", 40)),
        ("8", "s08_encoders", chip("dado M7 sopra") + chip("pin verso il retro") + chip("fili giù subito")),
        ("9", "s09_oled", chip("vetro nella finestra") + icon("glue", 40)),
        ("10", "s10_close", chip("M3×8 ×4", "screwdriver")),
        ("11", "s11_knobs", chip("facoltative") + chip("stl/knob.stl")),
    ]
    # due passi per pagina; il cablaggio (schemi SVG) ha una pagina tutta per sé
    queue = []
    for s in steps + [None]:
        wide = s is not None and s[1].startswith("<")
        if queue and (s is None or wide or len(queue) == 2):
            pages.append(page("Montaggio", f'<div class="two steps">{"".join(step(*q) for q in queue)}</div>', n))
            n, queue = n + 1, []
        if wide:
            pages.append(page("Cablaggio", f'<div class="two steps">{step(*s)}</div>', n))
            wiring, n = cab.build_pages(n + 1)          # le tavole di _DOCS/CABLAGGIO.pdf
            pages.extend(wiring)
        elif s is not None:
            queue.append(s)

    pages.append(page("Pronto", '<div class="two">'
                      f'<div class="col">{figure("hero_io")}</div><div class="col">{figure("hero_top")}</div></div>'
                      f'<div class="cap center">{chip("PLAY · MENU · REC", strong=True)}{chip("E2 E3 / E1 E4")}'
                      f'{chip("micro-SD: togli il pannello")}</div>', n))

    css = f"""
    @page {{ size: A4 landscape; margin: 0; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; font-family: 'Segoe UI', Helvetica, Arial, sans-serif; color: {INK}; background: #fff; }}
    .page {{ width: 297mm; height: 210mm; page-break-after: always; position: relative; overflow: hidden;
             display: flex; flex-direction: column; }}
    header {{ background: {BG}; color: #e6edf3; display: flex; align-items: center; height: 15mm; padding: 0 9mm; }}
    .brand {{ font-weight: 800; font-size: 6.5mm; letter-spacing: .02em; }}
    .brand.big {{ font-size: 20mm; color: {BG}; }}
    .ttl {{ margin-left: 8mm; font-size: 5mm; color: #9aa4b2; text-transform: uppercase; letter-spacing: .12em; }}
    .pn {{ margin-left: auto; font-size: 5mm; font-weight: 700; }}
    .stripe {{ display: flex; height: 1.6mm; }} .stripe i {{ flex: 1; }} .stripe.big {{ height: 4mm; }}
    main {{ flex: 1; padding: 6mm 9mm 7mm; display: flex; flex-direction: column; gap: 4mm; min-height: 0; }}
    .fig {{ position: relative; flex: 1; min-height: 0; display: flex; }}
    .fig img {{ width: 100%; height: 100%; object-fit: contain; }}
    .fig .ov {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .two {{ display: flex; gap: 6mm; flex: 1; min-height: 0; }}
    .col {{ flex: 1; display: flex; flex-direction: column; gap: 3mm; min-height: 0; }}
    .step {{ flex: 1; position: relative; display: flex; flex-direction: column; border: .4mm solid #e3e6ea;
             border-radius: 4mm; padding: 4mm; min-height: 0; }}
    .num {{ position: absolute; top: 3mm; left: 3mm; width: 14mm; height: 14mm; border-radius: 50%; background: {ORANGE};
            color: #fff; font-weight: 800; font-size: 7.5mm; display: flex; align-items: center; justify-content: center; z-index: 2; }}
    .cap {{ display: flex; flex-wrap: wrap; gap: 2.5mm; align-items: center; }}
    .cap.center {{ justify-content: center; }}
    .chip {{ display: inline-flex; align-items: center; gap: 1.5mm; background: #f1f3f5; border-radius: 99px;
             padding: 1.2mm 3.5mm; font-size: 4mm; }}
    .chip.strong {{ background: {BG}; color: #fff; }}
    .chip .ico {{ width: 6mm; height: 6mm; }}
    .note {{ color: {SUB}; font-size: 3.6mm; }}
    .svg2 {{ gap: 4mm; }} .svg2 > div {{ flex: 1; display: flex; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, 1fr); grid-template-rows: repeat(2, 1fr); gap: 3mm;
             height: 96mm; flex: none; }}
    .item {{ position: relative; display: flex; flex-direction: column; border: .4mm solid #e3e6ea; border-radius: 3mm;
             padding: 2mm; min-height: 0; }}
    .item .q {{ position: absolute; top: 1.5mm; right: 3mm; font-size: 8mm; font-weight: 800; color: {ORANGE}; }}
    .item .nm {{ font-size: 3.5mm; text-align: center; color: {SUB}; }}
    .kit {{ display: flex; gap: 8mm; height: 62mm; flex: none; align-items: center; }}
    .kit .fig {{ height: 100%; }}
    .tools {{ display: flex; gap: 6mm; }}
    .cover {{ background: #fff; }}
    .ctitle {{ padding: 10mm 14mm 0; }} .sub {{ font-size: 7mm; color: {SUB}; margin-top: -2mm; }}
    .fig.hero {{ flex: 1; margin: 0 10mm; }}
    .cfoot {{ display: flex; gap: 4mm; justify-content: center; padding: 0 0 10mm; }}
    """
    doc = (f'<!doctype html><html lang="it"><head><meta charset="utf-8"><title>ichosynth · case · montaggio</title>'
           f'<style>{css}{cab.CSS}.fig.ovw .ill {{ max-height: 150mm; }}</style></head><body>{"".join(pages)}</body></html>')
    out = CASE / "MONTAGGIO.html"
    out.write_text(doc, encoding="utf-8")
    return out


def build_pdf(html_path):
    chrome = next((p for p in CHROME if Path(p).exists()), None)
    if not chrome:
        print("Chrome/Edge non trovato: PDF non generato (l'HTML è pronto)")
        return None
    pdf = html_path.with_suffix(".pdf")
    subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                    "--allow-file-access-from-files", f"--print-to-pdf={pdf}", html_path.as_uri()],
                   check=True, capture_output=True, timeout=180)
    return pdf


def main():
    h = build_html()
    p = build_pdf(h)
    print("scritto", h.relative_to(REPO), "e", p.relative_to(REPO) if p else "(niente PDF)")


if __name__ == "__main__":
    main()
