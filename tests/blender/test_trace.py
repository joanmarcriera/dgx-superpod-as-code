"""Headless test of the DGX Trace add-on on the built mixed hall.

Run:  blender -b blender/out/superpod-mixed.blend --python tests/blender/test_trace.py
      [-- --out docs/renders/mixed]       (also writes trace-<device>.png Workbench renders)

For six named objects it runs the trace operator (Isolate, follow, all fabrics) and asserts
that the set of objects left visible equals what dgx_links.json implies, computed here
INDEPENDENTLY of trace_core: links of the device -> far ends -> bundles between the racks;
its cords; its rack's unit -> hoses -> loop pipes -> CDUs -> FWS mains -> plant. Then it
clears and asserts nothing is left hidden, dimmed or selected. Exit 1 on any failure.
"""
import json
import os
import sys
from collections import defaultdict

import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "blender", "addon"))
sys.path.insert(0, os.path.join(REPO, "blender"))

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = argv[argv.index("--out") + 1] if "--out" in argv else None

import dgx_trace  # noqa: E402

CASES = ["ibc-su1-leaf-r1", "dgx-su1-n01", "gb-su1-r01-t01", "cdu-dlc-01", "cdu-rdhx-01", "gb-mgmt-r01-rdhx"]
PIPE_KINDS = ("header", "main", "drop")


def props(ob):
    return {k: ob[k] for k in ob.keys() if k.startswith("dgx_")}


def expected(data, allp, name):
    cols = data["links_cols"]
    links = [dict(zip(cols, r)) for r in data["links"]]
    rack_of = data["rack_of"]
    racks = {r["name"]: r for r in data["racks"]}
    cool = data["cooling"]
    unit_loop = {r["cooling"]["unit"]: r["cooling"]["loop"] for r in racks.values() if r.get("cooling")}
    unit_rack = {r["cooling"]["unit"]: r["name"] for r in racks.values() if r.get("cooling")}
    cdu_loop = {c: k for k, lp in cool["loops"].items() for c in lp["cdus"]}
    plant = [u["name"] for u in cool["plant"]["units"]]
    out = {name}
    p = allp[name]

    def loop_set(loop, with_racks):
        s = set()
        for n, q in allp.items():
            k = q.get("dgx_kind")
            if k == "pipe" and q.get("dgx_pipe_kind") in PIPE_KINDS and q.get("dgx_loop") in (loop, "fws") \
                    and not unit_rack.get(q.get("dgx_b", "")) and not q.get("dgx_b", "").startswith("crah-"):
                s.add(n)
            elif k == "cdu" and cdu_loop.get(n) == loop:
                s.add(n)
            elif k == "plant":
                s.add(n)
            elif with_racks and k in ("hose", "pipe") and unit_loop.get(q.get("dgx_b", "")) == loop:
                s.add(n)
            elif with_racks and k == "unit" and unit_loop.get(n) == loop:
                s.add(n)
                s.add(unit_rack[n])
        return s

    def unit_chain(unit):
        s = {unit} | {n for n, q in allp.items() if q.get("dgx_kind") in ("hose", "pipe") and q.get("dgx_b") == unit}
        return s | loop_set(unit_loop[unit], False)

    if p["dgx_kind"] in ("device", "unit"):
        rack = p.get("dgx_rack")
        for row in links:
            if name not in (row["a"], row["b"]):
                continue
            far = row["b"] if row["a"] == name else row["a"]
            if row["fabric"] == "power":
                continue
            out.add(far)
            fr = rack_of.get(far)
            if fr and fr != rack:
                out.add(fr)
                lo, hi = min(rack, fr), max(rack, fr)
                out |= {n for n, q in allp.items() if q.get("dgx_kind") == "bundle" and q.get("dgx_fabric") == row["fabric"]
                        and {q.get("dgx_a"), q.get("dgx_b")} == {lo, hi}}
        out |= {n for n, q in allp.items() if q.get("dgx_kind") in ("power", "cable") and q.get("dgx_a") == name}
        unit = name if p["dgx_kind"] == "unit" else racks[rack]["cooling"]["unit"]
        out |= unit_chain(unit)
    elif p["dgx_kind"] == "cdu":
        out |= {n for n, q in allp.items() if q.get("dgx_kind") == "pipe" and q.get("dgx_b") == name}
        out |= loop_set(cdu_loop[name], True)
    return {n for n in out if n in allp}


def main():
    dgx_trace.register()
    sc = bpy.context.scene
    st = sc.dgx_trace
    st.mode, st.depth, st.auto = "ISOLATE", "FOLLOW", False
    data = json.loads(bpy.data.texts["dgx_links.json"].as_string())
    objs = {ob.name.split(".")[0]: ob for ob in bpy.data.objects if "dgx_kind" in ob.keys()}
    allp = {n: props(ob) for n, ob in objs.items()}
    failures = []
    for name in CASES:
        ob = objs[name]
        bpy.context.view_layer.objects.active = ob
        bpy.ops.dgx.trace()
        got = {n for n, o in objs.items() if not o.hide_get() and o.get("dgx_kind") != "decor"}
        want = expected(data, allp, name)
        extra, missing = got - want, want - got
        counts = defaultdict(int)
        for n in got:
            counts[allp[n]["dgx_kind"]] += 1
        print(f"{name}: {len(got)} objects " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        if extra or missing:
            failures.append(f"{name}: extra {sorted(extra)[:6]} missing {sorted(missing)[:6]}")
        if OUT:
            render_trace(name)
        bpy.ops.dgx.clear()
    # nothing left behind
    left = [n for n, o in objs.items() if o.hide_get() or o.select_get() or tuple(o.color) != (1.0, 1.0, 1.0, 1.0)]
    if left:
        failures.append(f"clear left {len(left)} objects modified: {left[:5]}")
    if bpy.data.collections.get("Trace") and len(bpy.data.collections["Trace"].objects):
        failures.append("Trace collection not emptied")
    # per-port fan-out for the leaf, compute fabric only: 32 down + 32 up = 64 curves
    for f in ("f_storage", "f_inband", "f_oob", "f_nvlink", "f_power", "f_supply", "f_return"):
        setattr(st, f, False)
    bpy.context.view_layer.objects.active = objs["ibc-su1-leaf-r1"]
    bpy.ops.dgx.build_ports()
    n_ports = sum(1 for o in bpy.data.collections["Trace"].objects if o.type == "CURVE")
    print(f"per-port cables for ibc-su1-leaf-r1: {n_ports}")
    if n_ports != 64:
        failures.append(f"per-port fan-out built {n_ports} curves, want 64")
    bpy.ops.dgx.clear()
    if failures:
        print("TRACE TEST FAILED:")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print("trace test: OK")


def render_trace(name):
    """Workbench render in object-colour mode: traced objects keep their colour, the rest
    is dimmed (the add-on's Highlight technique), from a camera framing the traced set."""
    sc = bpy.context.scene
    st = sc.dgx_trace
    st.mode = "ISOLATE"
    bpy.ops.dgx.trace()
    from mathutils import Vector
    pts = []
    for ob in bpy.data.objects:
        if "dgx_kind" in ob.keys() and ob.select_get() and ob.get("dgx_kind") != "plant" and ob.get("dgx_loop") != "fws":
            pts += [ob.matrix_world @ Vector(c) for c in (ob.bound_box if ob.type != "EMPTY" else [(0, 0, 0)])]
            if ob.type == "EMPTY":
                pts.append(ob.matrix_world.translation)
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    centre, size = (lo + hi) / 2, max((hi - lo).length, 4.0)
    cam = bpy.data.objects.get("cam_trace") or bpy.data.objects.new("cam_trace", bpy.data.cameras.new("cam_trace"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    cam.data.lens = 28
    cam.location = centre + Vector((-0.45, -1.0, 0.85)).normalized() * size * 0.75
    cam.rotation_euler = (centre - cam.location).to_track_quat("-Z", "Y").to_euler()
    sc.camera = cam
    sc.render.engine = "BLENDER_WORKBENCH"
    sh = sc.display.shading
    sh.light, sh.color_type, sh.show_object_outline = "STUDIO", "OBJECT", True
    sh.show_xray = False
    sh.show_shadows, sh.show_cavity = False, True
    sc.world = sc.world or bpy.data.worlds.new("World")
    sc.world.color = (0.03, 0.03, 0.035)
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = 1600, 900, 100
    sc.view_settings.view_transform = "Standard"
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = lc.name in ("Ceiling", "Lights")
    sc.render.filepath = os.path.join(OUT, f"trace-{name}.png")
    bpy.ops.render.render(write_still=True)
    print(f"rendered {sc.render.filepath}")


main()
