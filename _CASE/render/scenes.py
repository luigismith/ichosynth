"""Prepara le scene dei render del case ichosynth per Blender.

    python _CASE/render/scenes.py        # -> _CASE/render/build/*.stl + scenes.json + oled.png

Ogni scena elenca oggetti (mesh STL in coordinate di montaggio + materiale + rotazione/
posizione), la camera e i punti 3D da proiettare per frecce ed etichette della guida.
La geometria dei componenti viene da parts.py (la stessa delle verifiche di check_fit.py).
Il render lo fa blender_render.py (lanciato da render.ps1).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_case as b                                   # noqa: E402
import parts                                             # noqa: E402
from build_case import box, cyl, to_trimesh              # noqa: E402

BUILD = HERE / "build"
VOICE = ["#E83A3A", "#3A6BE8", "#E8D23A", "#36C24A", "#E83AA6", "#A6E03A", "#FF7A1A", "#2AD4B8"]
ENC_COL = {"E1": "#3A6BE8", "E2": "#36C24A", "E3": "#E8D23A", "E4": "#E83AA6"}   # design system

_meshes = {}


def reg(items):
    """Esporta (una volta) le mesh di una lista (nome, Manifold, materiale) -> [(nome, materiale)]."""
    out = []
    for name, man, mat in items:
        if name not in _meshes:
            to_trimesh(man).export(BUILD / f"{name}.stl")
            _meshes[name] = man
        out.append((name, mat))
    return out


def split_window(win, z, tag):
    """Diffusore diviso alla quota del cambio colore: sopra traslucido, sotto nero (o al
    contrario per il pezzo capovolto sul piatto). `z` va spostata di 0,01 mm rispetto al
    piano delle celle: tagliando ESATTAMENTE su quel piano il booleano lascia le facce del
    soffitto delle celle (spessore zero) nella parte nera e la luce dei LED non passa."""
    x0, y0, z0, x1, y1, z1 = win.bounding_box()
    hi = win ^ box(x0 - 1, y0 - 1, z, x1 + 1, y1 + 1, z1 + 1)
    lo = win ^ box(x0 - 1, y0 - 1, z0 - 1, x1 + 1, y1 + 1, z)
    return hi, lo


def oled_texture(path):
    """Schermata HUD 128x64 in stile OLED, ingrandita a pixel."""
    img = Image.new("L", (128, 64), 0)
    d = ImageDraw.Draw(img)
    f = ImageFont.load_default()
    d.text((2, 0), "CH1  DRAW", fill=255, font=f)
    d.text((2, 14), "> PLAY  120 BPM", fill=255, font=f)
    d.text((2, 28), "VOL", fill=255, font=f)
    d.rectangle([26, 31, 86, 37], outline=255)
    d.rectangle([28, 33, 68, 35], fill=255)
    d.text((2, 44), "PAGE 1/4", fill=255, font=f)
    img = img.resize((128 * 6, 64 * 6), Image.NEAREST).convert("RGB")
    arr = np.asarray(img).astype(float) / 255 * np.array([0.80, 0.93, 1.0])
    Image.fromarray((arr * 255).astype(np.uint8)).save(path)


def led_pattern():
    """Una sequenza stile TŒRN: cassa, rullante, hat, voci e melodia, playhead."""
    lit = {}
    for s in range(0, 16, 4):
        lit[(s, 15)] = VOICE[0]
    for s in (4, 12):
        lit[(s, 13)] = VOICE[1]
    for s in range(0, 16, 2):
        lit[(s, 11)] = VOICE[2]
    for s in (2, 7, 10, 15):
        lit[(s, 9)] = VOICE[3]
    for s in (3, 11):
        lit[(s, 7)] = VOICE[4]
    for s, r in ((0, 4), (3, 3), (6, 5), (8, 2), (11, 4), (14, 6)):
        lit[(s, r)] = VOICE[7]
    for r in range(16):
        lit.setdefault((6, r), "#9aa4b2")
    lit[(6, 0)] = "#e6edf3"
    return lit


# --- trasformazioni / scene -------------------------------------------------------------------
def rmat(rot):
    a, bb, c = np.radians(rot)
    rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    ry = np.array([[np.cos(bb), 0, np.sin(bb)], [0, 1, 0], [-np.sin(bb), 0, np.cos(bb)]])
    rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return rz @ ry @ rx           # = Euler XYZ di Blender


class Scene:
    def __init__(self, name, elev, azim, res=(1240, 1300), samples=64, focal=70, floor=True, led=9000.0):
        # formato quasi quadrato di default: è quello delle schede dei passi nella guida
        self.d = dict(name=name, elev=elev, azim=azim, res=list(res), samples=samples, focal=focal,
                      floor=floor, led=led, objects=[], planes=[], points={}, arrows=[], labels=[], fit=None)

    def add(self, items, pre=(0, 0, 0), rot=(0, 0, 0), loc=(0, 0, 0)):
        """world = R(rot) @ (p + pre) + loc  (stessa formula di point())."""
        R = rmat(rot)
        L = (R @ np.asarray(pre, float) + np.asarray(loc, float)).tolist()
        for name, mat in items:
            self.d["objects"].append(dict(mesh=f"{name}.stl", mat=mat, rot=list(rot), loc=L))
        return self

    def point(self, key, p, pre=(0, 0, 0), rot=(0, 0, 0), loc=(0, 0, 0)):
        R = rmat(rot)
        self.d["points"][key] = (R @ (np.asarray(p, float) + np.asarray(pre, float)) + np.asarray(loc, float)).tolist()
        return key

    def arrow(self, a, c):
        self.d["arrows"].append([a, c])

    def label(self, key, text):
        self.d["labels"].append([key, text, ""])

    def callout(self, at, text, offset, **tf):
        n = len(self.d["labels"])
        a = self.point(f"co{n}a", at, **tf)
        lab = self.point(f"co{n}b", np.asarray(at, float) + np.asarray(offset, float), **tf)
        self.d["labels"].append([lab, text, "callout:" + a])

    def oled_screen(self, lift=0.0):
        ox, oy = b.ctrl(*b.OLED_C)
        self.d["planes"].append(dict(image="oled.png", center=[ox, oy, b.Z_WALL_C + 0.02 + lift],
                                     size=list(parts.OLED_ACTIVE)))
        return self

    def fit(self, x0, y0, z0, x1, y1, z1):
        self.d["fit"] = [x0, y0, z0, x1, y1, z1]


def build_scenes():
    tray = reg([("tray", b.build_tray(), "pla_black")])
    panel = reg([("panel", b.build_panel(), "pla_black")])
    hi, lo = split_window(b.build_window(), b.Z_TOP_M - b.DIFF_T - 0.01, "a")
    window = reg([("window_top", hi, "pla_diffuser"), ("window_low", lo, "pla_black")])
    mat_lit, mat_off = reg(parts.matrix(led_pattern())), reg(parts.matrix())
    tee = reg(parts.teensy())
    jacks = reg(sum((parts.jack(n) for n in b.JACKS), []))
    encs = reg(sum((parts.encoder(n) for n in b.ENCODERS), []))
    encs_nonut = reg(sum((parts.encoder(n, nut=False) for n in b.ENCODERS), []))
    oled = reg(parts.oled())
    sws = reg(sum((parts.switch(n) for n in b.BUTTONS), []))
    knobs = reg(sum((parts.knob(n, "pla_" + ENC_COL[n]) for n in b.ENCODERS), []))
    sm, sc = reg(parts.screws("m")), reg(parts.screws("c"))
    feet = reg(parts.feet())
    plugs = reg(parts.plugs())
    zc = b.Z_TOP_C
    tx, y1, _, zp = parts.teensy_geom()
    zu = zp + 1.6 + b.USB_Z_ABOVE_PCB

    def base(s, leds=True, window_on=True):
        s.add(tray + tee + jacks + feet).add(mat_lit if leds else mat_off).add(sws)
        if window_on:
            s.add(window).add(sm)
        return s

    def full(s, knobs_on=True):
        base(s).add(panel + encs + oled + sc).oled_screen()
        if knobs_on:
            s.add(knobs)
        return s

    S = []
    S.append(full(Scene("hero", 30, -118, res=(2200, 1400), samples=96)))
    s = full(Scene("hero_io", 22, 38, res=(2000, 1300), samples=96))
    s.add(plugs)
    s.callout((tx, b.D + 26, zu), "USB", (-22, 0, -14))
    s.callout((tx, b.D + 26, b.HP_Z), "PHONES", (-22, 0, 18))
    for i, (n, (v, _)) in enumerate(b.JACKS.items()):       # fili paralleli, non si incrociano
        s.callout((b.W + 3, b.CY0 + v, b.JACK_Z), n, (40, 0, -10 - 9 * i))
    S.append(s)
    S.append(full(Scene("hero_top", 89.0, -90, res=(2000, 1500), samples=96)))

    s = Scene("exploded", 28, -120, res=(2000, 1500), samples=80, led=60.0)
    base(s, window_on=False)
    s.add(window, loc=(0, 0, 45)).add(sm, loc=(0, 0, 75))
    s.add(panel, loc=(0, 0, 70)).add(encs + oled, loc=(0, 0, 50)).add(sc, loc=(0, 0, 95))
    s.add(knobs, loc=(0, 0, 115))
    S.append(s)

    # 1 · piedini (vasca capovolta)
    flip, lift = (180, 0, 0), (0, b.D, b.Z_WALL_C)
    s = Scene("s01_feet", 34, -120)
    s.add(tray, rot=flip, loc=lift).add(feet, pre=(0, 0, -18), rot=flip, loc=lift)
    for i, (x, y) in enumerate(parts.FEET):
        s.arrow(s.point(f"f{i}a", (x, y, -15), rot=flip, loc=lift), s.point(f"f{i}b", (x, y, -4), rot=flip, loc=lift))
    S.append(s)

    # 2 · jack LINE IN 6,35 sul fianco: corpo da dentro, dado da fuori
    s = Scene("s02_jacks", 30, -32)
    s.add(tray)
    for n, (v, _) in b.JACKS.items():
        s.add(reg(parts.jack(n, "body")), pre=(-28, 0, 0)).add(reg(parts.jack(n, "nut")), pre=(16, 0, 0))
        y = b.CY0 + v
        s.arrow(s.point(f"{n}a", (b.W - 30, y, b.JACK_Z + 10)), s.point(f"{n}b", (b.W - 8, y, b.JACK_Z + 10)))
        s.callout((b.W + 17, y, b.JACK_Z), n, (24, 0, 14))
    s.fit(b.X_STEP - 20, 40, 0, b.W + 40, b.D, 40)
    S.append(s)

    # 3 · Teensy + scheda audio nella culla: USB e cuffie dal retro
    s = Scene("s03_teensy", 38, -128)
    s.add(tray + jacks).add(tee, pre=(0, 0, 32))
    s.arrow(s.point("t0", (tx, b.D - 40, 44)), s.point("t1", (tx, b.D - 40, 14)))
    s.callout((tx, b.D, zu), "USB", (-16, 18, -8))
    s.callout((tx, b.D, b.HP_Z), "PHONES", (-16, 18, 12))
    s.fit(b.X_STEP - 10, 60, 0, b.W, b.D + 20, 50)
    S.append(s)

    # 5 · matrice
    s = Scene("s05_matrix", 32, -120)
    s.add(tray + tee + jacks).add(mat_off, pre=(0, 0, 30))
    for i, (px, py) in enumerate(((b.MX - 60, b.MY - 60), (b.MX + 60, b.MY + 60))):
        s.arrow(s.point(f"m{i}a", (px, py, 42)), s.point(f"m{i}b", (px, py, 12)))
    S.append(s)

    # 6 · diffusore + 4 viti
    s = Scene("s06_window", 32, -120, led=60.0)
    s.add(tray + tee + jacks).add(mat_lit)
    s.add(window, loc=(0, 0, 35)).add(sm, loc=(0, 0, 65))
    s.arrow(s.point("w0", (b.MX, b.MY - 70, 58)), s.point("w1", (b.MX, b.MY - 70, 22)))
    s.label(s.point("wl", (b.SCREWS_M[2][0], b.SCREWS_M[2][1], b.Z_TOP_M + 76)), "×4  M3×8")
    S.append(s)

    # 7 · tact switch sui piedistalli (fili già saldati)
    s = Scene("s07_switches", 42, -128)
    s.add(tray + tee + jacks).add(mat_lit).add(window).add(sm).add(sws, pre=(0, 0, 16))
    for n in b.BUTTONS:
        x, y = b.ctrl(*b.BUTTONS[n])
        s.arrow(s.point(f"{n}a", (x, y, b.Z_WALL_C + 20)), s.point(f"{n}b", (x, y, b.Z_WALL_C + 4)))
    s.callout(b.ctrl(46, 20) + (b.Z_WALL_C + 16,), "6×6×4,3", (26, -10, 10))
    s.fit(b.X_STEP - 10, 0, 0, b.W + 20, 80, 50)
    S.append(s)

    # 8 · encoder nel pannello (pannello capovolto)
    pflip, up = (180, 0, 0), (0, b.D, zc + 2)
    s = Scene("s08_encoders", 48, -122)
    s.add(panel, rot=pflip, loc=up).add(encs_nonut, pre=(0, 0, -26), rot=pflip, loc=up)
    for n in b.ENCODERS:
        x, y = b.ctrl(*b.ENCODERS[n])
        s.arrow(s.point(f"{n}a", (x, y, b.Z_WALL_C - 18), rot=pflip, loc=up),
                s.point(f"{n}b", (x, y, b.Z_WALL_C - 3), rot=pflip, loc=up))
        s.callout((x, y, b.Z_WALL_C - 26), n, (0, 0, -10), rot=pflip, loc=up)
    S.append(s)

    # 9 · OLED (pannello capovolto, encoder montati)
    s = Scene("s09_oled", 48, -122)
    s.add(panel + encs_nonut, rot=pflip, loc=up).add(oled, pre=(0, 0, -22), rot=pflip, loc=up)
    ox, oy = b.ctrl(*b.OLED_C)
    s.arrow(s.point("o0", (ox, oy, b.Z_WALL_C - 20), rot=pflip, loc=up), s.point("o1", (ox, oy, b.Z_WALL_C - 6), rot=pflip, loc=up))
    S.append(s)

    # 10 · chiusura pannello + 4 viti
    s = Scene("s10_close", 32, -120)
    base(s).add(panel + encs + oled, loc=(0, 0, 40)).add(sc, loc=(0, 0, 70)).oled_screen(lift=40)
    s.arrow(s.point("c0", (b.CX0 + 29, 100, 66)), s.point("c1", (b.CX0 + 29, 100, 36)))
    s.label(s.point("cl", (b.SCREWS_C[2][0], b.SCREWS_C[2][1], zc + 82)), "×4  M3×8")
    S.append(s)

    # 11 · manopole (facoltative)
    s = Scene("s11_knobs", 40, -125)
    full(s, knobs_on=False).add(knobs, loc=(0, 0, 22))
    for n in b.ENCODERS:
        x, y = b.ctrl(*b.ENCODERS[n])
        s.arrow(s.point(f"k{n}a", (x, y, zc + 40)), s.point(f"k{n}b", (x, y, zc + 26)))
    s.fit(b.X_STEP - 10, 0, 0, b.W + 2, b.D, 60)
    S.append(s)

    # miniature "cosa serve"
    items = {"item_matrix": mat_off, "item_teensy": tee, "item_encoder": reg(parts.encoder("E1")),
             "item_oled": oled, "item_switch": reg(parts.switch("PLAY")), "item_jack": reg(parts.jack("LINE IN")),
             "item_screw": reg([parts.screw(0, 0, 0, "item")]),
             "item_feet": reg([("foot_item", cyl(0, 0, 0, 2.2, 5.0), "rubber")])}
    for name, it in items.items():
        S.append(Scene(name, 34, -120, res=(560, 420), samples=32, led=60.0).add(it))
    s = Scene("item_prints", 40, -120, res=(1200, 700), samples=32)
    zmin = lambda name: _meshes[name].bounding_box()[2]       # noqa: E731  appoggiati a terra
    s.add(tray).add(window, loc=(0, b.D + 30, -zmin("window_low"))).add(panel, loc=(15, b.D + 30, -zmin("panel")))
    S.append(s)

    # piatti di stampa (pezzi già orientati come in stl/)
    tray_p, panel_p = b.layout([b.print_pose(b.build_tray()), b.print_pose(b.build_panel(), flip=True, turn=True)])
    (win_p,) = b.layout([b.print_pose(b.build_window(), flip=True)])
    w_hi, w_lo = split_window(win_p, b.DIFF_T + 0.01, "p")   # capovolto: i primi 1,4 mm sono traslucidi
    bed = reg([("bed", box(0, 0, -1.2, b.PLATE, b.PLATE, 0), "bed")])
    s = Scene("plate1", 52, -105, res=(1500, 1200), samples=48)
    S.append(s.add(bed + reg([("p1_tray", tray_p, "pla_black"), ("p1_panel", panel_p, "pla_black")])))
    s = Scene("plate2", 52, -105, res=(1500, 1200), samples=48)
    S.append(s.add(bed + reg([("p2_win_hi", w_hi, "pla_black"), ("p2_win_lo", w_lo, "pla_diffuser")])))
    return S


def main():
    BUILD.mkdir(exist_ok=True)
    oled_texture(BUILD / "oled.png")
    scenes = [s.d for s in build_scenes()]
    (BUILD / "scenes.json").write_text(json.dumps(scenes, indent=1), encoding="utf-8")
    print(f"{len(scenes)} scene, {len(_meshes)} mesh -> {BUILD}")


if __name__ == "__main__":
    main()
