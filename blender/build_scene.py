"""Build a DGX SuperPOD data hall in Blender from a scene.json (H200 pod, or the mixed
H200 + GB300 liquid-cooled pod — docs/dgx-superpod-mixed/scene.json).

Usage (headless, from the repo root):
    blender -b -P blender/build_scene.py -- [--scene docs/scene.json]
        [--library docs/blender/device-library.yaml] [--out blender/out/superpod.blend]
        [--hero dgx-su1-r01,mgmt-r01,stor-r01,stor-r02,gb-su1-r01,gb-mgmt-r01] [--brand]
    blender -b -P blender/build_scene.py -- --scene docs/dgx-superpod-mixed/scene.json \
        --out blender/out/superpod-mixed.blend

Reads the scene (racks, devices, cable bundles, hall) and the device library (envelopes,
colours), models each device type once as an asset collection, instances it everywhere,
draws the hall/overhead/cables, then VERIFIES the result and exits non-zero on any error:
  * instance counts per device type == scene.json (racks too);
  * no device intersects another or pokes outside its rack (checked on the built geometry:
    each asset's chassis bounds x the instance transform);
  * built chassis bounds agree with the layout envelopes (catches asset modelling errors);
  * with a cooling section: CDU / CRAH / plant counts, no clashes between racks (with their
    doors), units and the overhead pipes, every hose ends within 5 mm of its socket, one
    connected pipe network per loop (+ the facility water), door swing clearance.
Every object carries tracing props (dgx_kind, dgx_a, dgx_b, dgx_fabric, dgx_loop, dgx_rack,
dgx_labels) and the links table is stored as the text datablock dgx_links.json.
--brand adds the NVIDIA/DDN wordmarks (trademarks: off by default for published renders).
"""
import argparse
import os
import sys
import time
from collections import Counter

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)

from superpod import coolant as C  # noqa: E402
from superpod import layout as L  # noqa: E402
from superpod.assets import Assets  # noqa: E402
from superpod.hall import Hall  # noqa: E402

ENVELOPE_SUFFIXES = ("_body", "_frame", "_bezel")


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ap = argparse.ArgumentParser(prog="build_scene.py")
    ap.add_argument("--scene", default=os.path.join(REPO, "docs", "scene.json"))
    ap.add_argument("--library", default=os.path.join(REPO, "docs", "blender", "device-library.yaml"))
    ap.add_argument("--out", default=os.path.join(HERE, "out", "superpod.blend"))
    ap.add_argument("--hero", default="dgx-su1-r01,mgmt-r01,stor-r01,stor-r02,gb-su1-r01,gb-mgmt-r01",
                    help="racks whose in-rack cables are drawn individually (unknown names are ignored)")
    ap.add_argument("--brand", action="store_true", help="add vendor wordmarks (trademarks)")
    return ap.parse_args(argv)


def asset_envelope(coll):
    """Local AABB (min, max) of an asset's chassis objects (cables/transceivers excluded)."""
    pts = []
    for ob in coll.all_objects:
        if ob.type == "MESH" and ob.name.split(".")[0].endswith(ENVELOPE_SUFFIXES):
            pts += [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    if not pts:
        raise SystemExit(f"asset {coll.name} has no chassis object to measure")
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def verify(scene, lib):
    errors = []
    want = Counter(d["type"] for r in scene["racks"] for d in r["devices"])
    got = Counter(ob["device_type"] for ob in bpy.data.objects
                  if "device_type" in ob.keys() and ob.get("dgx_kind") not in ("cdu", "crah", "plant"))
    racks = sum(1 for ob in bpy.data.objects if ob.get("role") == "rack")
    print("\n== instance counts (built / scene.json) ==")
    print(f"  {'rack':28s} {racks:4d} / {len(scene['racks'])}")
    for t in sorted(set(want) | set(got)):
        flag = "" if want[t] == got[t] else "   <-- MISMATCH"
        print(f"  {t:28s} {got[t]:4d} / {want[t]}{flag}")
        if want[t] != got[t]:
            errors.append(f"count {t}: built {got[t]} != scene {want[t]}")
    if racks != len(scene["racks"]):
        errors.append(f"racks: built {racks} != scene {len(scene['racks'])}")

    if scene.get("cooling"):
        cs = scene["cooling"]
        kinds = Counter(ob.get("dgx_kind") for ob in bpy.data.objects)
        for key, want_n in (("cdu", len(cs["cdus"])), ("crah", len(cs["crahs"])), ("plant", len(cs["plant"]["units"]))):
            print(f"  {key:28s} {kinds[key]:4d} / {want_n}")
            if kinds[key] != want_n:
                errors.append(f"count {key}: built {kinds[key]} != scene {want_n}")
        hoses = kinds["hose"]
        if hoses != 2 * len(scene["racks"]):
            errors.append(f"hoses: built {hoses} != 2 x {len(scene['racks'])} racks")
    env_cache = {}
    rb = L.racks_by_name(scene)
    per_rack = {}
    for ob in bpy.data.objects:
        if "device_type" not in ob.keys() or ob.get("dgx_kind") in ("cdu", "crah", "plant"):
            continue
        coll = ob.instance_collection
        if coll.name not in env_cache:
            env_cache[coll.name] = asset_envelope(coll)
        lo, hi = env_cache[coll.name]
        corners = [ob.matrix_world @ Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
        wb = L.Box(min(c.x for c in corners), min(c.y for c in corners), min(c.z for c in corners),
                   max(c.x for c in corners), max(c.y for c in corners), max(c.z for c in corners))
        rack = rb[ob["rack"]]
        dev = next(d for d in rack["devices"] if d["name"] == ob.name.split(".")[0])
        expect = L.box_to_world(rack, L.device_box(rack, dev, lib))
        # the NVL72 manifold asset is two thin strips: only its containment is checked
        if dev.get("mount") != "rear-manifold" and max(abs(a - b) for a, b in zip(wb, expect)) > 0.003:
            errors.append(f"{dev['name']}: built chassis {tuple(round(v, 4) for v in wb)} != envelope {tuple(round(v, 4) for v in expect)}")
        per_rack.setdefault(rack["name"], {})[dev["name"]] = wb
    for name, boxes in per_rack.items():
        rack = rb[name]
        yaw = L.rack_yaw(rack)
        if abs(yaw) > 1e-9 and abs(abs(yaw) - 3.141592653589793) > 1e-9:
            raise SystemExit("verify: only racks facing +Y/-Y are supported")
        # world AABB -> rack-local AABB (axis-aligned facings only), so check_rack applies
        local = {}
        for n, b in boxes.items():
            corners = [(x, y, z) for x in (b.x0, b.x1) for y in (b.y0, b.y1) for z in (b.z0, b.z1)]
            ox, oy = rack["origin"][0], rack["origin"][1]
            c, s_ = (1.0, 0.0) if abs(yaw) < 1e-9 else (-1.0, 0.0)
            pts = [(c * (x - ox) + s_ * (y - oy), -s_ * (x - ox) + c * (y - oy), z) for x, y, z in corners]
            local[n] = L.Box(min(p[0] for p in pts), min(p[1] for p in pts), min(p[2] for p in pts),
                             max(p[0] for p in pts), max(p[1] for p in pts), max(p[2] for p in pts))
        errors += L.check_rack(rack, lib, local)
    errors += L.check_scene(scene, lib)
    if scene.get("cooling"):
        errors += C.cooling_clashes(scene, lib)
        errors += C.door_clearance_ok(scene, lib)
        runs, sockets = C.all_runs(scene, lib)
        for run in runs:
            if run.kind == "hose":
                port = "SUPPLY" if run.fabric.endswith("supply") else "RETURN"
                if L._len(L._sub(run.points[-1], sockets[(run.b, port)])) > 0.005:
                    errors.append(f"hose to {run.b} {port} ends off its socket")
        want = set(scene["cooling"]["loops"]) | {"fws"}
        for fabric, groups in C.components(runs).items():
            loops = sorted(next(iter({runs[i].loop for i in g})) for g in groups)
            if loops != sorted(want) or any(len({runs[i].loop for i in g}) != 1 for g in groups):
                errors.append(f"{fabric}: pipe network components {loops} != one per loop + fws")
    return errors


def main():
    args = parse_args()
    t0 = time.time()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system, sc.unit_settings.scale_length = "METRIC", 1.0
    scene, lib = L.load_scene(args.scene), L.load_library(args.library)
    texdir = os.path.join(REPO, "reference", "brand-and-3d", "media", "textures", "polyhaven_concrete_floor_painted")
    assets = Assets(lib, brand=args.brand)
    hall = Hall(scene, lib, assets, hero=[h for h in args.hero.split(",") if h], texdir=texdir)
    stats = hall.build()
    sc["room_box"] = list(hall.room_box)
    if getattr(hall, "plant_box", None):
        sc["plant_box"] = list(hall.plant_box)
    sc["brand"] = bool(args.brand)
    bpy.context.view_layer.update()
    print("\n== build stats ==")
    for k, v in sorted(stats.items()):
        print(f"  {k:20s} {v}")
    print(f"  asset variants      {len(assets.cache)}")
    errors = verify(scene, lib)
    if errors:
        print(f"\nVERIFY FAILED ({len(errors)} errors):", file=sys.stderr)
        for e in errors[:40]:
            print("  " + e, file=sys.stderr)
        sys.exit(1)
    print("\nverify: OK (counts match scene.json; no intersections; every device inside its rack"
          + ("; hoses on their sockets; one pipe network per loop; doors can swing)" if scene.get("cooling") else ")"))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=args.out, compress=True)
    print(f"saved {args.out} in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    try:
        main()
    except SystemExit as e:
        if e.code not in (0, None):
            sys.stdout.flush()
            os._exit(e.code if isinstance(e.code, int) else 1)
        raise
