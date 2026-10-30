"""Render delle scene del case ichosynth (Blender 4.2+ / 5.x, Cycles su CPU).

Si lancia da render.ps1 (priorità bassa, thread limitati):
    blender -b --factory-startup -t 6 -P blender_render.py -- [build_dir] [out_dir] [scena ...]

Legge build/scenes.json (scritto da scenes.py), importa le mesh STL (in mm), applica i
materiali, sistema luci/camera, renderizza in out/<scena>.png e salva out/<scena>.json
con le coordinate in pixel dei punti per frecce ed etichette.
"""
import json
import math
import sys
from pathlib import Path

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Euler, Matrix, Vector

S = 0.001                                       # mm -> m

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
HERE = Path(__file__).resolve().parent
BUILD = Path(argv[0]) if len(argv) > 0 else HERE / "build"
OUT = Path(argv[1]) if len(argv) > 1 else HERE / "out"
ONLY = set(argv[2:])
OUT.mkdir(parents=True, exist_ok=True)


def srgb(h):
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return [(x / 12.92) if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c] + [1.0]


# --- materiali ------------------------------------------------------------------------
_mats = {}
LED = {"k": 9000.0}                            # emissione LED della scena corrente


def principled(name, color, rough=0.5, metal=0.0, coat=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    p = m.node_tree.nodes["Principled BSDF"]
    p.inputs["Base Color"].default_value = srgb(color) if isinstance(color, str) else color
    p.inputs["Roughness"].default_value = rough
    p.inputs["Metallic"].default_value = metal
    if coat and "Coat Weight" in p.inputs:
        p.inputs["Coat Weight"].default_value = coat
    return m


def emission(name, color, strength):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = srgb(color)
    e.inputs["Strength"].default_value = strength
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(e.outputs[0], o.inputs[0])
    return m


def diffuser(name):
    """PLA traslucido: diffuso + traslucente (la luce dei LED lo attraversa)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    d = nt.nodes.new("ShaderNodeBsdfDiffuse")
    d.inputs["Color"].default_value = srgb("#cfccc4")
    t = nt.nodes.new("ShaderNodeBsdfTranslucent")
    t.inputs["Color"].default_value = srgb("#fffaf0")
    g = nt.nodes.new("ShaderNodeBsdfGlossy")
    g.inputs["Roughness"].default_value = 0.35
    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.85
    mix2 = nt.nodes.new("ShaderNodeMixShader")
    mix2.inputs["Fac"].default_value = 0.06
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(d.outputs[0], mix.inputs[1])
    nt.links.new(t.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], mix2.inputs[1])
    nt.links.new(g.outputs[0], mix2.inputs[2])
    nt.links.new(mix2.outputs[0], o.inputs[0])
    return m


def material(key):
    if key.startswith("emit_"):
        key = f"{key}@{LED['k']:g}"            # stessa tinta, intensità diversa per scena
    if key in _mats:
        return _mats[key]
    fixed = {
        "pla_black": lambda: principled(key, "#0f0f11", 0.72),
        "pla_diffuser": lambda: diffuser(key),
        "pcb_green": lambda: principled(key, "#1f6b3a", 0.45, coat=0.3),
        "pcb_blue": lambda: principled(key, "#1f4fa8", 0.45, coat=0.3),
        "pcb_black": lambda: principled(key, "#17191c", 0.45, coat=0.3),
        "pcb_white": lambda: principled(key, "#e9e6df", 0.5),
        "led_body": lambda: principled(key, "#f4f2ec", 0.35),
        "metal": lambda: principled(key, "#c8ccd2", 0.28, metal=1.0),
        "metal_dark": lambda: principled(key, "#3a3d42", 0.35, metal=1.0),
        "gold": lambda: principled(key, "#d4a64a", 0.3, metal=1.0),
        "black_plastic": lambda: principled(key, "#141416", 0.45),
        "glass_black": lambda: principled(key, "#050608", 0.08, coat=1.0),
        "rubber": lambda: principled(key, "#0e0e0e", 0.85),
        "bed": lambda: principled(key, "#2b2b2e", 0.75),
        "floor": lambda: principled(key, "#eeeeec", 0.9),
    }
    if key in fixed:
        m = fixed[key]()
    elif key.startswith("emit_"):
        m = emission(key, key[5:12], LED["k"])
    elif key.startswith("pla_#"):
        m = principled(key, key[4:], 0.55)
    else:
        m = principled(key, "#ff00ff", 0.5)
    _mats[key] = m
    return m


# --- scena ------------------------------------------------------------------------------
def reset():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    for coll in (bpy.data.meshes, bpy.data.lights, bpy.data.cameras, bpy.data.images):
        for d in list(coll):
            if d.users == 0:
                coll.remove(d)


_imported = {}


def import_stl(path):
    """Importa (una volta) e ritorna una copia collegata dell'oggetto."""
    if path not in _imported:
        before = set(bpy.data.objects)
        bpy.ops.wm.stl_import(filepath=str(path))
        ob = (set(bpy.data.objects) - before).pop()
        me = ob.data
        me.transform(Matrix.Scale(S, 4))        # mm -> m nella mesh (l'importer scala l'oggetto)
        try:
            me.shade_smooth()
            me.set_sharp_from_angle(angle=math.radians(32))
        except Exception:
            pass
        me.use_fake_user = True                 # resta in cache fra una scena e l'altra
        _imported[path] = me
        bpy.data.objects.remove(ob, do_unlink=True)
    me = _imported[path]
    ob = bpy.data.objects.new(Path(path).stem, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def image_plane(spec):
    img = bpy.data.images.load(str(BUILD / spec["image"]))
    w, h = spec["size"]
    me = bpy.data.meshes.new("plane")
    me.from_pydata([(-w / 2, -h / 2, 0), (w / 2, -h / 2, 0), (w / 2, h / 2, 0), (-w / 2, h / 2, 0)], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new()
    for i, c in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uv.data[i].uv = c
    me.transform(Matrix.Scale(S, 4))
    ob = bpy.data.objects.new("oled_screen", me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(spec["center"]) * S
    ob.rotation_euler = Euler([math.radians(a) for a in spec.get("rot", (0, 0, 0))])
    m = bpy.data.materials.new("oled_screen")
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Closest"
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Strength"].default_value = 14.0
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(tex.outputs["Color"], e.inputs["Color"])
    nt.links.new(e.outputs[0], o.inputs[0])
    me.materials.append(m)


def area_light(name, loc, target, power, size):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy = power
    ld.size = size
    ob = bpy.data.objects.new(name, ld)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup_render(sc):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = sc["samples"]
    s.cycles.use_adaptive_sampling = True
    s.cycles.use_denoising = True
    try:
        s.cycles.denoiser = "OPENIMAGEDENOISE"
    except Exception:
        pass
    s.cycles.max_bounces = 6
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.render.resolution_x, s.render.resolution_y = sc["res"]
    s.render.resolution_percentage = 100
    s.render.film_transparent = False
    s.view_settings.view_transform = "AgX"
    s.view_settings.exposure = -1.6
    try:
        s.view_settings.look = "AgX - Punchy"
    except Exception:
        pass
    s.render.image_settings.file_format = "PNG"
    w = bpy.data.worlds.new("w") if not bpy.data.worlds else bpy.data.worlds[0]
    s.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = srgb("#f4f4f2")
    bg.inputs["Strength"].default_value = 0.35


def bbox_world(objs):
    pts = []
    for ob in objs:
        if ob.type == "MESH":
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return pts


def place_camera(sc, objs):
    e, a = math.radians(sc["elev"]), math.radians(sc["azim"])
    view = Vector((math.cos(e) * math.cos(a), math.cos(e) * math.sin(a), math.sin(e)))   # verso la camera
    if sc.get("fit"):
        x0, y0, z0, x1, y1, z1 = [v * S for v in sc["fit"]]
        pts = [Vector((x, y, z)) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    else:
        pts = bbox_world(objs)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    center = (lo + hi) / 2
    cd = bpy.data.cameras.new("cam")
    cd.lens = sc["focal"]
    cd.sensor_fit = "AUTO"
    cd.clip_start, cd.clip_end = 0.01, 50
    cam = bpy.data.objects.new("cam", cd)
    bpy.context.scene.collection.objects.link(cam)
    bpy.context.scene.camera = cam
    up = Vector((0, 0, 1)) if abs(view.z) < 0.98 else Vector((0, 1, 0))
    right = up.cross(view).normalized()
    upv = view.cross(right).normalized()
    w, h = sc["res"]
    half_w = math.atan(cd.sensor_width / (2 * cd.lens))
    tx = math.tan(half_w) * (1 if w >= h else w / h)
    ty = math.tan(half_w) * (h / w if w >= h else 1)
    margin = 0.86
    d = 0.0
    for p in pts:
        q = p - center
        z = q.dot(view)
        d = max(d, abs(q.dot(right)) / (tx * margin) + z, abs(q.dot(upv)) / (ty * margin) + z)
    cam.location = center + view * d
    cam.rotation_euler = (-view).to_track_quat("-Z", "Y").to_euler()
    if abs(view.z) >= 0.98:
        cam.rotation_euler = Euler((0, 0, 0))
    return cam, center, view, d


def render_scene(sc):
    reset()
    LED["k"] = sc.get("led", 9000.0)
    setup_render(sc)
    objs = []
    for o in sc["objects"]:
        ob = import_stl(BUILD / o["mesh"])
        ob.rotation_euler = Euler([math.radians(v) for v in o["rot"]])
        ob.location = Vector(o["loc"]) * S
        if not ob.data.materials:               # mesh condivise: materiale per oggetto
            ob.data.materials.append(None)
        ob.material_slots[0].link = "OBJECT"
        ob.material_slots[0].material = material(o["mat"])
        objs.append(ob)
    for p in sc["planes"]:
        image_plane(p)
    bpy.context.view_layer.update()

    pts = bbox_world(objs)
    zmin = min(p.z for p in pts)
    if sc["floor"]:
        bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, zmin - 0.0002))
        bpy.context.active_object.data.materials.append(material("floor"))

    cam, center, view, d = place_camera(sc, objs)
    span = max((p - center).length for p in pts)
    right = Vector((0, 0, 1)).cross(view).normalized() if abs(view.z) < 0.98 else Vector((1, 0, 0))
    key = center + (view * 1.2 - right * 1.0 + Vector((0, 0, 1.6))).normalized() * span * 4
    fill = center + (view * 1.0 + right * 1.3 + Vector((0, 0, 0.6))).normalized() * span * 4
    rim = center + (-view * 1.0 + Vector((0, 0, 1.2))).normalized() * span * 4
    dist2 = (span * 4) ** 2                    # potenza proporzionale alla distanza^2
    area_light("key", key, center, 130 * dist2, span * 2.2)
    area_light("fill", fill, center, 45 * dist2, span * 2.5)
    area_light("rim", rim, center, 80 * dist2, span * 2.0)

    out = OUT / f"{sc['name']}.png"
    bpy.context.scene.render.filepath = str(out)
    bpy.ops.render.render(write_still=True)

    s = bpy.context.scene
    w, h = sc["res"]
    proj = {}
    for k, p in sc["points"].items():
        co = world_to_camera_view(s, cam, Vector(p) * S)
        proj[k] = [round(co.x * w, 1), round((1 - co.y) * h, 1)]
    meta = dict(name=sc["name"], res=sc["res"], points=proj, arrows=sc["arrows"], labels=sc["labels"])
    (OUT / f"{sc['name']}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(f"[render] {sc['name']} -> {out}", flush=True)


def main():
    scenes = json.loads((BUILD / "scenes.json").read_text(encoding="utf-8"))
    preview = "PREVIEW" in ONLY                 # anteprima veloce: 40% risoluzione, 12 campioni
    names = ONLY - {"PREVIEW"}
    for sc in scenes:
        if not names or sc["name"] in names:
            if preview:
                sc["res"] = [int(v * 0.4) for v in sc["res"]]
                sc["samples"] = 12
            render_scene(sc)


main()
