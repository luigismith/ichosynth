"""Componenti acquistati del case ichosynth, in coordinate di montaggio.

Una sola fonte per la geometria: la usano check_fit.py (interferenze) e render/scenes.py
(render). Ogni funzione ritorna una lista di (nome, Manifold, materiale): il nome serve ai
render, check_fit unisce i pezzi di ogni componente.
"""
import build_case as b
from build_case import M, box, cyl, union

E = 0.05   # ritiro sulle facce che toccano il case: il contatto non è un'interferenza


def hexcyl(x, y, z0, z1, r):
    return M.cylinder(z1 - z0, r, r, 6).translate([x, y, z0])


def rot_x(m):
    """Cilindro lungo Z -> lungo X."""
    return m.rotate([0, 90, 0])


def rot_y(m):
    """Cilindro lungo Z -> lungo +Y."""
    return m.rotate([-90, 0, 0])


# --- matrice --------------------------------------------------------------------------
def matrix(lit=None):
    """PCB flessibile + 256 LED 5050. lit: {(colonna, riga_dall_alto): '#rrggbb'} -> tappi emissivi."""
    z, x0, y0 = b.Z_MAT, b.MX - b.MAT / 2, b.MY - b.MAT / 2
    out = [("matrix_flex", box(x0, y0, z + E, x0 + 160, y0 + 160, z + 0.3), "pcb_white")]
    leds, by_col = [], {}
    for i in range(16):
        for j in range(16):
            cx, cy = x0 + 5 + 10 * i, y0 + 5 + 10 * j
            leds.append(box(cx - 2.5, cy - 2.5, z + 0.3, cx + 2.5, cy + 2.5, z + 1.9))
            col = (lit or {}).get((i, 15 - j))
            if col:
                by_col.setdefault(col, []).append(box(cx - 2.1, cy - 2.1, z + 1.9, cx + 2.1, cy + 2.1, z + 2.0))
    out.append(("matrix_leds", union(leds), "led_body"))
    for col, parts in by_col.items():
        out.append((f"led_{col[1:]}", union(parts), "emit_" + col))
    return out


# --- Teensy 4.1 + scheda audio Rev D impilata ----------------------------------------------
def teensy_geom():
    y1 = b.D - b.T - 0.6                  # bordo lato USB
    return b.TEENSY_X, y1, y1 - 61.0, b.FLOOR + b.TEENSY_STANDOFF


def teensy():
    tx, y1, y0, zp = teensy_geom()
    za = b.Z_AUDIO
    aw, al = b.AUDIO
    hdr = []
    for sx in (-1, 1):
        xc = tx + sx * 7.62
        # pettini maschi lunghi su tutta la lunghezza (come sul primo prototipo), plastica sul Teensy
        hdr.append(box(xc - 1.27, y0 + 1, zp + 1.6, xc + 1.27, y1 - 1, za))        # plastica dell'header
        hdr.append(box(xc - 1.27, y0 + 1, zp - 2.5, xc + 1.27, y1 - 1, zp))        # pin sotto
        hdr.append(box(xc - 0.4, y0 + 1, za, xc + 0.4, y1 - 1, zp + 1.6 + b.HDR_PIN_UP))  # pin sopra
    return [
        ("teensy_pcb", box(tx - 8.9, y0, zp + E, tx + 8.9, y1, zp + 1.6), "pcb_green"),
        ("teensy_chip", union([box(tx - 5, y0 + 26, zp + 1.6, tx + 5, y0 + 36, zp + 2.5),
                               box(tx - 3, y0 + 13, zp + 1.6, tx + 3, y0 + 19, zp + 2.4)]), "black_plastic"),
        # micro-USB (sporge 0,4 mm) e slot micro-SD sul lato opposto
        ("teensy_metal", union([box(tx - 3.9, y1 - 5, zp + 1.6, tx + 3.9, y1 + 0.4, zp + 4.2),
                                box(tx - 6, y0, zp + 1.6, tx + 6, y0 + 12, zp + 3.4)]), "metal"),
        ("teensy_headers", union(hdr), "black_plastic"),
        ("audio_pcb", box(tx - aw / 2, y1 - al, za, tx + aw / 2, y1, za + 1.6), "pcb_green"),
        ("audio_chip", box(tx - 3, y1 - 22, za + 1.6, tx + 3, y1 - 16, za + 2.4), "black_plastic"),
        # jack cuffie sul lato USB, a filo del bordo, spostato verso un angolo
        ("audio_jack", box(tx + b.AUDIO_JACK_DX - 3.5, y1 - 12, za + 1.6,
                           tx + b.AUDIO_JACK_DX + 3.5, y1 + 0.3, za + 1.6 + b.AUDIO_JACK_H), "black_plastic"),
    ]


def plugs():
    """Spine inserite: micro-USB e cuffie, dal bordo del Teensy fino a fuori dal case."""
    tx, y1, _, zp = teensy_geom()
    zu = zp + 1.6 + b.USB_Z_ABOVE_PCB
    usb = union([box(tx - 3.6, y1 + 0.4 + E, zu - 1.2, tx + 3.6, b.D - b.T + 1, zu + 1.2),      # spinotto
                 box(tx - 5.25, b.D - b.T + 1.0, zu - 3.5, tx + 5.25, b.D + 25, zu + 3.5)])     # corpo 10,5x7
    hx = tx + b.AUDIO_JACK_DX
    hp = union([rot_y(M.cylinder(b.T + 4, 1.75, 1.75, 24)).translate([hx, y1 + 0.3 + E, b.HP_Z]),
                rot_y(M.cylinder(25, 4.0, 4.0, 32)).translate([hx, b.D - b.T + 1.0, b.HP_Z])])    # corpo Ø8
    return [("plug_usb", usb, "black_plastic"), ("plug_phones", hp, "black_plastic")]


# --- encoder KY-040 -----------------------------------------------------------------------
def encoder(name, nut=True):
    """EC11 sul pannello + PCB 19x26 + 5 pin piegati verso ENC_HEADER (fili saldati sui pin)."""
    x, y = b.ctrl(*b.ENCODERS[name])
    zw, s = b.Z_WALL_C, b.ENC_HEADER
    metal = [box(x - 6, y - 6, zw - 6.5, x + 6, y + 6, zw - E), cyl(x, y, zw - E, zw + 7, 3.4),
             cyl(x, y, zw + 7, zw + 20, 3.0) - box(x + 1.5, y - 4, zw + 12, x + 5, y + 4, zw + 21)]
    pcb_y = sorted((y - 11 * s, y + 15 * s))
    pin_y = sorted((y + 15 * s, y + 21 * s))
    sol_y = sorted((y + 21 * s, y + 24 * s))                 # stagnatura + filo
    pins = [box(x - 5.4 + 2.54 * k, pin_y[0], zw - 7.6, x - 4.76 + 2.54 * k, pin_y[1], zw - 7.0) for k in range(5)]
    solder = box(x - 6.5, sol_y[0], zw - 8.6, x + 6.5, sol_y[1], zw - 6.0)
    out = [(f"enc_{name}_metal", union(metal), "metal"),
           (f"enc_{name}_pcb", box(x - 9.5, pcb_y[0], zw - 8.1, x + 9.5, pcb_y[1], zw - 6.5), "pcb_black"),
           (f"enc_{name}_pins", union(pins), "gold"),
           (f"enc_{name}_solder", solder, "metal_dark")]
    if nut:
        zt = b.Z_TOP_C
        out.append((f"enc_{name}_nut", hexcyl(x, y, zt + E, zt + 2, 5.3) - cyl(x, y, zt - 1, zt + 3, 3.5), "metal"))
    return out


def knob(name, mat="pla_black"):
    """Manopola calzata fino in fondo: il foro tocca la punta dell'albero, la base resta
    3,2 mm sopra il pannello (libera dal dado M7)."""
    x, y = b.ctrl(*b.ENCODERS[name])
    k = b.build_knob()                         # orientamento di stampa: faccia superiore a z=0
    return [(f"knob_{name}", k.rotate([180, 0, 0]).translate([x, y, b.Z_TOP_C + 3.2 + 15]), mat)]


# --- OLED ---------------------------------------------------------------------------------
OLED_ACTIVE = (21.7, 10.9)


def oled():
    ox, oy = b.ctrl(*b.OLED_C)
    zw = b.Z_WALL_C
    return [("oled_pcb", box(ox - 13.65, oy - 13.9, zw - 3.25, ox + 13.65, oy + 13.9, zw - 1.65), "pcb_blue"),
            ("oled_glass", box(ox - 13.35, oy - 9.6, zw - 1.65, ox + 13.35, oy + 9.6, zw - E), "glass_black"),
            ("oled_pins", union(box(ox - 3.81 + 2.54 * k - 0.32, oy + 11.2, zw - 6.5, ox - 3.81 + 2.54 * k + 0.32,
                                    oy + 11.84, zw - 3.25) for k in range(4)), "gold")]


# --- tact switch ----------------------------------------------------------------------------
def switch(name, pressed=0.0):
    """Switch 6x6 sul piedistallo della vasca. pressed: corsa del pulsantino (mm)."""
    x, y = b.ctrl(*b.BUTTONS[name])
    zf = b.Z_WALL_C - (b.SW_BODY[2] + 0.1)
    zt = zf + b.SW_BODY[2]
    legs = [box(x + sx * 3.25 - 0.35, y + sy * 2.25 - 0.2, zf - 3.5, x + sx * 3.25 + 0.35, y + sy * 2.25 + 0.2, zf + 0.5)
            for sx in (-1, 1) for sy in (-1, 1)]
    return [(f"sw_{name}_body", union([box(x - 3, y - 3, zf + E, x + 3, y + 3, zt - 0.35),
                                        cyl(x, y, zt - 0.05, zf + b.SW_H - pressed, 1.75)]), "black_plastic"),
            (f"sw_{name}_metal", union([box(x - 3, y - 3, zt - 0.35, x + 3, y + 3, zt)] + legs), "metal")]


# --- jack 6,35 mm --------------------------------------------------------------------------
def jack(name, part="all"):
    """Jack mono 6,35 (ingombro tondo Ø JACK_BODY_H-1 x JACK_DEPTH dietro la parete) + boccola 3/8" + dado fuori."""
    v, dia = b.JACKS[name]
    y, z, xi, xo = b.CY0 + v, b.JACK_Z, b.W - b.T, b.W
    hole = rot_x(M.cylinder(40, 3.2, 3.2, 32)).translate([xi - 30, y, z])
    r = b.JACK_BODY_H / 2 - 0.5
    body = rot_x(M.cylinder(b.JACK_DEPTH - E, r, r, 48)).translate([xi - b.JACK_DEPTH, y, z])
    bush = rot_x(M.cylinder(xo + 2.5 - xi, dia / 2 - 0.2, dia / 2 - 0.2, 32)).translate([xi - E, y, z]) - hole
    nut = rot_x(M.cylinder(2.4, 7.3, 7.3, 6)).translate([xo + E, y, z]) - hole
    key = name.replace(" ", "")
    out = []
    if part in ("body", "all"):
        out += [(f"jack_{key}_body", body, "black_plastic"), (f"jack_{key}_bush", bush, "metal")]
    if part in ("nut", "all"):
        out.append((f"jack_{key}_nut", nut, "metal"))
    return out


def jack_plug(name):
    """Punta della spina 6,35 inserita: la parte che sporge dal fondo del jack, dentro il case."""
    v, _ = b.JACKS[name]
    y, z = b.CY0 + v, b.JACK_Z
    back = b.W - b.T - b.JACK_DEPTH                    # fondo del jack
    tip = min(b.W + 2.5 - b.PLUG_LEN, back - 0.5)      # battuta della spina sulla boccola
    return [(f"plug_{name.replace(' ', '')}", rot_x(M.cylinder(back - E - tip, 3.25, 3.25, 32)).translate([tip, y, z]),
             "metal")]


# --- minuteria --------------------------------------------------------------------------
def screw(x, y, ztop, tag):
    head = cyl(x, y, ztop - 1.5, ztop - E, 1.6, 3.05) - hexcyl(x, y, ztop - 1.0, ztop + 1, 1.25)
    shaft = cyl(x, y, ztop - 8.0, ztop - 1.5, 1.2)           # M3x8 al diametro di nocciolo (il filetto morde il foro pilota)
    return (f"screw_{tag}", union([head, shaft]), "metal_dark")


def screws(kind):
    pts, zt = (b.SCREWS_M, b.Z_TOP_M) if kind == "m" else (b.SCREWS_C, b.Z_TOP_C)
    return [screw(x, y, zt, f"{kind}{i}") for i, (x, y) in enumerate(pts)]


FEET = [(15, 15), (b.W - 15, 15), (15, b.D - 15), (b.W - 15, b.D - 15)]


def feet():
    return [("feet", union(cyl(x, y, -1.4, 0.8 - E, 5.0) for x, y in FEET), "rubber")]


def all_components():
    """{nome componente: [(nome, Manifold, materiale), ...]} del case montato."""
    c = {"matrice": matrix(), "teensy+audio": teensy(), "OLED": oled(), "piedini": feet()}
    for n in b.ENCODERS:
        c[f"KY-040 {n}"] = encoder(n)
    for n in b.BUTTONS:
        c[f"switch {n}"] = switch(n)
    for n in b.JACKS:
        c[f"jack {n}"] = jack(n)
        c[f"spina {n}"] = jack_plug(n)
    c["spina USB"], c["spina cuffie"] = [plugs()[0]], [plugs()[1]]
    c["viti diffusore"], c["viti pannello"] = screws("m"), screws("c")
    return c
