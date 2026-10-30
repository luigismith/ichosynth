"""Verifiche del case ichosynth: esce con codice 1 se qualcosa non va.

    python _CASE/check_fit.py

I componenti (parts.py, gli stessi dei render) sono solidi semplici alle quote reali.
Controlla: pezzi stampati fra loro, componenti contro pezzi, componenti fra loro, spine
inserite, micro-SD estraibile, matrice spostata del gioco massimo sotto la griglia, corsa
dei tasti flessibili, pezzi in un corpo unico, griglia attaccata al diffusore.
"""
import sys

import build_case as b
import parts
from build_case import box, union

TOL = 0.1                    # mm3: sotto questa soglia è contatto fra facce, non interferenza
failures = []


def check(ok, msg):
    if not ok:
        failures.append(msg)
        print("  FAIL", msg)


if hasattr(sys.stdout, "reconfigure"):           # console Windows cp1252: niente crash sui caratteri
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def vol(a, c):
    return (a ^ c).volume()


def main():
    printed = {"vasca": b.build_tray(), "pannello": b.build_panel(), "diffusore": b.build_window()}
    for n in b.ENCODERS:
        printed[f"manopola {n}"] = parts.knob(n)[0][1]
    comps = {k: union(m for _, m, _ in v) for k, v in parts.all_components().items()}

    names = list(printed)
    for i, p in enumerate(names):
        for q in names[i + 1:]:
            v = vol(printed[p], printed[q])
            check(v < TOL, f"{p} / {q}: {v:.2f} mm3")
    for c, cm in comps.items():
        for p, pm in printed.items():
            v = vol(cm, pm)
            check(v < TOL, f"{c} / {p}: {v:.2f} mm3")
    cn = list(comps)
    for i, c in enumerate(cn):
        for d in cn[i + 1:]:
            v = vol(comps[c], comps[d])
            check(v < TOL, f"{c} / {d}: {v:.2f} mm3")

    # micro-SD: la scheda entra ed esce dal lato anteriore del Teensy
    tx, _, y0, zp = parts.teensy_geom()
    card = box(tx - 5.5, y0 - 16, zp + 1.6 + 0.4, tx + 5.5, y0 + 0.5, zp + 1.6 + 1.3)
    check(vol(card, printed["vasca"]) < TOL, "la micro-SD non passa davanti alla culla del Teensy")

    # matrice spostata del gioco massimo: i LED restano fra le pareti della griglia
    mat = comps["matrice"]
    for dx, dy in ((b.MAT_CLR, 0), (-b.MAT_CLR, 0), (0, b.MAT_CLR), (0, -b.MAT_CLR)):
        v = vol(mat.translate([dx, dy, 0]), printed["diffusore"])
        check(v < TOL, f"matrice spostata di ({dx}, {dy}) tocca la griglia: {v:.2f} mm3")

    # tasti: gioco reale perno-pulsantino fra 0,25 e 0,6 mm (switch 4,3 +-0,2 mm, corsa 0,25 mm),
    # e lo switch appoggia davvero sul piedistallo della vasca
    zf = b.Z_WALL_C - (b.SW_BODY[2] + 0.1)
    for n in b.BUTTONS:
        sw = union(m for _, m, _ in parts.switch(n))
        gap = sw.min_gap(printed["pannello"], 3.0)
        check(0.25 <= gap <= 0.6, f"tasto {n}: gioco perno-pulsantino {gap:.2f} mm (atteso 0,25-0,6)")
        x, y = b.ctrl(*b.BUTTONS[n])
        seat = printed["vasca"] ^ box(x - 3, y - 3, zf - 0.3, x + 3, y + 3, zf)
        check(seat.volume() > 0.3 * 36 * 0.3, f"tasto {n}: lo switch non appoggia sul piedistallo")

    # viti svasate: almeno 0,8 mm di materiale fra la svasatura e il bordo del pezzo
    for pname, pts, x0, x1 in (("diffusore", b.SCREWS_M, 0, b.X_STEP - 0.2), ("pannello", b.SCREWS_C, b.X_STEP, b.W)):
        inset = (b.rrect(b.W, b.D, b.R_CORNER) ^ b.CS.square([x1 - x0, b.D]).translate([x0, 0])).offset(-0.8)
        for x, y in pts:
            out = (b.CS.circle(b.SCREW_CSK / 2, 48).translate([x, y]) - inset).area()
            check(out < 0.01, f"{pname}: svasatura in ({x:.1f}, {y:.1f}) a meno di 0,8 mm dal bordo")

    # pezzi stampati in un corpo unico
    for p in ("vasca", "pannello", "diffusore"):
        n = len(printed[p].decompose())
        check(n == 1, f"{p}: {n} corpi separati (atteso 1)")

    # griglia attaccata al diffusore: stessa sezione appena sotto il diffusore e a metà altezza
    zd, hw = b.Z_TOP_M - b.DIFF_T, b.MAT / 2 + 0.4
    core = printed["diffusore"] ^ box(b.MX - hw, b.MY - hw, 0, b.MX + hw, b.MY + hw, 100)
    a_top, a_mid = core.slice(zd - 0.05).area(), core.slice(zd - 3.0).area()
    check(a_mid > 3000, f"griglia mancante: sezione {a_mid:.0f} mm2")
    check(abs(a_top - a_mid) < 0.02 * max(a_mid, 1), f"griglia staccata: {a_top:.0f} vs {a_mid:.0f} mm2")
    # luce fra le celle: la griglia deve scendere fra i LED fin quasi al PCB flessibile
    a_low = core.slice(b.Z_MAT + 0.3 + 1.2).area()
    check(abs(a_low - a_mid) < 0.02 * max(a_mid, 1), "la griglia non scende fra i LED (luce che filtra fra le celle)")

    print(f"{len(printed)} pezzi, {len(comps)} componenti — controlli falliti: {len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
