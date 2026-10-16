"""Pure tracing rules for the DGX Trace add-on (no bpy; tested by tests/test_trace_core.py).

  Index(data)                 indexes dgx_links.json: links per device, rack of device, cooling
                              graph (pipes), loops, racks, library
  trace(idx, name, props, all_props, fabrics, follow) -> set of object base names to show
  per_port_path(idx, link_row, layout) -> world polyline for one link (port tip to port tip)

Objects are identified by their base name (Blender suffixes like ".001" stripped) and by the
dgx_* props build_scene.py wrote on them:
  dgx_kind   rack | device | unit | cable | bundle | power | pipe | hose | cdu | crah | plant | leak | decor
  dgx_a/b    endpoints (devices, racks for bundles, headers/CDUs/plant for pipes)
  dgx_fabric compute | storage | inband | oob | nvlink | power | storage-eth | mgmt |
             coolant-supply | coolant-return
  dgx_loop   rdhx | dlc | fws
  dgx_rack   the rack an object belongs to

Rules (what the brief requires, docs/blender/README.md "Tracing"):
  device  -> its links (filtered by fabric) -> the far-end devices; the bundles between its
             rack and theirs (same fabric); its power cords; hero per-port cables of its own;
             + its rack's door/manifold and (follow) the coolant chain
  switch  -> same rule: a QM9700 leaf gives 32 down + 32 up links, their bundles, far ends
  unit    -> hoses -> (follow) drops -> header -> CDU drops -> CDUs -> FWS mains -> plant
  cdu     -> its drops, loop header(s), every unit + rack on the loop (follow), FWS + plant
  rack    -> its devices' bundles (all fabrics on), its unit and coolant chain
  bundle/cable/power/pipe/hose -> its two ends
"""
from __future__ import annotations

from collections import defaultdict


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


class Index:
    def __init__(self, data: dict):
        self.data = data
        cols = data.get("links_cols") or ["a", "a_port", "b", "b_port", "fabric", "cable", "rail", "label"]
        self.links = [dict(zip(cols, row)) for row in data.get("links", [])]
        self.by_dev: dict[str, list] = defaultdict(list)
        for row in self.links:
            self.by_dev[row["a"]].append(row)
            self.by_dev[row["b"]].append(row)
        self.rack_of = dict(data.get("rack_of", {}))
        self.racks = {r["name"]: r for r in data.get("racks", [])} if isinstance(data.get("racks"), list) \
            else dict(data.get("racks", {}))
        self.library = data.get("library", {})
        self.render = data.get("render", {})
        cool = data.get("cooling") or {}
        self.pipes = cool.get("pipes", [])                   # [a, a_port, b, b_port, fabric]
        self.loops = cool.get("loops", {})
        self.cdus = list(cool.get("cdus", []))
        self.plant_units = [u["name"] for u in (cool.get("plant") or {}).get("units", [])]
        self.fws_header = (cool.get("plant") or {}).get("header", "")
        self.unit_loop: dict[str, str] = {}
        self.rack_unit: dict[str, str] = {}
        self.unit_rack: dict[str, str] = {}
        for name, r in self.racks.items():
            c = r.get("cooling") or {}
            if c.get("unit"):
                self.unit_loop[c["unit"]] = c["loop"]
                self.rack_unit[name] = c["unit"]
                self.unit_rack[c["unit"]] = name
        self.cdu_loop = {c: k for k, lp in self.loops.items() for c in lp.get("cdus", [])}
        self.header_loop = {h: k for k, lp in self.loops.items() for h in lp.get("headers", [])}
        if self.fws_header:
            self.header_loop[self.fws_header] = "fws"
        self.pipe_adj: dict[str, set] = defaultdict(set)
        for a, _ap, b, _bp, _f in self.pipes:
            self.pipe_adj[a].add(b)
            self.pipe_adj[b].add(a)

    def links_of(self, dev: str) -> list:
        return self.by_dev.get(dev, [])

    def colour_for(self, fabric: str, rail=None) -> str:
        fc = (self.render.get("fabric_colours") or {}).get(fabric, {})
        tie = fc.get("tie")
        if tie == "rail":
            if rail:
                return self.render.get("rail_colours", ["#888888"] * 8)[(int(rail) - 1) % 8]
            return fc.get("jacket") or "#888888"             # whole-fabric colour: the jacket
        return tie or fc.get("jacket") or "#888888"


def _match(props: dict, **want) -> bool:
    return all(props.get(k) == v for k, v in want.items())


def _bundles_between(all_props, ra, rb, fabric):
    lo, hi = min(ra, rb), max(ra, rb)
    return {n for n, p in all_props.items() if p.get("dgx_kind") == "bundle" and p.get("dgx_fabric") == fabric
            and {p.get("dgx_a"), p.get("dgx_b")} == {lo, hi}}


def coolant_chain(idx: Index, unit: str, all_props: dict, fabrics: set, follow: bool) -> set:
    """Unit's hoses, then (follow) branch drops, header, CDU drops, CDUs, FWS mains, plant."""
    out = set()
    want_f = {f for f in ("coolant-supply", "coolant-return") if f in fabrics}
    if not want_f:
        return out
    for n, p in all_props.items():
        if p.get("dgx_kind") in ("hose", "pipe") and p.get("dgx_b") == unit and p.get("dgx_fabric") in want_f:
            out.add(n)
    if not follow:
        return out
    loop = idx.unit_loop.get(unit)
    if not loop:
        return out
    out |= loop_chain(idx, loop, all_props, want_f, racks=False)
    return out


def loop_chain(idx: Index, loop: str, all_props: dict, want_f: set, racks: bool) -> set:
    """Every pipe of a technology loop (headers, drops to CDUs), its CDUs, the FWS mains and
    plant; with `racks`, every unit + rack + hose on the loop too."""
    out = set()
    for n, p in all_props.items():
        k = p.get("dgx_kind")
        if k == "pipe" and p.get("dgx_fabric") in want_f and p.get("dgx_loop") in (loop, "fws") \
                and p.get("dgx_pipe_kind") in ("header", "main", "drop") and not idx.unit_rack.get(p.get("dgx_b", "")):
            if p.get("dgx_loop") == "fws" and p.get("dgx_b", "").startswith("crah-"):
                continue
            out.add(n)
        elif k == "cdu" and idx.cdu_loop.get(n) == loop:
            out.add(n)
        elif k == "plant":
            out.add(n)
        elif racks and k in ("hose", "pipe") and p.get("dgx_fabric") in want_f and idx.unit_loop.get(p.get("dgx_b", "")) == loop:
            out.add(n)
        elif racks and k == "unit" and idx.unit_loop.get(n) == loop:
            out.add(n)
            out.add(idx.unit_rack[n])
    return out


def trace(idx: Index, name: str, props: dict, all_props: dict, fabrics: set, follow: bool = True) -> set:
    kind = props.get("dgx_kind")
    out = {name}
    if kind in ("device", "unit"):
        rack = props.get("dgx_rack") or idx.rack_of.get(name)
        for row in idx.links_of(name):
            f = row["fabric"]
            if f not in fabrics:
                continue
            far = row["b"] if row["a"] == name else row["a"]
            if f == "power":
                continue                      # cords are objects: matched below
            out.add(far)
            if follow and rack and idx.rack_of.get(far) and idx.rack_of[far] != rack:
                out |= _bundles_between(all_props, rack, idx.rack_of[far], f)
                out.add(idx.rack_of[far])
        for n, p in all_props.items():
            k = p.get("dgx_kind")
            if k == "power" and "power" in fabrics and p.get("dgx_a") == name:
                out.add(n)
            elif k == "cable" and p.get("dgx_a") == name and p.get("dgx_fabric") in fabrics:
                out.add(n)
        if kind == "unit":
            out |= coolant_chain(idx, name, all_props, fabrics, follow)
        elif rack and idx.rack_unit.get(rack):
            unit = idx.rack_unit[rack]
            chain = coolant_chain(idx, unit, all_props, fabrics, follow)
            if chain:
                out.add(unit)
                out |= chain
    elif kind == "rack":
        for n, p in all_props.items():
            if p.get("dgx_kind") == "bundle" and name in (p.get("dgx_a"), p.get("dgx_b")) and p.get("dgx_fabric") in fabrics:
                out.add(n)
                if follow:
                    out.add(p["dgx_b"] if p["dgx_a"] == name else p["dgx_a"])
        unit = idx.rack_unit.get(name)
        if unit:
            chain = coolant_chain(idx, unit, all_props, fabrics, follow)
            if chain:
                out.add(unit)
                out |= chain
    elif kind == "cdu":
        loop = idx.cdu_loop.get(name)
        want_f = {f for f in ("coolant-supply", "coolant-return") if f in fabrics}
        for n, p in all_props.items():
            if p.get("dgx_kind") == "pipe" and p.get("dgx_fabric") in want_f and p.get("dgx_b") == name:
                out.add(n)
        if follow and loop:
            out |= loop_chain(idx, loop, all_props, want_f, racks=True)
    elif kind in ("crah", "plant"):
        want_f = {f for f in ("coolant-supply", "coolant-return") if f in fabrics}
        for n, p in all_props.items():
            if p.get("dgx_kind") == "pipe" and p.get("dgx_fabric") in want_f and (p.get("dgx_b") == name or (
                    follow and p.get("dgx_loop") == "fws" and p.get("dgx_pipe_kind") == "main")):
                out.add(n)
        if follow:
            out |= set(idx.plant_units)
    elif kind in ("bundle", "cable", "power", "pipe", "hose", "trace"):
        for end in (props.get("dgx_a"), props.get("dgx_b")):
            if end and end in all_props:
                out.add(end)
    return {n for n in out if n in all_props}


def per_port_path(idx: Index, row: dict, L):
    """World polyline for one link: a's port tip -> rack roof -> row tray (-> crossover) ->
    far rack roof -> b's port tip, using layout.py's port maps and bundle routing. None when an
    end has no port map (e.g. the DC-core demarc)."""
    scene = {"racks": list(idx.racks.values()), "hall": idx.data.get("hall", {})}
    lib = idx.library
    rb = {r["name"]: r for r in scene["racks"]}

    def tip(dev, port):
        rack_name = idx.rack_of.get(dev)
        if not rack_name:
            return None
        rack = rb[rack_name]
        d = next((x for x in rack["devices"] if x["name"] == dev), None)
        if d is None:
            return None
        ports = L.device_ports(d, lib)
        if not ports:
            return None
        # the i-th port of this fabric in the link order of the device (render CHOICE)
        same = [p for p in ports if p.fabric == row["fabric"] or (row["fabric"] == "storage-eth" and p.fabric in ("storage-eth", "inband"))]
        if not same:
            same = ports
        rows = [r for r in idx.links_of(dev) if r["fabric"] == row["fabric"]]
        i = next((k for k, r in enumerate(rows) if r["label"] == row["label"]), 0) % len(same)
        p = same[i]
        if d.get("mount") == "rear-door":
            local = (p.x, -rack["depth"] / 2 + p.y, p.z)
        else:
            local = (p.x, L.rail_y(rack) + p.y, d["z_bottom"] + p.z)
        return L.rack_to_world(rack, local), rack

    ta, tb = tip(row["a"], row["a_port"]), tip(row["b"], row["b_port"])
    if ta is None or tb is None:
        return None
    (pa, ra), (pb, rbk) = ta, tb
    H = L.rack_height(lib)
    if ra["name"] == rbk["name"]:
        return L.fillet([pa, (pa[0], pa[1], pa[2] + 0.05), (pb[0], pb[1], pb[2] + 0.05), pb], 0.03, samples=4)
    bundle = {"a": ra["name"], "b": rbk["name"], "fabric": row["fabric"], "count": 1}
    path = L.bundle_path(bundle, scene, lib)
    return L.fillet([pa, (pa[0], pa[1], H - 0.02)] + list(path[1:-1]) + [(pb[0], pb[1], H - 0.02), pb], 0.08, samples=5)
