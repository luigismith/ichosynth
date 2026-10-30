"""ichosynth — case stampabile in 3D (3 pezzi, 2 piatti) per Anycubic Kobra S1 (250x250).

    python _CASE/build_case.py          # genera _CASE/stl/*.stl

Il case è a gradino: la zona matrice è bassa (~16 mm), la zona comandi alta (~29 mm)
perché sotto c'è lo stack Teensy 4.1 + scheda audio.

Pezzi:
  piatto 1, opaco:
    tray.stl   — VASCA a gradino: fondo, pareti, nervature sotto la matrice, culla del
                 Teensy, colonne viti, piedistalli dei 3 tact switch, fori USB / PHONES
                 (retro) e LINE IN (fianco destro).
    panel.stl  — PANNELLO COMANDI: fori encoder, finestra OLED, 3 tasti flessibili
                 ricavati nel pannello, scritte incise.
  piatto 2, traslucido:
    window.stl — DIFFUSORE sopra la matrice con la griglia anti-alone incorporata.
  knob.stl     — facoltativo (manopola per KY-040).
  plate1.stl   — vasca + pannello già disposti sul piatto 1 (comodo da importare).

Misure in mm. Origine: angolo esterno anteriore-sinistro del fondo della vasca, X verso
destra, Y verso il retro, Z verso l'alto. Le quote dei componenti acquistati (matrice,
KY-040, OLED, tact switch, stack Teensy) sono parametri qui sotto: misura i tuoi e correggi.
"""
from pathlib import Path

import numpy as np
import manifold3d as m3
import trimesh
from matplotlib.font_manager import FontProperties
from matplotlib.textpath import TextPath

M, CS = m3.Manifold, m3.CrossSection
SEG = 48                      # segmenti per i cerchi

# --- parametri ------------------------------------------------------------------
PLATE = 250.0                 # piatto Kobra S1
PLATE_GAP = 3.0               # distanza fra i pezzi sullo stesso piatto
T = 2.4                       # spessore pareti
FLOOR = 2.0                   # spessore fondo
R_CORNER = 5.0                # raggio spigoli verticali esterni

MAT = 160.0                   # matrice WS2812B 16x16 flessibile
MAT_PITCH = 10.0              # passo LED
MAT_T = 2.2                   # spessore matrice (PCB flex + LED)
MAT_CLR = 0.6                 # gioco laterale matrice
MARGIN = 7.0                  # spazio fra matrice e pareti (colonne viti)
UNDER_H = 4.0                 # spazio sotto la matrice (nervature, fili)
CTRL = 58.0                   # larghezza interna zona comandi

LID_T = 2.5                   # spessore pannello/diffusore (KY-040: filetto M7, ok fino a ~4)
DIFF_T = 1.4                  # spessore del diffusore sopra i LED
BAFFLE_H = 6.0                # griglia anti-alone: distanza LED -> diffusore
BAFFLE_T = 0.8                # spessore pareti griglia
BAFFLE_GAP = 0.3              # gioco fra griglia e LED
BAFFLE_FOOT = 1.0             # la griglia scende fra i LED fino a 1 mm dal PCB flessibile
                              # (spazio per eventuali condensatori SMD): meno luce che filtra

ENC_HOLE = 7.4                # foro boccola M7 del KY-040
ENC_RING = (5.5, 9.0, 1.0)    # sede anulare per la linguetta EC11 (r_in, r_out, prof.)
SW_BODY = (6.0, 6.0, 3.5)     # tact switch 6x6, altezza corpo
SW_H = 4.3                    # altezza totale switch (6x6x4.3, il più comune del kit)
SW_PIN_X = 3.25               # gambe a +-3.25 (passo 6.5)
# tasti flessibili ricavati nel pannello: linguetta a sbalzo, cerniera verso il retro.
# Lo switch NON è appeso al pannello: sta su un piedistallo che sale dal fondo della vasca.
TAB_W, TAB_FRONT, TAB_BACK = 13.0, 6.0, 13.0   # larghezza; dallo switch al bordo libero / alla cerniera
TAB_T = 0.8                   # spessore linguetta: k ~2,7 N/mm (PLA) -> ~3 N per premere
TAB_SLOT = 0.8                # fessura attorno alla linguetta
NUB_D, NUB_GAP = 4.0, 0.4     # perno sotto la linguetta e gioco sul pulsantino (switch 4,3 +-0,2 mm)
OLED_PCB = (27.8, 28.3)       # modulo SSD1306 0.96" (PCB 27.3x27.8 + gioco)
OLED_WIN = (25.0, 14.5)       # finestra (area attiva 21.7x10.9)
OLED_GLASS = 1.6              # spessore vetro sopra il PCB
TEENSY = (18.4, 61.2)         # Teensy 4.1 (17.8x61 + gioco)
TEENSY_STANDOFF = 3.0         # PCB sollevato (spazio per i pin sotto)
STACK_GAP = 11.0              # Teensy -> scheda audio impilata (header femmina)
AUDIO = (35.0, 37.0)          # scheda audio Rev D (x, y), impilata sul lato USB del Teensy
AUDIO_JACK_H = 5.2            # jack cuffie sopra la scheda audio: il punto più alto dello stack
                              # (il jack è sullo stesso lato della USB -> esce dal retro)
STACK_CLR = 2.0               # aria fra lo stack e il pannello
USB_Z_ABOVE_PCB = 1.4         # centro connettore micro-USB sopra il PCB
SCREW_PILOT = 2.5             # foro pilota per vite autofilettante M3
SCREW_HOLE = 3.4
SCREW_CSK = 6.4               # svasatura testa piana M3
JACK_Z = 12.0                 # centro dei jack 6,35: corpo alto fino a 16 mm, fra il fondo e l'OLED
TXT_DEPTH = 0.6

# --- quote derivate -----------------------------------------------------------------
BAY = MAT + 2 * MARGIN                  # zona matrice, interno
X_STEP = T + BAY                        # faccia del gradino lato matrice
CX0, CY0 = X_STEP + T, T                # origine interna zona comandi
W = CX0 + CTRL + T
D = T + BAY + T
MX = MY = T + MARGIN + MAT / 2          # centro matrice

Z_MAT = FLOOR + UNDER_H                 # appoggio matrice (cima nervature)
Z_TOP_M = Z_MAT + MAT_T + BAFFLE_GAP + BAFFLE_H + DIFF_T    # piano zona matrice
Z_WALL_M = Z_TOP_M - LID_T
Z_WALL_C = FLOOR + TEENSY_STANDOFF + 1.6 + STACK_GAP + 1.6 + AUDIO_JACK_H + STACK_CLR
Z_TOP_C = Z_WALL_C + LID_T              # piano zona comandi
Z_AUDIO = FLOOR + TEENSY_STANDOFF + 1.6 + STACK_GAP                  # fondo della scheda audio
HP_Z = Z_AUDIO + 1.6 + AUDIO_JACK_H / 2                             # asse del jack cuffie
HP_R = 6.5                              # apertura cuffie: dall'asse in giù (spine fino a Ø12)
HP_RELIEF = 1.5                         # scasso sotto il bordo posteriore del pannello sopra l'apertura

# zona comandi, coordinate (u, v) dall'angolo interno anteriore-sinistro della zona.
# v 0-136: comandi (sotto c'è solo la parte "nuda" del Teensy); oltre: sopra lo stack, libero.
# In DRAW di TŒRN E1 = cursore Y ed E4 = cursore X (i più usati) -> fila in basso, vicino
# alla mano; E2 = pagina, E3 = filtro rapido -> fila in alto.
ENCODERS = {"E2": (13.5, 82), "E3": (44.5, 82), "E1": (13.5, 44), "E4": (44.5, 44)}
ENC_HEADER = +1                         # i 5 pin dei KY-040 puntano verso il retro (+Y)
BUTTONS = {"PLAY": (12, 20), "MENU": (29, 20), "REC": (46, 20)}
OLED_C = (29, 122)
LOGO_V = 155
TEENSY_X = CX0 + 18                     # Teensy lungo Y, a sinistra, USB contro la parete posteriore
# fianco destro: nome -> (v, diametro foro). Jack mono TS 6,35 mm (filetto 3/8").
JACKS = {"LINE IN": (122, 9.8)}       # l'uscita è solo quella cuffie della scheda audio (retro)
JACK_DEPTH = 22.0                       # ingombro massimo del jack dietro la parete (corpo + linguette)

R_COL_M = 3.5                           # colonne zona matrice (strette: c'è poco margine)
COL_M_IN = 4.5                          # colonne lato gradino più all'interno: svasatura lontana dal bordo
SCREWS_M = [(T + R_COL_M, T + R_COL_M), (T + R_COL_M, D - T - R_COL_M),
            (X_STEP - COL_M_IN, T + R_COL_M), (X_STEP - COL_M_IN, D - T - R_COL_M)]
# la colonna posteriore-sinistra è avanzata (v=128): dietro c'è la scheda audio
SCREWS_C = [(CX0 + 4, T + 4), (CX0 + 4, CY0 + 128), (W - T - 4, T + 4), (W - T - 4, D - T - 4)]


def ctrl(u, v):
    return CX0 + u, CY0 + v


# --- primitive ----------------------------------------------------------------------
def box(x0, y0, z0, x1, y1, z1):
    return M.cube([x1 - x0, y1 - y0, z1 - z0]).translate([x0, y0, z0])


def cyl(x, y, z0, z1, r, r_top=None):
    rt = r if r_top is None else r_top
    return M.cylinder(z1 - z0, r, rt, SEG).translate([x, y, z0])


def rrect(w, h, r):
    return CS.square([w - 2 * r, h - 2 * r]).translate([r, r]).offset(r, m3.JoinType.Round, 2.0, SEG)


def outline(x0, x1, z0, z1):
    """Sagoma esterna del case (spigoli arrotondati) ritagliata fra x0 e x1."""
    return rrect(W, D, R_CORNER).extrude(z1 - z0).translate([0, 0, z0]) ^ box(x0, -1, z0 - 1, x1, D + 1, z1 + 1)


def union(parts):
    return M.batch_boolean(list(parts), m3.OpType.Add)


_FONT = FontProperties(family="DejaVu Sans", weight="bold")


def text_cs(s, size):
    """Testo centrato in (0,0) come CrossSection."""
    tp = TextPath((0, 0), s, size=size, prop=_FONT)
    polys = [p for p in tp.to_polygons(closed_only=True) if len(p) >= 3]
    cs = CS(polys, m3.FillRule.EvenOdd)
    x0, y0, x1, y1 = cs.bounds()
    return cs.translate([-(x0 + x1) / 2, -(y0 + y1) / 2])


def text_cut(s, size, origin, ex, ey):
    """Solido per incidere `s` su una faccia: ex/ey assi del testo, la normale ex x ey
    punta fuori dalla faccia; il solido va da -TXT_DEPTH a +0.05 lungo la normale."""
    ez = np.cross(ex, ey)
    solid = text_cs(s, size).extrude(TXT_DEPTH + 0.05).translate([0, 0, -TXT_DEPTH])
    return solid.transform(np.column_stack([ex, ey, ez, origin]).astype(float))


def countersunk(x, y, z_top, z_bottom):
    return union([cyl(x, y, z_bottom - 0.01, z_top + 0.01, SCREW_HOLE / 2),
                  cyl(x, y, z_top - (SCREW_CSK - SCREW_HOLE) / 2, z_top + 0.01, SCREW_HOLE / 2, SCREW_CSK / 2)])


def column(x, y, z_top, r):
    """Colonna vite raccordata alle pareti più vicine."""
    parts = [cyl(x, y, FLOOR - 0.01, z_top, r)]
    for wy in (T, D - T):
        if abs(y - wy) <= r + 0.01:
            parts.append(box(x - r, min(y, wy), FLOOR - 0.01, x + r, max(y, wy), z_top))
    for wx in (T, X_STEP, X_STEP + T, W - T):
        if abs(x - wx) <= r + 0.01:
            parts.append(box(min(x, wx), y - r, FLOOR - 0.01, max(x, wx), y + r, z_top))
    return union(parts)


# --- VASCA -----------------------------------------------------------------------------
def build_tray():
    body = outline(0, W, 0, Z_WALL_C)
    body -= box(-1, -1, Z_WALL_M, X_STEP, D + 1, Z_WALL_C + 1)           # zona matrice bassa
    body -= box(T, T, FLOOR, X_STEP, D - T, Z_WALL_C + 1)                # vano matrice
    body -= box(CX0, T, FLOOR, W - T, D - T, Z_WALL_C + 1)               # vano comandi
    add, cut = [], []

    # nervature a griglia sotto la matrice, con tacche in cima per i fili
    rib_t, x0m, y0m = 1.6, MX - MAT / 2, MY - MAT / 2
    stations = [2, 41, 80, 119, 158]
    for s in stations:
        add.append(box(x0m + s - rib_t / 2, y0m + 2, FLOOR - 0.01, x0m + s + rib_t / 2, y0m + 158, Z_MAT))
        add.append(box(x0m + 2, y0m + s - rib_t / 2, FLOOR - 0.01, x0m + 158, y0m + s + rib_t / 2, Z_MAT))
    for a, b in zip(stations[:-1], stations[1:]):
        mid = (a + b) / 2
        for s in stations:
            cut.append(box(x0m + mid - 5, y0m + s - 2, Z_MAT - 2.5, x0m + mid + 5, y0m + s + 2, Z_MAT + 0.01))
            cut.append(box(x0m + s - 2, y0m + mid - 5, Z_MAT - 2.5, x0m + s + 2, y0m + mid + 5, Z_MAT + 0.01))

    # squadrette agli angoli della matrice (centrano i LED sotto la griglia; basse, la griglia
    # scende fino a Z_MAT + 0.3 + BAFFLE_FOOT)
    h, zg = MAT / 2 + MAT_CLR, Z_MAT + 1.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = MX + sx * h, MY + sy * h
            add.append(box(min(cx, cx + sx * 1.2), min(cy - sy * 8, cy + sy * 1.2), FLOOR - 0.01,
                           max(cx, cx + sx * 1.2), max(cy - sy * 8, cy + sy * 1.2), zg))
            add.append(box(min(cx - sx * 8, cx + sx * 1.2), min(cy, cy + sy * 1.2), FLOOR - 0.01,
                           max(cx - sx * 8, cx + sx * 1.2), max(cy, cy + sy * 1.2), zg))

    # colonne viti
    for x, y in SCREWS_M:
        add.append(column(x, y, Z_WALL_M, R_COL_M))
        cut.append(cyl(x, y, FLOOR + 0.8, Z_WALL_M + 0.01, SCREW_PILOT / 2))
    for x, y in SCREWS_C:
        add.append(column(x, y, Z_WALL_C, 4.0))
        cut.append(cyl(x, y, Z_WALL_C - 12, Z_WALL_C + 0.01, SCREW_PILOT / 2))

    # culla Teensy 4.1: sponde laterali + fermo anteriore basso (sotto il PCB, così la micro-SD
    # del Teensy entra ed esce) + due appoggi alle estremità, lontano dalla PSRAM sotto
    tw, tl = TEENSY
    ty1 = D - T - 0.6
    ty0 = ty1 - tl
    fh, zs = FLOOR + TEENSY_STANDOFF + 1.6 + 1.0, FLOOR + TEENSY_STANDOFF
    for x0 in (TEENSY_X - tw / 2 - 1.2, TEENSY_X + tw / 2):
        add.append(box(x0, ty0 - 1.2, FLOOR - 0.01, x0 + 1.2, ty1, fh))
    add.append(box(TEENSY_X - tw / 2, ty0 - 1.2, FLOOR - 0.01, TEENSY_X + tw / 2, ty0, zs))
    for x0 in (TEENSY_X - tw / 2, TEENSY_X + 6.0):   # fermi d'angolo: tengono il PCB, la micro-SD (+-5,5) passa
        add.append(box(x0, ty0 - 1.2, FLOOR - 0.01, x0 + tw / 2 - 6.0, ty0, fh))
    for yb in (ty0, ty1 - 4.5):
        add.append(box(TEENSY_X - 5, yb, FLOOR - 0.01, TEENSY_X + 5, yb + 4.5, zs))

    # piedistalli dei tact switch: lo switch appoggia qui, la linguetta del pannello lo preme.
    # Bordino che lo centra + asole per le gambe aperte sul davanti (fili saldati prima).
    zb = Z_WALL_C - (SW_BODY[2] + 0.1)          # appoggio del corpo dello switch
    for u, v in BUTTONS.values():
        x, y = ctrl(u, v)
        post = box(x - 5.2, y - 5.0, FLOOR - 0.01, x + 5.2, y + 5.0, zb + 1.0)
        post -= box(x - 3.2, y - 3.2, zb, x + 3.2, y + 3.2, zb + 1.1)                  # sede del corpo
        for sx in (-1, 1):
            post -= box(x + sx * SW_PIN_X - 1.4, y - 5.1, zb - 7.0, x + sx * SW_PIN_X + 1.4, y + 2.25 + 1.0, zb + 1.1)
        add.append(post)

    # battuta lungo il gradino per il bordo destro del diffusore (2 mm, smusso a 45° sotto:
    # stampabile senza supporti); i passaggi fili più sotto la interrompono
    ledge = CS([[(X_STEP, Z_WALL_M - 4.0), (X_STEP + 0.01, Z_WALL_M), (X_STEP - 2.0, Z_WALL_M),
                 (X_STEP - 2.0, Z_WALL_M - 2.0)]]).extrude(D - 2 * T)
    add.append(ledge.rotate([90, 0, 0]).translate([0, D - T, 0]))

    body = union([body] + add)

    # passaggi fili nel gradino (matrice -> zona comandi)
    for yc in (D * 0.3, D * 0.55):              # lontano dalla colonna del pannello a v=128
        cut.append(box(X_STEP - 0.01, yc - 15, FLOOR, CX0 + 0.01, yc + 15, Z_WALL_M - 1.5))

    # fori: USB + cuffie (retro), jack 6,35 (fianco destro)
    zu = FLOOR + TEENSY_STANDOFF + 1.6 + USB_Z_ABOVE_PCB
    usb = rrect(14, 10, 2.5).extrude(T + 2).translate([-7, -5, 0])
    cut.append(usb.rotate([-90, 0, 0]).translate([TEENSY_X, D - T - 1, zu]))
    # il jack cuffie della scheda audio è sul lato USB: apertura larga quanto la scheda
    # (la posizione del jack lungo il bordo cambia fra i lotti), chiusa in alto dal pannello
    cut.append(box(TEENSY_X - AUDIO[0] / 2, D - T - 1, HP_Z - HP_R, TEENSY_X + AUDIO[0] / 2, D + 1, Z_WALL_C + 1))
    for v, dia in JACKS.values():
        cut.append(M.cylinder(T + 2, dia / 2, -1, SEG).rotate([0, 90, 0]).translate([W - T - 1, CY0 + v, JACK_Z]))

    # piedini adesivi: sedi sul fondo
    for x, y in [(15, 15), (W - 15, 15), (15, D - 15), (W - 15, D - 15)]:
        cut.append(cyl(x, y, -0.01, 0.8, 5.5))

    # scritte sulle pareti
    side = (np.array([0, 1, 0]), np.array([0, 0, 1]))
    back = (np.array([-1, 0, 0]), np.array([0, 0, 1]))       # letto da dietro
    cut.append(text_cut("USB", 3.0, [TEENSY_X - 13, D, zu], *back))
    cut.append(text_cut("PHONES", 3.0, [TEENSY_X + AUDIO[0] / 2 + 10, D, HP_Z], *back))
    for name, (v, dia) in JACKS.items():          # sopra il dado da 3/8" (14,6 mm sugli spigoli)
        cut.append(text_cut(name, 2.4, [W, CY0 + v, JACK_Z + 7.3 + 2.4], *side))

    return body - union(cut)


# --- DIFFUSORE (zona matrice, traslucido) -------------------------------------------------
def build_window():
    z0 = Z_WALL_M
    win = outline(0, X_STEP - 0.2, z0, Z_TOP_M)
    add, cut = [], []

    hw = MAT / 2 + 0.5                       # sopra la matrice si assottiglia a DIFF_T
    cut.append(box(MX - hw, MY - hw, z0 - 0.01, MX + hw, MY + hw, Z_TOP_M - DIFF_T))

    # griglia 16x16: le pareti cadono fra i LED (a metà fra due file) e scendono fino a
    # BAFFLE_FOOT dal PCB flessibile, sotto la cima dei LED -> pochissima luce fra le celle
    zb0, zb1 = Z_MAT + 0.3 + BAFFLE_FOOT, Z_TOP_M - DIFF_T + 0.01
    n = int(round(MAT / MAT_PITCH))
    for i in range(n + 1):
        t = -MAT / 2 + i * MAT_PITCH
        bt = BAFFLE_T if 0 < i < n else 1.2
        add.append(box(MX + t - bt / 2, MY - MAT / 2 - 0.6, zb0, MX + t + bt / 2, MY + MAT / 2 + 0.6, zb1))
        add.append(box(MX - MAT / 2 - 0.6, MY + t - bt / 2, zb0, MX + MAT / 2 + 0.6, MY + t + bt / 2, zb1))

    for x, y in SCREWS_M:
        cut.append(countersunk(x, y, Z_TOP_M, z0))
    # la griglia va unita DOPO aver scavato l'incavo, altrimenti lo scavo la stacca dal diffusore
    return union([win - union(cut)] + add)


# --- PANNELLO COMANDI (opaco) --------------------------------------------------------------
def build_panel():
    z0 = Z_WALL_C
    panel = outline(X_STEP, W, z0, Z_TOP_C)
    add, cut, post = [], [], []          # post: aggiunte dopo i tagli

    # tasti flessibili: linguetta (spessa TAB_T, a filo del piano) con un perno che preme lo
    # switch. Lo switch sta sul piedistallo della vasca (build_tray), non appeso qui:
    # niente ponti in stampa, e la quota dipende solo dalla vasca.
    bw, bd, bh = SW_BODY
    hw = TAB_W / 2
    zf = z0 - (bh + 0.1)                          # appoggio del corpo dello switch (= build_tray)
    act_top = zf + SW_H
    nub_len = (Z_TOP_C - TAB_T) - act_top - NUB_GAP
    assert nub_len > 0.2, (f"perno troppo corto ({nub_len:.2f} mm): linguetta, gioco e switch non tornano "
                           "-> controlla SW_H, TAB_T e NUB_GAP")
    for u, v in BUTTONS.values():
        x, y = ctrl(u, v)
        y0, y1 = y - TAB_FRONT, y + TAB_BACK
        # fessura a U (passante) + vuoto sotto la linguetta
        cut.append(box(x - hw - TAB_SLOT, y0 - TAB_SLOT, z0 - 0.01, x - hw, y1, Z_TOP_C + 0.01))
        cut.append(box(x + hw, y0 - TAB_SLOT, z0 - 0.01, x + hw + TAB_SLOT, y1, Z_TOP_C + 0.01))
        cut.append(box(x - hw - TAB_SLOT, y0 - TAB_SLOT, z0 - 0.01, x + hw + TAB_SLOT, y0, Z_TOP_C + 0.01))
        cut.append(box(x - hw, y0, z0 - 0.01, x + hw, y1, Z_TOP_C - TAB_T))
        post.append(cyl(x, y, Z_TOP_C - TAB_T - nub_len, Z_TOP_C - TAB_T + 0.01, NUB_D / 2))   # perno

    # OLED: finestra + squadrette di posizionamento del PCB
    ox, oy = ctrl(*OLED_C)
    pw, ph = OLED_PCB
    cut.append(box(ox - OLED_WIN[0] / 2, oy - OLED_WIN[1] / 2, z0 - 0.01, ox + OLED_WIN[0] / 2, oy + OLED_WIN[1] / 2, Z_TOP_C + 0.01))
    gz0 = z0 - OLED_GLASS - 1.6 - 1.0
    for sx in (-1, 1):
        for sy in (-1, 1):
            cx, cy = ox + sx * pw / 2, oy + sy * ph / 2
            add.append(box(min(cx, cx + sx * 1.2), min(cy, cy - sy * 7), gz0, max(cx, cx + sx * 1.2), max(cy, cy - sy * 7), z0 + 0.01))
            add.append(box(min(cx, cx - sx * 7), min(cy, cy + sy * 1.2), gz0, max(cx, cx - sx * 7), max(cy, cy + sy * 1.2), z0 + 0.01))

    panel = union([panel] + add)

    # encoder: foro boccola + sede anulare per la linguetta antirotazione
    for u, v in ENCODERS.values():
        x, y = ctrl(u, v)
        cut.append(cyl(x, y, z0 - 0.01, Z_TOP_C + 0.01, ENC_HOLE / 2))
        ri, ro, dp = ENC_RING
        cut.append(cyl(x, y, z0 - 0.01, z0 + dp, ro) - cyl(x, y, z0 - 0.02, z0 + dp + 0.01, ri))

    for x, y in SCREWS_C:
        cut.append(countersunk(x, y, Z_TOP_C, z0))
    # scasso sopra l'apertura delle cuffie: la spina passa anche se è più grossa di Ø9
    cut.append(box(TEENSY_X - AUDIO[0] / 2, D - T - 0.5, z0 - 0.01, TEENSY_X + AUDIO[0] / 2, D + 1, z0 + HP_RELIEF))

    # scritte incise
    up = (np.array([1, 0, 0]), np.array([0, 1, 0]))
    for name, (u, v) in ENCODERS.items():
        x, y = ctrl(u, v)
        cut.append(text_cut(name, 3.0, [x, y + 12.5, Z_TOP_C], *up))
    for name, (u, v) in BUTTONS.items():
        x, y = ctrl(u, v)
        cut.append(text_cut(name, 2.8, [x, y - TAB_FRONT - TAB_SLOT - 3.0, Z_TOP_C], *up))
    cut.append(text_cut("ichosynth", 5.0, [*ctrl(CTRL / 2, LOGO_V), Z_TOP_C], *up))

    return union([panel - union(cut)] + post)


# --- MANOPOLA (facoltativa) ----------------------------------------------------------------
def build_knob(d=18.0, h=15.0):
    body = M.cylinder(h, d / 2, d / 2, 72)
    body -= union(M.cylinder(h + 2, 0.7, 0.7, 12).translate([d / 2 + 0.25, 0, -1]).rotate([0, 0, a])
                  for a in range(0, 360, 15))
    body -= M.cylinder(4.5, 5.75, 5.75, SEG)                                  # sede dado/boccola
    # albero a D 6 mm: il piatto dell'EC11 copre solo gli ultimi ~8 mm -> piatto nel foro solo in fondo
    shaft = M.cylinder(10, 3.075, 3.075, SEG) - box(1.5, -4, 3, 5, 4, 12)
    body -= shaft.translate([0, 0, 4.4])
    body -= box(-0.6, d / 2 - 5, h - 0.6, 0.6, d / 2 - 1.2, h + 0.1)         # indice
    return body.translate([0, 0, -h]).rotate([180, 0, 0])                    # piano sul piatto


# --- export ---------------------------------------------------------------------------
def to_trimesh(man):
    mesh = man.to_mesh()
    return trimesh.Trimesh(vertices=np.asarray(mesh.vert_properties)[:, :3],
                           faces=np.asarray(mesh.tri_verts), process=False)


def print_pose(man, flip=False, turn=False):
    """Orientamento di stampa: flip = faccia superiore sul piatto; turn = ruotato di 90°."""
    if flip:
        man = man.rotate([180, 0, 0])
    if turn:
        man = man.rotate([0, 0, 90])
    x0, y0, z0, _, _, _ = man.bounding_box()
    return man.translate([-x0, -y0, -z0])


def size(man):
    x0, y0, z0, x1, y1, z1 = man.bounding_box()
    return x1 - x0, y1 - y0, z1 - z0


def layout(parts):
    """Impila i pezzi lungo Y, centrati sul piatto; verifica che stiano nei 250x250."""
    total = sum(size(p)[1] for p in parts) + PLATE_GAP * (len(parts) - 1)
    y, placed = (PLATE - total) / 2, []
    for p in parts:
        w, d, _ = size(p)
        placed.append(p.translate([(PLATE - w) / 2, y, 0]))
        y += d + PLATE_GAP
    x0, y0, _, x1, y1, _ = union(placed).bounding_box()
    assert min(x0, y0) >= 2 and max(x1, y1) <= PLATE - 2, f"non entra nel piatto: {x1 - x0:.1f} x {y1 - y0:.1f}"
    return placed


def main():
    out = Path(__file__).resolve().parent / "stl"
    out.mkdir(exist_ok=True)
    tray, panel, window, knob = build_tray(), build_panel(), build_window(), build_knob()
    for man in (tray, panel, window, knob):
        assert man.status() == m3.Error.NoError, man.status()

    tray_p, panel_p = layout([print_pose(tray), print_pose(panel, flip=True, turn=True)])
    (window_p,) = layout([print_pose(window, flip=True)])
    files = {"tray": tray_p, "panel": panel_p, "window": window_p, "knob": knob,
             "plate1": union([tray_p, panel_p])}
    for name, man in files.items():
        tm = to_trimesh(man)
        tm.export(out / f"{name}.stl")
        ext = tm.bounds[1] - tm.bounds[0]
        print(f"{name:6s} {ext[0]:6.1f} x {ext[1]:6.1f} x {ext[2]:5.1f} mm  {tm.volume / 1000:6.1f} cm3  "
              f"watertight={tm.is_watertight}")
    print(f"case chiuso: {W:.1f} x {D:.1f} mm, alto {Z_TOP_M:.1f} (matrice) / {Z_TOP_C:.1f} (comandi) mm")


if __name__ == "__main__":
    main()
