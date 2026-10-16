"""Render the SuperPOD shots from blender/out/superpod.blend (built by build_scene.py).

Usage (headless, from the repo root):
    blender -b -P blender/render.py -- [--quality draft|final] [--shots a,b,c,d,e,f]
        [--blend blender/out/superpod.blend] [--scene docs/scene.json] [--out blender/out]
        [--samples N] [--scale PCT]

Shots (cameras derived from scene.json, never hard-coded rack coordinates):
  a hero      cold aisle of the first row at eye height (1.6 m), 30 mm, DGX fronts receding
  b hotaisle  inside the containment: DGX rears, exhaust grilles, PSUs, fibre
  c fabric    front close-up of the rack holding the compute leaves + UFM (mgmt-r01)
  d storage   split frame: DDN rack | VAST rack (they sit back-to-back across the hot aisle,
              so no single physical viewpoint sees both fronts)
  e overview  orthographic top-down of the hall (same orientation as the draw.io floor plan)
  f product   one DGX H200, bezel on, 3/4 front, studio three-point light (square)
Mixed pod only (scene with a cooling section):
  g rowb      row-B cold aisle at eye height: NVL72 fronts (champagne trays), CDU block at the end
  h cdu       the CDU block from the row-B cold aisle: cabinets, secondary headers, FWS mains
  i rearaisle inside the uncontained rear aisle: ChilledDoors, branch valves, hoses, headers
  j plant     outside the pipe wall: the three Uniflair modules, sleeves, mains
Cycles on Metal GPU, AgX view transform, OIDN denoise. draft = 1280x720 @ 64 spp;
final = 3840x2160 @ 256 spp (product 4096x4096). Output: <out>/<shot>.png
"""
import argparse
import math
import os
import sys
import time

import bpy
import numpy as np
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from superpod import layout as L  # noqa: E402

SHOTS = {"a": "hero", "b": "hotaisle", "c": "fabric", "d": "storage", "e": "overview", "f": "product",
         "g": "rowb", "h": "cdu", "i": "rearaisle", "j": "plant"}
QUALITY = {"draft": dict(res=(1280, 720), square=1024, samples=64),
           "final": dict(res=(3840, 2160), square=4096, samples=256)}


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="render.py")
    ap.add_argument("--quality", choices=QUALITY, default="draft")
    ap.add_argument("--shots", default="a,b,c,d,e,f")
    ap.add_argument("--blend", default=os.path.join(HERE, "out", "superpod.blend"))
    ap.add_argument("--scene", default=os.path.join(REPO, "docs", "scene.json"))
    ap.add_argument("--library", default=os.path.join(REPO, "docs", "blender", "device-library.yaml"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--samples", type=int, default=None)
    ap.add_argument("--scale", type=int, default=100, help="resolution percentage")
    return ap.parse_args(argv)


# ---------------------------------------------------------------- render settings -----------
def enable_metal():
    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.get_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"
    return [d.name for d in prefs.devices if d.use]


def setup(scene, samples, res, scale):
    scene.render.engine = "CYCLES"
    c = scene.cycles
    c.device = "GPU"
    c.samples = samples
    c.use_adaptive_sampling = True
    c.adaptive_threshold = 0.012
    c.use_denoising = True
    c.denoiser = "OPENIMAGEDENOISE"
    c.denoising_use_gpu = True
    c.max_bounces, c.diffuse_bounces, c.glossy_bounces = 8, 3, 4
    c.transmission_bounces, c.transparent_max_bounces = 4, 12
    c.caustics_reflective = c.caustics_refractive = False
    c.blur_glossy = 1.0
    c.sample_clamp_indirect = 6.0
    try:
        c.use_light_tree = True
    except AttributeError:
        pass
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.resolution_percentage = scale
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_depth = "8"
    scene.render.use_persistent_data = True
    vs = scene.view_settings
    vs.view_transform = "AgX"
    for look in ("AgX - Medium High Contrast", "Medium High Contrast"):
        try:
            vs.look = look
            break
        except TypeError:
            continue


def world(scene, colour=(0.02, 0.021, 0.024), strength=1.0):
    w = scene.world or bpy.data.worlds.new("World")
    scene.world = w
    nt = w.node_tree
    bg = next(n for n in nt.nodes if n.type == "BACKGROUND")
    bg.inputs["Color"].default_value = (*colour, 1.0)
    bg.inputs["Strength"].default_value = strength


def show(view_layer, **flags):
    """Include/exclude top-level collections by name for this shot."""
    for lc in view_layer.layer_collection.children:
        if lc.name in flags:
            lc.exclude = not flags[lc.name]


def camera(scene, name, loc, target, lens=30.0, ortho=None, shift=(0.0, 0.0)):
    cd = bpy.data.cameras.get(name) or bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36.0
    cd.clip_start, cd.clip_end = 0.02, 200.0
    cd.shift_x, cd.shift_y = shift
    if ortho:
        cd.type, cd.ortho_scale = "ORTHO", ortho
    ob = bpy.data.objects.get(name) or bpy.data.objects.new(name, cd)
    if ob.name not in scene.collection.objects:
        scene.collection.objects.link(ob)
    ob.location = loc
    ob.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
    scene.camera = ob
    return ob


def render(scene, path):
    t = time.time()
    scene.render.filepath = path
    bpy.ops.render.render(write_still=True, scene=scene.name)
    dt = time.time() - t
    print(f"RENDERED {os.path.basename(path)} {scene.render.resolution_x}x{scene.render.resolution_y}"
          f" @ {scene.cycles.samples} spp in {dt:.0f}s", flush=True)
    return dt


# ---------------------------------------------------------------- scene-derived framing -----
class Frames:
    def __init__(self, s, lib):
        self.s, self.lib = s, lib
        self.rows = [r["name"] for r in s["hall"]["rows"]]
        self.H = L.rack_height(lib)

    def rack_with(self, *roles):
        for row in self.rows:
            for r in L.row_racks(self.s, row):
                have = {d.get("role") for d in r["devices"]}
                if all(x in have for x in roles):
                    return r
        raise SystemExit(f"no rack holds roles {roles}")

    def rack_with_type(self, t):
        return next(r for r in self.s["racks"] if any(d["type"] == t for d in r["devices"]))

    def zspan(self, rack, pred):
        ds = [d for d in rack["devices"] if d.get("position") and pred(d)]
        lo = min(d["z_bottom"] for d in ds)
        hi = max(d["z_bottom"] + d["u_height"] * L.U for d in ds)
        return lo, hi

    def hero(self):
        row = self.rows[0]
        c = L.cold_aisle(self.s, self.lib, row)
        fy = L.row_racks(self.s, row)[0]["facing"][1]
        front = c[1] if fy > 0 else c[3]
        w = c[3] - c[1]
        # from the aisle entrance (between the CRAH fan wall and the first rack), eye height
        loc = (c[0] - 0.45, front + fy * w * 0.72, 1.6)
        tgt = (c[0] + 4.2, front - fy * 0.05, 1.18)
        return loc, tgt

    def hotaisle(self):
        x0, y0, x1, y1 = L.hot_aisle(self.s, self.lib)
        ym = (y0 + y1) / 2
        # from near one end, close to the second row, looking diagonally at the first row's
        # rears so the grilles/PSUs are not hidden behind the 0U PDUs
        rows = [L.row_racks(self.s, r) for r in self.rows]
        ya = L.box_to_world(rows[0][0], L.rack_interior(rows[0][0], self.lib))
        first_rear = ya.y0 if rows[0][0]["facing"][1] > 0 else ya.y1
        sgn = 1 if first_rear > ym else -1
        return (x0 + 0.25, ym - sgn * 0.50, 1.30), (x0 + 1.75, first_rear - sgn * 0.02, 0.72)

    def rowb(self):
        """Second row's cold aisle from its entrance, eye height, looking down the NVL72 fronts."""
        row = self.rows[1]
        c = L.cold_aisle(self.s, self.lib, row)
        fy = L.row_racks(self.s, row)[0]["facing"][1]
        front = c[1] if fy > 0 else c[3]
        w = c[3] - c[1]
        loc = (c[0] - 0.45, front + fy * w * 0.70, 1.6)
        tgt = (c[0] + 4.5, front - fy * 0.08, 1.15)
        return loc, tgt

    def cdu(self):
        """The CDU block seen from the row-B cold aisle, 3/4, with the headers above."""
        cs = self.s["cooling"]
        cd = cs["cdus"]
        xs = [c["origin"][0] for c in cd]
        c0 = cd[0]
        fy = c0["facing"][1]
        xm = (min(xs) + max(xs)) / 2
        loc = (min(xs) - 2.6, c0["origin"][1] + fy * 3.4, 1.9)
        tgt = (xm + 0.3, c0["origin"][1] + fy * 0.2, 1.9)
        return loc, tgt

    def rearaisle(self):
        """Inside the rear aisle near the row start, looking along it at the first row's doors."""
        x0, y0, x1, y1 = L.hot_aisle(self.s, self.lib)
        ym = (y0 + y1) / 2
        rows = [L.row_racks(self.s, r) for r in self.rows]
        ya = L.box_to_world(rows[0][0], L.rack_interior(rows[0][0], self.lib))
        first_rear = ya.y0 if rows[0][0]["facing"][1] > 0 else ya.y1
        sgn = 1 if first_rear > ym else -1
        return (x0 + 0.3, ym - sgn * 0.45, 1.55), (x0 + 5.0, first_rear + sgn * 0.05, 1.5)

    def plant(self):
        """Outside the pipe wall: the chiller block with the wall and sleeves behind it."""
        units = self.s["cooling"]["plant"]["units"]
        u0 = units[0]
        xs = [u["origin"][0] for u in units]
        loc = (max(xs) + 5.0, u0["origin"][1] - u0["depth"] / 2 - 5.5, 3.0)
        tgt = ((min(xs) + max(xs)) / 2 - 1.2, u0["origin"][1] - 1.0, 1.3)
        return loc, tgt

    def front_three_quarter(self, rack, zmid, dist=1.15, side=-0.45, dz=0.08, look_x=0.0):
        loc = L.rack_to_world(rack, (side, 0.60 + dist, zmid + dz))
        tgt = L.rack_to_world(rack, (look_x, 0.50, zmid))
        return loc, tgt


# ---------------------------------------------------------------- product studio -----------
def product_scene(res, samples, scale):
    """Separate scene: one DGX asset instance on a seamless cyclorama, three-point light."""
    sc = bpy.data.scenes.get("Product") or bpy.data.scenes.new("Product")
    for ob in list(sc.collection.objects):
        sc.collection.objects.unlink(ob)
    dgx = next(c for c in bpy.data.collections if c.name.startswith("nvidia-dgx-h200|"))
    inst = bpy.data.objects.new("DGX_product", None)
    inst.instance_type, inst.instance_collection = "COLLECTION", dgx
    sc.collection.objects.link(inst)
    # cyclorama: floor + quarter-round cove + back wall, charcoal
    import bmesh
    me = bpy.data.meshes.new("cyc")
    bm = bmesh.new()
    # (y, z) profile: floor from the front, cove behind the DGX, back wall
    prof = [(3.0, 0.0)] + [(-1.5 - 0.7 * math.sin(a), 0.7 - 0.7 * math.cos(a)) for a in np.linspace(0, math.pi / 2, 16)] + [(-2.2, 3.0)]
    rows = []
    for x in (-3.0, 3.0):
        rows.append([bm.verts.new((x, y, z)) for y, z in prof])
    for i in range(len(prof) - 1):
        bm.faces.new((rows[0][i], rows[1][i], rows[1][i + 1], rows[0][i + 1]))
    bm.to_mesh(me)
    for p in me.polygons:
        p.use_smooth = True
    mat = bpy.data.materials.new("cyc")
    p = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    p.inputs["Base Color"].default_value = (0.012, 0.013, 0.015, 1)
    p.inputs["Roughness"].default_value = 0.3
    me.materials.append(mat)
    cyc = bpy.data.objects.new("cyclorama", me)
    sc.collection.objects.link(cyc)
    # three-point lighting (area lights), aimed at the chassis centre
    centre = Vector((0.0, -0.35, 0.18))

    def area(name, loc, energy, size, colour=(1, 1, 1), aim=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.size, ld.color = energy, size, colour
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        lo.rotation_euler = (Vector(aim or centre) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()
        sc.collection.objects.link(lo)

    area("key", (1.3, 1.6, 0.9), 110, 1.8, (1.0, 0.96, 0.9))
    area("fill", (-1.6, 1.4, 0.5), 45, 2.2, (0.85, 0.92, 1.0))
    area("rim", (-1.2, -2.0, 1.3), 420, 1.0, (0.85, 0.92, 1.0))
    area("backdrop", (0.0, -0.9, 0.05), 60, 1.2, (0.7, 0.8, 1.0), aim=(0.0, -2.2, 1.0))   # glow on the cove
    setup(sc, samples, (res, res), scale)
    world(sc, (0.01, 0.011, 0.013), 1.0)
    camera(sc, "cam_product", (0.78, 1.02, 0.40), (0.0, -0.28, 0.16), lens=55.0)
    return sc


# ---------------------------------------------------------------- split-frame composite ------
def hstack(paths, out, divider=4):
    imgs = [bpy.data.images.load(p, check_existing=False) for p in paths]
    arrs = []
    for im in imgs:
        a = np.empty(im.size[0] * im.size[1] * 4, dtype=np.float32)
        im.pixels.foreach_get(a)
        arrs.append(a.reshape(im.size[1], im.size[0], 4))
    h = arrs[0].shape[0]
    bar = np.zeros((h, divider, 4), dtype=np.float32)
    bar[..., :3], bar[..., 3] = 0.02, 1.0
    full = np.concatenate([arrs[0], bar, arrs[1]], axis=1)
    img = bpy.data.images.new("storage_split", full.shape[1], full.shape[0])
    img.pixels.foreach_set(full.ravel())
    img.filepath_raw, img.file_format = out, "PNG"
    img.save()
    for im in imgs:
        bpy.data.images.remove(im)


# ---------------------------------------------------------------- main -----------------------
def main():
    a = parse_args()
    bpy.ops.wm.open_mainfile(filepath=a.blend)
    devs = enable_metal()
    print("Cycles devices:", devs)
    q = QUALITY[a.quality]
    samples = a.samples or q["samples"]
    s, lib = L.load_scene(a.scene), L.load_library(a.library)
    F = Frames(s, lib)
    hall = bpy.data.scenes["Scene"]
    vl = hall.view_layers[0]
    os.makedirs(a.out, exist_ok=True)
    times = {}
    for key in a.shots.split(","):
        shot = SHOTS[key]
        path = os.path.join(a.out, f"{key}_{shot}.png")
        if shot == "product":
            sc = product_scene(q["square"], samples, a.scale)
            times[shot] = render(sc, path)
            continue
        setup(hall, samples, q["res"], a.scale)
        world(hall)
        hall.view_settings.exposure = 0.0
        show(vl, Ceiling=True, Lights=True, Containment=True, Overhead=True)
        sun = bpy.data.objects.get("overview_sun")
        if sun:
            sun.hide_render = True
        if shot == "hero":
            loc, tgt = F.hero()
            camera(hall, "cam_hero", loc, tgt, lens=24.0)
        elif shot == "hotaisle":
            loc, tgt = F.hotaisle()
            camera(hall, "cam_hotaisle", loc, tgt, lens=22.0)
            hall.view_settings.exposure = 0.8
        elif shot == "fabric":
            r = F.rack_with("ufm", "ib-compute-leaf")
            lo, hi = F.zspan(r, lambda d: d["role"].startswith("ib-compute") or d["role"] == "ufm")
            loc, tgt = F.front_three_quarter(r, (lo + hi) / 2 - 0.07, dist=0.9, side=-0.36, dz=0.0)
            camera(hall, "cam_fabric", loc, tgt, lens=26.0)
        elif shot == "storage":
            halves = []
            for t, name in (("ddn-ai400x2t", "ddn"), ("vast-cbox", "vast")):
                r = F.rack_with_type(t)
                lo, hi = F.zspan(r, lambda d: d["role"] in ("hps-storage", "nas-storage", "eth-storage-backend"))
                loc, tgt = F.front_three_quarter(r, (lo + hi) / 2 - 0.05, dist=0.95, side=-0.42, dz=0.05)
                camera(hall, f"cam_storage_{name}", loc, tgt, lens=24.0)
                hall.render.resolution_x = q["res"][0] // 2 - 2
                hp = os.path.join(a.out, f"{key}_{shot}_{name}.png")
                times[f"{shot}_{name}"] = render(hall, hp)
                halves.append(hp)
            hstack(halves, path)
            print(f"COMPOSITED {os.path.basename(path)}")
            continue
        elif shot == "rowb":
            loc, tgt = F.rowb()
            camera(hall, "cam_rowb", loc, tgt, lens=24.0)
        elif shot == "cdu":
            loc, tgt = F.cdu()
            camera(hall, "cam_cdu", loc, tgt, lens=26.0)
            hall.view_settings.exposure = 0.3
        elif shot == "rearaisle":
            loc, tgt = F.rearaisle()
            camera(hall, "cam_rearaisle", loc, tgt, lens=20.0)
            hall.view_settings.exposure = 0.6
        elif shot == "plant":
            loc, tgt = F.plant()
            camera(hall, "cam_plant", loc, tgt, lens=28.0)
            show(vl, Ceiling=False, Lights=False)
            world(hall, (0.55, 0.62, 0.72), 1.0)          # overcast sky outside
            if not sun:
                ld = bpy.data.lights.new("overview_sun", "SUN")
                ld.energy, ld.angle = 1.6, math.radians(25)
                sun = bpy.data.objects.new("overview_sun", ld)
                sun.rotation_euler = (math.radians(4), math.radians(-3), 0.0)
                hall.collection.objects.link(sun)
            sun.rotation_euler = (math.radians(35), math.radians(20), math.radians(-30))
            sun.data.energy = 3.0
            sun.hide_render = False
        elif shot == "overview":
            x0, y0, x1, y1 = hall["room_box"]
            if "plant_box" in hall:                       # include the plant block outside the wall
                px0, py0, px1, py1 = hall["plant_box"]
                x1, y0, y1 = max(x1, px1), min(y0, py0), max(y1, py1)
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            aspect = q["res"][0] / q["res"][1]
            scale = max(x1 - x0, (y1 - y0) * aspect) * 1.02
            camera(hall, "cam_overview", (cx, cy, 20.0), (cx, cy + 1e-4, 0.0), ortho=scale)
            # floor-plan view: racks, containment, CRAH and floor only (overhead paths and
            # cables would hide the racks from above; shots a-d show them)
            show(vl, Ceiling=False, Lights=False, Overhead=False, Cables=False, Power=False)
            world(hall, (0.55, 0.56, 0.58), 1.0)
            if not sun:
                ld = bpy.data.lights.new("overview_sun", "SUN")
                ld.energy, ld.angle = 1.6, math.radians(25)
                sun = bpy.data.objects.new("overview_sun", ld)
                sun.rotation_euler = (math.radians(4), math.radians(-3), 0.0)
                hall.collection.objects.link(sun)
            sun.hide_render = False
        times[shot] = render(hall, path)
    print("\nTIMES " + ", ".join(f"{k}={v:.0f}s" for k, v in times.items()))


if __name__ == "__main__":
    main()
