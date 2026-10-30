"""ichosynth — progetto pronto da stampare per Anycubic Slicer Next (Kobra S1 Combo + ACE Pro).

    python case/make_slicer_project.py                # -> case/ichosynth_case_S1Combo.3mf
    python case/make_slicer_project.py --verifica     # idem + slicing headless dei 2 piatti e controlli
    python case/make_slicer_project.py --petg         # variante tutta in PETG (nero + traslucido)
                                                       #   -> case/ichosynth_case_S1Combo_PETG.3mf

Legge gli STL di case/stl/ (quote e posizioni prese dai file, niente numeri fissi: dopo aver
rigenerato gli STL con build_case.py basta rilanciarlo) e scrive un progetto 3MF nel formato
che Anycubic Slicer Next (fork di Bambu Studio 2.0) salva da sé: 2 piatti, preset di sistema
della Kobra S1, filamenti assegnati agli slot dell'ACE Pro e cambio filamento automatico.

  piatto 1: tray.stl + panel.stl, nelle stesse posizioni XY di plate1.stl     -> nero (slot 1)
  piatto 2: window.stl (faccia sul piatto) -> traslucido (slot 2) fino a DIFF_T = 1,4 mm,
            poi nero: cambio filamento automatico al layer 1,4-1,6 mm
  knob.stl (manopole, facoltative) non è nel progetto.

Impostazioni sopra al preset "0.20mm Standard": 3 perimetri e niente brim; skirt 0,
riempimento 15 %, niente supporti e strato 0,2 sono già quelli del preset.

Formato (ricavato da progetti salvati da Anycubic Slicer Next 2.0.0.3 su questo PC e
confermato dal 3MF che la sua riga di comando riscrive dopo lo slicing):
  3D/3dmodel.model + 3D/Objects/*.model   mesh (estensione "production" del 3MF)
  Metadata/model_settings.config          oggetti -> filamento (slot), piatti -> oggetti
  Metadata/project_settings.config        tutti i parametri (preset di sistema + modifiche)
  Metadata/custom_gcode_per_layer.xml     cambi filamento/colore, per piatto
I valori dei preset si leggono dall'installazione dello slicer (resources/profiles/Anycubic),
quindi il progetto si apre senza "preset sconosciuto". Solo libreria standard + numpy/trimesh.

--verifica: lancia AnycubicSlicerNext.exe da riga di comando (--slice 0) a priorità bassa,
con cartella dati temporanea (non tocca AppData), e controlla il G-code: numero di layer,
cambio filamento, niente skirt/brim, spurgo fuori dai pezzi, torre dentro il piatto.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent
STL = HERE / "stl"
SLICER = Path(r"C:\Program Files\AnycubicSlicerNext")
PROFILES = SLICER / "resources" / "profiles"
VENDOR = "Anycubic"
APP_VERSION = "2.0.0.3"                 # versione di Anycubic Slicer Next installata

# --- preset (nomi esatti come li mostra lo slicer) ------------------------------------
PRINTER = "Anycubic Kobra S1 0.4 nozzle"           # la S1 Combo usa lo stesso preset della S1
PROCESS = "0.20mm Standard @Anycubic Kobra S1 0.4 nozzle"
F_PLA_NERO = ("Anycubic PLA @Anycubic Kobra S1 0.4 nozzle", "#000000", "PLA nero")
F_PETG_NERO = ("Anycubic PETG @Anycubic Kobra S1 0.4 nozzle", "#000000", "PETG nero")
F_PLA_TRASL = ("Anycubic PLA Translucent @Anycubic Kobra S1 0.4 nozzle", "#F0F0F0", "PLA traslucido")
# niente preset "PETG Translucent" per la S1: stesso preset del PETG, cambia solo il colore
F_PETG_TRASL = ("Anycubic PETG @Anycubic Kobra S1 0.4 nozzle", "#F0F0F0", "PETG traslucido")

# Filamenti = slot dell'ACE Pro, nell'ordine. Il PETG non si attacca al PLA (si usano l'uno
# come interfaccia di distacco dei supporti dell'altro): ogni progetto è tutto di un
# materiale, così la griglia nera del diffusore si salda al piano traslucido.
PETG = "--petg" in sys.argv
FILAMENTS = [F_PETG_NERO, F_PETG_TRASL] if PETG else [F_PLA_NERO, F_PLA_TRASL]
SLOT_P1, SLOT_WIN, SLOT_GRID = 1, 2, 1     # nero = slot 1, traslucido = slot 2
OUT = HERE / ("ichosynth_case_S1Combo_PETG.3mf" if PETG else "ichosynth_case_S1Combo.3mf")

# modifiche al preset di processo (tutto il resto resta quello di sistema)
OVERRIDES = {
    "wall_loops": "3",                  # 3 perimetri (preset: 2)
    "brim_type": "no_brim",             # piatto 1 pieno (preset: auto_brim)
    "skirt_loops": "0",                 # = preset, scritto per chiarezza
    "sparse_infill_density": "15%",     # = preset
    "enable_support": "0",              # = preset
    "layer_height": "0.2",              # = preset
}
BED_TYPE = "High Temp Plate"            # come nei progetti S1 salvati su questo PC

# --- piatti -----------------------------------------------------------------------------
BED = 250.0
# La GUI affianca i piatti a passo (lato del modello del piatto S1 - 2) * 1,2: il modello
# "Anycubic Kobra S1_buildplate_model.stl" è 264 x 276 -> 314,4 mm in X (ricavato da un
# progetto a 7 piatti salvato dallo slicer: oggetti centrati a x = 125, 439,4, 753,8).
# La riga di comando invece usa 250 * 1,2 = 300: per --verifica si scrive una copia a 300.
PLATE_STRIDE_GUI = (264.0 - 2.0) * 1.2
PLATE_STRIDE_CLI = BED * 1.2


def build_case_param(name, default):
    """Legge un parametro da build_case.py (così resta allineato al generatore)."""
    m = re.search(rf"^{name}\s*=\s*([\d.]+)", (HERE / "build_case.py").read_text(encoding="utf-8"), re.M)
    return float(m.group(1)) if m else default


DIFF_T = build_case_param("DIFF_T", 1.4)   # spessore del diffusore: sotto traslucido, sopra nero
LAYER = float(OVERRIDES["layer_height"])
# Il cambio va sul PRIMO layer nero: per DIFF_T = 1,4 quello da 1,4 a 1,6 (lo slicer lo
# chiama "1.6"), così i layer 0-1,4 mm sono traslucidi e la griglia esce tutta nera.
CHANGE_Z = round(round(DIFF_T / LAYER) * LAYER + LAYER, 3)
# Torre di spurgo del piatto 2 (angolo anteriore-sinistro del corpo, coordinate del piatto).
# Il corpo è 30 x ~14 mm e col suo brim occupa ~[x-6, x+36] x [y-7,5, y+21]: in (7, 9) sta
# nell'angolo davanti a sinistra, dentro il piatto e ~6 mm davanti al diffusore (controllato
# da --verifica). Sul piatto 1 c'è un solo filamento: niente torre.
WIPE_TOWER_P2 = (7.0, 9.0)
# Linea di spurgo della S1: è nel "before_layer_change_gcode" del preset stampante (layer 0),
# a Y = 255-255,45 e X 89,4-158,8, cioè fuori dall'area stampabile 250 x 250.
PURGE_Y = 255.0

# chiavi dei preset che lo slicer NON scrive nel progetto (confronto con un progetto salvato
# da Anycubic Slicer Next 2.0.0.3): metadati del preset o opzioni che questa versione scarta
SKIP_KEYS = {"type", "from", "setting_id", "instantiation", "inherits", "is_custom_defined",
             "version", "name", "compatible_printers", "compatible_printers_condition",
             "compatible_prints", "compatible_prints_condition", "filament_id", "bed_type",
             "filament_load_time", "filament_unload_time", "overhang_speed_classic",
             "overhang_totally_speed", "retract_on_top_layer", "rotate_solid_infill_direction",
             "solid_infill_filament", "sparse_infill_filament", "wall_filament",
             "tree_support_branch_diameter_double_wall"}
# parametri dei filamenti che dipendono dal tipo di ugello (X_BRASS / X_HS): lo slicer
# copia in X il valore del tipo montato (S1 di serie: ottone) e completa quelli mancanti con X
NOZZLE_KEYS = ["nozzle_temperature", "nozzle_temperature_initial_layer", "fan_max_speed",
               "fan_min_speed", "fan_cooling_layer_time", "slow_down_layer_time"]


# --- preset -----------------------------------------------------------------------------
def preset_index():
    idx = json.loads((PROFILES / f"{VENDOR}.json").read_text(encoding="utf-8"))
    return {e["name"]: PROFILES / VENDOR / e["sub_path"]
            for k in ("machine_list", "process_list", "filament_list") for e in idx[k]}


def flatten(name, paths):
    """Preset di sistema con tutta la catena "inherits" risolta (il figlio vince)."""
    if name not in paths:
        raise SystemExit(f"preset non trovato nello slicer: {name!r}")
    d = json.loads(paths[name].read_text(encoding="utf-8"))
    out = flatten(d["inherits"], paths) if d.get("inherits") else {}
    out.update(d)
    return out


def nozzle_variant(fil, suffix):
    """Allinea X / X_BRASS / X_HS come fa lo slicer per l'ugello montato."""
    fil = dict(fil)
    for k in NOZZLE_KEYS:
        if k not in fil:
            continue
        base = fil[k]
        brass, hs = fil.get(k + "_BRASS", base), fil.get(k + "_HS", base)
        fil[k + "_BRASS"], fil[k + "_HS"] = brass, hs
        fil[k] = brass if suffix == "BRASS" else hs
    return fil


def flush_volume(c_from, c_to):
    """mm3 di spurgo per passare da un colore all'altro: verso uno scuro basta poco."""
    if c_from == c_to:
        return 0
    lum = lambda c: sum(int(c[i:i + 2], 16) for i in (1, 3, 5)) / 765
    return 185 if lum(c_to) <= lum(c_from) else 600


def project_settings():
    paths = preset_index()
    machine, process = flatten(PRINTER, paths), flatten(PROCESS, paths)
    suffix = "BRASS" if machine.get("nozzle_type", "brass") == "brass" else "HS"
    fils = [nozzle_variant(flatten(n, paths), suffix) for n, _, _ in FILAMENTS]
    for n, f in zip(FILAMENTS, fils):
        assert PRINTER in f.get("compatible_printers", [PRINTER]), f"{n[0]} non compatibile con {PRINTER}"

    cfg = {k: v for k, v in machine.items() if k not in SKIP_KEYS}
    cfg.update({k: v for k, v in process.items() if k not in SKIP_KEYS})
    for k in sorted(set().union(*fils) - SKIP_KEYS):   # opzioni dei filamenti: un valore per slot
        vals = []
        for f in fils:
            v = f.get(k, fils[0].get(k))
            vals += v if isinstance(v, list) else [v]
        cfg[k] = vals
    diff = sorted(k for k, v in OVERRIDES.items() if process.get(k) != v)
    cfg.update(OVERRIDES)

    colours = [c for _, c, _ in FILAMENTS]
    n = len(FILAMENTS)
    cfg.update({
        "name": "project_settings", "from": "project", "version": APP_VERSION,
        "printer_settings_id": PRINTER, "print_settings_id": PROCESS,
        "filament_settings_id": [p for p, _, _ in FILAMENTS],
        "filament_ids": [f["filament_id"] for f in fils],
        "filament_colour": colours, "filament_colour_info": colours,
        "default_filament_colour": [""] * n,
        "filament_map": ["1"] * n, "filament_map_mode": "Auto For Flush",
        "flush_volumes_matrix": [str(flush_volume(a, b)) for a in colours for b in colours],
        "flush_multiplier": "1",
        "curr_bed_type": BED_TYPE,
        "print_compatible_printers": [PRINTER],
        "nozzle_volume_type": ["Standard"], "default_nozzle_volume_type": ["Standard"],
        # torre di spurgo, una posizione per piatto (piatto 1: default dello slicer, non usata)
        "wipe_tower_x": ["165", f"{WIPE_TOWER_P2[0]:g}"],
        "wipe_tower_y": ["230", f"{WIPE_TOWER_P2[1]:g}"],
        # [processo, filamento 1..n, stampante]: "" = preset di sistema senza genitore
        "inherits_group": [""] * (n + 2),
        "different_settings_to_system": [";".join(diff)] + [""] * (n + 1),
    })
    return cfg


# --- mesh e XML -------------------------------------------------------------------------
def load(name):
    tm = trimesh.load(STL / f"{name}.stl", process=True)
    assert len(tm.faces) and tm.is_winding_consistent, f"{name}.stl: mesh rovinata"
    return tm


def object_model(oid, tm, center, uuid):
    v = "\n".join(f'     <vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in tm.vertices - center)
    t = "\n".join(f'     <triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in tm.faces)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
            ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
            ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
            ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n <resources>\n'
            f'  <object id="{oid}" p:UUID="{uuid}" type="model">\n   <mesh>\n    <vertices>\n{v}\n'
            f'    </vertices>\n    <triangles>\n{t}\n    </triangles>\n   </mesh>\n  </object>\n'
            ' </resources>\n <build/>\n</model>\n')


def tr(off):
    return "1 0 0 0 1 0 0 0 1 " + " ".join(f"{c:.6f}" for c in off)


def parts():
    """(nome, STL, piatto, slot) + mesh e controlli sulla disposizione."""
    spec = [("vasca", "tray", 1, SLOT_P1), ("pannello", "panel", 1, SLOT_P1),
            ("diffusore", "window", 2, SLOT_WIN)]
    objs = []
    for i, (name, stl, plate, slot) in enumerate(spec, start=1):
        tm = load(stl)
        lo, hi = tm.bounds
        assert lo[0] >= 0 and lo[1] >= 0 and hi[0] <= BED and hi[1] <= BED, f"{stl}: fuori dal piatto"
        assert abs(lo[2]) < 1e-6, f"{stl}: non appoggia sul piatto (z min {lo[2]})"
        assert hi[1] < PURGE_Y, f"{stl}: tocca la linea di spurgo"
        objs.append(dict(name=name, stl=stl, plate=plate, slot=slot, tm=tm, center=(lo + hi) / 2,
                         mesh_id=2 * i - 1, obj_id=2 * i, file=f"{name}_{i}.model", n=i))

    # piatto 1 identico a plate1.stl (stesse posizioni XY dei due pezzi)
    p1 = trimesh.load(STL / "plate1.stl")
    lo1 = np.min([o["tm"].bounds[0] for o in objs if o["plate"] == 1], axis=0)
    hi1 = np.max([o["tm"].bounds[1] for o in objs if o["plate"] == 1], axis=0)
    assert np.allclose(p1.bounds, [lo1, hi1], atol=1e-3), "tray+panel non coincidono con plate1.stl"
    # il diffusore cambia sezione a DIFF_T: c'è un piano di vertici a quella quota
    win = next(o["tm"] for o in objs if o["stl"] == "window")
    assert np.any(np.isclose(win.vertices[:, 2], DIFF_T, atol=1e-4)), "window.stl: niente gradino a DIFF_T"
    return objs


def write_3mf(objs, cfg, out, stride):
    for o in objs:   # mesh centrata (come la salva lo slicer), posizione nell'istanza
        o["world"] = o["center"] + [stride * (o["plate"] - 1), 0, 0]
    files = {}
    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
        ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
        ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
        ' <Default Extension="png" ContentType="image/png"/>\n'
        ' <Default Extension="gcode" ContentType="text/x.gcode"/>\n</Types>\n')
    files["_rels/.rels"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" '
        'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n</Relationships>\n')
    files["3D/_rels/3dmodel.model.rels"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
        + "".join(f' <Relationship Target="/3D/Objects/{o["file"]}" Id="rel-{o["n"]}" '
                  'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n' for o in objs)
        + '</Relationships>\n')

    res, items = [], []
    for o in objs:
        files[f"3D/Objects/{o['file']}"] = object_model(
            o["mesh_id"], o["tm"], o["center"], f"{o['n']:04x}0000-81cb-4c03-9d28-80fed5dfa1dc")
        res.append(f'  <object id="{o["obj_id"]}" p:UUID="{o["n"]:08x}-61cb-4c03-9d28-80fed5dfa1dc" type="model">\n'
                   f'   <components>\n    <component p:path="/3D/Objects/{o["file"]}" objectid="{o["mesh_id"]}"'
                   f' p:UUID="{o["n"]:04x}0000-b206-40ff-9872-83e8017abed1" transform="1 0 0 0 1 0 0 0 1 0 0 0"/>\n'
                   '   </components>\n  </object>\n')
        items.append(f'  <item objectid="{o["obj_id"]}" p:UUID="{o["obj_id"]:08x}-b1ec-4553-aec9-835e5b724bb4"'
                     f' transform="{tr(o["world"])}" printable="1"/>\n')
    today = date.today().isoformat()
    meta = {"Application": f"BambuStudio-{APP_VERSION}", "BambuStudio:3mfVersion": "1", "Copyright": "",
            "CreationDate": today, "Description": "", "Designer": "", "DesignerCover": "",
            "DesignerUserId": "", "License": "", "ModificationDate": today, "Origin": "",
            "Title": "ichosynth case"}
    files["3D/3dmodel.model"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02"'
        ' xmlns:BambuStudio="http://schemas.bambulab.com/package/2021"'
        ' xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
        + "".join(f' <metadata name="{k}">{v}</metadata>\n' for k, v in meta.items())
        + ' <resources>\n' + "".join(res) + ' </resources>\n'
        ' <build p:UUID="2c7c17d8-22b5-4d84-8835-1976022ea369">\n' + "".join(items) + ' </build>\n</model>\n')

    # oggetti -> filamento (slot ACE), piatti -> oggetti
    ms = ['<?xml version="1.0" encoding="UTF-8"?>\n<config>\n']
    for o in objs:
        ms.append(f'  <object id="{o["obj_id"]}">\n'
                  f'    <metadata key="name" value={quoteattr(o["name"])}/>\n'
                  f'    <metadata key="extruder" value="{o["slot"]}"/>\n'
                  f'    <part id="{o["mesh_id"]}" subtype="normal_part">\n'
                  f'      <metadata key="name" value={quoteattr(o["name"])}/>\n'
                  '      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n'
                  f'      <metadata key="source_file" value={quoteattr(str(STL / (o["stl"] + ".stl")))}/>\n'
                  '      <metadata key="source_object_id" value="0"/>\n'
                  '      <metadata key="source_volume_id" value="0"/>\n'
                  + "".join(f'      <metadata key="source_offset_{a}" value="{c:.6f}"/>\n'
                            for a, c in zip("xyz", o["center"]))
                  + '      <mesh_stat edges_fixed="0" degenerate_facets="0" facets_removed="0" '
                  'facets_reversed="0" backwards_edges="0"/>\n    </part>\n  </object>\n')
    for plate in (1, 2):
        # nome del piatto vuoto: con un nome la riga di comando dello slicer 2.0.0.3 va in crash
        ms.append(f'  <plate>\n    <metadata key="plater_id" value="{plate}"/>\n'
                  '    <metadata key="plater_name" value=""/>\n'
                  '    <metadata key="locked" value="false"/>\n'
                  '    <metadata key="filament_map_mode" value="Auto For Flush"/>\n'
                  f'    <metadata key="filament_maps" value="{" ".join(["1"] * len(FILAMENTS))}"/>\n')
        for o in objs:
            if o["plate"] == plate:
                ms.append('    <model_instance>\n'
                          f'      <metadata key="object_id" value="{o["obj_id"]}"/>\n'
                          '      <metadata key="instance_id" value="0"/>\n'
                          f'      <metadata key="identify_id" value="{100 + o["n"]}"/>\n'
                          '    </model_instance>\n')
        ms.append('  </plate>\n')
    ms.append('  <assemble>\n' + "".join(
        f'   <assemble_item object_id="{o["obj_id"]}" instance_id="0" transform="{tr(o["world"])}" offset="0 0 0" />\n'
        for o in objs) + '  </assemble>\n</config>\n')
    files["Metadata/model_settings.config"] = "".join(ms)

    # cambio filamento del piatto 2. type: 0 ColorChange (M600, pausa), 1 PausePrint,
    # 2 ToolChange (cambio slot ACE, automatico), 3 Template, 4 Custom. top_z = primo layer
    # col filamento nuovo; extruder = slot (1..n). mode MultiAsSingle = oggetto con un solo
    # filamento + cambi a quota (è anche quello che lo slicer riscrive dopo lo slicing).
    grid_col = FILAMENTS[SLOT_GRID - 1][1]
    files["Metadata/custom_gcode_per_layer.xml"] = (
        '<?xml version="1.0" encoding="utf-8"?>\n<custom_gcodes_per_layer>\n'
        '<plate>\n<plate_info id="1"/>\n<mode value="MultiAsSingle"/>\n</plate>\n'
        '<plate>\n<plate_info id="2"/>\n'
        f'<layer top_z="{CHANGE_Z:g}" type="2" extruder="{SLOT_GRID}" color="{grid_col}" extra="" gcode="tool_change"/>\n'
        '<mode value="MultiAsSingle"/>\n</plate>\n</custom_gcodes_per_layer>\n')
    files["Metadata/project_settings.config"] = json.dumps(cfg, indent=4, sort_keys=True, ensure_ascii=False) + "\n"
    files["Metadata/slice_info.config"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n  <header>\n'
        '    <header_item key="X-ACNext-Client-Type" value="slicer"/>\n'
        f'    <header_item key="X-ACNext-Client-Version" value="{APP_VERSION}"/>\n  </header>\n</config>\n')
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in files.items():
            z.writestr(name, data)


# --- verifica headless -------------------------------------------------------------------
def gcode_stats(path):
    """Layer, cambi filamento, ingombri per tipo di estrusione e stime dal G-code."""
    z, tool, typ, x, y = 0.0, None, None, None, None
    layers, changes, stats = [], [], {}
    bounds, tool_z = {}, {}
    for line in open(path, encoding="utf-8", errors="replace"):
        s = line.strip()
        if s.startswith(";Z:"):
            z = float(s[3:]); layers.append(z)
        elif s.startswith(";TYPE:"):
            typ = s[6:]
        elif re.match(r"^T\d+\b", s):
            t = int(re.match(r"^T(\d+)", s).group(1))
            if tool is not None and t != tool:
                changes.append((tool + 1, t + 1, z))      # slot 1..n
            tool = t
        elif s.startswith("; ") and " = " in s:
            k, _, v = s[2:].partition(" = ")
            stats[k] = v
        elif s.startswith("G1"):
            g = dict(re.findall(r"([XYE])([-\d.]+)", s.split(";")[0]))
            nx, ny = float(g.get("X", x if x is not None else "nan")), float(g.get("Y", y if y is not None else "nan"))
            if float(g.get("E", 0)) > 0 and ("X" in g or "Y" in g) and x is not None:
                b = bounds.setdefault(typ, [1e9, 1e9, -1e9, -1e9])
                b[:] = [min(b[0], x, nx), min(b[1], y, ny), max(b[2], x, nx), max(b[3], y, ny)]
                tool_z.setdefault(tool + 1, []).append(z)
            x, y = nx, ny
    return dict(layers=layers, changes=changes, stats=stats, bounds=bounds,
                tool_z={k: (min(v), max(v)) for k, v in tool_z.items()})


def verify(objs, cfg):
    tmp = Path(tempfile.mkdtemp(prefix="ichosynth_slice_"))
    proj = tmp / "progetto_cli.3mf"
    write_3mf(objs, cfg, proj, PLATE_STRIDE_CLI)      # stessa cosa, passo piatti della CLI
    out, datadir = tmp / "out", tmp / "datadir"
    out.mkdir(); datadir.mkdir()
    cmd = [str(SLICER / "AnycubicSlicerNext.exe"), "--datadir", str(datadir), "--slice", "0",
           "--outputdir", str(out), "--export-3mf", "sliced.3mf", str(proj)]
    print(f"slicing headless (priorità bassa): {tmp}")
    flags = subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    with open(tmp / "slicer_log.txt", "w") as log:
        rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, creationflags=flags, timeout=1800).returncode
    assert rc == 0, f"lo slicer è uscito con codice {rc} (log in {tmp / 'slicer_log.txt'})"

    ok = True
    def check(cond, msg):
        nonlocal ok
        ok &= bool(cond)
        print(f"  [{'ok' if cond else 'NO'}] {msg}")

    for plate in (1, 2):
        g = gcode_stats(out / f"plate_{plate}.gcode")
        st, bb = g["stats"], g["bounds"]
        mine = [o for o in objs if o["plate"] == plate]
        zmax = max(o["tm"].bounds[1][2] for o in mine)
        print(f"piatto {plate}: {len(g['layers'])} layer, {st.get('estimated printing time (normal mode)')}, "
              f"filamento [g] {st.get('filament used [g]')} (slot 1..{len(FILAMENTS)})")
        check(len(g["layers"]) == round(zmax / LAYER), f"layer = altezza {zmax:.1f} / {LAYER}")
        check(not any(t and ("skirt" in t.lower() or "brim" in t.lower()) for t in bb), "niente skirt né brim")
        check(st.get("wall_loops") == "3" and st.get("sparse_infill_density") == "15%"
              and st.get("enable_support") == "0", "3 perimetri, 15 %, niente supporti")
        purge = bb.get("Custom")
        check(purge and purge[1] >= BED, f"spurgo fuori dal piatto (y {purge[1]:.2f}-{purge[3]:.2f})" if purge else "spurgo")
        lo = np.min([o["tm"].bounds[0] for o in mine], axis=0)
        hi = np.max([o["tm"].bounds[1] for o in mine], axis=0)
        parts_bb = [v for k, v in bb.items() if k not in ("Custom", "Prime tower")]
        pb = [min(b[0] for b in parts_bb), min(b[1] for b in parts_bb),
              max(b[2] for b in parts_bb), max(b[3] for b in parts_bb)]
        check(pb[0] >= lo[0] - 0.5 and pb[1] >= lo[1] - 0.5 and pb[2] <= hi[0] + 0.5 and pb[3] <= hi[1] + 0.5,
              f"pezzi dove sono negli STL (x {pb[0]:.1f}-{pb[2]:.1f}, y {pb[1]:.1f}-{pb[3]:.1f})")
        if plate == 1:
            check(not g["changes"] and list(g["tool_z"]) == [SLOT_P1], f"un solo filamento (slot {SLOT_P1})")
        else:
            check(g["changes"] == [(SLOT_WIN, SLOT_GRID, CHANGE_Z)] if SLOT_WIN != SLOT_GRID else False,
                  f"cambio slot {SLOT_WIN} -> {SLOT_GRID} al layer {CHANGE_Z:g}: {g['changes']}")
            zt = g["tool_z"].get(SLOT_WIN, (0, 99))
            check(zt[1] <= DIFF_T + 1e-6, f"traslucido solo fino a {zt[1]:g} mm (DIFF_T {DIFF_T:g})")
            t = bb.get("Prime tower")
            if t:
                inside = t[0] >= 0 and t[1] >= 0 and t[2] <= BED and t[3] <= BED
                clear = t[3] < lo[1] or t[2] < lo[0] or t[1] > hi[1] or t[0] > hi[0]
                check(inside and clear, f"torre x {t[0]:.1f}-{t[2]:.1f} y {t[1]:.1f}-{t[3]:.1f}: nel piatto, "
                                        "lontana dal diffusore")
    print("verifica " + ("superata" if ok else "NON superata") + f" (G-code in {out})")
    return ok


def main():
    objs = parts()
    cfg = project_settings()
    write_3mf(objs, cfg, OUT, PLATE_STRIDE_GUI)
    print(f"{OUT.name}: stampante {PRINTER!r}, processo {PROCESS!r}")
    for i, (p, c, label) in enumerate(FILAMENTS, start=1):
        print(f"  slot ACE {i}: {label:15s} {c}  {p!r}")
    print(f"  processo: {', '.join(f'{k}={cfg[k]}' for k in sorted(OVERRIDES))}")
    for o in objs:
        lo, hi = o["tm"].bounds
        print(f"  piatto {o['plate']}: {o['name']:9s} slot {o['slot']}  x {lo[0]:5.1f}-{hi[0]:5.1f}"
              f"  y {lo[1]:5.1f}-{hi[1]:5.1f}  alto {hi[2]:4.1f}")
    print(f"  piatto 2: slot {SLOT_WIN} fino a {DIFF_T:g} mm, cambio allo slot {SLOT_GRID} al layer {CHANGE_Z:g}")
    print(f"  spurgo S1 a Y={PURGE_Y:g} (fuori dal piatto), torre del piatto 2 a {WIPE_TOWER_P2}")
    if "--verifica" in sys.argv and not verify(objs, cfg):
        sys.exit(1)


if __name__ == "__main__":
    main()
