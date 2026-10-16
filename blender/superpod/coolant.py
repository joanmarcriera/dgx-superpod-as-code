"""Pure-Python coolant geometry for the Blender build (no bpy; tested by
tests/test_blender_layout.py): where every door / manifold / CDU / CRAH / plant module has its
pipe sockets, how a branch drops from the overhead header and hoses to the socket, how the
CDUs and CRAHs hang off the facility-water mains, and a connectivity check over the drawn
pipe network. Everything derives from scene.json["cooling"] (headers, units with origins
and facings) and the device library, so nothing here names a rack.

Pipe network = list of PipeRun(points, kind, fabric, a, b, loop, radius): header runs come
straight from scene.json polylines; branches, hoses and unit drops are built here. A tee is a
branch whose first point lies ON a header segment, so `components()` joins runs that touch.
"""
from __future__ import annotations

import math
from collections import namedtuple

from . import layout as L

PipeRun = namedtuple("PipeRun", "points kind fabric a b loop radius")   # kind: header|main|branch|hose|drop

# Branch geometry (CHOICE; docs/design-choices.md §7.2 "Headers")
VALVE_DROP = 0.35          # isolation valve this far below the header on every branch
HOSE_RISE = 0.22           # the flex hose takes over this far above the socket
DROP_SPLIT = 0.07          # supply / return drops of one rack are this far apart (x)
HEADER_R = {125: 0.0699, 100: 0.0572, 200: 0.1095}   # outer radius incl. 30 mm insulation (DN -> m)
HOSE_R = 0.0165            # 1 in bore hose, ~33 mm OD
DRIP_TRAY = (0.30, 0.18, 0.04)     # W x D x H under each branch valve pair


def rear_unit(rack):
    return next((d for d in rack["devices"] if d.get("mount") in ("rear-door", "rear-manifold")), None)


def unit_sockets(rack, lib):
    """World SUPPLY/RETURN socket points of the rack's door (hose connections on the hinged
    side, top feed) or NVL72 manifolds (FD83 fittings at the top of the rear extension).
    Seen from the rear, 'left' is rack-local +X."""
    u = rear_unit(rack)
    if u is None:
        return {}
    H = L.rack_height(lib, rack)
    hw, hd = rack["width"] / 2, rack["depth"] / 2
    if u["mount"] == "rear-door":
        dd = L.rear_unit_depth(lib, u["type"])
        y = -hd - dd * 0.55
        pts = {"SUPPLY": (hw - 0.08, y, H + 0.02), "RETURN": (hw - 0.17, y, H + 0.02)}
    else:
        # knob centres at x 0.36 (left, return) and 0.64 (right, supply) of the rack width
        pts = {"RETURN": (hw - 0.36 * rack["width"], -hd + 0.07, H + 0.02),
               "SUPPLY": (hw - 0.64 * rack["width"], -hd + 0.07, H + 0.02)}
    return {k: L.rack_to_world(rack, p) for k, p in pts.items()}


def unit_frame(unit):
    """A CDU/CRAH/plant dict has origin + facing like a rack: reuse the rack frame maths."""
    return {"origin": unit["origin"], "facing": unit["facing"]}


def cdu_sockets(cdu):
    """Top connections (spec: 'top or bottom' — top here): primary pair towards the rear,
    secondary pair towards the front, x spread across the lid."""
    h, d = cdu["height"], cdu["depth"]
    loc = {"PRI-S": (-0.26, -d * 0.2, h), "PRI-R": (-0.10, -d * 0.2, h),
           "SEC-S": (0.10, d * 0.2, h), "SEC-R": (0.26, d * 0.2, h)}
    return {k: L.rack_to_world(unit_frame(cdu), p) for k, p in loc.items()}


def crah_sockets(crah):
    h, w = crah["height"], crah["width"]
    loc = {"SUPPLY": (-w * 0.3, 0.0, h), "RETURN": (w * 0.3, 0.0, h)}
    return {k: L.rack_to_world(unit_frame(crah), p) for k, p in loc.items()}


def plant_sockets(unit):
    """Chilled-water connections on the module's wall-facing flank (local +X = world -X for
    a module facing -Y), low level, near its middle."""
    w = unit["width"]
    loc = {"SUPPLY": (w / 2 - 0.3, -0.35, 0.7), "RETURN": (w / 2 - 0.3, 0.35, 0.7)}
    return {k: L.rack_to_world(unit_frame(unit), p) for k, p in loc.items()}


def _on_segment(p, a, b, tol=0.002):
    """True when p lies on segment ab (3D) within tol."""
    ab = L._sub(b, a)
    ap = L._sub(p, a)
    lab = L._len(ab)
    if lab < 1e-9:
        return L._len(ap) <= tol
    t = (ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / (lab * lab)
    if t < -tol / lab or t > 1 + tol / lab:
        return False
    q = L._add(a, L._mul(ab, max(0.0, min(1.0, t))))
    return L._len(L._sub(p, q)) <= tol


def tee_point(header_pts, x, y=None):
    """Point on the header's first (row-long) segment at world x (y given = the branch's
    lateral offset is ignored: the tee sits on the header line)."""
    a, b = header_pts[0], header_pts[1]
    x = max(min(a[0], b[0]), min(max(a[0], b[0]), x))
    return (x, a[1], a[2])


def branch_runs(header, socket, kind, loop, x_split):
    """Header tee -> down past the isolation valve -> hose to the socket (two runs: the rigid
    drop and the flex hose). `x_split` offsets supply/return drops so they do not merge."""
    fabric = f"coolant-{kind}"
    sx, sy, sz = socket
    tee = tee_point(header["polyline"], sx + x_split)
    z_valve = tee[2] - VALVE_DROP
    z_hose = sz + HOSE_RISE
    drop = [tee, (tee[0], tee[1], z_valve), (tee[0], tee[1], z_hose)]
    hose = [(tee[0], tee[1], z_hose), (tee[0], (tee[1] + sy) / 2, z_hose - 0.04),
            (sx, sy, sz + 0.06), (sx, sy, sz)]
    r = HEADER_R.get(header.get("dn", 125), 0.06) * 0.42
    return [PipeRun(drop, "drop", fabric, header["name"], None, loop, r),
            PipeRun(L.fillet(hose, 0.08, samples=5), "hose", fabric, header["name"], None, loop, HOSE_R)]


def unit_drop(main_pts, socket, kind, loop, a, b, radius):
    """Vertical drop from a main (header end or FWS mains) above the socket, then a short
    horizontal to the socket: used for CDU primaries/secondaries, CRAHs and plant modules."""
    sx, sy, sz = socket
    # nearest point of the main's polyline to the socket's (x, y)
    best, bd = None, 1e9
    for p, q in zip(main_pts, main_pts[1:]):
        for t in (i / 20 for i in range(21)):
            c = L._add(p, L._mul(L._sub(q, p), t))
            dd = math.hypot(c[0] - sx, c[1] - sy)
            if dd < bd:
                best, bd = c, dd
    pts = [best, (best[0], best[1], sz + 0.3), (sx, sy, sz + 0.3), (sx, sy, sz)]
    return PipeRun(L.dedupe(pts), "drop", f"coolant-{kind}", a, b, loop, radius)


def all_runs(scene, lib):
    """Every pipe run of the hall: headers and FWS mains from scene.json, plus the branches,
    hoses and drops built here. Returns (runs, sockets) where sockets maps
    (device, port) -> world point for the endpoint check."""
    cs = scene["cooling"]
    rb = L.racks_by_name(scene)
    runs, sockets = [], {}
    hdr_by = {(h["loop"], h["row"], h["kind"]): h for h in cs["headers"]}
    for h in cs["headers"]:
        r = HEADER_R.get(h.get("dn", 125), 0.06)
        runs.append(PipeRun([tuple(p) for p in h["polyline"]], "header", f"coolant-{h['kind']}",
                            h["name"], None, h["loop"], r))
    for m in cs["fws_mains"]:
        runs.append(PipeRun([tuple(p) for p in m["polyline"]], "main", f"coolant-{m['kind']}",
                            m["name"], None, "fws", HEADER_R.get(m.get("dn", 200), 0.1095)))
    for rack in scene["racks"]:
        c = rack.get("cooling")
        if not c:
            continue
        socks = unit_sockets(rack, lib)
        for kind, split in (("supply", -DROP_SPLIT), ("return", DROP_SPLIT)):
            h = hdr_by[(c["loop"], rack["row"], kind)]
            port = "SUPPLY" if kind == "supply" else "RETURN"
            sockets[(c["unit"], port)] = socks[port]
            for run in branch_runs(h, socks[port], kind, c["loop"], split):
                runs.append(run._replace(b=c["unit"]))
    fws = {m["kind"]: m for m in cs["fws_mains"]}
    for cdu in cs["cdus"]:
        socks = cdu_sockets(cdu)
        for port, pt in socks.items():
            sockets[(cdu["name"], port)] = pt
        kind_of = {"PRI-S": "supply", "PRI-R": "return", "SEC-S": "supply", "SEC-R": "return"}
        for port in ("PRI-S", "PRI-R"):
            runs.append(unit_drop(fws[kind_of[port]]["polyline"], socks[port], kind_of[port], "fws",
                                  fws[kind_of[port]]["name"], cdu["name"], 0.045))
        for port in ("SEC-S", "SEC-R"):
            h = next(x for x in cs["headers"] if x["loop"] == cdu["loop"] and x["kind"] == kind_of[port])
            runs.append(unit_drop(h["polyline"][-3:], socks[port], kind_of[port], cdu["loop"],
                                  h["name"], cdu["name"], HEADER_R.get(h.get("dn", 125), 0.06) * 0.8))
    for crah in cs["crahs"]:
        socks = crah_sockets(crah)
        for port, kind in (("SUPPLY", "supply"), ("RETURN", "return")):
            sockets[(crah["name"], port)] = socks[port]
            runs.append(unit_drop(fws[kind]["polyline"], socks[port], kind, "fws", fws[kind]["name"],
                                  crah["name"], 0.045))
    for u in cs["plant"]["units"]:
        socks = plant_sockets(u)
        for port, kind in (("SUPPLY", "supply"), ("RETURN", "return")):
            sockets[(u["name"], port)] = socks[port]
            main = fws[kind]["polyline"]
            # the mains start at the first module; later modules tee off an extension along
            # the module line outside the wall
            ext = [tuple(main[0]), (socks[port][0], main[0][1], main[0][2])]
            runs.append(PipeRun(ext, "main", f"coolant-{kind}", fws[kind]["name"], None, "fws", 0.1095))
            runs.append(unit_drop(ext, socks[port], kind, "fws", fws[kind]["name"], u["name"], 0.08))
    return runs, sockets


def components(runs, tol=0.004):
    """Connected components of the pipe network, per fabric: runs touch when an endpoint of
    one lies on (or within tol of) a segment of the other. Returns {fabric: [set(run idx)]}."""
    out = {}
    for fabric in sorted({r.fabric for r in runs}):
        idx = [i for i, r in enumerate(runs) if r.fabric == fabric]
        parent = {i: i for i in idx}

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        for i in idx:
            for j in idx:
                if j <= i:
                    continue
                ri, rj = runs[i], runs[j]
                touch = any(_on_segment(p, a, b, tol) for p in (ri.points[0], ri.points[-1])
                            for a, b in zip(rj.points, rj.points[1:]))
                touch = touch or any(_on_segment(p, a, b, tol) for p in (rj.points[0], rj.points[-1])
                                     for a, b in zip(ri.points, ri.points[1:]))
                if touch:
                    parent[find(i)] = find(j)
        groups = {}
        for i in idx:
            groups.setdefault(find(i), set()).add(i)
        out[fabric] = list(groups.values())
    return out


def door_clearance_ok(scene, lib):
    """Every ChilledDoor can swing open: the clear aisle behind the door (rear aisle minus the
    doors on both rows) is at least the door width (90-95 deg swing, reference pack cs §1)."""
    errors = []
    rows = {row["name"] for row in scene["hall"]["rows"]}
    door_depth = {}
    for r in scene["racks"]:
        u = rear_unit(r)
        if u and u["mount"] == "rear-door":
            door_depth[r["row"]] = max(door_depth.get(r["row"], 0), L.rear_unit_depth(lib, u["type"]))
    clear = scene["hall"]["hot_aisle"] - sum(door_depth.get(row, 0) for row in rows)
    for r in scene["racks"]:
        u = rear_unit(r)
        if u and u["mount"] == "rear-door" and clear < r["width"]:
            errors.append(f"{r['name']}: {clear:.2f} m behind the door < {r['width']} m swing")
    return errors


def cooling_clashes(scene, lib):
    """AABB clashes between racks (incl. their doors), CDUs, CRAHs, plant modules and the
    overhead headers/mains (tube AABBs). Returns error strings."""
    boxes = []
    for r in scene["racks"]:
        b = L.box_to_world(r, L.rack_envelope(r, lib))
        boxes.append((r["name"], b))
    cs = scene["cooling"]
    for kind in ("cdus", "crahs"):
        for u in cs[kind]:
            fr = unit_frame(u)
            b = L.box_to_world(fr, L.Box(-u["width"] / 2, -u["depth"] / 2, 0.0, u["width"] / 2, u["depth"] / 2, u["height"]))
            boxes.append((u["name"], b))
    for u in cs["plant"]["units"]:
        fr = unit_frame(u)
        b = L.box_to_world(fr, L.Box(-u["width"] / 2, -u["depth"] / 2, 0.0, u["width"] / 2, u["depth"] / 2, u["height"]))
        boxes.append((u["name"], b))
    errors = []
    for i, (na, a) in enumerate(boxes):
        for nb, b in boxes[i + 1:]:
            if L.boxes_overlap(a, b):
                errors.append(f"clash: {na} intersects {nb}")
    runs, _ = all_runs(scene, lib)
    for run in runs:
        if run.kind not in ("header", "main"):
            continue
        for p, q in zip(run.points, run.points[1:]):
            r = run.radius
            seg = L.Box(min(p[0], q[0]) - r, min(p[1], q[1]) - r, min(p[2], q[2]) - r,
                        max(p[0], q[0]) + r, max(p[1], q[1]) + r, max(p[2], q[2]) + r)
            for name, b in boxes:
                if L.boxes_overlap(seg, b):
                    errors.append(f"clash: {run.kind} {run.a} ({run.fabric}) passes through {name}")
                    break
    return errors
