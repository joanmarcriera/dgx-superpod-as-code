"""Pure-Python layout for the Blender build (no bpy; unit-tested by tests/test_blender_layout.py).

Everything positional in the render is derived here from docs/scene.json plus the envelopes in
docs/blender/device-library.yaml, so a spec change re-renders correctly. Nothing in this module
names a specific rack or device.

Frames (all metres, Z up):
  world       scene.json frame.
  rack-local  origin = rack `origin` (floor footprint centre); +Y = rack `facing` (front door);
              +X = +Y rotated -90 deg about Z (for a rack facing +Y world, rack-local == world).
              0U PDU `side` is the sign of rack-local X.
  device      origin = centre of the front-ear plane at the device's bottom edge; +Y = front.
              A front-mounted device sits at rack-local (0, RAIL_Y, z_bottom).

Face fractions from the reference packs ("x from the left edge as seen from that side, y from
the top") map to device-local X as:  front  x = +W/2 - f*W      rear  x = -W/2 + f*W.

Usage (inside or outside Blender):
    from superpod import layout
    scene = layout.load_scene("docs/scene.json"); lib = layout.load_library(".../device-library.yaml")
    errors = layout.check_scene(scene, lib)          # [] when every device fits its rack
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
from collections import namedtuple

# ---------------------------------------------------------------- constants -----------------
U = 0.04445                    # one rack unit (EIA-310), metres
EAR_HALF = 0.4826 / 2          # 19" panel half-width (ear to ear)
FRONT_RAIL_SETBACK = 0.10      # AR3307B2 front rail plane behind the rack front (CHOICE, adjustable rails)
SIDE_WALL = 0.02               # frame post + side panel thickness inboard of the rack envelope
REAR_INSET = 0.04              # rear frame depth in front of which the 0U PDUs sit (clears the corner posts)
PDU_GAP = 0.006                # gap between two 0U PDUs on the same side
FACE_PROUD = {                 # how far a device's face/bezel stands proud of its ear plane
    "nvidia-dgx-h200": 0.025,  # champagne bezel frame (DGX envelope 897.1 mm includes it)
    "ddn-ai400x2t": 0.030,     # sculpted DDN bezel
    "dell-poweredge-r750": 0.012,   # honeycomb bezel
}
DEFAULT_PROUD = 0.004

# Overhead infrastructure, rack-local Y (towards the front) and absolute Z.
RACEWAY_Y, RACEWAY_Z, RACEWAY_W, RACEWAY_H = 0.05, 2.60, 0.167, 0.113   # yellow 6x4 fibre raceway
LADDER_Y, LADDER_Z, LADDER_W = 0.38, 2.92, 0.30                          # black ladder rack (copper)
BUSWAY_Y = {"A": -0.18, "B": -0.33, "C": -0.48}                           # Starline T5 per feed
BUSWAY_Z, BUSWAY_SECTION = 2.56, (0.111, 0.128)                           # centre height, W x H
LADDER_CROSS_DX = 0.45        # ladder crossover sits beside the raceway crossover
EXIT_Y = RACEWAY_Y             # cables leave every rack through the roof straight under the raceway
LANE_FRONT_X = 0.262           # front vertical cable managers: between rail ears and side panel
LANE_REAR_X = 0.115            # rear vertical fibre lane (clear of the three 0U PDUs)
LANE_REAR_Y = -0.462
FABRIC_ORDER = ["compute", "storage", "inband", "storage-eth", "oob", "mgmt"]
COPPER_FABRICS = {"oob", "mgmt"}   # ride the ladder rack; everything else rides the raceway
FIBRE_R = 0.0016               # single duplex/MPO fibre radius
BUNDLE_R_PER_SQRT = 0.0018     # bundle radius = this * sqrt(count)
TIE_PITCH = 0.30               # tie band spacing along a bundle

Box = namedtuple("Box", "x0 y0 z0 x1 y1 z1")
Port = namedtuple("Port", "face kind fabric x y z tie")   # device-local connector tip
PduPlace = namedtuple("PduPlace", "x y z0 length width depth")


# ---------------------------------------------------------------- loading -------------------
def load_scene(path):
    with open(path) as fh:
        return json.load(fh)


def load_library(path):
    """Load device-library.yaml. Blender's bundled Python has no PyYAML, so fall back to the
    repo's .venv (pure-Python PyYAML works across interpreter versions)."""
    try:
        import yaml  # noqa: WPS433
    except ImportError:
        repo = os.path.abspath(os.path.join(os.path.dirname(path), "..", ".."))
        for sp in glob.glob(os.path.join(repo, ".venv", "lib", "python*", "site-packages")):
            import sys
            sys.path.append(sp)
        try:
            import yaml  # noqa: WPS433,F811
        except ImportError as exc:
            raise SystemExit("PyYAML not found: run `uv sync` in the repo (creates .venv)") from exc
    with open(path) as fh:
        return yaml.safe_load(fh)


def hex_rgb(h):
    """'#RRGGBB' -> sRGB floats 0..1."""
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def srgb_to_linear(c):
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


def stable_int(*parts):
    """Deterministic small hash (Python's hash() is salted per process)."""
    return int(hashlib.md5("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


# ---------------------------------------------------------------- frames --------------------
def rack_yaw(rack):
    """Z rotation (radians) taking rack-local +Y onto the rack's facing vector."""
    fx, fy = rack["facing"][0], rack["facing"][1]
    return math.atan2(fy, fx) - math.pi / 2


def rack_to_world(rack, p):
    yaw = rack_yaw(rack)
    c, s = math.cos(yaw), math.sin(yaw)
    ox, oy, oz = rack["origin"]
    return (ox + c * p[0] - s * p[1], oy + s * p[0] + c * p[1], oz + p[2])


def box_to_world(rack, b):
    pts = [rack_to_world(rack, (x, y, z)) for x in (b.x0, b.x1) for y in (b.y0, b.y1) for z in (b.z0, b.z1)]
    xs, ys, zs = zip(*pts)
    return Box(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


RACK_KIND_KEY = {"sx": "rack", "nvl72": "nvl72_rack"}     # scene rack kind -> library entry
NVL72_PREFIX = "nvidia-dgx-gb300"


def rack_kind(rack):
    """'nvl72' for a rack holding GB300 trays/shelves (NVIDIA MGX frame), else 'sx' (APC SX)."""
    return "nvl72" if any(d["type"].startswith(NVL72_PREFIX) for d in rack["devices"]) else "sx"


def rack_dims(lib, kind="sx"):
    w, h, d = (v / 1000.0 for v in lib[RACK_KIND_KEY[kind]]["size"])
    return w, h, d


def rail_y(rack):
    return rack["depth"] / 2 - FRONT_RAIL_SETBACK


def rack_height(lib, rack=None):
    """Frame height; the hall's shared height (SX) when no rack is given."""
    return rack_dims(lib, rack_kind(rack) if rack else "sx")[1]


def rear_unit_depth(lib, dtype):
    """Depth a rear-mounted cooling unit adds behind the rack's rear face (door) or occupies
    inside the rack rear (NVL72 manifold strips)."""
    return lib[dtype]["size"][2] / 1000.0


# ---------------------------------------------------------------- envelopes -----------------
def device_dims(lib, dtype):
    """(W, H, D) metres from the library (W x H x D mm)."""
    w, h, d = (v / 1000.0 for v in lib[dtype]["size"])
    return w, h, d


def device_box(rack, dev, lib):
    """Rack-local AABB of a device's chassis (cables/transceivers excluded)."""
    if dev.get("mount") == "rear-0U":
        p = pdu_place(rack, dev, lib)
        return Box(p.x - p.width / 2, p.y - p.depth / 2, p.z0, p.x + p.width / 2, p.y + p.depth / 2, p.z0 + p.length)
    if dev.get("mount") == "rear-door":          # RDHx: hangs on the rear face, outside the frame
        dd = rear_unit_depth(lib, dev["type"])
        hw = rack["width"] / 2
        return Box(-hw, -rack["depth"] / 2 - dd, 0.0, hw, -rack["depth"] / 2, rack_height(lib, rack))
    if dev.get("mount") == "rear-manifold":      # NVL72 manifolds: strips inside the rear extension
        md = rear_unit_depth(lib, dev["type"])
        hw = rack["width"] / 2 - SIDE_WALL
        hm = lib[dev["type"]]["size"][1] / 1000.0
        z0 = (rack_height(lib, rack) - hm) / 2
        return Box(-hw, -rack["depth"] / 2 + 0.01, z0, hw, -rack["depth"] / 2 + 0.01 + md, z0 + hm)
    w, h, d = device_dims(lib, dev["type"])
    proud = FACE_PROUD.get(dev["type"], DEFAULT_PROUD)
    half = max(w / 2, EAR_HALF)
    ry = rail_y(rack)
    z0 = dev["z_bottom"]
    return Box(-half, ry - (d - proud), z0, half, ry + proud, z0 + h)


def pdu_place(rack, dev, lib):
    """0U PDU in the rear corner: outlet face towards the rear, `slot` stacks inboard."""
    width_mm, length_mm, depth_mm = lib[dev["type"]]["size"]
    width, length, depth = width_mm / 1000, length_mm / 1000, depth_mm / 1000
    inner = rack["width"] / 2 - SIDE_WALL
    x = dev["side"] * (inner - width / 2 - dev["slot"] * (width + PDU_GAP))
    y = -rack["depth"] / 2 + REAR_INSET + depth / 2
    z0 = (rack_height(lib) - length) / 2
    return PduPlace(x, y, z0, length, width, depth)


def rack_interior(rack, lib):
    h = rack_height(lib, rack)
    return Box(-rack["width"] / 2, -rack["depth"] / 2, 0.0, rack["width"] / 2, rack["depth"] / 2, h)


def rack_envelope(rack, lib):
    """Interior plus whatever hangs on the rear face (a ChilledDoor) — the footprint that must
    stay clear of aisles, CDUs and neighbours."""
    b = rack_interior(rack, lib)
    doors = [d for d in rack["devices"] if d.get("mount") == "rear-door"]
    if doors:
        b = Box(b.x0, b.y0 - rear_unit_depth(lib, doors[0]["type"]), b.z0, b.x1, b.y1, b.z1)
    return b


def boxes_overlap(a, b, tol=1e-4):
    return (a.x0 < b.x1 - tol and b.x0 < a.x1 - tol and a.y0 < b.y1 - tol and b.y0 < a.y1 - tol
            and a.z0 < b.z1 - tol and b.z0 < a.z1 - tol)


def box_inside(inner, outer, tol=1e-6):
    return (inner.x0 >= outer.x0 - tol and inner.y0 >= outer.y0 - tol and inner.z0 >= outer.z0 - tol
            and inner.x1 <= outer.x1 + tol and inner.y1 <= outer.y1 + tol and inner.z1 <= outer.z1 + tol)


def check_rack(rack, lib, boxes=None):
    """Return error strings for devices outside the rack or intersecting each other.
    `boxes` ({name: Box}, rack-local) overrides the computed envelopes (used to check the
    geometry Blender actually built)."""
    errors = []
    boxes = boxes or {d["name"]: device_box(rack, d, lib) for d in rack["devices"]}
    interior = rack_interior(rack, lib)
    envelope = rack_envelope(rack, lib)
    mount = {d["name"]: d.get("mount") for d in rack["devices"]}
    names = sorted(boxes)
    for n in names:
        # a rear door hangs outside the frame but inside the rack's envelope; everything else
        # must sit inside the frame
        if not box_inside(boxes[n], envelope if mount.get(n) == "rear-door" else interior):
            errors.append(f"{rack['name']}: {n} pokes outside the rack {tuple(round(v, 4) for v in boxes[n])}")
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if boxes_overlap(boxes[a], boxes[b]):
                errors.append(f"{rack['name']}: {a} intersects {b}")
    for d in rack["devices"]:
        if d.get("position") and abs(d["z_bottom"] - (lib["rack"]["u1_from_floor"] / 1000 + (d["position"] - 1) * U)) > 2e-3:
            errors.append(f"{rack['name']}: {d['name']} z_bottom disagrees with U{d['position']}")
    return errors


def check_scene(scene, lib):
    errors = []
    for r in scene["racks"]:
        errors.extend(check_rack(r, lib))
    return errors


def occupied_units(rack):
    used = set()
    for d in rack["devices"]:
        if d.get("position") and d["u_height"]:
            used.update(range(d["position"], d["position"] + d["u_height"]))
    return used


def empty_units(rack):
    """Front U positions (1-based) that get a blanking panel."""
    return [u for u in range(1, rack["u_height"] + 1) if u not in occupied_units(rack)]


def u_bottom(lib, u):
    return lib["rack"]["u1_from_floor"] / 1000 + (u - 1) * U


# ---------------------------------------------------------------- ports ---------------------
# Face layouts (fractions) transcribed from reference/*/README.md "Blender modelling notes";
# +-0.02. Kinds: osfp (twin-port, 2 MPO fibres), osfp_fin (finned twin-port), qsfp (AOC/DAC,
# one cable), rj45 (copper), c20/c14 (power inlet).
DGX_REAR_W = 0.442             # rear figure is the chassis body without ears
DGX_PSU_X = [0.015 + 0.16 * (i + 0.5) + 0.002 * i for i in range(6)]   # 6 PSUs across 0.015-0.985
DGX_OSFP_X = [0.37 + 0.06 * (k + 0.5) for k in range(4)]               # 4 twin cages, x 0.37-0.61
QM_GROUP_X = [0.034, 0.255, 0.474, 0.693]                              # 4 blocks of 4 cages per row
QM_PITCH = 0.0537


def _front_x(w, f):
    return w / 2 - f * w


def _rear_x(w, f):
    return -w / 2 + f * w


def qm9700_cage_centres(w, h):
    """[(row, col, x, z)] for the 32 front OSFP cages (row 0 = top)."""
    out = []
    for row, zf in ((0, 0.28), (1, 0.72)):
        for col in range(16):
            f = QM_GROUP_X[col // 4] + (col % 4 + 0.5) * QM_PITCH
            out.append((row, col, _front_x(w, f), h * (1 - zf)))
    return out


def sn4600c_port_centres(w, h):
    out = []
    for col in range(16):
        f = 0.045 + (col + 0.5) * (0.80 / 16)
        for row, zf in enumerate((0.22, 0.40, 0.60, 0.78)):
            out.append((row, col, _front_x(w, f), h * (1 - zf)))
    return out


def sn2201_port_centres(w, h):
    out = []
    for col in range(24):
        f = 0.05 + (col + 0.5) * (0.74 / 24) + 0.012 * (col // 6)
        for row, zf in enumerate((0.32, 0.68)):
            out.append((row, col, _front_x(w, f), h * (1 - zf)))
    return out


def q3400_cage_centres(w, h):
    """[(tier, row, col, x, z)] for the 72 front OSFP cages of a Q3400-RD (3 groups x 4 columns,
    3 tiers x 2 rows; fractions from reference/compute-dgx-gb300 'Q3400-RD front')."""
    groups = [(0.145, 0.361), (0.396, 0.611), (0.646, 0.861)]
    tiers = [((0.087, 0.169), (0.192, 0.272)), ((0.411, 0.498), (0.517, 0.603)), ((0.741, 0.820), (0.843, 0.922))]
    out = []
    for ti, rows in enumerate(tiers):
        for ri, (ya, yb) in enumerate(rows):
            for gi, (xa, xb) in enumerate(groups):
                for ci in range(4):
                    f = xa + (ci + 0.5) * (xb - xa) / 4
                    out.append((ti, ri, gi * 4 + ci, _front_x(w, f), h * (1 - (ya + yb) / 2)))
    return out


def sn5600_cage_centres(w, h):
    """[(row, col, x, z)] for the 64 front OSFP cages (4 groups x 4 columns x 2 rows x 2 stacked)."""
    groups = [(0.05, 0.273), (0.28, 0.495), (0.503, 0.715), (0.7225, 0.9375)]
    rows = [(0.17, 0.52), (0.59, 0.92)]
    out = []
    for ri, (ya, yb) in enumerate(rows):
        for st in range(2):                              # two stacked cages per cell
            zf = ya + (st + 0.5) * (yb - ya) / 2
            for gi, (xa, xb) in enumerate(groups):
                for ci in range(4):
                    f = xa + (ci + 0.5) * (xb - xa) / 4
                    out.append((ri * 2 + st, gi * 4 + ci, _front_x(w, f), h * (1 - zf)))
    return out


# GB300 compute tray front (reference/compute-dgx-gb300 'Compute tray front'; 483 mm face)
GB_TRAY_FACE = 0.483
GB_TRAY_OSFP = [(0.1265, 0.75), (0.2165, 0.75), (0.723, 0.745), (0.811, 0.745)]   # (x frac, y frac) rails 1-4
GB_TRAY_QSFP = [(0.805, 0.255), (0.848, 0.255)]                                   # BF3 P1, P2
GB_TRAY_RJ45 = {"BMC": (0.6155, 0.37), "BF3-BMC": (0.733, 0.23), "LOM": (0.29, 0.75)}
GB_NVS_RJ45 = {"console": 0.0975, "BMC": 0.145, "COMe1": 0.1935, "COMe2": 0.243, "leak": 0.292}   # y 0.71
GB_SHELF_PMC_RJ45 = (0.0805, 0.47)


def device_ports(dev, lib, rack_devices=()):
    """Cabled ports of a device in device-local coordinates (tip = where the cable leaves).

    Port fill for switches is a render CHOICE (the cable map is per device pair, not per port):
    compute IB 100 %, storage IB 75 %, in-band 50 %, OOB 80 % of RJ45s. GB300 kit: trays are
    cabled on the FRONT (4 XDR + 2 BF3 + 3 RJ45), the busbar clip is on the rear; Q3400-RD
    compute leaves 100 %, spines 100 %; SN5600 compute leaves 90 %, mgmt 50 %, spines 100 %."""
    t, role, name = dev["type"], dev.get("role", ""), dev["name"]
    if t not in lib or dev.get("mount") in ("rear-0U", "rear-manifold"):
        return []
    if dev.get("mount") == "rear-door":          # the fan cord is the door's only cable
        w, h, d = device_dims(lib, t)
        return [Port("rear", "c14", "power", w / 2 - 0.09, -d + 0.05, 0.25, None)]
    w, h, d = device_dims(lib, t)
    proud = FACE_PROUD.get(t, DEFAULT_PROUD)
    rear_y = -(d - proud)
    ports = []
    if t == "nvidia-dgx-gb300-compute-tray":
        yf = proud + 0.075
        for k, (fx, fy) in enumerate(GB_TRAY_OSFP):
            ports.append(Port("front", "osfp_fin", "compute", _front_x(GB_TRAY_FACE, fx), yf, h * (1 - fy), k + 1))
        for (fx, fy), fab in zip(GB_TRAY_QSFP, ("storage-eth", "inband")):
            ports.append(Port("front", "qsfp", fab, _front_x(GB_TRAY_FACE, fx), proud + 0.055, h * (1 - fy), None))
        for fx, fy in GB_TRAY_RJ45.values():
            ports.append(Port("front", "rj45", "oob", _front_x(GB_TRAY_FACE, fx), proud + 0.03, h * (1 - fy), None))
        ports.append(Port("rear", "busbar", "power", 0.0, rear_y - 0.01, h * 0.5, None))
        return ports
    if t == "nvidia-dgx-gb300-nvlink-switch-tray":
        for key in ("BMC", "COMe1", "COMe2"):
            ports.append(Port("front", "rj45", "oob", _front_x(GB_TRAY_FACE, GB_NVS_RJ45[key]), proud + 0.03, h * (1 - 0.71), None))
        ports.append(Port("rear", "busbar", "power", 0.0, rear_y - 0.01, h * 0.5, None))
        return ports
    if t == "nvidia-dgx-gb300-power-shelf":
        fx, fy = GB_SHELF_PMC_RJ45
        ports.append(Port("front", "rj45", "oob", _front_x(w, fx), proud + 0.03, h * (1 - fy), None))
        ports.append(Port("rear", "whip", "power", _rear_x(w, 0.24), rear_y - 0.04, h * 0.5, None))
        return ports
    if t == "nvidia-q3400-rd":
        tail = name.rsplit("-", 2)[-2] if "-cl" in name else ""
        rail = int(tail[1:]) if tail[:1] == "r" and tail[1:].isdigit() else None
        for i, (ti, ri, col, x, z) in enumerate(q3400_cage_centres(w, h)):
            tie = rail if rail else (i // 18) % 4 + 1
            ports.append(Port("front", "osfp_fin", "compute", x, proud + 0.075, z, tie))
        ports.append(Port("front", "rj45", "oob", _front_x(w, 0.915), proud + 0.03, h * (1 - 0.855), None))
        return ports
    if t == "nvidia-sn5600":
        fill = {"eth-compute-leaf": 0.9, "eth-mgmt-leaf": 0.5, "eth-storage-leaf": 0.5}.get(role, 1.0)
        fab = "storage-eth" if role == "eth-storage-leaf" else "inband"
        pts = sn5600_cage_centres(w, h)
        n = int(round(len(pts) * fill))
        for row, col, x, z in sorted(pts, key=lambda c: (c[1], c[0]))[:n]:
            ports.append(Port("front", "osfp", fab, x, proud + 0.070, z, None))
        ports.append(Port("front", "rj45", "oob", _front_x(w, 0.975), proud + 0.03, h * 0.5, None))
        return ports
    if t == "nvidia-dgx-h200":
        tip = rear_y - 0.070                      # OSFP (48 mm) + MPO boot
        for k, f in enumerate(DGX_OSFP_X):
            for p in (0, 1):
                x = _rear_x(DGX_REAR_W, f) + (p - 0.5) * 0.009
                ports.append(Port("rear", "osfp", "compute", x, tip, h * (1 - 0.71), 2 * k + p + 1))
        for f in (0.135, 0.185):                  # upper-left dual-port card: storage IB
            ports.append(Port("rear", "qsfp", "storage", _rear_x(DGX_REAR_W, f), rear_y - 0.055, h * (1 - 0.655), None))
        for f in (0.715, 0.765):                  # right card (slot 2): in-band Ethernet
            ports.append(Port("rear", "qsfp", "inband", _rear_x(DGX_REAR_W, f), rear_y - 0.055, h * (1 - 0.70), None))
        ports.append(Port("rear", "rj45", "oob", _rear_x(DGX_REAR_W, 0.38), rear_y - 0.035, h * (1 - 0.825), None))
        for i, f in enumerate(DGX_PSU_X):
            ports.append(Port("rear", "c20", "power", _rear_x(DGX_REAR_W, f), rear_y - 0.060, h * (1 - 0.935), i))
        return ports
    if t == "nvidia-qm9700":
        compute = role.startswith("ib-compute")
        fill = 1.0 if compute else 0.75
        cages = qm9700_cage_centres(w, h)
        n = int(round(len(cages) * fill))
        rail = None
        if role == "ib-compute-leaf":             # leaf rN serves rail N; name ends in r<N>
            tail = name.rsplit("-", 1)[-1]
            rail = int(tail[1:]) if tail[:1] == "r" and tail[1:].isdigit() else 1
        for i, (row, col, x, z) in enumerate(sorted(cages, key=lambda c: (c[1], c[0]))[:n]):
            tie = rail if rail else ((col // 2) % 8 + 1 if compute else None)
            ports.append(Port("front", "osfp_fin", "compute" if compute else "storage", x, 0.004 + 0.075, z, tie))
        ports.append(Port("front", "rj45", "oob", _front_x(w, 0.955), 0.004 + 0.03, h * 0.62, None))
        return ports
    if t == "mellanox-sn4600c":
        backend = role == "eth-storage-backend"
        pts = sn4600c_port_centres(w, h)
        n = len(pts) // 2 if not backend else 30
        fab = "storage-eth" if backend else "inband"
        for row, col, x, z in sorted(pts, key=lambda c: (c[1], c[0]))[:n]:
            ports.append(Port("front", "qsfp", fab, x, 0.004 + 0.055, z, None))
        ports.append(Port("front", "rj45", "oob", _front_x(w, 0.93), 0.004 + 0.03, h * 0.5, None))
        return ports
    if t == "nvidia-sn2201":
        pts = sn2201_port_centres(w, h)
        n = int(len(pts) * 0.8)
        for row, col, x, z in sorted(pts, key=lambda c: (c[1], c[0]))[:n]:
            ports.append(Port("front", "rj45", "oob", x, 0.004 + 0.03, z, None))
        for i in range(2):
            ports.append(Port("front", "qsfp", "oob", _front_x(w, 0.86 + 0.03 * i), 0.004 + 0.055, h * 0.5, None))
        return ports
    # Generic rear-cabled 1U/2U devices: (fabric, kind, x-fraction, z-fraction) per type.
    rear = {
        "nvidia-ufm-appliance-3-1": [("compute" if "ufm-c" in name else "storage", "osfp", 0.45, 0.5),
                                     ("compute" if "ufm-c" in name else "storage", "osfp", 0.55, 0.5),
                                     ("oob", "rj45", 0.30, 0.6)],
        "dell-poweredge-r750": [("inband", "qsfp", 0.55, 0.35), ("inband", "qsfp", 0.62, 0.35), ("oob", "rj45", 0.30, 0.7)],
        "ddn-ai400x2t": [("storage", "osfp", 0.30 + 0.12 * i, 0.45) for i in range(4)] + [("oob", "rj45", 0.12, 0.7)],
        "vast-cbox": [("inband" if j == 0 else "storage-eth", "qsfp", 0.10 + 0.22 * i + 0.05 * j, 0.35)
                      for i in range(4) for j in range(2)] + [("oob", "rj45", 0.93, 0.7)],
        "vast-dbox-df3015v2": [("storage-eth", "qsfp", f, 0.5) for f in (0.30, 0.36, 0.64, 0.70)] + [("oob", "rj45", 0.5, 0.5)],
    }.get(t, [])
    for fab, kind, fx, fz in rear:
        ports.append(Port("rear", kind, fab, _rear_x(w * 0.92, fx), rear_y - (0.07 if kind == "osfp" else 0.05), h * (1 - fz), None))
    for fx in (0.06, 0.94):                        # two PSUs, one per end
        ports.append(Port("rear", "c14", "power", _rear_x(w * 0.92, fx), rear_y - 0.045, h * 0.5, None))
    return ports


def power_assignments(rack, dev, lib):
    """[(power Port, PDU device)] for a device: PSUs and rPDUs are both sorted by rack-local X
    and split into contiguous groups, so cords never cross (DGX: PSU 1-2 -> outer -X PDU,
    3-4 -> inner -X PDU, 5-6 -> +X PDU; 2-PSU devices: one cord to each side)."""
    pdus = sorted((d for d in rack["devices"] if d.get("mount") == "rear-0U"),
                  key=lambda p: pdu_place(rack, p, lib).x)
    # device-local X == rack-local X for front-mounted devices (all of them in scene.json)
    psus = sorted((p for p in device_ports(dev, lib) if p.fabric == "power"), key=lambda p: p.x)
    if not pdus:
        return []
    return [(p, pdus[min(len(pdus) - 1, i * len(pdus) // len(psus))]) for i, p in enumerate(psus)]


def feed_letter(pdu_dev):
    return pdu_dev["name"].rsplit("-", 1)[-1].upper()


# ---------------------------------------------------------------- polylines -----------------
def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def dedupe(points, eps=1e-6):
    out = []
    for p in points:
        if not out or _len(_sub(p, out[-1])) > eps:
            out.append(tuple(p))
    return out


def fillet(points, radius, samples=6):
    """Round every interior corner of a polyline with a quadratic arc (bend radius control).
    Endpoints are preserved exactly."""
    pts = dedupe(points)
    if len(pts) < 3:
        return pts
    out = [pts[0]]
    for i in range(1, len(pts) - 1):
        p, a, b = pts[i], pts[i - 1], pts[i + 1]
        va, vb = _sub(a, p), _sub(b, p)
        la, lb = _len(va), _len(vb)
        cosang = (va[0] * vb[0] + va[1] * vb[1] + va[2] * vb[2]) / (la * lb)
        if cosang < -0.9999:                       # collinear: no corner
            out.append(p)
            continue
        r = min(radius, 0.45 * la, 0.45 * lb)
        s, e = _add(p, _mul(va, r / la)), _add(p, _mul(vb, r / lb))
        for k in range(samples + 1):
            t = k / samples
            q = _add(_add(_mul(s, (1 - t) ** 2), _mul(p, 2 * (1 - t) * t)), _mul(e, t * t))
            out.append(q)
    out.append(pts[-1])
    return dedupe(out)


def path_length(points):
    return sum(_len(_sub(points[i + 1], points[i])) for i in range(len(points) - 1))


def sample_along(points, pitch, margin):
    """[(position, unit tangent)] every `pitch` metres, skipping `margin` at both ends."""
    total = path_length(points)
    out, s, acc = [], margin, 0.0
    for i in range(len(points) - 1):
        seg = _sub(points[i + 1], points[i])
        L = _len(seg)
        if L == 0:
            continue
        while s <= acc + L and s <= total - margin:
            t = (s - acc) / L
            out.append((_add(points[i], _mul(seg, t)), _mul(seg, 1 / L)))
            s += pitch
        acc += L
    return out


# ---------------------------------------------------------------- overhead routing ----------
def racks_by_name(scene):
    return {r["name"]: r for r in scene["racks"]}


def crossover_x(scene):
    """X where inter-row bundles cross the hot aisle: centre of the racks holding no DGX
    (the mid-row management/storage block)."""
    xs = [r["origin"][0] for r in scene["racks"] if not any(d["type"] == "nvidia-dgx-h200" for d in r["devices"])]
    if not xs:
        xs = [r["origin"][0] for r in scene["racks"]]
    return sum(xs) / len(xs)


def exit_point(rack, lib, fabric, jitter=0.0):
    """Rack-roof point where a fabric's cables leave the rack (world)."""
    idx = FABRIC_ORDER.index(fabric) if fabric in FABRIC_ORDER else 0
    x = -0.20 + idx * 0.075 + jitter
    return rack_to_world(rack, (x, EXIT_Y, rack_height(lib)))


def tray_for(fabric):
    """(rack-local y, z of tray floor) of the overhead path a fabric uses."""
    if fabric in COPPER_FABRICS:
        return LADDER_Y, LADDER_Z + 0.012
    return RACEWAY_Y, RACEWAY_Z + 0.006


def bundle_radius(count):
    return BUNDLE_R_PER_SQRT * math.sqrt(max(count, 1))


def bundle_path(bundle, scene, lib, index=0):
    """World polyline (before filleting) for an inter-rack cable bundle:
    rack A roof -> up into its row's tray -> along the row (-> across the hot aisle at the
    crossover -> along the other row) -> down into rack B's roof. None for in-rack bundles."""
    rb = racks_by_name(scene)
    a, b = rb[bundle["a"]], rb[bundle["b"]]
    if a["name"] == b["name"]:
        return None
    fab = bundle["fabric"]
    r = bundle_radius(bundle["count"])
    h = stable_int(bundle["a"], bundle["b"], fab)
    ty, tz = tray_for(fab)
    width = LADDER_W if fab in COPPER_FABRICS else RACEWAY_W
    lat = ((h % 9) / 8.0 - 0.5) * max(0.0, width - 2 * r - 0.02)     # spread across the tray
    z = tz + r + 0.012 * ((h >> 4) % 3)                               # loose stacking
    jit = ((h >> 8) % 5 - 2) * 0.012
    pa, pb = exit_point(a, lib, fab, jit), exit_point(b, lib, fab, jit)

    def tray_pt(rack, x):
        # a point on the rack's row tray at world X = x, laterally offset
        p = rack_to_world(rack, (0.0, ty + lat, z))
        return (x, p[1], z)

    pts = [pa, (pa[0], pa[1], z), tray_pt(a, pa[0])]
    if a["row"] == b["row"]:
        pts += [tray_pt(a, pb[0])]
    else:
        cx = crossover_x(scene) + (LADDER_CROSS_DX if fab in COPPER_FABRICS else 0.0) + lat * 0.8
        pts += [tray_pt(a, cx), tray_pt(b, cx), tray_pt(b, pb[0])]
    pts += [(pb[0], pb[1], z), pb]
    return dedupe(pts)


def hall_extent(scene, lib):
    """World AABB of all racks (x0, y0, x1, y1)."""
    xs, ys = [], []
    for r in scene["racks"]:
        b = box_to_world(r, rack_interior(r, lib))
        xs += [b.x0, b.x1]
        ys += [b.y0, b.y1]
    return min(xs), min(ys), max(xs), max(ys)


def row_racks(scene, row_name):
    return [r for r in scene["racks"] if r["row"] == row_name]


def row_extent(scene, lib, row_name):
    boxes = [box_to_world(r, rack_interior(r, lib)) for r in row_racks(scene, row_name)]
    return (min(b.x0 for b in boxes), min(b.y0 for b in boxes), max(b.x1 for b in boxes), max(b.y1 for b in boxes))


def hot_aisle(scene, lib):
    """(x0, y0, x1, y1) of the contained aisle between the two rows (rears face each other)."""
    rows = [r["name"] for r in scene["hall"]["rows"]]
    e0, e1 = row_extent(scene, lib, rows[0]), row_extent(scene, lib, rows[1])
    lo, hi = sorted([e0, e1], key=lambda e: e[1])
    return (min(e0[0], e1[0]), lo[3], max(e0[2], e1[2]), hi[1])


def cold_aisle(scene, lib, row_name):
    """(x0, y0, x1, y1) of the cold aisle in front of a row."""
    e = row_extent(scene, lib, row_name)
    fy = row_racks(scene, row_name)[0]["facing"][1]
    w = scene["hall"]["cold_aisle"]
    return (e[0], e[3], e[2], e[3] + w) if fy > 0 else (e[0], e[1] - w, e[2], e[1])
