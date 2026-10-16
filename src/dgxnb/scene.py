"""3D scene export for Blender (or any renderer), built offline from the Design.

  scene_json(spec, types, design) -> dict      written by `bin/dgxnb export` as scene.json

Same source as NetBox and the draw.io pages, so a render cannot drift from the model.
Coordinates are metres, right-handed, Z up:
  X  along the rows (rack 1 of every row at the smallest X)
  Y  across the rows; spec["hall"]["rows"] listed first sits at the largest Y ("up" in
     the floor plan), so a row with front "up" faces +Y and one with front "down" faces −Y
  Z  from the finished floor
A rack's `origin` is the floor-level centre of its footprint and `facing` the unit vector
its front door points along. A device's `z_bottom` is measured from the rack's floor
(`rack_u0_mm` + (position − 1) × 44.45 mm). 0U kit (PDUs) has `position: null` and a
`mount: "rear-0U"` with `side` −1/+1 (left/right seen from the front).

Cable bundles aggregate every non-power cable between two racks per fabric; each carries
the jacket/tie colours chosen in spec["render"]["fabric_colours"] (compute ties use the
rail palette, given per bundle in `rails`), so the render, the draw.io pages and the cable
schedule agree. `links` lists EVERY cable (power included) with both ends as device + port,
the same rows as topology-graph.json, so a renderer or the Blender tracing add-on can fan
a device out to its exact far ends.
"""
from __future__ import annotations

from collections import Counter, defaultdict

from . import export
from .drawio import RAIL
from .model import Design

U_MM = 44.45


def _rack_layout(spec: dict) -> dict[str, dict]:
    """rack -> {origin, facing, row} from spec["hall"] (same rules as the floor plan)."""
    hall, r = spec["hall"], spec["racks"]
    w, d = r["width_mm"] / 1000, r["depth_mm"] / 1000
    cold, hot = hall["cold_aisle_mm"] / 1000, hall["hot_aisle_mm"] / 1000
    rows = hall["rows"]
    out: dict[str, dict] = {}
    y = 0.0                      # top edge of the current row, walking down (−Y)
    for i, row in enumerate(rows):
        if i:
            prev = rows[i - 1]
            y -= hot if prev["front"] == "up" else cold
        cy = y - d / 2
        facing = [0, 1, 0] if row["front"] == "up" else [0, -1, 0]
        for j, rack in enumerate(row["racks"]):
            out[rack] = {"row": row["name"], "index": j + 1,
                         "origin": [round(j * w + w / 2, 4), round(cy, 4), 0.0],
                         "facing": facing}
        y -= d
    return out


REAR_MOUNT = {"cooling-rdhx": "rear-door", "cooling-manifold": "rear-manifold"}


def scene_json(spec: dict, types: dict, design: Design) -> dict:
    """Racks, devices, 0U PDUs, cable bundles, links, cooling and aisles for a 3D build."""
    r = spec["racks"]
    render = spec.get("render", {})
    colours = render.get("fabric_colours", {})
    layout = _rack_layout(spec)
    kw = export.rack_power(types, design)
    devs = design.all("dcim.devices")
    rack_of = {o.data["name"]: o.data["rack"].key[0] for o in devs if "rack" in o.data}
    by_rack: dict[str, list] = defaultdict(list)
    pdu_side: Counter = Counter()
    for o in sorted(devs, key=lambda o: o.data["name"]):
        if "rack" not in o.data:
            continue
        rack = o.data["rack"].key[0]
        slug = o.data["device_type"].key[0]
        t = types[slug]
        pos = o.data.get("position")
        role = o.data["role"].key[0]
        if role == "pdu":
            # KNOWN GAP: the Blender pipeline only knows vertical rear-0U rPDUs, so the DGX
            # racks' 3U horizontal units (design-choices §6.1) are drawn as 0U stand-ins.
            pos = None
        item = {"name": o.data["name"], "type": slug, "model": t["model"],
                "manufacturer": t.get("manufacturer", ""), "role": role,
                "u_height": t["u_height"], "position": pos,
                "is_full_depth": t.get("is_full_depth", True)}
        if pos:
            item["z_bottom"] = round((r.get("rack_u0_mm", 100) + (pos - 1) * U_MM) / 1000, 4)
            item["mount"] = "front"
        elif role in REAR_MOUNT:                 # a rear door / in-rack manifold: one per rack
            item["mount"] = REAR_MOUNT[role]
        else:
            n = pdu_side[rack]
            pdu_side[rack] += 1
            item.update(mount="rear-0U", side=-1 if n % 2 == 0 else 1, slot=n // 2)
        by_rack[rack].append(item)

    racks = []
    for o in design.all("dcim.racks"):
        name = o.key[0]
        racks.append({"name": name, **layout[name], "width": r["width_mm"] / 1000,
                      "depth": r["depth_mm"] / 1000, "u_height": r["u_height"],
                      "peak_kw": round(kw.get(name, 0), 2), "devices": by_rack[name]})

    bundles: dict[tuple, Counter] = defaultdict(Counter)
    rails: dict[tuple, Counter] = defaultdict(Counter)
    for o in design.all("dcim.cables"):
        fabric = o.data["custom_fields"]["dgx_fabric"]
        if fabric == "power":
            continue
        a = rack_of.get(o.data["a_terminations"][0].parent)
        b = rack_of.get(o.data["b_terminations"][0].parent)
        if not a or not b:              # e.g. the DC-core demarc: no rack in the hall
            continue
        key = tuple(sorted((a, b))) + (fabric,)
        bundles[key][o.data["type"]] += 1
        if o.data["custom_fields"].get("dgx_rail"):
            rails[key][o.data["custom_fields"]["dgx_rail"]] += 1
    cable_bundles = [{"a": a, "b": b, "fabric": f, "count": sum(c.values()),
                      "types": dict(sorted(c.items())), "colour": colours.get(f),
                      **({"rails": dict(sorted(rails[(a, b, f)].items()))}
                         if rails[(a, b, f)] else {})}
                     for (a, b, f), c in sorted(bundles.items())]

    links = [[a[0].parent, "+".join(t.name for t in a), b[0].parent, "+".join(t.name for t in b),
              cf["dgx_fabric"], o.data["type"], cf.get("dgx_rail") or 0, o.data["label"]]
             for o in design.all("dcim.cables")
             for a, b, cf in [(o.data["a_terminations"], o.data["b_terminations"],
                               o.data["custom_fields"])]]

    hall = spec["hall"]
    out = {
        "units": "metres", "up": "Z",
        "design": {"name": spec["name"], "description": spec["description"],
                   "tag": spec["tag"], "site": spec["site"]["slug"]},
        "hall": {"cold_aisle": hall["cold_aisle_mm"] / 1000,
                 "hot_aisle": hall["hot_aisle_mm"] / 1000,
                 "containment": hall.get("containment", "hot-aisle"),
                 "rows": [{"name": row["name"], "front": row["front"], "racks": row["racks"]}
                          for row in hall["rows"]],
                 "note": hall.get("note", "")},
        "render": {**render, "rail_colours": RAIL},
        "racks": racks,
        "cable_bundles": cable_bundles,
        "links_cols": ["a", "a_port", "b", "b_port", "fabric", "cable", "rail", "label"],
        "links": links,
    }
    if spec.get("cooling"):
        out["cooling"] = cooling_json(spec, types, design, layout, racks)
    return out


# ---------------------------------------------------------------- cooling -----------------
def cooling_json(spec: dict, types: dict, design: Design, layout: dict, racks: list) -> dict:
    """Plant, loops, CDUs (with hall positions), headers as polylines and the per-rack
    door/manifold + branch. Also annotates each rack dict with cooling {loop, unit, kw}.

    Positions (CHOICE, docs/design-choices.md "Mixed pod"): CDUs fill the rack positions row
    B does not use, in loop order, facing like that row; the plant sits outside the hall wall
    beyond the row ends (x), centred on the rear aisle; each header runs at `headers.z_mm`
    just behind the rear face of its row (supply nearer the racks, return further out) from
    the row's first rack to the CDU block, then across to each CDU's secondary connection.
    """
    from . import cooling as cl
    cs = spec["cooling"]
    m = cl.model(spec, types, design)
    r = spec["racks"]
    w, d = r["width_mm"] / 1000, r["depth_mm"] / 1000
    by_name = {rk["name"]: rk for rk in racks}
    rows = {row["name"]: row for row in spec["hall"]["rows"]}
    z_hdr = cs["headers"]["z_mm"] / 1000
    hy = cs["headers"]["y_behind_rear_mm"]           # {supply, return} offsets behind the rear face
    # --- CDU slots: the free rack positions of the shortest row, from its last rack onwards
    slot_row = rows[cs["cdu_slots"]["row"]]
    first = by_name[slot_row["racks"][0]]
    facing = first["facing"]
    cy, x0 = first["origin"][1], len(slot_row["racks"]) * w + cs["cdu_slots"].get("gap_mm", 300) / 1000
    cdus, x = [], x0
    for lp in m.loops.values():
        cd = cs["loops"][lp.key]["cdu"]
        cw, cdep, ch = cd["width_mm"] / 1000, cd["depth_mm"] / 1000, cd["height_mm"] / 1000
        for name in lp.cdus:
            cdus.append({"name": name, "loop": lp.key, "type": lp.cdu_type, "kw": lp.cdu_kw,
                         "origin": [round(x + cw / 2, 4), round(cy, 4), 0.0], "facing": facing,
                         "width": cw, "depth": cdep, "height": ch, "row": slot_row["name"]})
            x += cw + cs["cdu_slots"].get("gap_mm", 300) / 1000
    cdu_by = {c["name"]: c for c in cdus}
    # --- plant block: modules side by side outside the +X wall, their long side along the
    # wall, centred on the rear aisle; the FWS mains cross the wall at fws_z
    x_end = max(rk["origin"][0] + w / 2 for rk in racks)
    x_start = min(rk["origin"][0] - w / 2 for rk in racks)
    ys = sorted(rk["origin"][1] for rk in racks)
    rear_y = (max(ys) + min(ys)) / 2                   # midway between the two rows' centres
    pl, hall = cs["plant"], spec["hall"]
    wall_x = x_end + hall.get("end_clear_mm", 3200) / 1000
    pw, pd, ph = pl["width_mm"] / 1000, pl["depth_mm"] / 1000, pl["height_mm"] / 1000
    px = wall_x + hall.get("wall_mm", 200) / 1000 + pl["clear_mm"] / 1000
    units = []
    for i, name in enumerate(m.plant_units):
        # facing -Y: the module's long side (depth) runs along the wall (Y), its local +X
        # (water connections) points back at the wall (-X world)
        units.append({"name": name, "type": m.plant_type, "kw": m.plant_kw_each,
                      "origin": [round(px + pw / 2 + i * (pw + 1.0), 4), round(rear_y, 4), 0.0],
                      "facing": [0, -1, 0], "width": pw, "depth": pd, "height": ph})
    plant = {"header": m.fws_header, "units": units, "kw": m.plant_kw,
             "load_kw": round(m.plant_load_kw, 1), "fws_supply_c": m.fws_supply_c,
             "fws_return_c": m.fws_return_c, "wall_x": round(wall_x, 4)}
    # --- CRAHs: one at the -X end of each cold aisle, blowing along it (CHOICE)
    ra = cs["residual_air"]
    cw_, cd_, ch_ = ra["width_mm"] / 1000, ra["depth_mm"] / 1000, ra["height_mm"] / 1000
    crahs = []
    for i, name in enumerate(m.crah_units):
        row = spec["hall"]["rows"][i % len(spec["hall"]["rows"])]
        rk0 = by_name[row["racks"][0]]
        fy = rk0["facing"][1]
        aisle_y = rk0["origin"][1] + fy * (d / 2 + spec["hall"]["cold_aisle_mm"] / 2000)
        crahs.append({"name": name, "type": m.crah_type, "kw": m.crah_kw_each, "aisle_row": row["name"],
                      "origin": [round(x_start - 0.9 - cd_ / 2, 4), round(aisle_y, 4), 0.0],
                      "facing": [1, 0, 0], "width": cw_, "depth": cd_, "height": ch_})
    # --- FWS mains: along the rear-aisle centre line at fws_z from the plant (through the
    # wall) to the CDU block and on to the CRAHs at the far end
    z_fws = cs["headers"]["fws_z_mm"] / 1000
    fws_lines = []
    for kind, dy in (("supply", -0.15), ("return", 0.15)):
        y = rear_y + dy
        pts = [[round(units[0]["origin"][0] - pw / 2, 4), round(y, 4), z_fws],
               [round(wall_x + 0.3, 4), round(y, 4), z_fws],
               [round(x_start - 0.9, 4), round(y, 4), z_fws]]
        fws_lines.append({"name": m.fws_header, "kind": kind, "z": z_fws, "y": round(y, 4),
                          "polyline": pts, "dn": cs["headers"].get("fws_dn", 200)})
    # --- headers: per loop per row, supply and return polylines
    loops, headers = {}, []
    for lp in m.loops.values():
        ls = cs["loops"][lp.key]
        loops[lp.key] = {"label": lp.label, "unit_kind": lp.unit_kind, "unit_type": lp.unit_type,
                         "load_kw": round(lp.load_kw, 1), "cdus": lp.cdus, "cdu_kw": lp.cdu_kw,
                         "tcs_supply_c": lp.tcs_supply_c, "tcs_return_c": lp.tcs_return_c,
                         "flow_lpm": round(lp.flow_lpm, 1), "liquid_fraction": lp.liquid_fraction,
                         "headers": list(lp.headers.values()), "racks": lp.racks,
                         "unit": {k: v for k, v in ls["unit"].items()}}
        for row_name, hdr in lp.headers.items():
            row = rows[row_name]
            racks_in = [by_name[n] for n in row["racks"] if n in lp.racks]
            rk0 = by_name[row["racks"][0]]
            fy = rk0["facing"][1]
            rear = rk0["origin"][1] - fy * d / 2          # world y of the row's rear face
            off = ls["header"].get("offset_mm", 0) / 1000     # loops sharing a row sit side by side
            for kind in ("supply", "return"):
                y = rear - fy * (hy[kind] / 1000 + off)
                xa = min(rk["origin"][0] - w / 2 for rk in racks_in)
                xb = max(rk["origin"][0] + w / 2 for rk in racks_in)
                pts = [[round(xa, 4), round(y, 4), z_hdr], [round(xb, 4), round(y, 4), z_hdr]]
                # on to the CDU block: along the row line to above the first CDU, then to each
                cx = [cdu_by[c]["origin"][0] for c in lp.cdus]
                yc = cdu_by[lp.cdus[0]]["origin"][1] - cdu_by[lp.cdus[0]]["facing"][1] * (hy[kind] / 1000 + off + d / 2)
                pts += [[round(max(cx), 4), round(y, 4), z_hdr], [round(max(cx), 4), round(yc, 4), z_hdr],
                        [round(min(cx), 4), round(yc, 4), z_hdr]]
                headers.append({"name": hdr, "loop": lp.key, "row": row_name, "kind": kind,
                                "dn": ls["header"]["dn"], "z": z_hdr, "y": round(y, 4),
                                "polyline": pts, "flow_lpm": round(lp.header_flow_lpm(hdr), 1),
                                "rated_lpm": lp.header_rated_lpm})
        for rk_name in lp.racks:
            by_name[rk_name]["cooling"] = {"loop": lp.key, "unit": lp.unit_of[rk_name],
                                           "unit_kind": lp.unit_kind, "kw": lp.rack_kw[rk_name],
                                           "header": lp.header_of[rk_name],
                                           "branch": lp.branch_of[rk_name]}
    return {"colours": cs["colours"], "plant": plant, "crahs": crahs,
            "residual_air_kw": round(m.residual_air_kw, 1), "loops": loops, "cdus": cdus,
            "headers": headers, "fws_mains": fws_lines,
            "leak_detection": cs.get("leak_detection", {}),
            "pipes": [list(e) for e in cl.hydraulic_edges(design)]}
