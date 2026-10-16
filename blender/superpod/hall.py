"""The data hall: racks and device instances placed from scene.json, overhead power and
cable paths, hot-aisle containment, CRAH fan walls, lighting and every cable.

All positions derive from scene.json (via layout.py). Collections created here (render.py
toggles some of them per shot):
  Racks, Devices, Blanks, Cables, Power, Overhead, Containment, Room, Ceiling, Lights
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict

import json

from . import blutil
from . import coolant as C
from . import layout as L
from .blutil import CurveBatch, MeshBuilder

CEILING_Z = 4.0
DAC_JACKET = "#111111"          # passive DAC is copper: black jacket regardless of fabric


def jacket_for(scene, fabric, types=None):
    if types and all(t.startswith("dac") for t in types):
        return DAC_JACKET
    if fabric == "storage-eth":
        return DAC_JACKET
    return scene["render"]["fabric_colours"].get(fabric, {}).get("jacket", "#00A7B5")


def tie_colours(scene, fabric, rails=None):
    fc = scene["render"]["fabric_colours"].get(fabric, {})
    if fc.get("tie") == "rail":
        rc = scene["render"]["rail_colours"]
        keys = sorted(rails, key=int) if rails else range(1, len(rc) + 1)
        return [rc[int(k) - 1] for k in keys]
    return [fc.get("tie", "#888888")]


class Hall:
    def __init__(self, scene, lib, assets, hero=(), texdir=None):
        self.s, self.lib, self.assets, self.hero, self.texdir = scene, lib, assets, set(hero), texdir
        self.H = L.rack_height(lib)
        self.c = {n: blutil.collection(n) for n in
                  ("Racks", "Devices", "Blanks", "Cables", "Power", "Overhead", "Containment", "Room", "Ceiling", "Lights",
                   "Cooling", "Plant")}
        self.stats = Counter()
        self.cool = scene.get("cooling")
        self.contained = scene["hall"].get("containment", "hot-aisle") != "none"
        self.rack_of = {d["name"]: r["name"] for r in scene["racks"] for d in r["devices"]}
        self.loop_of = {r["name"]: r.get("cooling", {}).get("loop", "") for r in scene["racks"]}
        # cable labels per (rack a, rack b, fabric), from the links table (for bundle props)
        cols = scene.get("links_cols", [])
        self.pair_labels = defaultdict(list)
        self.power_feed_of = {}                     # device -> feed letter (NVL72 shelves)
        if cols:
            ia, ib, ifab, ilab = cols.index("a"), cols.index("b"), cols.index("fabric"), cols.index("label")
            for row in scene["links"]:
                if row[ifab] == "power":
                    if row[ib].startswith("PP-"):
                        self.power_feed_of[row[ia]] = row[ib][3:]
                    continue
                ra, rb = self.rack_of.get(row[ia]), self.rack_of.get(row[ib])
                if ra and rb and ra != rb:
                    self.pair_labels[(min(ra, rb), max(ra, rb), row[ifab])].append(row[ilab])
        for r in scene["racks"]:
            f = r["facing"]
            if abs(f[0]) + abs(f[1]) != 1 or f[2] != 0:
                raise SystemExit(f"{r['name']}: only axis-aligned rack facings are supported, got {f}")

    # ------------------------------------------------------------ helpers -------------------
    def w(self, rack, p):
        return L.rack_to_world(rack, p)

    def wbox(self, mb, rack, a, b, mat):
        """Axis-aligned rack-local box -> world (valid for axis-aligned facings)."""
        pa, pb = self.w(rack, a), self.w(rack, b)
        mb.box(pa[0], pa[1], pa[2], pb[0], pb[1], pb[2], mat)

    def row_y(self, row_name, y_local):
        r0 = L.row_racks(self.s, row_name)[0]
        return self.w(r0, (0.0, y_local, 0.0))[1]

    # ------------------------------------------------------------ build ---------------------
    def build(self):
        self.racks_and_devices()
        self.in_rack_cables()
        self.power()
        self.overhead()
        self.bundles()
        if self.contained:
            self.containment()
        self.room()
        if self.cool:
            self.cooling()
        self.lights()
        self.links_datablock()
        return self.stats

    def racks_and_devices(self):
        blank = self.assets.blank()
        for r in self.s["racks"]:
            yaw = L.rack_yaw(r)
            kind = L.rack_kind(r)
            cool = r.get("cooling", {})
            blutil.instance(r["name"], self.assets.rack(kind), r["origin"], yaw, self.c["Racks"],
                            {"rack": r["name"], "role": "rack", "dgx_kind": "rack", "dgx_rack": r["name"],
                             "dgx_loop": cool.get("loop", ""), "dgx_kw": float(r.get("peak_kw", 0)),
                             "rack_kind": kind})
            self.stats["rack"] += 1
            self.stats[f"rack_{kind}"] += 1
            ry = L.rail_y(r)
            for d in r["devices"]:
                coll = self.assets.for_device(r, d)
                if d.get("mount") == "rear-0U":
                    p = L.pdu_place(r, d, self.lib)
                    loc = self.w(r, (p.x, p.y, p.z0))
                elif d.get("mount") in ("rear-door", "rear-manifold"):
                    loc = self.w(r, (0.0, -r["depth"] / 2, 0.0))
                    self.stats[d["mount"]] += 1
                else:
                    loc = self.w(r, (0.0, ry, d["z_bottom"]))
                props = {"device_type": d["type"], "rack": r["name"], "asset": coll.name,
                         "dgx_kind": "device", "dgx_rack": r["name"], "dgx_role": d.get("role", ""),
                         "dgx_type": d["type"], "dgx_loop": cool.get("loop", "")}
                if d["name"] == cool.get("unit"):
                    props.update(dgx_kind="unit", dgx_kw=float(cool.get("kw", 0)))
                blutil.instance(d["name"], coll, loc, yaw, self.c["Devices"], props)
            self.roof_label(r)
            for u in L.empty_units(r):
                blutil.instance(f"{r['name']}-blank-U{u}", blank, self.w(r, (0.0, ry, L.u_bottom(self.lib, u))), yaw, self.c["Blanks"])
                self.stats["blank"] += 1

    def roof_label(self, r):
        """Rack name painted on the roof (reads in the top-down overview, like the draw.io plan)."""
        import bpy
        cu = bpy.data.curves.new(f"label_{r['name']}", "FONT")
        cu.body, cu.size, cu.align_x, cu.align_y = r["name"], 0.078, "CENTER", "CENTER"
        cu.materials.append(blutil.material("logo_white"))
        ob = bpy.data.objects.new(f"label_{r['name']}", cu)
        ob.location = self.w(r, (0.0, -0.32, self.H + 0.0015))
        ob.rotation_euler = (0.0, 0.0, 0.0)
        self.c["Racks"].objects.link(ob)

    # ------------------------------------------------------------ cables in racks ----------
    def in_rack_cables(self):
        """Hero racks: every cable individually from its port to the rack-roof exit.
        Other racks: short tails from each port into the vertical cable lane, plus one lane
        bundle per lane up to the roof exit (so nothing floats)."""
        fibres = CurveBatch("cables_in_rack", resolution=1)
        lanes = CurveBatch("cable_lanes", resolution=3)
        ties = MeshBuilder()
        H, ztop = self.H, self.H - 0.075
        for r in self.s["racks"]:
            hero = r["name"] in self.hero
            ry = L.rail_y(r)
            groups = defaultdict(list)        # lane key -> [(tip, lane xy, fabric, kind, tie)]
            for d in r["devices"]:
                if d.get("mount") == "rear-0U":
                    continue
                for i, p in enumerate(L.device_ports(d, self.lib)):
                    if p.fabric == "power":
                        continue
                    tip = (p.x, ry + p.y, d["z_bottom"] + p.z)
                    h = L.stable_int(d["name"], i)
                    if p.face == "front":
                        side = 1 if p.x > 0 else -1
                        lx = side * (L.LANE_FRONT_X + ((h % 7) - 3) * 0.0035)
                        ly = ry + 0.088 + ((h >> 3) % 5 - 2) * 0.0025
                        key = ("front", side)
                    else:
                        lx = L.LANE_REAR_X + ((h % 9) - 4) * 0.0045
                        ly = L.LANE_REAR_Y + ((h >> 3) % 5 - 2) * 0.0022
                        key = ("rear", 1)
                    groups[key].append((tip, (lx, ly), p, h, d["z_bottom"], d["name"]))
            for (face, side), items in groups.items():
                d = 1 if face == "front" else -1
                for tip, (lx, ly), p, h, zfloor, dname in items:
                    n = 2 if p.kind.startswith("osfp") else 1
                    rad = L.FIBRE_R if p.kind.startswith("osfp") else (0.0028 if p.fabric == "storage-eth" else 0.0023)
                    jacket = blutil.jacket_material(jacket_for(self.s, p.fabric))
                    tie = (self.s["render"]["rail_colours"][p.tie - 1] if (p.fabric == "compute" and p.tie)
                           else tie_colours(self.s, p.fabric)[0])
                    ex = -0.20 + L.FABRIC_ORDER.index(p.fabric) * 0.075 + ((h >> 6) % 5 - 2) * 0.006
                    droop = 0.006 + (h % 4) * 0.0025      # dressed cables: short lead-out, slight droop
                    for k in range(n):
                        off = (k - 0.5) * 0.0048 if n == 2 else 0.0
                        s0 = (tip[0] + off, tip[1], tip[2])
                        toward = math.copysign(0.03, lx - s0[0])
                        # keep each device's cables within its own U so the unit below stays visible
                        zrun = max(tip[2] - droop, zfloor + 0.003)
                        pts = [s0, (s0[0], tip[1] + d * 0.012, tip[2] - 0.002),
                               (s0[0] + toward, ly, zrun), (lx + off * 0.4, ly, max(zrun - 0.004, zfloor + 0.002))]
                        if hero:
                            pts += [(lx + off * 0.4, ly, ztop - 0.02 * ((h >> 9) % 3)),
                                    (ex + off, L.EXIT_Y, ztop + 0.03), (ex + off, L.EXIT_Y, H + 0.004)]
                        wp = [self.w(r, q) for q in pts]
                        if hero:
                            blutil.curve(f"cable_{dname}_{i}_{k}", L.fillet(wp, 0.035, samples=4), rad, jacket,
                                         self.c["Cables"], {"dgx_kind": "cable", "dgx_a": dname, "dgx_b": "",
                                                            "dgx_fabric": p.fabric, "dgx_rack": r["name"]}, resolution=1)
                        else:
                            fibres.add(L.fillet(wp, 0.035, samples=4), rad, jacket)
                        self.stats["cable_individual" if hero else "cable_tail"] += 1
                    if hero:   # label/tie band 60 mm behind the connector, in the tie colour
                        c = self.w(r, (tip[0], tip[1] + d * 0.008, tip[2] - 0.001))
                        ties.ring(c, (0, d, 0) if r["facing"][1] > 0 else (0, -d, 0), 0.0068 if n == 2 else 0.0045,
                                  0.010, blutil.tie_material(tie), seg=12)
                if not hero:
                    zs = [it[0][2] for it in items]
                    lx = sum(it[1][0] for it in items) / len(items)
                    ly = sum(it[1][1] for it in items) / len(items)
                    fab = Counter(it[2].fabric for it in items).most_common(1)[0][0]
                    rad = L.bundle_radius(len(items)) * 0.5   # dressed lane bundle (tightly packed)
                    pts = [(lx, ly, min(zs) - 0.06), (lx, ly, ztop), (-0.05, L.EXIT_Y, ztop + 0.03), (-0.05, L.EXIT_Y, H + 0.004)]
                    lp = L.fillet([self.w(r, q) for q in pts], 0.08)
                    lanes.add(lp, rad, blutil.bundle_material(jacket_for(self.s, fab)))
                    tie = tie_colours(self.s, fab)[0]
                    for pos, tan in L.sample_along(lp, L.TIE_PITCH, 0.1):
                        ties.ring(pos, tan, rad * 1.06 + 0.0007, 0.0042, blutil.tie_material(tie), seg=12)
                    self.stats["lane_bundle"] += 1
        for ob in (fibres.build(self.c["Cables"]), lanes.build(self.c["Cables"]), ties.build("cable_labels", self.c["Cables"])):
            if ob is not None:
                ob["dgx_kind"] = "decor"

    # ------------------------------------------------------------ power ---------------------
    def power(self):
        """PSU cords (A red / B blue / C green) to the rear 0U PDUs, PDU inlet cords up to
        Starline tap-off boxes on the busway of the same feed."""
        mb = MeshBuilder()
        H = self.H
        feed_col = self.s["render"]["power_feed_colours"]
        for r in self.s["racks"]:
            ry = L.rail_y(r)
            pdus = [d for d in r["devices"] if d.get("mount") == "rear-0U"]
            if not pdus:
                self.busbar_whips(r, mb)
                continue
            places = {d["name"]: L.pdu_place(r, d, self.lib) for d in pdus}
            edge = {}
            for side in (-1, 1):
                ps = [places[d["name"]] for d in pdus if d["side"] == side]
                if ps:
                    edge[side] = (max(p.x + p.width / 2 for p in ps) + 0.014) if side < 0 else (min(p.x - p.width / 2 for p in ps) - 0.014)
            used = defaultdict(set)
            for dev in r["devices"]:
                if dev.get("mount") == "rear-0U":
                    continue
                for k, (port, pdu) in enumerate(L.power_assignments(r, dev, self.lib)):
                    pp = places[pdu["name"]]
                    feed = L.feed_letter(pdu)
                    col = blutil.jacket_material(feed_col.get(feed, "#333333"))
                    if dev.get("mount") == "rear-door":      # the door's C14 is in the door frame (rack rear face)
                        tip = (port.x, -r["depth"] / 2 + port.y, port.z)
                    else:
                        tip = (port.x, ry + port.y, dev["z_bottom"] + port.z)
                    xe = edge[pdu["side"]] + ((k % 3) - 1) * 0.005
                    y_face = pp.y - pp.depth / 2
                    # outlet: nearest free C19 on the column facing the routing edge
                    colx = pp.x + math.copysign(0.024, xe - pp.x)
                    outlets = [pp.z0 + 0.14 + g * 0.50 + j * 0.045 for g in range(3) for j in range(8)]
                    free = [z for z in outlets if (colx, round(z, 3)) not in used[pdu["name"]]]
                    zc = min(free, key=lambda z: abs(z - (tip[2] - 0.03)))
                    used[pdu["name"]].add((colx, round(zc, 3)))
                    yb = y_face - 0.034
                    yl = L.LANE_REAR_Y - 0.004              # just behind the transceivers
                    if dev.get("mount") == "rear-door":      # door fan cord: outside the rear face, round to the PDU
                        pts = [tip, (tip[0], tip[1] - 0.03, tip[2]), (xe, -r["depth"] / 2 - 0.02, tip[2]),
                               (xe, yb, (tip[2] + zc) / 2), (colx, yb, zc), (colx, y_face - 0.026, zc)]
                    else:
                        pts = [tip, (tip[0], yl, tip[2] - 0.02), (xe, yl, tip[2] - 0.035),
                               (xe, yb, (tip[2] + zc) / 2), (colx, yb, zc), (colx, y_face - 0.026, zc)]
                    blutil.curve(f"cord_{dev['name']}_{k}", L.fillet([self.w(r, q) for q in pts], 0.03, samples=4), 0.0045, col,
                                 self.c["Power"], {"dgx_kind": "power", "dgx_a": dev["name"], "dgx_b": pdu["name"],
                                                   "dgx_fabric": "power", "dgx_rack": r["name"], "dgx_feed": feed})
                    self.wbox(mb, r, (colx - 0.0095, y_face - 0.027, zc - 0.012), (colx + 0.0095, y_face - 0.002, zc + 0.012), "plug_black")
                    self.stats["power_cord"] += 1
            for d in pdus:                                   # PDU inlet -> busway tap-off
                pp, feed = places[d["name"]], L.feed_letter(d)
                by = L.BUSWAY_Y.get(feed, -0.3)
                zt = L.BUSWAY_Z - L.BUSWAY_SECTION[1] / 2
                tap_bottom = zt - 0.17
                pts = [(pp.x, pp.y, pp.z0 + pp.length + 0.04), (pp.x, pp.y, H - 0.03), (pp.x, pp.y, H + 0.03),
                       (pp.x, by, H + 0.07), (pp.x, by, tap_bottom)]
                blutil.curve(f"inlet_{d['name']}", L.fillet([self.w(r, q) for q in pts], 0.06), 0.008,
                             blutil.jacket_material(feed_col.get(feed, "#333333")), self.c["Power"],
                             {"dgx_kind": "power", "dgx_a": d["name"], "dgx_b": f"PP-{feed}", "dgx_fabric": "power",
                              "dgx_rack": r["name"], "dgx_feed": feed})
                self.wbox(mb, r, (pp.x - 0.07, by - 0.05, tap_bottom), (pp.x + 0.07, by + 0.05, zt), "fixture")
                self.wbox(mb, r, (pp.x - 0.07, by - 0.051, tap_bottom + 0.11), (pp.x + 0.07, by + 0.051, tap_bottom + 0.135),
                          blutil.tie_material(feed_col.get(feed, "#333333")))
                self.wbox(mb, r, (pp.x - 0.012, by - 0.058, tap_bottom + 0.04), (pp.x + 0.012, by + 0.058, tap_bottom + 0.08), "plug_black")
                self.wbox(mb, r, (pp.x - 0.015, pp.y - 0.015, H - 0.001), (pp.x + 0.015, pp.y + 0.015, H + 0.004), "brush")
        ob = mb.build("plugs_and_tapoffs", self.c["Power"])
        if ob is not None:
            ob["dgx_kind"] = "decor"

    def busbar_whips(self, r, mb):
        """NVL72 rack: each power shelf's AC whip rises from its rear connector to a Starline
        tap-off on the busway of its feed (A: shelves 1-4, B: 5-8 per the design links)."""
        H = self.H
        feed_col = self.s["render"]["power_feed_colours"]
        ry = L.rail_y(r)
        n = 0
        for dev in r["devices"]:
            whip = next((p for p in L.device_ports(dev, self.lib) if p.kind == "whip"), None)
            if whip is None:
                continue
            feed = self.power_feed_of.get(dev["name"], "A")
            by = L.BUSWAY_Y.get(feed, -0.3)
            zt = L.BUSWAY_Z - L.BUSWAY_SECTION[1] / 2
            tap_bottom = zt - 0.17
            xw = -0.2 + 0.05 * (n % 8)
            tip = (whip.x, ry + whip.y, dev["z_bottom"] + whip.z)
            pts = [tip, (tip[0], tip[1] - 0.05, tip[2]), (xw, L.LANE_REAR_Y - 0.03, tip[2]),
                   (xw, L.LANE_REAR_Y - 0.03, H - 0.03), (xw, L.LANE_REAR_Y - 0.03, H + 0.03), (xw, by, H + 0.07), (xw, by, tap_bottom)]
            blutil.curve(f"whip_{dev['name']}", L.fillet([self.w(r, q) for q in pts], 0.05), 0.011,
                         blutil.jacket_material(feed_col.get(feed, "#333333")), self.c["Power"],
                         {"dgx_kind": "power", "dgx_a": dev["name"], "dgx_b": f"PP-{feed}", "dgx_fabric": "power",
                          "dgx_rack": r["name"], "dgx_feed": feed})
            self.wbox(mb, r, (xw - 0.07, by - 0.05, tap_bottom), (xw + 0.07, by + 0.05, zt), "fixture")
            self.wbox(mb, r, (xw - 0.07, by - 0.051, tap_bottom + 0.11), (xw + 0.07, by + 0.051, tap_bottom + 0.135),
                      blutil.tie_material(feed_col.get(feed, "#333333")))
            self.stats["busbar_whip"] += 1
            n += 1

    # ------------------------------------------------------------ overhead ------------------
    def overhead(self):
        mb, rods = MeshBuilder(), MeshBuilder()
        rows = [row["name"] for row in self.s["hall"]["rows"]]
        hx0, hy0, hx1, hy1 = L.hall_extent(self.s, self.lib)
        x0, x1 = hx0 - 0.3, hx1 + 0.3
        cx = L.crossover_x(self.s)
        ha = L.hot_aisle(self.s, self.lib)
        hot_mid = (ha[1] + ha[3]) / 2
        rw = L.RACEWAY_W / 2
        ry = {row: self.row_y(row, L.RACEWAY_Y) for row in rows}
        ly = {row: self.row_y(row, L.LADDER_Y) for row in rows}
        for row in rows:
            for feed, byl in L.BUSWAY_Y.items():             # Starline T5 busways
                y = self.row_y(row, byl)
                bw, bh = L.BUSWAY_SECTION[0] / 2, L.BUSWAY_SECTION[1] / 2
                mb.box(x0, y - bw, L.BUSWAY_Z - bh, x1, y + bw, L.BUSWAY_Z + bh, "busway")
                mb.box(x0, y - 0.012, L.BUSWAY_Z - bh - 0.001, x1, y + 0.012, L.BUSWAY_Z - bh + 0.002, "plug_black")
                mb.box(x1, y - 0.12, L.BUSWAY_Z - 0.2, x1 + 0.35, y + 0.12, L.BUSWAY_Z + 0.15, "fixture")    # end feed
                rods.cyl((x1 + 0.175, y, (L.BUSWAY_Z + 0.15 + CEILING_Z) / 2), (0, 0, 1), 0.03, CEILING_Z - L.BUSWAY_Z - 0.15, "rod", seg=12)
                mb.box(x1 + 0.05, y - 0.121, L.BUSWAY_Z - 0.05, x1 + 0.3, y + 0.121, L.BUSWAY_Z - 0.02,
                       blutil.tie_material(self.s["render"]["power_feed_colours"].get(feed, "#333333")))
            # yellow fibre raceway (U channel); the hot-aisle-side wall opens at the crossover
            y = ry[row]
            mb.box(x0, y - rw, L.RACEWAY_Z, x1, y + rw, L.RACEWAY_Z + 0.006, "raceway")
            for s in (-1, 1):
                wy0, wy1 = y + s * (rw - 0.005), y + s * rw
                hot_side = abs(y + s * rw - hot_mid) < abs(y - s * rw - hot_mid)
                spans = [(x0, cx - rw), (cx + rw, x1)] if hot_side else [(x0, x1)]
                for a, b in spans:
                    mb.box(a, wy0, L.RACEWAY_Z, b, wy1, L.RACEWAY_Z + L.RACEWAY_H, "raceway")
            # black ladder rack for copper
            y = ly[row]
            for s in (-1, 1):
                mb.box(x0, y + s * (L.LADDER_W / 2 - 0.006), L.LADDER_Z, x1, y + s * L.LADDER_W / 2, L.LADDER_Z + 0.07, "ladder")
            xx = x0 + 0.1
            while xx < x1:
                mb.box(xx - 0.011, y - L.LADDER_W / 2, L.LADDER_Z, xx + 0.011, y + L.LADDER_W / 2, L.LADDER_Z + 0.012, "ladder")
                xx += 0.3
            # hangers: threaded rods every 1.5 m for each overhead element
            xx = x0 + 0.4
            while xx < x1:
                for yy, ztop in ([(self.row_y(row, b), L.BUSWAY_Z + 0.064) for b in L.BUSWAY_Y.values()]
                                 + [(ry[row] - rw - 0.02, L.RACEWAY_Z), (ry[row] + rw + 0.02, L.RACEWAY_Z),
                                    (ly[row] - L.LADDER_W / 2 - 0.02, L.LADDER_Z), (ly[row] + L.LADDER_W / 2 + 0.02, L.LADDER_Z)]):
                    rods.cyl((xx, yy, (ztop + CEILING_Z) / 2), (0, 0, 1), 0.005, CEILING_Z - ztop, "rod", seg=8)
                for yy0, yy1, z in ((ry[row] - rw - 0.03, ry[row] + rw + 0.03, L.RACEWAY_Z - 0.03),
                                    (ly[row] - L.LADDER_W / 2 - 0.03, ly[row] + L.LADDER_W / 2 + 0.03, L.LADDER_Z - 0.03)):
                    rods.box(xx - 0.02, yy0, z, xx + 0.02, yy1, z + 0.03, "rod")        # trapeze strut
                xx += 1.5
        # crossovers over the hot aisle (fibre raceway and ladder)
        ya, yb = sorted((ry[rows[0]], ry[rows[1]]))
        mb.box(cx - rw, ya + rw, L.RACEWAY_Z, cx + rw, yb - rw, L.RACEWAY_Z + 0.006, "raceway")
        for s in (-1, 1):
            mb.box(cx + s * (rw - 0.005), ya + rw, L.RACEWAY_Z, cx + s * rw, yb - rw, L.RACEWAY_Z + L.RACEWAY_H, "raceway")
        lx = cx + L.LADDER_CROSS_DX
        ya, yb = sorted((ly[rows[0]], ly[rows[1]]))
        for s in (-1, 1):
            mb.box(lx + s * (L.LADDER_W / 2 - 0.006), ya, L.LADDER_Z, lx + s * L.LADDER_W / 2, yb, L.LADDER_Z + 0.07, "ladder")
        yy = ya + 0.2
        while yy < yb:
            mb.box(lx - L.LADDER_W / 2, yy - 0.011, L.LADDER_Z, lx + L.LADDER_W / 2, yy + 0.011, L.LADDER_Z + 0.012, "ladder")
            yy += 0.3
        mb.build("overhead", self.c["Overhead"], bevel=0.0015)
        rods.build("hangers", self.c["Overhead"])

    # ------------------------------------------------------------ bundles -------------------
    def bundles(self):
        """Every inter-rack cable_bundle as one swept tube in its jacket colour, tie bands every
        ~300 mm (compute: one band per rail colour carried by the bundle)."""
        ties = MeshBuilder()
        for i, b in enumerate(self.s["cable_bundles"]):
            path = L.bundle_path(b, self.s, self.lib, i)
            if path is None:
                self.stats["bundle_in_rack"] += 1
                continue
            pts = L.fillet(path, 0.10, samples=6)
            r = L.bundle_radius(b["count"])
            labels = self.pair_labels.get((min(b["a"], b["b"]), max(b["a"], b["b"]), b["fabric"]), [])
            blutil.curve(f"bundle_{b['a']}_{b['b']}_{b['fabric']}", pts, r,
                         blutil.bundle_material(jacket_for(self.s, b["fabric"], b.get("types"))), self.c["Cables"],
                         {"dgx_kind": "bundle", "dgx_a": b["a"], "dgx_b": b["b"], "dgx_fabric": b["fabric"],
                          "dgx_count": int(b["count"]), "dgx_labels": labels}, resolution=4)
            cols = tie_colours(self.s, b["fabric"], b.get("rails"))
            n = len(cols)
            for pos, tan in L.sample_along(pts, L.TIE_PITCH, 0.12):
                for k, c in enumerate(cols):
                    o = (k - (n - 1) / 2) * 0.0068
                    ties.ring((pos[0] + tan[0] * o, pos[1] + tan[1] * o, pos[2] + tan[2] * o), tan,
                              r * 1.06 + 0.0007, 0.0042, blutil.tie_material(c), seg=12)
                    self.stats["tie_band"] += 1
            self.stats["bundle"] += 1
        ob = ties.build("tie_bands", self.c["Cables"])
        if ob is not None:
            ob["dgx_kind"] = "decor"

    # ------------------------------------------------------------ containment ---------------
    def containment(self):
        """Hot-aisle containment: acrylic roof on a black frame at rack-top height, sliding
        double doors at both ends."""
        x0, y0, x1, y1 = L.hot_aisle(self.s, self.lib)
        H = self.H
        glass, frame = MeshBuilder(), MeshBuilder()
        z0 = H + 0.004
        n = max(1, round((x1 - x0) / 1.2))
        for i in range(n):
            a, b = x0 + (x1 - x0) * i / n, x0 + (x1 - x0) * (i + 1) / n
            glass.box(a + 0.015, y0, z0 + 0.004, b - 0.015, y1, z0 + 0.010, "acrylic")
            frame.box(a - 0.015, y0, z0, a + 0.015, y1, z0 + 0.03, "rack_black")
        frame.box(x1 - 0.015, y0, z0, x1 + 0.015, y1, z0 + 0.03, "rack_black")
        for yy in (y0, y1 - 0.03):
            frame.box(x0, yy, z0, x1, yy + 0.03, z0 + 0.03, "rack_black")
        for xd, s in ((x0, -1), (x1, 1)):                    # end doors (two sliding leaves)
            xa, xb = xd + s * 0.005, xd + s * 0.035
            mid = (y0 + y1) / 2
            for ya, yb in ((y0, mid + 0.02), (mid - 0.02, y1)):
                off = 0.0 if ya == y0 else s * 0.03
                fx0, fx1 = xa + off, xb + off
                frame.box(fx0, ya, 0.0, fx1, yb, 0.05, "rack_black")
                frame.box(fx0, ya, H - 0.05, fx1, yb, H, "rack_black")
                frame.box(fx0, ya, 0.0, fx1, ya + 0.04, H, "rack_black")
                frame.box(fx0, yb - 0.04, 0.0, fx1, yb, H, "rack_black")
                glass.box(fx0 + s * 0.008, ya + 0.04, 0.05, fx1 - s * 0.008, yb - 0.04, H - 0.05, "acrylic")
                hy = yb - 0.08 if ya == y0 else ya + 0.08
                frame.box(fx1, hy - 0.012, 0.9, fx1 + s * 0.025, hy + 0.012, 1.3, "steel")
            frame.box(xa, y0 - 0.02, H, xb + s * 0.03, y1 + 0.02, H + 0.035, "rack_black")      # header
        glass.build("containment_panels", self.c["Containment"])
        frame.build("containment_frame", self.c["Containment"], bevel=0.002)

    # ------------------------------------------------------------ room ----------------------
    def room(self):
        hx0, hy0, hx1, hy1 = L.hall_extent(self.s, self.lib)
        rows = [row["name"] for row in self.s["hall"]["rows"]]
        colds = [L.cold_aisle(self.s, self.lib, row) for row in rows]
        cy0 = min(c[1] for c in colds) - 1.8     # walkway beyond each cold aisle
        cy1 = max(c[3] for c in colds) + 1.8
        rx0, rx1 = hx0 - 3.2, hx1 + 3.2
        if self.cool:                            # the +X wall is the pipe wall; the plant sits beyond it
            rx1 = self.cool["plant"]["wall_x"]
        self.room_box = (rx0, cy0, rx1, cy1)
        floor = MeshBuilder()
        blutil.image_floor("floor_paint", self.texdir)       # register with the texture dir first
        floor.box(rx0, cy0, -0.05, rx1, cy1, 0.0, "floor_paint")
        floor.build("floor", self.c["Room"])
        walls = MeshBuilder()
        t = 0.2
        for a, b in (((rx0 - t, cy0 - t), (rx1 + t, cy0)), ((rx0 - t, cy1), (rx1 + t, cy1 + t)),
                     ((rx0 - t, cy0), (rx0, cy1)), ((rx1, cy0), (rx1 + t, cy1))):
            walls.box(a[0], a[1], 0.0, b[0], b[1], CEILING_Z, "wall")
            walls.box(a[0] - 0.002 if a[0] < rx0 else a[0], a[1], 0.0, b[0], b[1], 0.1, "skirting")
        walls.build("walls", self.c["Room"])
        ceil = MeshBuilder()
        ceil.box(rx0, cy0, CEILING_Z, rx1, cy1, CEILING_Z + 0.1, "ceiling")
        ceil.build("ceiling", self.c["Ceiling"])
        # floor safety line along each cold aisle edge (yellow) — standard hall marking
        tape = MeshBuilder()
        for row, c in zip(rows, colds):
            far = c[3] if L.row_racks(self.s, row)[0]["facing"][1] > 0 else c[1]
            tape.box(c[0] - 0.2, far - 0.025, 0.0, c[2] + 0.2, far + 0.025, 0.0012, "raceway")
        tape.build("floor_lines", self.c["Room"])
        if self.cool:                            # the CRAH units are placed by cooling()
            return
        # CRAH fan walls at both ends of every cold aisle, blowing along the aisle
        mb = MeshBuilder()
        for c in colds:
            for end, s in ((c[0], -1), (c[2], 1)):
                face_x = end + s * 0.9
                back_x = face_x + s * 0.9
                ya, yb = c[1] - 0.25, c[3] + 0.25
                mb.box(face_x, ya, 0.0, back_x, yb, 2.2, "crah_body")
                mb.box(face_x - s * 0.004, ya + 0.04, 0.12, face_x, yb - 0.04, 1.95, "crah_fan")
                ncol, nrow = 2, 3
                for i in range(ncol):
                    for j in range(nrow):
                        yc = ya + 0.04 + (yb - ya - 0.08) * (i + 0.5) / ncol
                        zc = 0.12 + (1.95 - 0.12) * (j + 0.5) / nrow
                        fr = min((yb - ya) / ncol, 1.83 / nrow) * 0.42
                        ax = (-s, 0, 0)
                        mb.cyl((face_x - s * 0.008, yc, zc), ax, fr, 0.008, "plug_black", seg=40)
                        for rr in (fr, fr * 0.72, fr * 0.44):
                            mb.ring((face_x - s * 0.02, yc, zc), ax, rr, 0.006, "steel", seg=40)
                        mb.cyl((face_x - s * 0.022, yc, zc), ax, fr * 0.18, 0.02, "steel", seg=20)
                        for k in range(4):
                            a = math.pi / 4 + k * math.pi / 2
                            mb.cyl((face_x - s * 0.02, yc, zc), (0, math.cos(a), math.sin(a)), 0.004, 2 * fr, "steel", seg=6)
                mb.box(face_x - s * 0.004, ya + 0.1, 2.0, face_x, ya + 0.35, 2.12, "lcd")
                mb.box(face_x, ya, 2.2, back_x, yb, 2.25, "switch_grey")
        mb.build("crah_fan_walls", self.c["Room"], bevel=0.004)

    # ------------------------------------------------------------ cooling -------------------
    def cooling(self):
        """CDUs, CRAHs and plant modules as instances; every header / main / drop / hose as its
        own tube with tracing props; colour bands + flow arrows on the mains; branch valves,
        drip trays, leak rope; the pipe wall with sleeves and the plant slab outside."""
        cs = self.cool
        sup, ret = cs["colours"]["supply"], cs["colours"]["return"]
        col = {"coolant-supply": sup, "coolant-return": ret}
        for cdu in cs["cdus"]:
            fr = C.unit_frame(cdu)
            blutil.instance(cdu["name"], self.assets.unit("cdu", cdu["type"]), cdu["origin"], L.rack_yaw(fr), self.c["Cooling"],
                            {"dgx_kind": "cdu", "dgx_loop": cdu["loop"], "dgx_type": cdu["type"], "dgx_kw": float(cdu["kw"]),
                             "dgx_rack": "", "device_type": cdu["type"]})
            self.stats["cdu"] += 1
        for crah in cs["crahs"]:
            fr = C.unit_frame(crah)
            blutil.instance(crah["name"], self.assets.unit("crah", crah["type"]), crah["origin"], L.rack_yaw(fr), self.c["Cooling"],
                            {"dgx_kind": "crah", "dgx_loop": "fws", "dgx_type": crah["type"], "dgx_kw": float(crah["kw"]),
                             "dgx_rack": "", "device_type": crah["type"]})
            self.stats["crah"] += 1
        for u in cs["plant"]["units"]:
            fr = C.unit_frame(u)
            blutil.instance(u["name"], self.assets.unit("plant", u["type"]), u["origin"], L.rack_yaw(fr), self.c["Plant"],
                            {"dgx_kind": "plant", "dgx_loop": "fws", "dgx_type": u["type"], "dgx_kw": float(u["kw"]),
                             "dgx_rack": "", "device_type": u["type"]})
            self.stats["plant"] += 1
        runs, _sockets = C.all_runs(self.s, self.lib)
        bands, fittings = MeshBuilder(), MeshBuilder()
        for i, run in enumerate(runs):
            mat = "pipe_insul" if run.kind in ("header", "main", "drop") else "hose_black"
            coll = self.c["Plant"] if (run.kind == "main" and run.points[0][0] > self.room_box[2]) else self.c["Cooling"]
            blutil.curve(f"{run.kind}_{i}_{run.a}", list(run.points), run.radius, mat, coll,
                         {"dgx_kind": "hose" if run.kind == "hose" else "pipe", "dgx_a": run.a or "", "dgx_b": run.b or "",
                          "dgx_fabric": run.fabric, "dgx_loop": run.loop, "dgx_pipe_kind": run.kind},
                         resolution=3 if run.kind in ("header", "main") else 2)
            self.stats[f"pipe_{run.kind}"] += 1
            if run.kind in ("header", "main"):      # identification bands + flow arrows every 3 m
                basic = cs["colours"].get("basic")           # BS 1710 green basic bands flank the code band
                for pos, tan in L.sample_along(list(run.points), 3.0, 0.6):
                    bands.ring(pos, tan, run.radius + 0.001, 0.12, blutil.tie_material(col[run.fabric]), seg=18)
                    if basic:
                        for s_ in (-1, 1):
                            bands.ring(L._add(pos, L._mul(tan, s_ * 0.12)), tan, run.radius + 0.001, 0.12,
                                       blutil.tie_material(basic), seg=18)
                    d = 1.0 if run.fabric.endswith("supply") else -1.0
                    tip = L._add(pos, L._mul(tan, d * 0.16))
                    base = L._add(pos, L._mul(tan, d * 0.08))
                    fittings.cyl(L._add(base, L._mul(tan, d * 0.04)), tan, run.radius + 0.012, 0.08, blutil.tie_material(col[run.fabric]), seg=14)
                    fittings.cyl(tip, tan, 0.003, 0.002, blutil.tie_material(col[run.fabric]), seg=6)
            if run.kind == "drop" and run.b and not run.b.startswith(("cdu-", "crah-", "plant-")):
                # branch isolation valve just below the tee + a drip tray under the pair
                vz = run.points[0][2] - C.VALVE_DROP + 0.12
                x, y = run.points[1][0], run.points[1][1]
                fittings.cyl((x, y, vz), (0, 0, 1), run.radius + 0.012, 0.10, "steel", seg=14)
                fittings.box(x - 0.006, y - 0.006, vz, x + 0.006, y + 0.09, vz + 0.012, "valve_red")
                if run.fabric.endswith("supply"):
                    tw, td, th = C.DRIP_TRAY
                    fittings.box(x - 0.01, y - td / 2, vz - 0.22, x + 2 * C.DROP_SPLIT + 0.01, y + td / 2, vz - 0.22 + th, "drip_tray")
        bands.build("pipe_bands", self.c["Cooling"])["dgx_kind"] = "decor"
        fittings.build("pipe_fittings", self.c["Cooling"])["dgx_kind"] = "decor"
        # leak-detection rope along each row's rear at floor level
        if cs.get("leak_detection"):
            for row in self.s["hall"]["rows"]:
                rr = L.row_racks(self.s, row["name"])
                fy = rr[0]["facing"][1]
                y = rr[0]["origin"][1] - fy * (rr[0]["depth"] / 2 + 0.42)
                xs = [r["origin"][0] for r in rr]
                blutil.curve(f"leak_rope_{row['name']}", [(min(xs) - 0.3, y, 0.012), (max(xs) + 0.3, y, 0.012)], 0.006,
                             "leak_rope", self.c["Cooling"], {"dgx_kind": "leak", "dgx_a": f"row-{row['name']}", "dgx_b": "",
                                                              "dgx_fabric": "", "dgx_loop": ""})
                self.stats["leak_rope"] += 1
        # pipe wall sleeves where the FWS mains cross the +X wall, and the plant slab outside
        mb = MeshBuilder()
        wx = cs["plant"]["wall_x"]
        for m in cs["fws_mains"]:
            mb.cyl((wx + 0.1, m["y"], m["z"]), (1, 0, 0), 0.16, 0.26, "sleeve", seg=20)
            mb.ring((wx - 0.005, m["y"], m["z"]), (1, 0, 0), 0.19, 0.01, "steel", seg=20)
            mb.ring((wx + 0.205, m["y"], m["z"]), (1, 0, 0), 0.19, 0.01, "steel", seg=20)
        units = cs["plant"]["units"]
        x0 = min(u["origin"][0] - u["width"] / 2 for u in units) - 1.0
        x1 = max(u["origin"][0] + u["width"] / 2 for u in units) + 1.0
        y0 = min(u["origin"][1] - u["depth"] / 2 for u in units) - 1.0
        y1 = max(u["origin"][1] + u["depth"] / 2 for u in units) + 1.0
        mb.box(wx + 0.2, y0, -0.3, x1, y1, 0.0, "concrete_pad")
        mb.box(wx + 0.2, y0 - 30.0, -0.35, x1 + 30.0, y1 + 30.0, -0.30, "asphalt")        # outdoor ground
        for u in units:                                # pipe stands outside: mains run at low level to the modules
            pass
        mb.build("wall_sleeves_and_slab", self.c["Plant"])["dgx_kind"] = "decor"
        self.plant_box = (wx, y0, x1, y1)

    def links_datablock(self):
        """Store the full links table and the cooling graph inside the .blend (text datablock
        dgx_links.json) so the tracing add-on needs nothing but the file."""
        import bpy
        data = {"design": self.s["design"], "links_cols": self.s.get("links_cols", []), "links": self.s.get("links", []),
                "rack_of": self.rack_of, "hall": self.s["hall"], "render": self.s["render"],
                "racks": self.s["racks"],                 # full rack dicts: frames + devices (port maps need them)
                "library": self.lib}                      # device envelopes / face fractions
        if self.cool:
            data["cooling"] = {"pipes": self.cool["pipes"], "loops": self.cool["loops"], "plant": self.cool["plant"],
                               "cdus": [c["name"] for c in self.cool["cdus"]], "crahs": [c["name"] for c in self.cool["crahs"]],
                               "colours": self.cool["colours"]}
        txt = bpy.data.texts.get("dgx_links.json") or bpy.data.texts.new("dgx_links.json")
        txt.clear()
        txt.write(json.dumps(data, separators=(",", ":")))

    # ------------------------------------------------------------ lights --------------------
    def area_light(self, name, loc, sx, sy, watts, colour=(0.96, 0.98, 1.0)):
        """Camera-invisible rectangular area light matching a fixture (5000 K-ish white)."""
        import bpy
        ld = bpy.data.lights.new(name, "AREA")
        ld.shape, ld.size, ld.size_y = "RECTANGLE", sx, sy
        ld.energy, ld.color = watts, colour
        ob = bpy.data.objects.new(name, ld)
        ob.location = loc
        self.c["Lights"].objects.link(ob)
        self.stats["area_light"] += 1
        return ob

    def lights(self):
        """Cool-white (5000 K) linear LED fixtures over the cold aisles; dim strips inside the
        contained hot aisle."""
        fix, rods = MeshBuilder(), MeshBuilder()
        rows = [row["name"] for row in self.s["hall"]["rows"]]
        z = 3.3
        for row in rows:
            c = L.cold_aisle(self.s, self.lib, row)
            yc = (c[1] + c[3]) / 2
            x = c[0] - 0.2
            while x + 1.4 <= c[2] + 0.4:
                fix.box(x, yc - 0.04, z, x + 1.4, yc + 0.04, z + 0.06, "fixture")
                fix.box(x + 0.02, yc - 0.03, z - 0.003, x + 1.38, yc + 0.03, z + 0.001, "led_panel")
                self.area_light(f"cold_{row}_{x:.1f}", (x + 0.7, yc, z - 0.01), 1.4, 0.06, 110.0)
                for xx in (x + 0.1, x + 1.3):
                    rods.cyl((xx, yc, (z + 0.06 + CEILING_Z) / 2), (0, 0, 1), 0.0008, CEILING_Z - z - 0.06, "rod", seg=6)
                x += 1.8
        x0, y0, x1, y1 = L.hot_aisle(self.s, self.lib)
        zc = self.H - 0.02
        for yy in ((y0 + y1) / 2 - 0.25, (y0 + y1) / 2 + 0.25):
            x = x0 + 0.3
            while x + 1.0 <= x1:
                fix.box(x, yy - 0.012, zc, x + 1.0, yy + 0.012, zc + 0.02, "fixture")
                fix.box(x + 0.01, yy - 0.009, zc - 0.002, x + 0.99, yy + 0.009, zc, "led_panel_dim")
                self.area_light(f"hot_{yy:.2f}_{x:.1f}", (x + 0.5, yy, zc - 0.005), 1.0, 0.02, 14.0)
                x += 1.9
        fix.build("light_fixtures", self.c["Lights"])
        rods.build("light_wires", self.c["Lights"])
