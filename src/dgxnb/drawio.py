"""draw.io export: editable Solutions-Architect drawings, built offline from the Design.

  drawio_xml(spec, types, design) -> str    one multi-page .drawio file (plain mxGraph XML)

Pages
  "Compute fabric — SU <s>"  the rail-optimised fat tree seen from one SU: every compute
                             spine, the SU's leaves (filled with their rail colour) and its
                             nodes grouped by rack. One line per node→leaf cable, coloured
                             by rail; one line per leaf→spine pair. UFM links are dashed.
                             An SU wider than MAX_NODES_PER_ROW (GB300: 144 trays) is drawn
                             as a folded fabric page instead.
  storage / in-band / OOB    fabric_page(): tiered (core, spine, leaf, endpoints), bulk kit
                             folded to one box per rack, one line per box pair.
  "Rack elevations — …"      front view of every rack, per SU then management & storage,
                             0U PDUs beside the frame, peak/budget kW.
  "Data hall floor plan"     spec["hall"] rows to scale with aisles, kW and raceways.

Everything comes from the same Design that feeds NetBox, so the drawing cannot drift from
the model. The file is a derived artefact (`bin/dgxnb export` writes docs/.../superpod.drawio):
open it in draw.io and "Save as" a copy for manual polish, never hand-edit the generated one.
Hover any box or line in draw.io for the full name, rack position or cable ports.

Render to PDF (all pages):  drawio -x -f pdf -a -o superpod.pdf docs/superpod.drawio
"""
from __future__ import annotations

import html
import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict

from . import export
from .cooling import ROLES_COOLING
from .graph import GROUPABLE, TIER
from .model import Design
from .topology import ROLES
from .topology_gb300 import ROLES_GB

_ALL_ROLES = {**ROLES, **ROLES_GB, **ROLES_COOLING}
ROLE_FILL = {k: "#" + c for k, (_, c) in _ALL_ROLES.items()}
ROLE_NAME = {k: n for k, (n, _) in _ALL_ROLES.items()}
# Rail palette: Okabe-Ito (colour-blind safe) with yellow/black swapped for print-legible
# gold/purple. Lime green is kept out of it: it marks the compute nodes.
RAIL = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#B8860B", "#6A3D9A"]
INK, MUTED, FONT = "#1a1a1a", "#6b7280", "Helvetica"

# Compute page geometry (px). Nodes sit in rack groups along one row.
M = 40                                   # page margin
NW, NH, NG = 56, 44, 8                   # node box, gap between nodes in a rack
RP, RG = 8, 18                           # rack group padding, gap between racks
SPINE_Y, LEAF_Y, NODE_Y = 170, 480, 840  # row tops
SWH, LWH = 52, 56                        # spine / leaf box heights

# Rack page geometry (px).
UPX, DEV_W, GUT, PDU_W = 18, 300, 28, 18


def rail_colour(rail: int) -> str:
    return RAIL[(rail - 1) % len(RAIL)]


def _ink(fill: str) -> str:
    """Readable text colour on `fill` (perceived luminance threshold)."""
    r, g, b = (int(fill[i:i + 2], 16) for i in (1, 3, 5))
    return INK if 0.299 * r + 0.587 * g + 0.114 * b > 150 else "#ffffff"


def _st(**kw) -> str:
    """draw.io style string from keyword pairs: _st(a=1, b="x") -> "a=1;b=x;"."""
    return "".join(f"{k}={v};" for k, v in kw.items())


def _n(v: float) -> str:
    return f"{v:.1f}".rstrip("0").rstrip(".")


def _esc(s) -> str:
    return html.escape(str(s), quote=False)


class _Page:
    """One draw.io page. Cells are kept in three z-order layers: back, edges, front."""

    def __init__(self, name: str, pid: str):
        self.name, self.pid = name, pid
        self.layers: dict[str, list[ET.Element]] = {"back": [], "edges": [], "front": []}
        self.w = self.h = 0.0

    def _add(self, layer: str, cid: str, label: str, tooltip, cell: ET.Element) -> str:
        """Wrap `cell` in an <object> when it carries a tooltip (draw.io's convention)."""
        full = f"{self.pid}-{cid}"
        if tooltip:
            el = ET.Element("object", id=full, label=label, tooltip=tooltip)
            el.append(cell)
        else:
            cell.set("id", full)
            cell.set("value", label)
            el = cell
        self.layers[layer].append(el)
        return full

    def box(self, cid, x, y, w, h, label, style, tooltip=None, layer="front") -> str:
        cell = ET.Element("mxCell", style=style, vertex="1", parent="1")
        ET.SubElement(cell, "mxGeometry", {"x": _n(x), "y": _n(y), "width": _n(w),
                                           "height": _n(h), "as": "geometry"})
        self.w, self.h = max(self.w, x + w), max(self.h, y + h)
        return self._add(layer, cid, label, tooltip, cell)

    def text(self, cid, x, y, w, h, label, size=11, colour=INK, bold=False, align="left",
             **extra) -> str:
        return self.box(cid, x, y, w, h, label, "text;" + _st(
            html=1, whiteSpace="wrap", align=align, verticalAlign="middle",
            fontFamily=FONT, fontSize=size, fontColor=colour, fontStyle=1 if bold else 0,
            strokeColor="none", fillColor="none", **extra))

    def line(self, cid, src, dst, style, tooltip=None, points=()) -> str:
        """Edge between two cells; `points` are optional (x, y) waypoints."""
        cell = ET.Element("mxCell", style=style, edge="1", parent="1", source=src, target=dst)
        geo = ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
        if points:
            arr = ET.SubElement(geo, "Array", {"as": "points"})
            for px, py in points:
                ET.SubElement(arr, "mxPoint", x=_n(px), y=_n(py))
        return self._add("edges", cid, "", tooltip, cell)

    def element(self) -> ET.Element:
        d = ET.Element("diagram", name=self.name, id=self.pid)
        g = ET.SubElement(d, "mxGraphModel", {
            "dx": "0", "dy": "0", "grid": "0", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
            "pageScale": "1", "pageWidth": _n(self.w + M), "pageHeight": _n(self.h + M),
            "math": "0", "shadow": "0", "background": "#FFFFFF"})
        root = ET.SubElement(g, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        for layer in ("back", "edges", "front"):
            root.extend(self.layers[layer])
        return d


def _device_box_style(fill: str, size: int = 10) -> str:
    return _st(rounded=1, absoluteArcSize=1, arcSize=8, html=1, whiteSpace="wrap", fillColor=fill,
               strokeColor="#00000033", fontColor=_ink(fill), fontFamily=FONT, fontSize=size)


def _title(p: _Page, spec: dict, title: str, subtitle: str, width: float) -> None:
    p.text("title", M, M - 10, width, 30, _esc(title), size=20, bold=True)
    p.text("subtitle", M, M + 20, width, 22, _esc(subtitle), size=12, colour=MUTED)
    p.text("source", M, M + 42, width, 20, _esc(
        f"{spec['description']} · site {spec['site']['slug']} · tag {spec['tag']} · generated "
        "by bin/dgxnb export — edit a copy, not this file"), size=10, colour=MUTED)


def _legend(p: _Page, x: float, y: float, items: list[tuple[str, str, str]]) -> float:
    """items = (kind 'line'|'box', colour, label). Returns the legend's bottom y."""
    p.text("legend-h", x, y, 200, 18, "Legend", size=11, bold=True)
    y += 24
    col_w, per_col = 190, 6
    for i, (kind, colour, label) in enumerate(items):
        cx, cy = x + (i // per_col) * col_w, y + (i % per_col) * 20
        if kind == "line":
            p.box(f"lg{i}", cx, cy + 7, 26, 3, "", _st(fillColor=colour, strokeColor="none"))
        else:
            p.box(f"lg{i}", cx + 4, cy + 2, 18, 12, "", _device_box_style(colour))
        p.text(f"lgt{i}", cx + 32, cy, col_w - 36, 16, _esc(label), size=10)
    return y + per_col * 20


def _index(design: Design):
    dev = {o.data["name"]: o for o in design.all("dcim.devices")}
    role = {n: o.data["role"].key[0] for n, o in dev.items()}
    return dev, role


def _rack(o) -> str:
    return o.data["rack"].key[0] if "rack" in o.data else "—"


def _su(o) -> int:
    return (o.data.get("custom_fields") or {}).get("dgx_su") or 1


def _ends(o):
    a, b = o.data["a_terminations"], o.data["b_terminations"]
    return a[0].parent, "+".join(t.name for t in a), b[0].parent, "+".join(t.name for t in b)


def compute_page(spec: dict, types: dict, design: Design, su: int,
                 node_role: str = "dgx-compute") -> _Page:
    """Rail-optimised compute fabric of one SU (spines are shared by every SU of a pod)."""
    dev, role = _index(design)
    nodes = sorted(n for n, o in dev.items() if role[n] == node_role and _su(o) == su)
    node_set = set(nodes)
    cables = [o for o in design.all("dcim.cables")
              if o.data["custom_fields"]["dgx_fabric"] == "compute"]

    down = []                       # (node, node_port, leaf, leaf_port, rail, cable)
    for o in cables:
        a, ap, b, bp = _ends(o)
        if a in node_set or b in node_set:
            n, np_, lf, lp = (a, ap, b, bp) if a in node_set else (b, bp, a, ap)
            down.append((n, np_, lf, lp, o.data["custom_fields"].get("dgx_rail") or 1, o))
    leaf_rail = {lf: Counter(r for _, _, l2, _, r, _ in down if l2 == lf).most_common(1)[0][0]
                 for lf in {d[2] for d in down}}
    leaves = sorted(leaf_rail, key=lambda lf: (leaf_rail[lf], lf))
    leaf_set = set(leaves)
    up: Counter = Counter()         # (leaf, spine) -> parallel cables
    ufm = []                        # (ufm, leaf, cable)
    for o in cables:
        a, _, b, _ = _ends(o)
        for lf, other in ((a, b), (b, a)):
            if lf in leaf_set and other not in node_set and other not in leaf_set:
                if role[other] == "ufm":
                    ufm.append((other, lf, o))
                else:
                    up[(lf, other)] += 1
    spines = sorted({s for _, s in up})
    rails = max(leaf_rail.values(), default=1)

    p = _Page(f"Compute fabric — SU {su}", f"su{su}")
    # --- node row: nodes grouped by rack, then any UFM that hangs off this SU's leaves
    groups: dict[str, list[str]] = defaultdict(list)
    for n in nodes + sorted({u for u, _, _ in ufm}):
        groups[_rack(dev[n])].append(n)
    pos: dict[str, tuple[float, float]] = {}
    x = M
    for rack, members in groups.items():
        rw = 2 * RP + len(members) * NW + (len(members) - 1) * NG
        p.box(f"rack-{rack}", x, NODE_Y - RP - 6, rw, NH + 2 * RP + 26, _esc(rack), _st(
            rounded=1, arcSize=6, html=1, fillColor="#f3f4f6", strokeColor="#d1d5db",
            dashed=1, verticalAlign="bottom", fontFamily=FONT, fontSize=10,
            fontColor=MUTED, spacingBottom=2), layer="back")
        for i, n in enumerate(members):
            pos[n] = (x + RP + i * (NW + NG), NODE_Y)
        x += rw + RG
    width = x - RG - M

    def spread(names, box_w, y, h, label_fn, fill_fn):
        """Space `names` evenly across the node row's width."""
        slot = width / max(len(names), 1)
        bw = min(box_w, slot - 16)
        for i, name in enumerate(names):
            bx = M + slot * i + (slot - bw) / 2
            pos[name] = (bx, y)
            p.box(name, bx, y, bw, h, label_fn(name), _device_box_style(fill_fn(name), 11),
                  tooltip=f"{name} · {types[dev[name].data['device_type'].key[0]]['model']}"
                          f" · rack {_rack(dev[name])}")
        return bw

    model = lambda n: _esc(types[dev[n].data["device_type"].key[0]]["model"])  # noqa: E731
    spread(spines, 200, SPINE_Y, SWH,
                     lambda n: f"<b>{_esc(n)}</b><br>{model(n)}", lambda n: ROLE_FILL[role[n]])
    spread(leaves, 220, LEAF_Y, LWH,
                    lambda n: f"<b>{_esc(n)}</b><br>Rail {leaf_rail[n]} · {model(n)}",
                    lambda n: rail_colour(leaf_rail[n]))

    for n in pos:
        if n in node_set or role.get(n) == "ufm":
            nx, ny = pos[n]
            fill = ROLE_FILL[role[n]]
            p.box(n, nx, ny, NW, NH, _esc(n.rsplit("-", 1)[-1] if n in node_set else n),
                  _device_box_style(fill, 10) + _st(fontStyle=1, verticalAlign="bottom",
                                                    spacingBottom=3),
                  tooltip=f"{n} · {types[dev[n].data['device_type'].key[0]]['model']} · rack "
                          f"{_rack(dev[n])} U{dev[n].data.get('position')}")
    # rail port pips on top of each node, where its cables leave
    for n in nodes:
        nx, ny = pos[n]
        for r in range(1, rails + 1):
            p.box(f"pip-{n}-{r}", nx + NW * (r - 0.5) / rails - 2.5, ny - 2.5, 5, 5, "",
                  _st(fillColor=rail_colour(r), strokeColor="#ffffff", strokeWidth=0.5))

    # --- lines: node→leaf fans out along the leaf's bottom edge in node order
    order = {n: i for i, n in enumerate(n for n in pos if n in node_set or role.get(n) == "ufm")}
    fan = len(order)
    for i, (n, np_, lf, lp, r, o) in enumerate(sorted(down, key=lambda d: (d[4], d[0]))):
        p.line(f"d{i}", f"{p.pid}-{n}", f"{p.pid}-{lf}", _st(
            endArrow="none", html=1, edgeStyle="none", strokeWidth=1, opacity=55,
            strokeColor=rail_colour(r), exitX=round((r - 0.5) / rails, 4), exitY=0,
            entryX=round((order[n] + 0.5) / fan, 4), entryY=1),
            tooltip=f"{o.data['label']}: {n}:{np_} → {lf}:{lp} ({o.data['type']})")
    for i, (u, lf, o) in enumerate(ufm):
        p.line(f"u{i}", f"{p.pid}-{u}", f"{p.pid}-{lf}", _st(
            endArrow="none", html=1, edgeStyle="none", strokeWidth=1.5, dashed=1,
            strokeColor=ROLE_FILL["ufm"], exitX=0.5, exitY=0,
            entryX=round((order[u] + 0.5) / fan, 4), entryY=1),
            tooltip=f"{o.data['label']} (UFM → leaf, {o.data['type']})")
    for i, ((lf, sp), k) in enumerate(sorted(up.items())):
        p.line(f"s{i}", f"{p.pid}-{lf}", f"{p.pid}-{sp}", _st(
            endArrow="none", html=1, edgeStyle="none", strokeWidth=1.5, opacity=70,
            strokeColor=rail_colour(leaf_rail[lf]),
            exitX=round((spines.index(sp) + 0.5) / len(spines), 4), exitY=0,
            entryX=round((leaves.index(lf) + 0.5) / len(leaves), 4), entryY=1),
            tooltip=f"{lf} → {sp}: {k} cable(s)")

    # --- row captions, title, legend
    k_up = sorted(set(up.values()))
    per_pair = ("0" if not k_up else f"{k_up[0]}" if len(k_up) == 1
                else f"{k_up[0]}–{k_up[-1]}")
    per_rail = len(leaves) // rails if leaves else 0
    node_model = types[dev[nodes[0]].data["device_type"].key[0]]["model"] if nodes else "?"
    p.text("cap-spine", M, SPINE_Y - 26, width, 20, _esc(
        f"SPINE · {len(spines)} switches shared by every SU · each line = {per_pair} parallel "
        "cables"), size=11, colour=MUTED, bold=True, labelBackgroundColor="#ffffff")
    p.text("cap-leaf", M, LEAF_Y - 26, width, 20, _esc(
        f"LEAF · {len(leaves)} switches, "
        f"{'one' if per_rail == 1 else per_rail} per rail (rail-optimised)"),
        size=11, colour=MUTED, bold=True, labelBackgroundColor="#ffffff")
    p.text("cap-node", M, NODE_Y - 44, width, 20, _esc(
        f"SU {su} · {len(nodes)} × {node_model} · port r of every node → rail-r leaf"),
        size=11, colour=MUTED, bold=True, labelBackgroundColor="#ffffff")
    gpus = len(nodes) * export.node_roles(spec)[node_role]
    _title(p, spec, f"Compute fabric — SU {su}", (
        f"{len(nodes)} nodes · {gpus} GPUs · {len(leaves)} leaves · {len(spines)} spines · "
        f"{len(down)} node→leaf + {sum(up.values())} leaf→spine"
        + (f" + {len(ufm)} UFM" if ufm else "") + " cables"),
        max(width, 900))
    items = [("line", rail_colour(r), f"Rail {r}") for r in range(1, rails + 1)]
    items += [("box", ROLE_FILL[r], ROLE_NAME[r])
              for r in dict.fromkeys([node_role, *(role[s] for s in spines)]
                                     + (["ufm"] if ufm else []))]
    items += [("line", ROLE_FILL["ufm"], "UFM → leaf (dashed)")] if ufm else []
    _legend(p, M, NODE_Y + NH + 50, items)
    return p


# --- generic fabric pages (storage, in-band, OOB; compute when an SU is too wide) ----------

FABRIC = {  # fabric: (page title, line colour)
    "compute": ("Compute fabric", "#1f77b4"),
    "storage": ("Storage fabric (InfiniBand)", "#9467bd"),
    "storage-eth": ("Storage fabric (Ethernet)", "#9467bd"),
    "inband": ("In-band management network", "#ff7f0e"),
    "oob": ("Out-of-band management network", "#8c564b"),
}
MAX_NODES_PER_ROW = 64      # an SU wider than this is drawn folded (one box per rack)
ROW_GAP, EP_W, EP_GAP = 250, 104, 12


def _rail_of(cables) -> int:
    return Counter(o.data["custom_fields"].get("dgx_rail") or 0 for o in cables).most_common(1)[0][0]


def fabric_page(spec: dict, types: dict, design: Design, fabric: str, pid: str,
                su: int | None = None) -> _Page:
    """Tiered drawing of one fabric. Rack-mounted endpoints that come in bulk (DGX nodes,
    GB300 trays, PDUs — graph.GROUPABLE) are folded into one box per rack, and parallel
    cables between two boxes become one line whose width grows with log2(count); the tooltip
    gives the exact count and cable types. Rows follow graph.TIER (demarc, spine, leaf,
    endpoints); switch rows are ordered by the barycentre of their lower neighbours so lines
    cross as little as possible. `su` restricts the page to one SU's cables (a folded compute
    fabric in a multi-pod design)."""
    dev, role = _index(design)
    cables = [o for o in design.all("dcim.cables") if o.data["custom_fields"]["dgx_fabric"] == fabric
              and (su is None or o.data["custom_fields"].get("dgx_su") == su)]
    title = FABRIC[fabric][0] + (f" — SU {su}" if su else "")

    def group(n: str) -> str:
        return f"rack:{_rack(dev[n])}" if role[n] in GROUPABLE else n

    members: dict[str, list[str]] = defaultdict(list)
    pairs: dict[tuple, list] = defaultdict(list)
    for o in cables:
        a, _, b, _ = _ends(o)
        for n in (a, b):
            if n not in members[group(n)]:
                members[group(n)].append(n)
        pairs[tuple(sorted((group(a), group(b))))].append(o)

    def tier(g: str) -> int:
        """Fabric managers (UFM) hang off leaves like any endpoint, so they sit in the
        endpoint row here rather than on graph.TIER's leaf row."""
        if g.startswith("rack:") or role[g] == "ufm":
            return 2
        return min(TIER.get(role[g], 2), 2)

    rows: dict[int, list[str]] = defaultdict(list)
    for g in members:
        rows[tier(g)].append(g)
    order = sorted(rows)
    ys = {t: M + 150 + i * ROW_GAP for i, t in enumerate(order)}

    # bottom row: by rack then name, so rack groups sit next to that rack's other kit
    p = _Page(title, pid)
    pos: dict[str, tuple[float, float, float, float]] = {}      # g -> x, y, w, h
    bottom = order[-1]
    x = M
    rack_of = {g: g[5:] if g.startswith("rack:") else _rack(dev[g]) for g in members}
    for g in sorted(rows[bottom], key=lambda g: (rack_of[g], g)):
        pos[g] = (x, ys[bottom], EP_W, 58)
        x += EP_W + EP_GAP
    width = max(x - EP_GAP - M, 900)

    peers: dict[str, set] = defaultdict(set)
    for ga, gb in pairs:
        peers[ga].add(gb)
        peers[gb].add(ga)
    for t in reversed(order[:-1]):          # upper rows: barycentre of already-placed peers
        def bary(g):
            xs = [pos[q][0] + pos[q][2] / 2 for q in peers[g] if q in pos]
            return (sum(xs) / len(xs) if xs else 0, g)
        names = sorted(rows[t], key=bary)
        slot = width / len(names)
        bw = min(200, slot - 16)
        for i, g in enumerate(names):
            pos[g] = (M + slot * i + (slot - bw) / 2, ys[t], bw, 52)

    # boxes
    for g, (bx, by, bw, bh) in pos.items():
        if g.startswith("rack:"):
            kinds = Counter(types[dev[n].data["device_type"].key[0]]["model"] for n in members[g])
            summary = "<br>".join(f"{k} × {_esc(m)}" for m, k in sorted(kinds.items()))
            fill = ROLE_FILL[Counter(role[n] for n in members[g]).most_common(1)[0][0]]
            p.box(g, bx, by, bw, bh, f"<b>{_esc(g[5:])}</b><br>{summary}",
                  _device_box_style(fill, 9), tooltip=", ".join(sorted(members[g])))
        else:
            model = types[dev[g].data["device_type"].key[0]]["model"]
            p.box(g, bx, by, bw, bh, f"<b>{_esc(g)}</b><br>{_esc(model)}",
                  _device_box_style(ROLE_FILL[role[g]], 10 if bw > 110 else 9),
                  tooltip=f"{g} · {model} · rack {rack_of[g]}")

    # ports: spread each box's lines along the facing side, ordered by the peer's x
    def cx(g):
        return pos[g][0] + pos[g][2] / 2

    side_slots: dict[tuple[str, str], list[str]] = defaultdict(list)   # (g, side) -> peers
    for ga, gb in sorted(pairs):
        if pos[ga][1] == pos[gb][1]:
            side_slots[(ga, "top")].append(gb)
            side_slots[(gb, "top")].append(ga)
        else:
            up, lo = (ga, gb) if pos[ga][1] < pos[gb][1] else (gb, ga)
            side_slots[(up, "bottom")].append(lo)
            side_slots[(lo, "top")].append(up)
    for k in side_slots:
        side_slots[k].sort(key=lambda q: (cx(q), q))

    def frac(g, side, peer):
        lst = side_slots[(g, side)]
        return round((lst.index(peer) + 0.5) / len(lst), 4)

    colour = FABRIC[fabric][1]
    leaf_rail = {}
    if fabric == "compute":   # colour compute lines by the rail of the switch end
        for (ga, gb), cs in pairs.items():
            for g in (ga, gb):
                if not g.startswith("rack:") and "leaf" in role[g]:
                    leaf_rail.setdefault(g, []).extend(cs)
        leaf_rail = {g: _rail_of(cs) for g, cs in leaf_rail.items()}
    for i, ((ga, gb), cs) in enumerate(sorted(pairs.items())):
        k = len(cs)
        rail = next((leaf_rail[g] for g in (ga, gb) if g in leaf_rail), 0)
        stroke = rail_colour(rail) if rail else colour
        kinds = ", ".join(f"{n} × {t}" for t, n in sorted(Counter(o.data["type"] for o in cs).items()))
        style = dict(endArrow="none", html=1, strokeColor=stroke, opacity=70,
                     strokeWidth=round(1 + min(4.0, math.log2(k)), 2))
        tip = f"{ga.replace('rack:', '')} ↔ {gb.replace('rack:', '')}: {k} cable(s) — {kinds}"
        if pos[ga][1] == pos[gb][1]:          # same row (ISL / MLAG peer link): arc above
            top_y = pos[ga][1] - 40 - 6 * (i % 4)
            p.line(f"e{i}", f"{pid}-{ga}", f"{pid}-{gb}", _st(
                **style, edgeStyle="none", curved=1, exitX=frac(ga, "top", gb), exitY=0,
                entryX=frac(gb, "top", ga), entryY=0), tooltip=tip,
                points=[((cx(ga) + cx(gb)) / 2, top_y)])
            continue
        up, lo = (ga, gb) if pos[ga][1] < pos[gb][1] else (gb, ga)
        p.line(f"e{i}", f"{pid}-{up}", f"{pid}-{lo}", _st(
            **style, edgeStyle="none", exitX=frac(up, "bottom", lo), exitY=1,
            entryX=frac(lo, "top", up), entryY=0), tooltip=tip)

    captions = {-1: "DATA-CENTRE CORE", 0: "SPINE / CORE", 1: "LEAF / ACCESS",
                2: "ENDPOINTS · bulk kit folded per rack"}
    for t in order:
        p.text(f"cap{t}", M, ys[t] - 26, width, 20, captions.get(t, ""), size=11,
               colour=MUTED, bold=True, labelBackgroundColor="#ffffff")
    n_sw = sum(len(rows[t]) for t in order[:-1])
    n_dev = sum(len(members[g]) for g in rows[bottom])
    _title(p, spec, title,
           f"{len(cables)} cables · {n_sw} switches/core devices · {n_dev} endpoint devices "
           f"in {len(rows[bottom])} boxes", width)
    items = ([("line", rail_colour(r), f"Rail {r}") for r in sorted(set(leaf_rail.values()))]
             or [("line", colour, FABRIC[fabric][0])])
    roles_here = dict.fromkeys(role[n] for g in pos for n in members[g])
    items += [("box", ROLE_FILL[r], ROLE_NAME[r]) for r in roles_here]
    _legend(p, M, ys[bottom] + 110, items)
    p.text("lw", M + 420, ys[bottom] + 110, 400, 18,
           "Line width grows with log₂(parallel cables); hover a line for the count.",
           size=10, colour=MUTED)
    return p


# --- rack elevations ------------------------------------------------------------------------

RACKS_PER_ROW = 8


def rack_groups(spec: dict, design: Design) -> list[tuple[str, list[str]]]:
    """[(page title, racks)]: one page per SU's compute racks, then everything else."""
    node_roles = export.node_roles(spec)
    dev, role = _index(design)
    su_of_rack: dict[str, int] = {}
    for n, o in dev.items():
        if role[n] in node_roles:
            su_of_rack[_rack(o)] = _su(o)
    racks = [o.key[0] for o in design.all("dcim.racks")]
    out = [(f"Rack elevations — SU {su}", [r for r in racks if su_of_rack.get(r) == su])
           for su in sorted(set(su_of_rack.values()))]
    rest = [r for r in racks if r not in su_of_rack]
    return out + ([("Rack elevations — management & storage", rest)] if rest else [])


def rack_page(spec: dict, types: dict, design: Design, racks: list[str],
              title: str = "Rack elevations", pid: str = "racks") -> _Page:
    """Front elevations, RACKS_PER_ROW to a row, with 0U PDUs as strips beside the frame."""
    dev, role = _index(design)
    uh = spec["racks"]["u_height"]
    kw = export.rack_power(types, design)
    p = _Page(title, pid)
    frame_w, frame_h = DEV_W + 2 * GUT, uh * UPX + 20
    col_w, row_h = frame_w + 6 * PDU_W + 80, frame_h + 110
    seen_roles: dict[str, None] = {}
    for idx, rack in enumerate(racks):
        x = M + 3 * PDU_W + (idx % RACKS_PER_ROW) * col_w
        top = M + 130 + (idx // RACKS_PER_ROW) * row_h
        members = sorted(n for n, o in dev.items() if _rack(o) == rack)
        inner_y = top + 10
        used = sum(types[dev[n].data["device_type"].key[0]]["u_height"]
                   for n in members if dev[n].data.get("position"))
        p.text(f"{rack}-h", x, top - 58, frame_w, 24, _esc(rack), size=16, bold=True,
               align="center")
        p.text(f"{rack}-kw", x, top - 34, frame_w, 20, _esc(
            f"{kw.get(rack, 0):.1f} kW peak / {export.rack_budget(spec, rack)} kW budget · "
            f"{used}/{uh} U"), size=10, colour=MUTED, align="center")
        p.box(f"{rack}-frame", x, top, frame_w, frame_h, "", _st(
            rounded=0, fillColor="#2b2f36", strokeColor="#111827"), layer="back")
        for u in range(1, uh + 1):
            uy = inner_y + (uh - u) * UPX
            p.box(f"{rack}-u{u}", x + GUT, uy, DEV_W, UPX, "", _st(
                fillColor="#f9fafb", strokeColor="#e5e7eb"), layer="back")
            for side, sx in (("l", x), ("r", x + GUT + DEV_W)):
                p.text(f"{rack}-n{side}{u}", sx, uy, GUT, UPX, str(u), size=8,
                       colour="#9ca3af", align="center")
        pdus = 0
        for n in members:
            o = dev[n]
            t = types[o.data["device_type"].key[0]]
            seen_roles[role[n]] = None
            if o.data.get("position"):
                h = t["u_height"]
                dy = inner_y + (uh - (o.data["position"] + h - 1)) * UPX
                label = (f"<b>{_esc(n)}</b> · {_esc(t['model'])}" if h < 2 else
                         f"<b>{_esc(n)}</b><br>{_esc(t['model'])} · {h}U")
                p.box(n, x + GUT + 1, dy + 1, DEV_W - 2, h * UPX - 2, label,
                      _device_box_style(ROLE_FILL[role[n]], 10),
                      tooltip=f"{n} · {t['model']} · U{o.data['position']}–"
                              f"U{o.data['position'] + h - 1}")
            else:          # 0U: PDUs mounted at the back, drawn beside the frame
                side = -1 if pdus % 2 == 0 else 1
                off = (pdus // 2) * (PDU_W + 4) + 6
                px = x - off - PDU_W if side < 0 else x + frame_w + off
                p.box(n, px, inner_y, PDU_W, uh * UPX, _esc(n), _device_box_style(
                    ROLE_FILL[role[n]], 9) + _st(horizontal=0), tooltip=f"{n} · {t['model']} · 0U")
                pdus += 1
    n_rows = (len(racks) + RACKS_PER_ROW - 1) // RACKS_PER_ROW
    width = min(len(racks), RACKS_PER_ROW) * col_w
    total = sum(kw.get(r, 0) for r in racks)
    _title(p, spec, f"{title} (front)",
           f"{len(racks)} racks · {total:.1f} kW peak · {racks[0]} … {racks[-1]}", max(width, 700))
    _legend(p, M, M + 130 + n_rows * row_h - 60,
            [("box", ROLE_FILL[r], ROLE_NAME[r]) for r in seen_roles])
    return p


# --- data-hall floor plan -------------------------------------------------------------------

FP_SCALE = 0.12          # px per mm on the floor plan


def floor_page(spec: dict, types: dict, design: Design) -> _Page | None:
    """Plan view of spec["hall"]: rows of racks to scale, cold/hot aisles, rack kW, and the
    overhead raceways. Returns None when the spec has no hall section."""
    hall = spec.get("hall")
    if not hall:
        return None
    dev, role = _index(design)
    kw = export.rack_power(types, design)
    node_roles = export.node_roles(spec)
    contained = hall.get("containment", "hot-aisle") != "none"
    kinds: dict[str, Counter] = defaultdict(Counter)
    for n, o in dev.items():
        if o.data.get("position"):
            kinds[_rack(o)][role[n]] += 1
    rw, rd = spec["racks"]["width_mm"] * FP_SCALE, spec["racks"]["depth_mm"] * FP_SCALE
    p = _Page("Data hall floor plan", "hall")
    x0, y = M + 60, M + 150
    rows = hall["rows"]
    widths = [len(r["racks"]) * rw for r in rows]
    width = max(widths)
    aisle_px = {k: hall[f"{k}_aisle_mm"] * FP_SCALE for k in ("cold", "hot")}

    def aisle(cid, ay, kind):
        h = aisle_px[kind]
        fill, ink, text = (("#dbeafe", "#1e40af", "COLD AISLE") if kind == "cold" else
                           ("#fee2e2", "#991b1b", "HOT AISLE · contained (doors + roof)")
                           if contained else ("#fef3c7", "#92400e", "REAR AISLE · uncontained (RDHx)"))
        p.box(cid, x0, ay, width, h, f"{text} · {hall[f'{kind}_aisle_mm'] / 1000:g} m",
              _st(html=1, fillColor=fill, strokeColor=ink if kind == "hot" else "none",
                  dashed=1 if kind == "hot" and contained else 0, fontColor=ink,
                  fontFamily=FONT, fontSize=11, fontStyle=1), layer="back")
        return h

    # first front-facing aisle, then each row followed by the aisle its back/front faces
    y += aisle("a-top", y, "cold" if rows[0]["front"] == "up" else "hot")
    for i, row in enumerate(rows):
        p.text(f"row-{row['name']}", M, y, 56, rd, f"<b>Row {_esc(row['name'])}</b>",
               size=12, align="center")
        for j, rack in enumerate(row["racks"]):
            rx = x0 + j * rw
            k = kinds[rack]
            fill = ("#d9f0b0" if any(k[r] for r in node_roles) else "#e9d5ff" if any(
                "storage" in r or "hps" in r for r in k) else "#e5e7eb")
            short = rack.replace("dgx-", "").replace("gb-", "")
            p.box(f"r-{rack}", rx, y, rw, rd, f"<b>{_esc(short)}</b><br>{kw.get(rack, 0):.1f} kW",
                  _st(html=1, whiteSpace="wrap", fillColor=fill, strokeColor="#374151",
                      fontFamily=FONT, fontSize=8, fontColor=INK, verticalAlign="top",
                      spacingTop=10),
                  tooltip=f"{rack} · {kw.get(rack, 0):.1f} kW peak · "
                          + ", ".join(f"{n} × {ROLE_NAME[r]}" for r, n in sorted(k.items())))
            fy = y if row["front"] == "up" else y + rd - 4     # front door = thick edge
            p.box(f"f-{rack}", rx + 2, fy, rw - 4, 4, "", _st(fillColor="#111827",
                                                              strokeColor="none"))
        p.box(f"tray-{row['name']}", x0, y + rd * 0.72, width, 4, "", _st(
            fillColor="#facc15", strokeColor="none", opacity=80))
        y += rd
        if i + 1 < len(rows):
            y += aisle(f"a{i}", y, "hot" if row["front"] == "up" else "cold")
    y += aisle("a-bot", y, "cold" if rows[-1]["front"] == "down" else "hot")
    total = sum(kw.values())
    _title(p, spec, "Data hall floor plan (to scale)", (
        f"{sum(len(r['racks']) for r in rows)} racks in {len(rows)} rows · "
        f"{spec['racks']['width_mm']}×{spec['racks']['depth_mm']} mm racks · "
        f"{total:.0f} kW IT peak · row length {width / FP_SCALE / 1000:.1f} m"), max(width, 700))
    _legend(p, M, y + 30, [
        ("box", "#d9f0b0", "Compute rack"), ("box", "#e5e7eb", "Management / network rack"),
        ("box", "#e9d5ff", "Storage rack"), ("line", "#111827", "Front door (cold side)"),
        ("line", "#facc15", "Overhead fibre raceway (above row)")])
    p.text("note", M + 420, y + 54, 520, 60, _esc(hall.get("note", "")), size=10,
           colour=MUTED)
    return p


# --- cooling: floor-plan overlay and hydraulic one-line ------------------------------------

def _fp_mapper(sc: dict):
    """metres (scene.json frame, Y up) -> floor-plan px, same scale/margins as floor_page."""
    k = FP_SCALE * 1000
    ys = [r["origin"][1] + r["depth"] / 2 for r in sc["racks"]]
    x_min = min(r["origin"][0] - r["width"] / 2 for r in sc["racks"])
    y_top = max(ys) + sc["hall"]["cold_aisle"]
    x0, y0 = M + 60, M + 150

    def px(x, y):
        return x0 + (x - x_min) * k, y0 + (y_top - y) * k

    return px, k


def cooling_floor_page(spec: dict, types: dict, design: Design) -> _Page | None:
    """Floor-plan overlay from the same scene.json geometry the 3D build uses: racks tinted by
    loop, doors/manifolds as a strip on the rear face, CDUs in row B's free slots, CRAHs at
    the far end, the plant block beyond the wall, supply/return headers and FWS mains."""
    if not spec.get("cooling") or not spec.get("hall"):
        return None
    from . import scene as sc_mod
    sc = sc_mod.scene_json(spec, types, design)
    cs = sc["cooling"]
    px, k = _fp_mapper(sc)
    sup, ret = cs["colours"]["supply"], cs["colours"]["return"]
    p = _Page("Cooling — floor plan", "coolfloor")
    loop_fill = {"rdhx": "#dcfce7", "dlc": "#dbeafe"}

    def rect(cid, cx, cy, w, d, label, style, tooltip=None, layer="front"):
        x, y = px(cx - w / 2, cy + d / 2)
        return p.box(cid, x, y, w * k, d * k, label, style, tooltip, layer)

    for r in sc["racks"]:
        c = r["cooling"]
        rect(f"r-{r['name']}", r["origin"][0], r["origin"][1], r["width"], r["depth"],
             f"<b>{_esc(r['name'].replace('dgx-', '').replace('gb-', ''))}</b><br>{c['kw']:.1f} kW",
             _st(html=1, whiteSpace="wrap", fillColor=loop_fill.get(c["loop"], "#e5e7eb"),
                 strokeColor="#374151", fontFamily=FONT, fontSize=7, fontColor=INK,
                 verticalAlign="top", spacingTop=6),
             tooltip=f"{r['name']} · {c['unit']} ({c['unit_kind']}) on {c['loop']} via {c['header']} branch {c['branch']} · {c['kw']} kW to liquid")
        fy = r["facing"][1]
        rear_y = r["origin"][1] - fy * r["depth"] / 2
        depth = 0.363 if c["unit_kind"] == "door" else 0.06        # door adds depth outboard of the rear face
        rect(f"u-{r['name']}", r["origin"][0], rear_y - fy * depth / 2, r["width"] - 0.02, depth, "",
             _st(fillColor="#166534" if c["unit_kind"] == "door" else "#9CA3AF", strokeColor="none", opacity=85),
             tooltip=f"{c['unit']} — {c['unit_kind']}")
    for c in cs["cdus"]:
        rect(f"cdu-{c['name']}", c["origin"][0], c["origin"][1], c["width"], c["depth"],
             f"<b>{_esc(c['name'])}</b><br>{c['kw']:.0f} kW", _device_box_style("#17becf", 8),
             tooltip=f"{c['name']} · {c['type']} · loop {c['loop']} · {c['kw']} kW at rated approach")
    for c in cs["crahs"]:
        rect(f"crah-{c['name']}", c["origin"][0], c["origin"][1], c["depth"], c["width"],
             f"<b>{_esc(c['name'])}</b><br>{c['kw']:.0f} kW", _device_box_style("#9edae5", 8),
             tooltip=f"{c['name']} · {c['type']} · residual air of the NVL72 row")
    for u in cs["plant"]["units"]:
        rect(f"plant-{u['name']}", u["origin"][0], u["origin"][1], u["width"], u["depth"],
             f"<b>{_esc(u['name'])}</b><br>{u['kw']:.0f} kW", _device_box_style("#1f77b4", 8),
             tooltip=f"{u['name']} · {u['type']} · {u['kw']} kW at {cs['plant']['fws_supply_c']}/{cs['plant']['fws_return_c']} C")
    wx, wy0 = px(cs["plant"]["wall_x"], max(r["origin"][1] for r in sc["racks"]) + 3)
    _, wy1 = px(0, min(r["origin"][1] for r in sc["racks"]) - 3)
    p.box("wall", wx, wy0, 0.2 * k, wy1 - wy0, "", _st(fillColor="#6b7280", strokeColor="none"), layer="back")
    p.text("wall-t", wx + 6, wy0, 120, 16, "hall wall (pipe sleeves)", size=8, colour=MUTED)

    def poly(cid, pts, colour, width, dashed=0, tip=None):
        (xa, ya), (xb, yb) = px(*pts[0][:2]), px(*pts[-1][:2])
        a = p.box(f"{cid}-a", xa - 1, ya - 1, 2, 2, "", _st(fillColor=colour, strokeColor="none"))
        b = p.box(f"{cid}-b", xb - 1, yb - 1, 2, 2, "", _st(fillColor=colour, strokeColor="none"))
        p.line(cid, a, b, _st(endArrow="none", html=1, strokeColor=colour, strokeWidth=width,
                              edgeStyle="none", dashed=dashed),
               tooltip=tip, points=[px(*q[:2]) for q in pts[1:-1]])

    for h in cs["headers"]:
        poly(f"hdr-{h['name']}-{h['kind']}", h["polyline"], sup if h["kind"] == "supply" else ret, 3,
             tip=f"{h['name']} {h['kind']} DN{h['dn']} at {h['z']} m · {h['flow_lpm']} / {h['rated_lpm']} l/min")
    for mline in cs["fws_mains"]:
        poly(f"fws-{mline['kind']}", mline["polyline"], sup if mline["kind"] == "supply" else ret, 4,
             tip=f"facility water {mline['kind']} main at {mline['z']} m")
    if cs.get("leak_detection"):
        for row in sc["hall"]["rows"]:
            rr = [r for r in sc["racks"] if r["row"] == row["name"]]
            fy = rr[0]["facing"][1]
            y = rr[0]["origin"][1] - fy * (rr[0]["depth"] / 2 + 0.45)
            xs = [r["origin"][0] for r in rr]
            poly(f"leak-{row['name']}", [[min(xs) - 0.3, y, 0], [max(xs) + 0.3, y, 0]], "#f59e0b", 1.5, dashed=1,
                 tip=f"leak-detection rope, row {row['name']} ({cs['leak_detection'].get('model', '')})")
    lines = [f"{k}: {v['load_kw']} kW → {len(v['cdus'])} × {v['cdu_kw']} kW CDU (N+1), "
             f"{v['tcs_supply_c']}/{v['tcs_return_c']} °C, {v['flow_lpm']} l/min" for k, v in cs["loops"].items()]
    lines.append(f"residual air {cs['residual_air_kw']} kW → {len(cs['crahs'])} CRAH (N+1); plant "
                 f"{cs['plant']['load_kw']} kW → {len(cs['plant']['units'])} modules (N+1), "
                 f"FWS {cs['plant']['fws_supply_c']}/{cs['plant']['fws_return_c']} °C")
    _title(p, spec, "Cooling — floor plan (to scale, same geometry as scene.json)", " · ".join(lines), max(p.w - M, 900))
    _legend(p, M, p.h + 30, [("box", "#dcfce7", "Rack on the RDHx loop (ChilledDoor)"),
                             ("box", "#dbeafe", "NVL72 rack on the DLC loop (manifold)"),
                             ("box", "#17becf", "CDU"), ("box", "#9edae5", "CRAH"),
                             ("box", "#1f77b4", "Plant module (outside)"),
                             ("line", sup, "Supply header / main"), ("line", ret, "Return header / main"),
                             ("line", "#f59e0b", "Leak-detection rope")])
    return p


def hydraulic_page(spec: dict, types: dict, design: Design) -> _Page | None:
    """One-line hydraulic schematic: plant modules → FWS header → CDUs / CRAHs → loop
    headers → every rack's door or manifold. One box per device, one line per coolant
    'cable' (supply and return in their colours), so it reads straight off NetBox."""
    if not spec.get("cooling"):
        return None
    from . import cooling as cl
    m = cl.model(spec, types, design)
    cs = spec["cooling"]
    sup, ret = cs["colours"]["supply"], cs["colours"]["return"]
    p = _Page("Cooling — hydraulic one-line", "hydraulic")
    cols = {0: M, 1: M + 300, 2: M + 600, 3: M + 900, 4: M + 1250}
    pos: dict[str, tuple[float, float, float, float]] = {}
    y = M + 130

    def put(name, col, label, fill, h=44, w=200, tip=None):
        nonlocal y
        yy = put.y[col]
        pos[name] = (cols[col], yy, w, h)
        p.box(name, cols[col], yy, w, h, label, _device_box_style(fill, 9), tooltip=tip)
        put.y[col] = yy + h + 10

    put.y = {c: y for c in cols}
    for u in m.plant_units:
        put(u, 0, f"<b>{_esc(u)}</b><br>{m.plant_kw_each} kW · {m.fws_supply_c}/{m.fws_return_c} °C", "#1f77b4", h=52)
    put(m.fws_header, 1, f"<b>{_esc(m.fws_header)}</b><br>facility water mains", "#aec7e8", h=60)
    for c in m.crah_units:
        put(c, 2, f"<b>{_esc(c)}</b><br>CRAH ≥ {m.crah_kw_each} kW", "#9edae5")
    for lp in m.loops.values():
        for c in lp.cdus:
            put(c, 2, f"<b>{_esc(c)}</b><br>{lp.cdu_kw} kW · {lp.tcs_supply_c}/{lp.tcs_return_c} °C", "#17becf", h=52)
        for row, hdr in lp.headers.items():
            put(hdr, 3, f"<b>{_esc(hdr)}</b><br>row {row} · {lp.header_flow_lpm(hdr):.0f} l/min", "#aec7e8")
        for r in lp.racks:
            put(lp.unit_of[r], 4, f"<b>{_esc(lp.unit_of[r])}</b> · {lp.rack_kw[r]:.1f} kW", "#2ca02c" if lp.unit_kind == "door" else "#98df8a", h=22, w=260)
    n = 0
    for a, ap, b, bp, fabric in cl.hydraulic_edges(design):
        if a not in pos or b not in pos:
            continue
        left, right = (a, b) if pos[a][0] <= pos[b][0] else (b, a)
        n += 1
        p.line(f"w{n}", f"{p.pid}-{left}", f"{p.pid}-{right}", _st(
            endArrow="none", html=1, strokeColor=sup if fabric.endswith("supply") else ret,
            strokeWidth=1.2, opacity=80, edgeStyle="orthogonalEdgeStyle", rounded=1,
            exitX=1, exitY=0.35 if fabric.endswith("supply") else 0.65,
            entryX=0, entryY=0.35 if fabric.endswith("supply") else 0.65),
            tooltip=f"{a}:{ap} → {b}:{bp} ({fabric})")
    caps = {0: "PLANT (outside)", 1: "FWS HEADER", 2: "CDUs · CRAHs", 3: "LOOP HEADERS", 4: "RACK UNITS"}
    for c, t in caps.items():
        p.text(f"cap{c}", cols[c], M + 104, 260, 20, t, size=11, colour=MUTED, bold=True)
    _title(p, spec, "Cooling — hydraulic one-line",
           f"{len(m.plant_units)} plant modules · {sum(len(l.cdus) for l in m.loops.values())} CDUs · "
           f"{len(m.crah_units)} CRAHs · {n} coolant runs · plant load {m.plant_load_kw:.0f} kW", 1500)
    _legend(p, M, max(put.y.values()) + 20, [("line", sup, "Supply"), ("line", ret, "Return")])
    return p


def drawio_xml(spec: dict, types: dict, design: Design) -> str:
    """The whole .drawio file: compute fabric per SU, the other fabrics, rack elevations,
    the floor plan (when the spec has a hall section) and the cooling pages (when it has
    a cooling section)."""
    node_roles = export.node_roles(spec)
    dev, role = _index(design)
    per_su = Counter(_su(o) for n, o in dev.items() if role[n] in node_roles)
    role_of_su = {_su(o): role[n] for n, o in dev.items() if role[n] in node_roles}
    fabrics = {o.data["custom_fields"]["dgx_fabric"] for o in design.all("dcim.cables")}
    pages: list[_Page] = []
    multi = len(node_roles) > 1
    for su in sorted(per_su):        # one page per SU; a wide SU (GB300: 144 trays) is folded
        if per_su[su] <= MAX_NODES_PER_ROW:
            pages.append(compute_page(spec, types, design, su, role_of_su[su]))
        else:
            pages.append(fabric_page(spec, types, design, "compute", f"compute{su}",
                                     su=su if multi else None))
    pages += [fabric_page(spec, types, design, f, f) for f in FABRIC
              if f != "compute" and f in fabrics]         # coolant fabrics: cooling pages below
    pages += [rack_page(spec, types, design, racks, title, f"racks{i}")
              for i, (title, racks) in enumerate(rack_groups(spec, design))]
    floor = floor_page(spec, types, design)
    pages += [floor] if floor else []
    pages += [pg for pg in (cooling_floor_page(spec, types, design), hydraulic_page(spec, types, design)) if pg]
    mx = ET.Element("mxfile", host="dgxnb", type="device")   # no timestamp: deterministic
    for page in pages:
        mx.append(page.element())
    ET.indent(mx)
    return ET.tostring(mx, encoding="unicode") + "\n"
