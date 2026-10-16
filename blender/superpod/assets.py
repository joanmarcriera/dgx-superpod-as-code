"""Device assets: each device type is modelled ONCE as a collection in device-local
coordinates (see layout.py) and instanced into the hall.

Face detail follows the fractional layouts in docs/blender/device-library.yaml and
reference/*/README.md "Blender modelling notes". Transceivers/plugs are part of the asset
(one variant per distinct set of cabled ports); the cables themselves are drawn by hall.py.

Trademarks: no logos unless build_scene.py runs with --brand.
"""
from __future__ import annotations

import hashlib
import math

import bpy

from . import blutil
from . import layout as L
from .blutil import MeshBuilder

ASSET_ROOT = "Assets"


class Assets:
    """Builds and caches asset collections; `for_device(rack, dev)` returns the collection to
    instance for that device."""

    def __init__(self, lib, brand=False):
        self.lib, self.brand, self.cache = lib, brand, {}
        self.root = blutil.collection(ASSET_ROOT)
        # assets live in the file but are not rendered directly (only through instances)
        bpy.context.view_layer.layer_collection.children[ASSET_ROOT].exclude = True

    def _coll(self, key):
        c = bpy.data.collections.new(key)
        self.root.children.link(c)
        return c

    def get(self, key, builder, *args):
        if key not in self.cache:
            c = self._coll(key)
            builder(c, *args)
            self.cache[key] = c
        return self.cache[key]

    def for_device(self, rack, dev):
        t = dev["type"]
        if dev.get("mount") == "rear-0U":
            feed = L.feed_letter(dev)
            return self.get(f"{t}|{feed}", build_pdu, self.lib, t, feed)
        if dev.get("mount") in UNIT_BUILDERS:          # rear door / NVL72 manifold: one asset each
            return self.get(t, UNIT_BUILDERS[dev["mount"]], self.lib, t)
        ports = L.device_ports(dev, self.lib)
        sig = hashlib.md5(repr([(p.face, p.kind, p.fabric, round(p.x, 4), round(p.z, 4)) for p in ports]).encode()).hexdigest()[:6]
        builder = BUILDERS.get(t, build_generic)
        return self.get(f"{t}|{sig}", builder, self.lib, t, ports, self.brand)

    def unit(self, kind, t):
        """Standalone cooling unit (cdu | crah | plant) of library type `t`."""
        return self.get(t, STANDALONE_BUILDERS[kind], self.lib, t)

    def rack(self, kind="sx"):
        if kind == "nvl72":
            return self.get("rack|NVL72-MGX", build_rack_nvl72, self.lib)
        return self.get("rack|AR3307B2", build_rack, self.lib)

    def blank(self):
        return self.get("blank|1U", build_blank)


# ---------------------------------------------------------------- shared parts --------------
def ears(mb, h, body_half, mat, y0=-0.003, y1=0.0, screws=True):
    for s in (-1, 1):
        mb.box(s * body_half, y0, 0.0005, s * L.EAR_HALF, y1, h - 0.0005, mat)
        if screws:
            for zf in ((0.5,) if h < 0.06 else (0.25, 0.75)):
                mb.cyl((s * (L.EAR_HALF - 0.008), y1 + 0.0012, h * zf), (0, 1, 0), 0.0035, 0.0024, "screw", seg=10)


def plugs(mb, ports):
    """Transceivers/plugs from each cabled port's face to its tip (tip = where the cable starts)."""
    for p in ports:
        d = 1.0 if p.face == "front" else -1.0
        if p.kind in ("osfp", "osfp_fin"):
            ln = 0.075 if p.kind == "osfp_fin" else 0.070
            y0 = p.y - d * ln
            yb = p.y - d * 0.020                           # end of the metal body
            mb.box(p.x - 0.01125, y0, p.z - 0.0065, p.x + 0.01125, yb, p.z + 0.0065, "osfp_body" if p.kind == "osfp" else "osfp_fin")
            if p.kind == "osfp_fin":                        # finned top
                for k in range(4):
                    fx = p.x - 0.008 + k * 0.0053
                    mb.box(fx - 0.0007, y0 + d * 0.004, p.z + 0.0065, fx + 0.0007, yb, p.z + 0.0085, "osfp_fin")
            mb.box(p.x - 0.004, yb, p.z - 0.009, p.x + 0.004, yb + d * 0.003, p.z - 0.0065, "plug_black")  # pull tab
            for s in (-1, 1):                               # two MPO connectors (green APC shells)
                cx = p.x + s * 0.0048
                mb.box(cx - 0.0038, yb, p.z - 0.0055, cx + 0.0038, p.y - d * 0.008, p.z + 0.0055, "mpo_green")
                mb.box(cx - 0.0025, p.y - d * 0.008, p.z - 0.0035, cx + 0.0025, p.y, p.z + 0.0035, "plug_black")
        elif p.kind == "qsfp":
            dac = p.fabric == "storage-eth"
            mb.box(p.x - 0.0091, p.y - d * 0.055, p.z - 0.0043, p.x + 0.0091, p.y - d * 0.016, p.z + 0.0043, "osfp_body")
            mb.box(p.x - 0.006, p.y - d * 0.016, p.z - 0.0035, p.x + 0.006, p.y, p.z + 0.0035,
                   "plug_black" if dac else ("jacket_9CA3AF" if p.fabric == "oob" else "jacket_00A7B5"))
        elif p.kind == "rj45":
            mb.box(p.x - 0.0058, p.y - d * 0.030, p.z - 0.0042, p.x + 0.0058, p.y - d * 0.012, p.z + 0.0042, "plug_grey")
            mb.box(p.x - 0.0045, p.y - d * 0.012, p.z - 0.0035, p.x + 0.0045, p.y, p.z + 0.0035, "jacket_9CA3AF")
        elif p.kind == "c20":
            mb.box(p.x - 0.016, p.y + 0.060, p.z - 0.013, p.x + 0.016, p.y + 0.014, p.z + 0.013, "plug_black")
            mb.cyl((p.x, p.y + 0.007, p.z), (0, 1, 0), 0.008, 0.014, "plug_black", seg=10)
        elif p.kind == "c14":
            mb.box(p.x - 0.011, p.y + 0.045, p.z - 0.008, p.x + 0.011, p.y + 0.012, p.z + 0.008, "plug_black")
            mb.cyl((p.x, p.y + 0.006, p.z), (0, 1, 0), 0.006, 0.012, "plug_black", seg=10)


def _ensure_jackets():
    blutil.jacket_material("#9CA3AF")
    blutil.jacket_material("#00A7B5")


def cage_opening(mb, x, z, w, h, y_face, d, mat="cage"):
    """A port cage: metal frame proud of the face with a dark opening."""
    mb.box(x - w / 2, y_face, z - h / 2, x + w / 2, y_face + d * 0.004, z + h / 2, mat)
    mb.box(x - w / 2 + 0.0012, y_face + d * 0.004, z - h / 2 + 0.0012, x + w / 2 - 0.0012, y_face + d * 0.0042, z + h / 2 - 0.0012, "plug_black")


def generic_rear(mb, w, h, rear_y, body_half, psu_mat="steel", fans=0, latch="blue_latch"):
    """PSU at each end + optional fan modules between, on the rear face."""
    rx = lambda f: -body_half + f * 2 * body_half          # noqa: E731
    y0, y1 = rear_y - 0.004, rear_y
    for f0, f1 in ((0.01, 0.17), (0.83, 0.99)):
        mb.box(rx(f0), y0, 0.002, rx(f1), y1, h - 0.002, "perf_silver_fine" if h > 0.05 else psu_mat)
        mb.box(rx(f1) - 0.008, y0 - 0.004, h * 0.2, rx(f1) - 0.003, y0, h * 0.8, latch)
    if fans:
        span = (0.83 - 0.17) / fans
        for i in range(fans):
            a, b = 0.17 + i * span + 0.004, 0.17 + (i + 1) * span - 0.004
            mb.box(rx(a), y0, 0.003, rx(b), y1, h - 0.003, "perf_black")
            mb.box(rx(a) + 0.004, y0 - 0.003, h * 0.35, rx(a) + 0.011, y0, h * 0.65, "tan_label")


def _text(coll, body, size, loc, xdir, ydir, mat, extrude=0.0006):
    """Text whose reading direction is `xdir` and glyph-up is `ydir` (world axes); it faces
    xdir x ydir."""
    from mathutils import Matrix, Vector
    x, y = Vector(xdir), Vector(ydir)
    rot = Matrix((x, y, x.cross(y))).transposed().to_euler()
    cu = bpy.data.curves.new(f"txt_{body}", "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    ob = bpy.data.objects.new(f"txt_{body}", cu)
    ob.location = loc
    ob.rotation_euler = rot
    cu.materials.append(blutil.material(mat))
    coll.objects.link(ob)
    return ob


# ---------------------------------------------------------------- DGX H200 (hero) -----------
def build_dgx(coll, lib, t, ports, brand):
    W, H, D = L.device_dims(lib, t)
    proud = L.FACE_PROUD[t]
    bh = L.DGX_REAR_W / 2
    rear_y = -(D - proud)
    fx = lambda f: W / 2 - f * W                           # noqa: E731  front fraction -> x
    rx = lambda f: -bh + f * 2 * bh                         # noqa: E731  rear fraction -> x
    zf = lambda f: H * (1 - f)                              # noqa: E731  from-top fraction -> z
    _ensure_jackets()
    body, frame, detail = MeshBuilder(), MeshBuilder(), MeshBuilder()
    body.box(-bh, rear_y, 0.002, bh, -0.004, H - 0.002, "dgx_chassis")
    for yy in (-0.30, -0.62):                               # top cover seams
        detail.box(-bh, yy - 0.0012, H - 0.0022, bh, yy + 0.0012, H - 0.0016, "dgx_dark")
    for s in (-1, 1):                                       # slide rails on the chassis sides
        detail.box(s * bh, rear_y + 0.03, H * 0.42, s * (bh + 0.0018), -0.03, H * 0.50, "rail_zinc")

    # front: champagne ears/frame, recessed metal-foam, logo pad, screws, LEDs
    frame.box(fx(0.06), -0.004, 0.0, W / 2, proud, H, "dgx_champagne")
    frame.box(-W / 2, -0.004, 0.0, fx(0.95), proud, H, "dgx_champagne")
    frame.box(fx(0.95), -0.004, zf(0.03), fx(0.06), proud - 0.004, H, "dgx_champagne")
    frame.box(fx(0.95), -0.004, 0.0, fx(0.06), proud - 0.004, zf(0.97), "dgx_champagne")
    detail.box(fx(0.95), -0.004, zf(0.97), fx(0.06), 0.004, zf(0.03), "dgx_dark")
    frame.rrect(fx(0.22), zf(0.95), fx(0.075), zf(0.05), 0.004, 0.019, 0.013, "dgx_pad", seg=6)
    for x in (fx(0.02), fx(0.98)):
        for f in (0.10, 0.48, 0.90):
            detail.cyl((x, proud + 0.0012, zf(f)), (0, 1, 0), 0.0048, 0.0024, "screw", seg=16)
    for f, mat in ((0.21, "led_green"), (0.27, "led_off"), (0.325, "led_amber_off")):
        detail.cyl((fx(0.98), proud + 0.0006, zf(f)), (0, 1, 0), 0.0036, 0.0012, "screw", seg=12)
        detail.cyl((fx(0.98), proud + 0.0014, zf(f)), (0, 1, 0), 0.0024, 0.0012, mat, seg=12)
    foam = MeshBuilder()
    x0, x1, z0, z1 = fx(0.95) + 0.0005, fx(0.06) - 0.0005, zf(0.968), zf(0.032)
    res = 0.0016                                            # ~2 verts per foam cell edge
    foam.grid(x0, z0, x1, z1, 0.0095, int((x1 - x0) / res), int((z1 - z0) / res), "dgx_foam")

    # rear: GPU tray hex grille, motherboard tray, 6 PSUs
    ry0, ry1 = rear_y - 0.004, rear_y + 0.002
    detail.box(rx(0.01), ry0, zf(0.595), rx(0.99), ry1, zf(0.004), "perf_silver")
    detail.box(rx(0.01), ry0 - 0.002, zf(0.604), rx(0.99), ry1, zf(0.595), "cage")          # tray lip
    for f in (0.47, 0.52):
        detail.cyl((rx(f), ry0 - 0.004, zf(0.53)), (0, 1, 0), 0.0065, 0.008, "tab_yg", seg=14)
    detail.box(rx(0.01), rear_y - 0.002, zf(0.865), rx(0.99), ry1, zf(0.604), "dgx_dark")
    for z_a, z_b, mat in ((0.625, 0.685, "perf_silver_fine"), (0.69, 0.74, "perf_silver_fine"), (0.745, 0.795, "perf_silver_fine")):
        detail.box(rx(0.03), ry0, zf(z_b), rx(0.33), rear_y, zf(z_a), mat)
        detail.box(rx(0.64), ry0, zf(z_b), rx(0.92), rear_y, zf(z_a), mat)
    detail.box(rx(0.35), ry0, zf(0.765), rx(0.63), rear_y, zf(0.62), "perf_silver_fine")
    for f in (0.135, 0.185):
        cage_opening(detail, rx(f), zf(0.655), 0.019, 0.0095, ry0, -1)
        cage_opening(detail, rx(f), zf(0.715), 0.019, 0.0095, ry0, -1)
    for f in (0.715, 0.765):
        cage_opening(detail, rx(f), zf(0.70), 0.019, 0.0095, ry0, -1)
    for f in L.DGX_OSFP_X:
        cage_opening(detail, rx(f), zf(0.71), 0.0245, 0.0155, ry0, -1)
    for f, mat in ((0.38, "plug_black"), (0.43, "plug_black")):
        detail.box(rx(f) - 0.008, ry0 - 0.002, zf(0.84), rx(f) + 0.008, ry0, zf(0.81), mat)
    detail.box(rx(0.55), ry0 - 0.001, zf(0.848), rx(0.63), ry0, zf(0.805), "ddn_gloss")
    detail.box(rx(0.565), ry0 - 0.0015, zf(0.84), rx(0.585), ry0 - 0.001, zf(0.815), "led_amber")
    detail.cyl((rx(0.47), ry0 - 0.001, zf(0.825)), (0, 1, 0), 0.0028, 0.002, "led_blue", seg=10)
    detail.cyl((rx(0.52), ry0 - 0.001, zf(0.825)), (0, 1, 0), 0.0022, 0.002, "led_green", seg=10)
    for f in L.DGX_PSU_X:
        a, b = f - 0.079, f + 0.079
        detail.box(rx(a), ry0, zf(0.996), rx(b), rear_y, zf(0.874), "perf_silver")
        detail.box(rx(f) - 0.018, ry0 - 0.001, zf(0.962), rx(f) + 0.018, ry0, zf(0.908), "plug_black")
        detail.box(rx(b) - 0.011, ry0 - 0.006, zf(0.958), rx(b) - 0.004, ry0, zf(0.905), "tab_yg")
        detail.box(rx(a) + 0.02, ry0 - 0.009, zf(0.994), rx(b) - 0.02, ry0 - 0.003, zf(0.982), "plug_black")
    plugs(detail, ports)

    body.build("dgx_body", coll, bevel=0.002)
    frame.build("dgx_frame", coll, bevel=0.0018, segments=3)
    detail.build("dgx_detail", coll)
    foam.build("dgx_foam", coll)
    if brand:   # NVIDIA wordmark on the pad, rotated 90 deg reading bottom-to-top (as shipped)
        _text(coll, "NVIDIA", 0.034, ((fx(0.22) + fx(0.075)) / 2, 0.0192, H * 0.62),
              (0, 0, 1), (1, 0, 0), "logo_emboss")


# ---------------------------------------------------------------- switches ------------------
def _switch_front_base(mb, w, h, d, face_mat="switch_black", body_mat="switch_black"):
    bh = w / 2
    mb.box(-bh, -(d - L.DEFAULT_PROUD), 0.0005, bh, -0.002, h - 0.0005, body_mat)
    mb.box(-bh, -0.002, 0.0, bh, L.DEFAULT_PROUD - 0.0005, h, face_mat)
    return bh


def build_qm9700(coll, lib, t, ports, brand):
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = _switch_front_base(mb, w, h, d)
    ears(mb, h, bh, "switch_black")
    yf = L.DEFAULT_PROUD - 0.0005
    for row, col, x, z in L.qm9700_cage_centres(w, h):
        cage_opening(det, x, z, 0.0235, 0.0152, yf, 1, "cage_dark")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    det.cyl((fx(0.018), yf + 0.001, h * 0.62), (0, 1, 0), 0.0016, 0.002, "led_green", seg=8)
    det.cyl((fx(0.018), yf + 0.001, h * 0.30), (0, 1, 0), 0.0028, 0.002, "screw", seg=10)
    det.box(fx(0.965), yf, h * 0.50, fx(0.945), yf + 0.002, h * 0.80, "plug_black")          # mgmt RJ45
    det.box(fx(0.935), yf, h * 0.55, fx(0.925), yf + 0.002, h * 0.80, "plug_black")          # USB
    for k in range(4):
        det.cyl((fx(0.915), yf + 0.001, h * (0.25 + 0.15 * k)), (0, 1, 0), 0.0011, 0.002, "led_green" if k < 3 else "led_off", seg=8)
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=7)
    plugs(det, ports)
    mb.build("qm9700_body", coll, bevel=0.0008)
    det.build("qm9700_detail", coll)


def build_sn4600c(coll, lib, t, ports, brand):
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = _switch_front_base(mb, w, h, d, face_mat="perf_black")
    ears(mb, h, bh, "switch_black")
    yf = L.DEFAULT_PROUD - 0.0005
    for row, col, x, z in L.sn4600c_port_centres(w, h):
        cage_opening(det, x, z, 0.0192, 0.0098, yf, 1, "cage")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    det.box(fx(0.945), yf, h * 0.55, fx(0.915), yf + 0.002, h * 0.72, "plug_black")
    det.box(fx(0.945), yf, h * 0.28, fx(0.915), yf + 0.002, h * 0.45, "plug_black")
    for k in range(3):
        det.cyl((fx(0.02), yf + 0.001, h * (0.3 + 0.2 * k)), (0, 1, 0), 0.0013, 0.002, "led_green", seg=8)
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=3)
    plugs(det, ports)
    mb.build("sn4600c_body", coll, bevel=0.001)
    det.build("sn4600c_detail", coll)


def build_sn2201(coll, lib, t, ports, brand):
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = _switch_front_base(mb, w, h, d, face_mat="switch_grey", body_mat="switch_grey")
    ears(mb, h, bh, "switch_grey")
    yf = L.DEFAULT_PROUD - 0.0005
    for row, col, x, z in L.sn2201_port_centres(w, h):
        det.box(x - 0.0063, yf, z - 0.0055, x + 0.0063, yf + 0.0008, z + 0.0055, "plug_black")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    for i in range(4):
        cage_opening(det, fx(0.86 + 0.03 * i), h * 0.5, 0.0185, 0.0095, yf, 1, "cage")
    for k in range(2):
        det.cyl((fx(0.02), yf + 0.001, h * (0.35 + 0.3 * k)), (0, 1, 0), 0.0012, 0.002, "led_green", seg=8)
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=0)
    plugs(det, ports)
    mb.build("sn2201_body", coll, bevel=0.0008)
    det.build("sn2201_detail", coll)


# ---------------------------------------------------------------- servers -------------------
def build_ufm(coll, lib, t, ports, brand):
    """UFM Enterprise Appliance 3.1: black 1U server, silver edge trim, drive bays, LEDs."""
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = 0.2175
    mb.box(-bh, -(d - L.DEFAULT_PROUD), 0.0005, bh, -0.002, h - 0.0005, "switch_black")
    mb.box(-bh, -0.002, 0.0, bh, 0.003, h, "switch_black")
    ears(mb, h, bh, "switch_black")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    det.box(-bh, 0.003, h - 0.0042, bh, 0.0048, h - 0.0006, "steel")                        # silver edge
    det.box(-bh, 0.003, 0.0006, bh, 0.0048, 0.0042, "steel")
    for i in range(8):
        a = 0.10 + i * 0.075
        det.box(fx(a + 0.068), 0.003, 0.006, fx(a), 0.0055, h - 0.006, "switch_grey")
        det.box(fx(a + 0.066), 0.0055, 0.009, fx(a + 0.010), 0.0062, h - 0.009, "perf_black")
        det.box(fx(a + 0.008), 0.0055, h * 0.62, fx(a + 0.004), 0.0065, h * 0.72, "led_green")
    det.box(fx(0.90), 0.003, 0.006, fx(0.72), 0.0052, h - 0.006, "switch_grey")               # control panel
    det.cyl((fx(0.88), 0.006, h * 0.5), (0, 1, 0), 0.0035, 0.002, "led_green", seg=12)
    det.cyl((fx(0.84), 0.006, h * 0.5), (0, 1, 0), 0.0025, 0.002, "led_blue", seg=12)
    det.box(fx(0.80), 0.0045, h * 0.35, fx(0.77), 0.006, h * 0.65, "plug_black")
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=0)
    plugs(det, ports)
    mb.build("ufm_body", coll, bevel=0.0008)
    det.build("ufm_detail", coll)


def build_r750(coll, lib, t, ports, brand):
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = 0.2175
    mb.box(-bh, -(d - L.FACE_PROUD[t]), 0.0005, bh, -0.002, h - 0.0005, "switch_black")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    mb.box(fx(0.93), -0.002, 0.004, fx(0.07), L.FACE_PROUD[t], h - 0.004, "perf_black_honey")          # bezel grille
    for s in (-1, 1):
        mb.box(s * bh, -0.003, 0.0005, s * L.EAR_HALF, 0.006, h - 0.0005, "steel")
    det.cyl((fx(0.03), 0.0065, h * 0.7), (0, 1, 0), 0.0025, 0.001, "led_blue", seg=10)
    det.cyl((fx(0.03), 0.0065, h * 0.5), (0, 1, 0), 0.0025, 0.001, "led_green", seg=10)
    generic_rear(det, w, h, -(d - L.FACE_PROUD[t]), bh, fans=0)
    plugs(det, ports)
    mb.build("r750_body", coll, bevel=0.002)
    det.build("r750_detail", coll)


# ---------------------------------------------------------------- storage -------------------
def _boolean_cut(target, cutters):
    """Apply a union of cutter meshes as a DIFFERENCE boolean (evaluated, then baked)."""
    tmp = bpy.data.collections.new("_cut_tmp")
    bpy.context.scene.collection.children.link(tmp)
    coll_prev = target.users_collection[0]
    coll_prev.objects.unlink(target)
    tmp.objects.link(target)
    cut = cutters.build("_cutter", tmp)
    mod = target.modifiers.new("cut", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = cut
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(target.evaluated_get(dg))
    target.modifiers.remove(mod)
    old = target.data
    target.data = me
    bpy.data.meshes.remove(old)
    bpy.data.objects.remove(cut)
    tmp.objects.unlink(target)
    coll_prev.objects.link(target)
    bpy.data.collections.remove(tmp)


def build_ddn(coll, lib, t, ports, brand):
    """DDN AI400X2T: glossy black sculpted bezel with slanted oval cut-outs over amber mesh."""
    w, h, d = L.device_dims(lib, t)
    proud = L.FACE_PROUD[t]
    _ensure_jackets()
    body, det = MeshBuilder(), MeshBuilder()
    bh = 0.215
    body.box(-bh, -(d - proud), 0.0005, bh, -0.002, h - 0.0005, "switch_black")
    for s in (-1, 1):                                       # steel ears with side vents
        body.box(s * bh, -0.004, 0.0, s * L.EAR_HALF, 0.0, h, "steel")
        for k in range(3):
            zc = h * (0.25 + 0.25 * k)
            det.box(s * (bh + 0.005), 0.0, zc - 0.009, s * (bh + 0.009), 0.0004, zc + 0.009, "plug_black")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    det.box(-0.214, 0.004, 0.006, 0.214, 0.008, h - 0.006, "amber_mesh")                     # mesh behind ovals
    bez = MeshBuilder()
    bez.box(-0.2185, 0.002, 0.003, 0.2185, proud, h - 0.003, "ddn_gloss")
    bezel = bez.build("ddn_bezel", coll)
    cut = MeshBuilder()
    for f0, f1 in ((0.015, 0.10), (0.12, 0.27), (0.29, 0.445), (0.47, 0.61)):
        a = (f1 - f0) * w / 2
        cut.ellipse(fx((f0 + f1) / 2), h * 0.5, a, h * 0.25, -0.01, 0.05, "ddn_gloss", seg=48, tilt=18.0)
    cut.rrect(fx(0.955), h * 0.2, fx(0.80), h * 0.8, -0.01, 0.05, 0.009, "ddn_gloss", seg=6)
    _boolean_cut(bezel, cut)
    mod = bezel.modifiers.new("bevel", "BEVEL")
    mod.width, mod.segments, mod.limit_method = 0.0035, 3, "ANGLE"
    mod.use_clamp_overlap = True
    det.ellipse(fx(0.705), h * 0.5, 0.040, h * 0.30, proud - 0.001, proud + 0.004, "ddn_gloss", seg=48, tilt=8.0)
    generic_rear(det, w, h, -(d - proud), bh, fans=0)
    plugs(det, ports)
    body.build("ddn_body", coll, bevel=0.001)
    det.build("ddn_detail", coll)
    if brand:
        _text(coll, "ddn", 0.03, (fx(0.705), proud + 0.0042, h * 0.47), (-1, 0, 0), (0, 0, 1), "logo_white")


def build_cbox(coll, lib, t, ports, brand):
    """VAST CBox (2U, 4 CNodes). Dimensions NOT FOUND in public sources: generic 4-sled 2U."""
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = 0.2175
    mb.box(-bh, -(d - L.DEFAULT_PROUD), 0.0005, bh, -0.002, h - 0.0005, "switch_black")
    ears(mb, h, bh, "switch_black")
    sled = (2 * bh - 0.006) / 4
    for i in range(4):
        x1 = bh - 0.003 - i * sled
        x0 = x1 - sled + 0.003
        det.box(x0, -0.002, 0.003, x1, 0.003, h - 0.003, "switch_black")
        det.box(x0 + 0.006, 0.003, h * 0.30, x1 - 0.006, 0.0036, h * 0.88, "perf_black")
        det.cyl(((x0 + x1) / 2, 0.012, h * 0.16), (1, 0, 0), 0.003, sled * 0.6, "steel", seg=10)
        for s in (-1, 1):
            det.box((x0 + x1) / 2 + s * sled * 0.3 - 0.002, 0.003, h * 0.12, (x0 + x1) / 2 + s * sled * 0.3 + 0.002, 0.012, h * 0.2, "steel")
        det.cyl((x1 - 0.008, 0.0038, h * 0.20), (0, 1, 0), 0.0017, 0.0015, "led_green", seg=8)
        det.cyl((x1 - 0.016, 0.0038, h * 0.20), (0, 1, 0), 0.0017, 0.0015, "led_blue" if i == 0 else "led_off", seg=8)
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=0, latch="salmon")
    plugs(det, ports)
    mb.build("cbox_body", coll, bevel=0.001)
    det.build("cbox_detail", coll)


def build_dbox(coll, lib, t, ports, brand):
    """VAST Ceres DBox DF-3015V2: ear, 11 E1.L bays, 3-fan module, 11 bays, ear."""
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = w / 2
    mb.box(-bh, -(d - L.DEFAULT_PROUD), 0.0005, bh, -0.002, h - 0.0005, "switch_black")
    fx = lambda f: w / 2 - f * w                            # noqa: E731
    ears(mb, h, bh, "vast_ear", screws=False)               # 19-inch mounting flanges
    for f0, f1 in ((0.0, 0.05), (0.95, 1.0)):
        mb.box(fx(f1), -0.002, 0.0, fx(f0), 0.004, h, "vast_ear")
        det.cyl((fx((f0 + f1) / 2), 0.0045, h * 0.5), (0, 1, 0), 0.0055, 0.002, "screw", seg=14)
    for base in (0.052, 0.682):
        pitch = 0.266 / 11
        for i in range(11):
            a = base + i * pitch
            det.box(fx(a + pitch - 0.002), -0.002, 0.003, fx(a), 0.003, h - 0.003, "vast_bay")
            det.box(fx(a + pitch * 0.65), 0.003, h * 0.52, fx(a + pitch * 0.35), 0.0036, h * 0.6, "switch_grey")
    det.box(fx(0.68), -0.002, 0.002, fx(0.32), 0.003, h - 0.002, "vast_fan")
    for f in (0.40, 0.53, 0.62):
        det.cyl((fx(f), 0.0032, h * 0.5), (0, 1, 0), 0.0185, 0.001, "plug_black", seg=24)
        det.cyl((fx(f), 0.0036, h * 0.5), (0, 1, 0), 0.0075, 0.0015, "steel", seg=16)
        for s in (-1, 1):
            det.cyl((fx(f), 0.0045, h * 0.5), (s, 0, 1), 0.0006, 0.048, "steel", seg=6)
    for f in (0.345, 0.36, 0.575):
        det.box(fx(f + 0.008), 0.003, h * 0.22, fx(f), 0.0036, h * 0.28, "led_yellow")
    generic_rear(det, w, h, -(d - L.DEFAULT_PROUD), bh, fans=0, latch="salmon")
    plugs(det, ports)
    mb.build("dbox_body", coll, bevel=0.0008)
    det.build("dbox_detail", coll)


def build_generic(coll, lib, t, ports, brand):
    w, h, d = L.device_dims(lib, t)
    mb = MeshBuilder()
    bh = min(w / 2, 0.2175)
    mb.box(-bh, -(d - L.DEFAULT_PROUD), 0.0005, bh, L.DEFAULT_PROUD, h - 0.0005, "switch_black")
    ears(mb, h, bh, "switch_black")
    plugs(mb, ports)
    mb.build(f"{t}_body", coll, bevel=0.001)


# ---------------------------------------------------------------- PDU, blank, rack ----------
def build_pdu(coll, lib, t, feed):
    """0U rPDU in its own frame: origin bottom centre, outlet face towards -Y (rack rear)."""
    width, length, depth = (v / 1000 for v in lib[t]["size"])
    mb, det = MeshBuilder(), MeshBuilder()
    mb.box(-width / 2, -depth / 2, 0.0, width / 2, depth / 2, length, "pdu_black")
    yf = -depth / 2
    for g in range(3):                                   # 3 branch groups of C13 + C19 outlets
        z0 = 0.14 + g * 0.50
        for k in range(8):
            z = z0 + k * 0.045
            for s in (-1, 1):
                det.box(s * 0.024 - 0.009, yf - 0.003, z - 0.008, s * 0.024 + 0.009, yf, z + 0.008, "switch_grey")
                det.box(s * 0.024 - 0.006, yf - 0.0034, z - 0.003, s * 0.024 + 0.006, yf - 0.003, z + 0.003, "plug_black")
        det.box(-0.045, yf - 0.001, z0 - 0.03, 0.045, yf, z0 - 0.022, blutil.tie_material(lib[t]["cord_tags"][feed]))
    det.box(-0.03, yf - 0.003, length - 0.13, 0.03, yf, length - 0.07, "lcd")
    det.box(-0.05, -depth / 2 - 0.0005, length - 0.05, 0.05, depth / 2 + 0.0005, length - 0.03,
            blutil.tie_material(lib[t]["cord_tags"][feed]))        # feed colour tag band
    det.cyl((0.0, 0.0, length + 0.02), (0, 0, 1), 0.012, 0.04, "plug_black", seg=12)   # inlet gland
    mb.build("pdu_body", coll, bevel=0.002)
    det.build("pdu_detail", coll)


def build_blank(coll):
    mb = MeshBuilder()
    mb.box(-L.EAR_HALF, 0.0, 0.0004, L.EAR_HALF, 0.003, L.U - 0.0004, "blank")
    mb.box(-L.EAR_HALF + 0.01, 0.003, L.U * 0.46, L.EAR_HALF - 0.01, 0.0036, L.U * 0.54, "blank")
    mb.build("blank_1u", coll, bevel=0.0008)


def build_rack(coll, lib):
    """APC NetShelter SX AR3307B2: 600 x 1200 x 2258, matt black, side panels on, no doors,
    zinc 19-inch rails, roof with a brush-strip cable entry under the raceway."""
    w, H, d = L.rack_dims(lib)
    hw, hd = w / 2, d / 2
    u0 = lib["rack"]["u1_from_floor"] / 1000
    ry = hd - L.FRONT_RAIL_SETBACK
    mb, rails = MeshBuilder(), MeshBuilder()
    for sx in (-1, 1):
        for sy in (-1, 1):
            mb.box(sx * (hw - 0.035), sy * (hd - 0.035), u0, sx * hw, sy * hd, H, "rack_black")
            mb.cyl((sx * (hw - 0.05), sy * (hd - 0.08), 0.015), (0, 0, 1), 0.02, 0.03, "steel", seg=12)
        mb.box(sx * (hw - 0.0015), -(hd - 0.035), u0, sx * hw, hd - 0.035, H - 0.04, "rack_black")   # side panel
        mb.box(sx * (hw - 0.035), -(hd - 0.035), H - 0.04, sx * hw, hd - 0.035, H, "rack_black")
    for sy in (-1, 1):
        mb.box(-hw + 0.035, sy * (hd - 0.035), H - 0.04, hw - 0.035, sy * hd, H, "rack_black")
        mb.box(-hw + 0.035, sy * (hd - 0.035), u0 - 0.01, hw - 0.035, sy * hd, u0 + 0.03, "rack_black")
    mb.box(-hw + 0.01, -hd + 0.01, 0.03, hw - 0.01, hd - 0.01, u0, "rack_black")                   # plinth
    ey = L.EXIT_Y
    mb.box(-hw + 0.035, -hd + 0.035, H - 0.006, hw - 0.035, ey - 0.06, H, "rack_black")            # roof
    mb.box(-hw + 0.035, ey + 0.06, H - 0.006, hw - 0.035, hd - 0.035, H, "rack_black")
    mb.box(-hw + 0.035, ey - 0.06, H - 0.012, -0.25, ey + 0.06, H, "rack_black")
    mb.box(0.25, ey - 0.06, H - 0.012, hw - 0.035, ey + 0.06, H, "rack_black")
    mb.box(-0.25, ey - 0.06, H - 0.014, 0.25, ey + 0.06, H - 0.004, "brush")
    top = u0 + 48 * L.U
    for yy in (ry, ry - 0.9):
        for sx in (-1, 1):
            rails.box(sx * 0.2245, yy - 0.0215, u0, sx * 0.2515, yy - 0.0035, top, "rail_zinc")
            rails.box(sx * 0.2515, yy - 0.08, u0, sx * 0.2535, yy - 0.0035, top, "rail_zinc")
    mb.build("rack_frame", coll, bevel=0.002)
    rails.build("rack_rails", coll, bevel=0.0006)


BUILDERS = {
    "nvidia-dgx-h200": build_dgx,
    "nvidia-qm9700": build_qm9700,
    "mellanox-sn4600c": build_sn4600c,
    "nvidia-sn2201": build_sn2201,
    "nvidia-ufm-appliance-3-1": build_ufm,
    "dell-poweredge-r750": build_r750,
    "ddn-ai400x2t": build_ddn,
    "vast-cbox": build_cbox,
    "vast-dbox-df3015v2": build_dbox,
}


# ================================================================ mixed pod: GB300 NVL72 kit ==
# Face fractions from reference/compute-dgx-gb300/README.md "Blender modelling notes" (±0.02);
# colours are the pack's estimates (champagne-bronze faceplates, black frame, silver lids).

def _tray_handles(mb, face_w, h, proud, mat="gb_champagne"):
    """Bent-loop handle at each end of a 1U tray faceplate (x 0-0.075 and 0.935-1.0)."""
    for s in (-1, 1):
        x0 = s * (face_w / 2 - 0.004)
        x1 = s * (face_w / 2 - 0.034)
        mb.box(min(x0, x1), proud, 0.004, max(x0, x1), proud + 0.016, h - 0.004, mat)
        mb.box(min(x0, x1) + 0.004, proud + 0.012, 0.009, max(x0, x1) - 0.004, proud + 0.016, h - 0.009, "plug_black")


def _champagne_face(mb, face_w, h, d, proud):
    """Tray body (silver lid/sides) + champagne faceplate between the EIA flanges."""
    bh = 0.438 / 2
    mb.box(-bh, -(d - proud), 0.0005, bh, -0.002, h - 0.0005, "gb_silver")
    mb.box(-face_w / 2, -0.002, 0.0, face_w / 2, proud, h, "gb_champagne")


def _tray_rear(det, h, rear_y):
    """Rear plate: outlet QD left, 2+2 NVLink blind-mate blocks, busbar clip centre, inlet QD
    right (fractions of the 438 mm body, seen from the rear)."""
    bw = 0.438
    rx = lambda f: -bw / 2 + f * bw                    # noqa: E731
    y0, y1 = rear_y - 0.003, rear_y
    det.box(rx(0.0), y0, 0.002, rx(1.0), y1, h - 0.002, "gb_silver")
    for f0, f1 in ((0.095, 0.234), (0.262, 0.408), (0.579, 0.727), (0.751, 0.900)):
        det.box(rx(f0), y0 - 0.012, h * 0.15, rx(f1), y0, h * 0.87, "plug_black")
        for f in (f0 + 0.03, f1 - 0.03):
            det.cyl((rx(f), y0 - 0.013, h * 0.72), (0, 1, 0), 0.004, 0.003, "steel", seg=10)
    det.box(rx(0.458), y0 - 0.02, h * 0.05, rx(0.524), y0, h * 0.98, "busbar_clip")
    for f, col in ((0.04, "qd_hot"), (0.96, "qd_cold")):
        det.cyl((rx(f), y0 - 0.008, h * 0.37), (0, 1, 0), 0.010, 0.016, "qd_metal", seg=14)
        det.ring((rx(f), y0 - 0.017, h * 0.37), (0, 1, 0), 0.0105, 0.004, col, seg=14)


def build_gb_tray(coll, lib, t, ports, brand):
    """DGX GB300 compute tray: champagne faceplate, mesh modules, 4 XDR OSFP, 2 BF3 QSFP,
    3 RJ45, 8 E1.S bays, IO board; rear per _tray_rear."""
    w, h, d = L.device_dims(lib, t)
    proud = L.DEFAULT_PROUD
    fw = L.GB_TRAY_FACE
    fx = lambda f: fw / 2 - f * fw                       # noqa: E731
    zf = lambda f: h * (1 - f)                           # noqa: E731
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    _champagne_face(mb, fw, h, d, proud)
    _tray_handles(det, fw, h, proud)
    yf = proud
    # square-hole mesh modules left (x 0.075-0.33) and right (0.669-0.93)
    for a, b in ((0.075, 0.33), (0.669, 0.93)):
        det.box(fx(b), yf, 0.004, fx(a), yf + 0.0015, h - 0.004, "perf_black_sq")
    for fxv, fyv in L.GB_TRAY_OSFP:
        cage_opening(det, fx(fxv), zf(fyv), 0.0235, 0.0152, yf, 1, "cage_dark")
    for fxv, fyv in L.GB_TRAY_QSFP:
        cage_opening(det, fx(fxv), zf(fyv), 0.019, 0.0098, yf, 1, "cage")
    for fxv, fyv in L.GB_TRAY_RJ45.values():
        det.box(fx(fxv) - 0.0063, yf, zf(fyv) - 0.0055, fx(fxv) + 0.0063, yf + 0.001, zf(fyv) + 0.0055, "plug_black")
    # E1.S block: 8 slim vertical carriers in 4 pairs, x 0.347-0.590
    span = (0.590 - 0.347) / 8
    for i in range(8):
        a = 0.347 + i * span
        det.box(fx(a + span - 0.003), yf, h * 0.08, fx(a + 0.003), yf + 0.003, h * 0.92, "vast_bay" if i < 4 else "gb_champagne")
        det.box(fx(a + span * 0.7), yf + 0.003, h * 0.82, fx(a + span * 0.3), yf + 0.0036, h * 0.88, "led_green" if i < 4 else "led_off")
    # front-IO board x 0.60-0.66: USB/DP column + LEDs + pull tab
    det.box(fx(0.66), yf, h * 0.05, fx(0.60), yf + 0.001, h * 0.95, "switch_black")
    det.box(fx(0.657) - 0.004, yf, zf(0.60) - 0.004, fx(0.637) + 0.004, yf + 0.001, zf(0.20), "plug_grey")
    for k, m in enumerate(("led_green", "led_blue", "led_amber_off")):
        det.cyl((fx(0.605 + 0.012 * k), yf + 0.0012, zf(0.10)), (0, 1, 0), 0.0012, 0.002, m, seg=8)
    det.box(fx(0.667), yf, h * 0.3, fx(0.661), yf + 0.006, h * 0.7, "plug_black")
    _tray_rear(det, h, -(d - proud))
    plugs(det, [p for p in ports if p.kind in ("osfp_fin", "qsfp", "rj45")])
    mb.build("gbtray_body", coll, bevel=0.001)
    det.build("gbtray_detail", coll)


def build_nvs_tray(coll, lib, t, ports, brand):
    """NVLink switch tray: champagne faceplate, LED/USB cluster, 5 RJ45, blank panel, pull tab."""
    w, h, d = L.device_dims(lib, t)
    proud = L.DEFAULT_PROUD
    fw = L.GB_TRAY_FACE
    fx = lambda f: fw / 2 - f * fw                       # noqa: E731
    zf = lambda f: h * (1 - f)                           # noqa: E731
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    _champagne_face(mb, fw, h, d, proud)
    _tray_handles(det, fw, h, proud)
    yf = proud
    for k, f in enumerate((0.085, 0.105, 0.127)):
        det.cyl((fx(f), yf + 0.001, zf(0.25)), (0, 1, 0), 0.0015, 0.002, ("led_green", "led_off", "led_blue")[k], seg=8)
    for k in range(5):
        det.cyl((fx(0.154 + 0.008 * k), yf + 0.001, zf(0.25)), (0, 1, 0), 0.0012, 0.002, "led_green", seg=8)
    det.box(fx(0.305), yf, zf(0.33), fx(0.278), yf + 0.001, zf(0.18), "plug_grey")
    for f in L.GB_NVS_RJ45.values():
        det.box(fx(f) - 0.0063, yf, zf(0.71) - 0.0055, fx(f) + 0.0063, yf + 0.001, zf(0.71) + 0.0055, "plug_black")
    det.box(fx(0.935), yf, 0.004, fx(0.332), yf + 0.0008, h - 0.004, "gb_champagne_dark")
    det.box(fx(0.935), yf, h * 0.28, fx(0.925), yf + 0.006, h * 0.72, "plug_black")
    _tray_rear(det, h, -(d - proud))
    plugs(det, [p for p in ports if p.kind == "rj45"])
    mb.build("nvs_body", coll, bevel=0.001)
    det.build("nvs_detail", coll)


def build_power_shelf(coll, lib, t, ports, brand):
    """33 kW power shelf: black, PMC RJ45 + reset, 6 PSU modules (mesh, fan, 2 LEDs, handle);
    rear: AC whip connector, busbar connector, 2 RJ45."""
    w, h, d = L.device_dims(lib, t)
    proud = L.DEFAULT_PROUD
    fx = lambda f: w / 2 - f * w                         # noqa: E731
    zf = lambda f: h * (1 - f)                           # noqa: E731
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = w / 2
    mb.box(-bh, -(d - proud), 0.0005, bh, -0.002, h - 0.0005, "shelf_black")
    mb.box(-L.EAR_HALF, -0.002, 0.0, L.EAR_HALF, proud, h, "shelf_black")
    yf = proud
    fxv, fyv = L.GB_SHELF_PMC_RJ45
    det.box(fx(fxv) - 0.0063, yf, zf(fyv) - 0.0055, fx(fxv) + 0.0063, yf + 0.001, zf(fyv) + 0.0055, "plug_black")
    det.cyl((fx(0.085), yf + 0.001, zf(0.79)), (0, 1, 0), 0.0012, 0.002, "led_red", seg=8)
    for c in (0.169, 0.308, 0.448, 0.589, 0.73, 0.876):
        a, b = c - 0.0675, c + 0.0675
        det.box(fx(b) + 0.002, yf, 0.004, fx(a) - 0.002, yf + 0.0015, h - 0.004, "perf_black_sq")
        det.cyl((fx(c), yf + 0.0016, h * 0.5), (0, 1, 0), h * 0.42, 0.001, "plug_black", seg=24)
        det.cyl((fx(c), yf + 0.002, h * 0.5), (0, 1, 0), h * 0.16, 0.002, "steel", seg=12)
        for k in range(2):
            det.cyl((fx(a + 0.012 + 0.009 * k), yf + 0.0018, zf(0.2)), (0, 1, 0), 0.0012, 0.002, "led_green", seg=8)
        det.box(fx(b) - 0.004, yf, h * 0.25, fx(b) - 0.009, yf + 0.008, h * 0.75, "plug_black")
    rear_y = -(d - proud)
    det.box(-bh, rear_y - 0.003, 0.002, bh, rear_y, h - 0.002, "shelf_black")
    rx = lambda f: -bh + f * w                           # noqa: E731
    det.box(rx(0.17), rear_y - 0.02, h * 0.3, rx(0.31), rear_y, h * 0.6, "plug_black")
    for k in range(7):
        det.cyl((rx(0.185 + 0.02 * k), rear_y - 0.021, h * 0.45), (0, 1, 0), 0.003, 0.004, "steel", seg=8)
    det.box(rx(0.46), rear_y - 0.02, h * 0.05, rx(0.52), rear_y, h * 0.98, "busbar_clip")
    for k in range(2):
        det.box(rx(0.86), rear_y - 0.002, h * (0.1 + 0.45 * k), rx(0.89), rear_y, h * (0.4 + 0.45 * k), "plug_black")
    plugs(det, [p for p in ports if p.kind == "rj45"])
    mb.build("shelf_body", coll, bevel=0.001)
    det.build("shelf_detail", coll)


def build_q3400(coll, lib, t, ports, brand):
    """Q3400-RD: 4U black face, 72 twin OSFP cages in 3 tiers, vent bands, FNM cage, mgmt
    ports; rear 8 fans + busbar connector."""
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = _switch_front_base(mb, w, h, d)
    ears(mb, h, bh, "switch_black")
    yf = L.DEFAULT_PROUD - 0.0005
    fx = lambda f: w / 2 - f * w                         # noqa: E731
    for ti, ri, col, x, z in L.q3400_cage_centres(w, h):
        cage_opening(det, x, z, 0.0235, 0.0152, yf, 1, "cage_dark")
    for ya, yb in ((0.28, 0.40), (0.61, 0.73)):
        det.box(fx(0.861), yf, h * (1 - yb), fx(0.145), yf + 0.001, h * (1 - ya), "perf_black_sq")
    cage_opening(det, fx(0.08), h * (1 - 0.89), 0.0235, 0.0152, yf, 1, "cage_dark")       # FNM
    for k in range(3):
        det.box(fx(0.945 - 0.02 * k) - 0.0063, yf, h * 0.08, fx(0.945 - 0.02 * k) + 0.0063, yf + 0.001, h * 0.21, "plug_black")
    for k in range(3):
        det.cyl((fx(0.90 + 0.012 * k), yf + 0.001, h * 0.285), (0, 1, 0), 0.0015, 0.002, "led_green", seg=8)
    rear_y = -(d - L.DEFAULT_PROUD)
    rx = lambda f: -bh + f * w                           # noqa: E731
    det.box(-bh, rear_y - 0.003, 0.002, bh, rear_y, h - 0.002, "switch_black")
    for (a, b) in ((0.013, 0.20), (0.21, 0.395), (0.61, 0.79), (0.805, 0.99)):
        for (za, zb) in ((0.0, 0.48), (0.50, 0.96)):
            det.box(rx(a), rear_y - 0.006, h * za + 0.003, rx(b), rear_y, h * zb, "perf_black")
            det.cyl(((rx(a) + rx(b)) / 2, rear_y - 0.004, h * (za + zb) / 2), (0, 1, 0), (rx(b) - rx(a)) * 0.42, 0.002, "plug_black", seg=24)
            det.cyl((rx(a) + 0.01, rear_y - 0.004, h * za + 0.012), (0, 1, 0), 0.0015, 0.002, "led_teal", seg=8)
    det.box(rx(0.47), rear_y - 0.02, h * 0.61, rx(0.53), rear_y, h * 0.84, "busbar_clip")
    plugs(det, ports)
    mb.build("q3400_body", coll, bevel=0.0008)
    det.build("q3400_detail", coll)


def build_sn5600(coll, lib, t, ports, brand):
    """SN5600(D): 2U perforated black face, 64 OSFP cages in 4 groups, SFP28, mgmt RJ45;
    rear 4 fans + busbar plug."""
    w, h, d = L.device_dims(lib, t)
    _ensure_jackets()
    mb, det = MeshBuilder(), MeshBuilder()
    bh = _switch_front_base(mb, w, h, d, face_mat="perf_black")
    ears(mb, h, bh, "gb_champagne_dark")
    yf = L.DEFAULT_PROUD - 0.0005
    fx = lambda f: w / 2 - f * w                         # noqa: E731
    for row, col, x, z in L.sn5600_cage_centres(w, h):
        cage_opening(det, x, z, 0.0235, 0.0152, yf, 1, "cage_dark")
    cage_opening(det, fx(0.03), h * (1 - 0.645), 0.014, 0.009, yf, 1, "cage")
    det.box(fx(0.975) - 0.0063, yf, h * 0.36, fx(0.975) + 0.0063, yf + 0.001, h * 0.64, "plug_black")
    det.box(fx(0.945) - 0.005, yf, h * 0.53, fx(0.945) + 0.005, yf + 0.001, h * 0.62, "plug_grey")
    rear_y = -(d - L.DEFAULT_PROUD)
    rx = lambda f: -bh + f * w                           # noqa: E731
    det.box(-bh, rear_y - 0.003, 0.002, bh, rear_y, h - 0.002, "switch_black")
    for (a, b) in ((0.022, 0.208), (0.218, 0.39), (0.59, 0.77), (0.78, 0.965)):
        det.box(rx(a), rear_y - 0.006, 0.004, rx(b), rear_y, h - 0.004, "perf_black")
        det.cyl(((rx(a) + rx(b)) / 2, rear_y - 0.004, h / 2), (0, 1, 0), (rx(b) - rx(a)) * 0.44, 0.002, "plug_black", seg=24)
        det.box(rx(a) + 0.01, rear_y - 0.012, h * 0.85, rx(b) - 0.01, rear_y - 0.004, h * 0.93, "gb_champagne")
    det.box(rx(0.46), rear_y - 0.02, h * 0.02, rx(0.54), rear_y, h * 0.47, "busbar_clip")
    plugs(det, ports)
    mb.build("sn5600_body", coll, bevel=0.0008)
    det.build("sn5600_detail", coll)


def build_rack_nvl72(coll, lib):
    """NVIDIA MGX / ORV3-derived NVL72 frame: 600 x 2236 x 1068 + 132 mm rear extension (the
    scene depth of 1200 includes it), 19-inch rails, black side panels, no doors, wedge seismic
    plinth, rear bezel fingers, centre busbar cover and 4 cable cartridges behind the trays.
    Origin: floor footprint centre; +Y front (same frame as the SX rack)."""
    w, H, d0 = L.rack_dims(lib, "nvl72")
    ext = lib["nvl72_rack"].get("rear_extension_frame_depth", 132) / 1000
    d = d0 + ext
    hw, hd = w / 2, d / 2
    u0 = lib["rack"]["u1_from_floor"] / 1000
    ry = hd - L.FRONT_RAIL_SETBACK
    mb, rails, det = MeshBuilder(), MeshBuilder(), MeshBuilder()
    y_rear_main = -hd + ext                             # main frame rear posts; extension behind
    for sx in (-1, 1):
        for sy in (hd, y_rear_main):
            mb.box(sx * (hw - 0.035), sy - 0.035 if sy > 0 else sy, u0, sx * hw, sy if sy > 0 else sy + 0.035, H, "rack_black")
        mb.box(sx * (hw - 0.02), -hd, u0, sx * hw, -hd + 0.02, H - 0.1, "rack_black")      # extension posts
        mb.box(sx * (hw - 0.0015), y_rear_main, u0, sx * hw, hd - 0.035, H - 0.04, "rack_black")   # side panel
        mb.box(sx * (hw - 0.0015), -hd, u0 + 0.2, sx * hw, y_rear_main, H - 0.1, "rack_black")     # extension side
    for sy in (hd, y_rear_main):
        mb.box(-hw + 0.035, sy - 0.035 if sy > 0 else sy, H - 0.04, hw - 0.035, sy if sy > 0 else sy + 0.035, H, "rack_black")
    mb.box(-hw + 0.035, y_rear_main, H - 0.006, hw - 0.035, hd - 0.035, H, "rack_black")      # roof
    mb.box(-hw + 0.035, -hd + 0.02, H - 0.1, hw - 0.035, y_rear_main, H - 0.094, "rack_black")   # extension top rail
    # wedge seismic plinth front and rear + base
    mb.box(-hw + 0.01, -hd + 0.01, 0.0, hw - 0.01, hd - 0.01, u0, "rack_black")
    mb.prism([(-hw, 0.0), (hw, 0.0), (hw, 0.0), (hw - 0.0, u0 * 0.6), (-hw, u0 * 0.6)], hd - 0.01, hd + 0.08, "rack_black")
    top = u0 + 48 * L.U
    for yy in (ry, ry - 0.75):
        for sx in (-1, 1):
            rails.box(sx * 0.2245, yy - 0.0215, u0, sx * 0.2515, yy - 0.0035, min(top, H - 0.02), "rail_zinc")
    # busbar cover (centre rear, full height) and 4 cable cartridges beside it
    det.box(-0.018, y_rear_main + 0.02, u0 + 0.12, 0.018, y_rear_main + 0.06, H - 0.14, "busbar_cover")
    for xx in (-0.19, -0.09, 0.09, 0.19):
        det.box(xx - 0.03, y_rear_main + 0.04, H * 0.24, xx + 0.03, y_rear_main + 0.11, H * 0.76, "cartridge")
    for k in range(5):                                  # cross-bars of the cartridge cage
        zc = H * (0.24 + 0.13 * k)
        det.box(-0.23, y_rear_main + 0.1, zc - 0.006, 0.23, y_rear_main + 0.115, zc + 0.006, "rack_black")
    for sx in (-1, 1):                                  # rear bezel: cable-management fingers
        for k in range(14):
            zc = u0 + 0.15 + k * 0.14
            det.box(sx * (hw - 0.07), -hd + 0.005, zc - 0.012, sx * (hw - 0.02), -hd + 0.03, zc + 0.012, "rack_black")
    mb.build("rack_nvl72_frame", coll, bevel=0.002)
    rails.build("rack_nvl72_rails", coll, bevel=0.0006)
    det.build("rack_nvl72_detail", coll)


# ================================================================ mixed pod: cooling kit =====
# Dimensions from reference/cooling-schneider/README.md §6; the units are instanced from the
# positions in scene.json["cooling"]. Frame: origin = floor footprint centre, +Y = facing
# (CDU / CRAH / plant) or the rack rear face centre with -Y outboard (door, manifold).

def build_door(coll, lib, t):
    """Motivair ChilledDoor M8: 600 x 2258 x 363 mm hung on the rack's rear face. Hinge on
    the +X side (left seen from the rear, CHOICE), brushed-stainless control door strip on
    the latch side, perforated mesh over the coil with 5 EC fans and a blue LED glow, two
    hose stubs on top at the hinge side (top feed), floor guide wheel under the latch."""
    w, H, dd = (v / 1000 for v in lib[t]["size"])
    hw = w / 2
    y1, y0 = 0.0, -dd                                   # rack rear face -> outboard
    mb, det = MeshBuilder(), MeshBuilder()
    strip = lib[t].get("control_strip", {}).get("width_frac", 0.25) * w
    # frame: sides, top, bottom, hinge posts, latch-side stainless door
    mb.box(-hw, y0, 0.0, hw, y0 + 0.03, 0.08, "door_black")
    mb.box(-hw, y0, H - 0.06, hw, y1, H, "door_black")
    mb.box(hw - 0.04, y0, 0.0, hw, y1, H, "door_black")
    mb.box(-hw, y0, 0.0, -hw + strip, y1, H, "stainless")
    mb.box(-hw + strip, y0, 0.0, hw - 0.04, y0 + 0.004, H, "door_black")          # outer skin behind the mesh
    # mesh over the coil area, coil fins behind it (copper/aluminium tint)
    det.box(-hw + strip + 0.01, y0 + 0.004, 0.09, hw - 0.05, y0 + 0.0055, H - 0.07, "coil_fin")
    det.box(-hw + strip + 0.01, y0 - 0.0006, 0.09, hw - 0.05, y0, H - 0.07, "perf_black_fine")
    # 5 EC fans in a column, rings visible through the mesh
    fr = (hw - 0.05 - (-hw + strip + 0.01)) * 0.46
    xc = (-hw + strip + 0.01 + hw - 0.05) / 2
    for k in range(5):
        zc = 0.09 + (H - 0.16) * (k + 0.5) / 5
        det.ring((xc, y0 + 0.004, zc), (0, 1, 0), fr, 0.008, "steel", seg=36)                 # guard ring
        det.ring((xc, y0 + 0.004, zc), (0, 1, 0), fr * 0.62, 0.006, "steel", seg=28)
        det.cyl((xc, y0 + 0.006, zc), (0, 1, 0), fr * 0.30, 0.03, "plug_black", seg=20)       # EC motor hub
        for j in range(7):                              # seven wide blades, seen through the mesh
            ang = j * 2 * math.pi / 7
            cx_, cz_ = xc + math.cos(ang) * fr * 0.62, zc + math.sin(ang) * fr * 0.62
            det.prism([(cx_ - fr * 0.06, cz_ - fr * 0.30), (cx_ + fr * 0.14, cz_ - fr * 0.22),
                       (cx_ + fr * 0.10, cz_ + fr * 0.26), (cx_ - fr * 0.12, cz_ + fr * 0.20)],
                      y0 + 0.006, y0 + 0.010, "fan_blade")
    det.box(xc - 0.004, y0 + 0.002, 0.10, xc + 0.004, y0 + 0.004, H - 0.08, "led_blue_strip")   # LED strip
    # stainless control door: small HMI, latch handle, logo plate
    det.box(-hw + strip / 2 - 0.045, y0 - 0.004, H * 0.62, -hw + strip / 2 + 0.045, y0, H * 0.645, "lcd")
    det.box(-hw + strip / 2 - 0.05, y0 - 0.003, H * 0.615, -hw + strip / 2 + 0.05, y0 - 0.004, H * 0.65, "plug_black")
    det.cyl((-hw + strip / 2, y0 - 0.012, H * 0.50), (0, 1, 0), 0.009, 0.024, "steel", seg=12)
    det.box(-hw + 0.02, y0 - 0.0015, H * 0.90, -hw + strip - 0.02, y0, H * 0.925, "door_badge")
    # hinge barrels (+X), floor guide wheel (-X)
    for zc in (0.25, H / 2, H - 0.25):
        det.cyl((hw + 0.012, y0 + 0.02, zc), (0, 0, 1), 0.012, 0.09, "steel", seg=12)
    det.cyl((-hw + 0.06, y0 + 0.05, 0.03), (1, 0, 0), 0.03, 0.025, "plug_black", seg=16)
    # hose stubs on top (hinge side): supply outboard, return inboard
    for xo in (0.08, 0.17):
        det.cyl((hw - xo, y0 + dd * 0.45, H + 0.01), (0, 0, 1), 0.016, 0.06, "steel", seg=12)
        det.ring((hw - xo, y0 + dd * 0.45, H + 0.03), (0, 0, 1), 0.021, 0.012, "qd_metal", seg=12)
    # fan power inlet (C14) low on the hinge side
    det.box(hw - 0.105, y0 + 0.02, 0.22, hw - 0.075, y0 + 0.05, 0.28, "plug_black")
    mb.build("door_body", coll, bevel=0.0015)
    det.build("door_detail", coll)


def build_manifold(coll, lib, t):
    """NVL72 rear manifolds: two vertical stainless strips inside the rear extension (left =
    return, right = supply seen from the rear), a QD pair per tray, FD83 fittings on top."""
    w, hm, md = (v / 1000 for v in lib[t]["size"])
    hw = w / 2
    lf, rf = lib[t]["strips"]["left_frac"], lib[t]["strips"]["right_frac"]
    mb, det = MeshBuilder(), MeshBuilder()
    z0 = (2.236 - hm) / 2
    for f, col in ((lf, "qd_hot"), (rf, "qd_cold")):
        x = hw - f * w                                  # seen from the rear: left = +X
        mb.cyl((x, 0.01 + md / 2, z0 + hm / 2), (0, 0, 1), 0.024, hm, "stainless", seg=16)
        for k in range(27):
            zc = z0 + 0.12 + k * (hm - 0.5) / 27
            det.cyl((x, 0.01 + md / 2 - 0.02, zc), (0, 1, 0), 0.009, 0.05, "qd_metal", seg=10)
            det.ring((x, 0.01 + md / 2 - 0.045, zc), (0, 1, 0), 0.0095, 0.004, col, seg=10)
    for f in (0.36, 0.64):                              # FD83 top fittings (hose connections)
        x = hw - f * w
        det.cyl((x, 0.07, z0 + hm + 0.03), (0, 0, 1), 0.02, 0.06, "qd_metal", seg=14)
        det.cyl((x, 0.07, z0 + hm + 0.0), (0, 1, 0), 0.016, 0.08, "stainless", seg=12)
    mb.build("manifold_body", coll)
    det.build("manifold_detail", coll)


def build_cdu(coll, lib, t):
    """Floor-standing Motivair MCDU cabinet: black, HMI at chest height, rotary handle,
    plinth vent, dotted LED lattice, 4 top connection stubs (PRI rear pair, SEC front pair)."""
    w, H, d = (v / 1000 for v in lib[t]["size"])
    hw, hd = w / 2, d / 2
    mb, det = MeshBuilder(), MeshBuilder()
    mb.box(-hw, -hd, 0.04, hw, hd, H, "cdu_black")
    mb.box(-hw + 0.02, -hd + 0.02, 0.0, hw - 0.02, hd - 0.02, 0.04, "plug_black")
    det.box(-hw + 0.03, hd, 0.06, hw - 0.03, hd + 0.004, 0.16, "perf_black")                # plinth vent
    det.box(-hw + 0.03, hd, H - 0.08, hw - 0.03, hd + 0.003, H - 0.02, "perf_black")
    det.box(-0.11, hd, 1.35, 0.11, hd + 0.006, 1.50, "lcd")                                   # touch HMI
    det.cyl((hw - 0.09, hd + 0.015, 1.15), (0, 1, 0), 0.016, 0.03, "steel", seg=14)          # handle
    for i in range(9):                                  # LED lattice dots
        for j in range(5):
            det.cyl((-hw + 0.10 + i * (w - 0.2) / 8, hd + 0.001, 0.35 + j * 0.16), (0, 1, 0), 0.004, 0.002, "led_blue_dim", seg=8)
    det.box(hw - 0.17, hd + 0.0005, 1.62, hw - 0.05, hd + 0.0025, 1.65, "door_badge")
    for x, y in ((-0.26, -d * 0.2), (-0.10, -d * 0.2), (0.10, d * 0.2), (0.26, d * 0.2)):   # top stubs (sockets)
        det.cyl((x, y, H + 0.03), (0, 0, 1), 0.04, 0.06, "steel", seg=16)
        det.ring((x, y, H + 0.06), (0, 0, 1), 0.052, 0.012, "qd_metal", seg=16)
    mb.build("cdu_body", coll, bevel=0.003)
    det.build("cdu_detail", coll)


def build_crah(coll, lib, t):
    """Uniflair HDCV perimeter CRAH (white RAL 9003): three panel bays, a front supply grille,
    display top-left, top connection stubs (supply/return)."""
    w, H, d = (v / 1000 for v in lib[t]["size"])
    hw, hd = w / 2, d / 2
    mb, det = MeshBuilder(), MeshBuilder()
    mb.box(-hw, -hd, 0.05, hw, hd, H, "crah_white")
    mb.box(-hw + 0.02, -hd + 0.02, 0.0, hw - 0.02, hd - 0.02, 0.05, "plug_black")
    for k in range(3):
        xa = -hw + 0.02 + k * (w - 0.04) / 3
        det.box(xa + 0.01, hd, 0.3, xa + (w - 0.04) / 3 - 0.01, hd + 0.003, H - 0.3, "crah_panel")
        det.box(xa + 0.03, hd, 0.4, xa + (w - 0.04) / 3 - 0.03, hd + 0.005, 1.6, "perf_silver_fine")
    det.box(-hw + 0.08, hd, H - 0.25, -hw + 0.30, hd + 0.006, H - 0.12, "lcd")
    for x, mat in ((-w * 0.3, "qd_cold"), (w * 0.3, "qd_hot")):
        det.cyl((x, 0.0, H + 0.03), (0, 0, 1), 0.04, 0.06, "steel", seg=16)
        det.ring((x, 0.0, H + 0.06), (0, 0, 1), 0.052, 0.012, mat, seg=16)
    mb.build("crah_body", coll, bevel=0.003)
    det.build("crah_detail", coll)


def build_plant(coll, lib, t):
    """Uniflair BCEF free-cooling chiller module: grey panelled box, 14 roof fans (2 x 7),
    V-coil banks along both flanks, isolator, low-level water connections at the wall end."""
    w, H, d = (v / 1000 for v in lib[t]["size"])        # w = 2.2 across, d = 10.72 along the wall
    hw, hd = w / 2, d / 2
    mb, det = MeshBuilder(), MeshBuilder()
    mb.box(-hw, -hd, 0.1, hw, hd, H - 0.25, "plant_grey")
    mb.box(-hw + 0.05, -hd + 0.05, 0.0, hw - 0.05, hd - 0.05, 0.1, "plug_black")
    mb.box(-hw + 0.02, -hd + 0.02, H - 0.25, hw - 0.02, hd - 0.02, H - 0.05, "plant_grey")
    nfan = lib[t].get("roof_fans", {}).get("count", 14)
    cols = nfan // 2
    for i in range(cols):
        for j in range(2):
            yc = -hd + 0.5 + (d - 1.0) * (i + 0.5) / cols
            xc = (j - 0.5) * (w * 0.46)
            det.cyl((xc, yc, H - 0.02), (0, 0, 1), 0.47, 0.10, "fan_cowl", seg=32)              # fan cowl
            det.cyl((xc, yc, H + 0.03), (0, 0, 1), 0.44, 0.004, "perf_black", seg=32)             # guard
            det.cyl((xc, yc, H + 0.00), (0, 0, 1), 0.10, 0.08, "steel", seg=16)
            for j in range(6):                          # blades under the guard
                ang = j * math.pi / 3
                det.box(xc - 0.02, yc - 0.02, H - 0.03, xc + 0.02, yc + 0.02, H + 0.0, "steel")
                blade = [(xc + math.cos(ang) * 0.12, yc + math.sin(ang) * 0.12),
                         (xc + math.cos(ang) * 0.40 - math.sin(ang) * 0.05, yc + math.sin(ang) * 0.40 + math.cos(ang) * 0.05),
                         (xc + math.cos(ang) * 0.40 + math.sin(ang) * 0.05, yc + math.sin(ang) * 0.40 - math.cos(ang) * 0.05)]
                det.prism_xy(blade, H - 0.02, H - 0.012, "steel")
    for sx in (-1, 1):                                  # V-coil banks as dark finned flanks with a louvred guard
        det.box(sx * (hw + 0.002) - 0.002, -hd + 0.4, 0.6, sx * (hw + 0.002) + 0.002, hd - 0.4, H - 0.35, "coil_dark")
        k = 0
        while 0.6 + 0.12 * k < H - 0.4:
            z = 0.6 + 0.12 * k
            det.box(sx * (hw + 0.012) - 0.006, -hd + 0.4, z, sx * (hw + 0.012) + 0.006, hd - 0.4, z + 0.03, "plant_grey")
            k += 1
    det.box(-hw + 0.3, hd - 0.9, 1.1, -hw + 0.5, hd - 0.7, 1.5, "plug_black")                  # electrical panel
    det.box(-hw + 0.35, hd - 0.85, 1.25, -hw + 0.45, hd - 0.75, 1.35, "hex:#C8102E")           # red isolator
    det.box(-hw + 0.2, hd - 0.42, 1.75, -hw - 0.0, hd - 0.1, 1.95, "hex:#3DCD58")               # green brand plate (plain)
    for y in (-0.35, 0.35):                             # water connections on the wall-facing flank (+X)
        det.cyl((hw - 0.2, y, 0.7), (1, 0, 0), 0.08, 0.5, "steel", seg=16)
    mb.build("plant_body", coll, bevel=0.01)
    det.build("plant_detail", coll)


BUILDERS.update({
    "nvidia-dgx-gb300-compute-tray": build_gb_tray,
    "nvidia-dgx-gb300-nvlink-switch-tray": build_nvs_tray,
    "nvidia-dgx-gb300-power-shelf": build_power_shelf,
    "nvidia-q3400-rd": build_q3400,
    "nvidia-sn5600": build_sn5600,
})
UNIT_BUILDERS = {"rear-door": build_door, "rear-manifold": build_manifold}
STANDALONE_BUILDERS = {"cdu": build_cdu, "crah": build_crah, "plant": build_plant}
