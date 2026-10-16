"""Offline tests of the Blender layout for the MIXED scene (docs/dgx-superpod-mixed/scene.json):
rack kinds, rear doors/manifolds in the envelope, GB300 port maps, coolant sockets, branch
and hose paths, one connected pipe network per loop, door swing clearance."""
import os
import sys
from collections import Counter

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "blender"))

from superpod import coolant as C  # noqa: E402
from superpod import layout as L  # noqa: E402


@pytest.fixture(scope="module")
def scene():
    return L.load_scene(os.path.join(REPO, "docs", "dgx-superpod-mixed", "scene.json"))


@pytest.fixture(scope="module")
def lib():
    return L.load_library(os.path.join(REPO, "docs", "blender", "device-library.yaml"))


def test_rack_kinds_and_envelopes(scene, lib):
    kinds = Counter(L.rack_kind(r) for r in scene["racks"])
    assert kinds == {"sx": 25, "nvl72": 8}
    assert L.check_scene(scene, lib) == []
    for r in scene["racks"]:
        u = C.rear_unit(r)
        b = L.device_box(r, u, lib)
        if u["mount"] == "rear-door":
            assert b.y1 == pytest.approx(-r["depth"] / 2) and b.y0 < b.y1 - 0.3
        else:
            assert b.y0 >= -r["depth"] / 2 and L.rack_kind(r) == "nvl72"


def test_every_device_type_has_a_library_envelope(scene, lib):
    assert {d["type"] for r in scene["racks"] for d in r["devices"]} <= set(lib)


def test_gb300_tray_ports(scene, lib):
    tray = next(d for r in scene["racks"] for d in r["devices"] if d["type"] == "nvidia-dgx-gb300-compute-tray")
    ports = L.device_ports(tray, lib)
    by = Counter((p.fabric, p.kind) for p in ports)
    assert by[("compute", "osfp_fin")] == 4 and sorted(p.tie for p in ports if p.fabric == "compute") == [1, 2, 3, 4]
    assert by[("storage-eth", "qsfp")] == 1 and by[("inband", "qsfp")] == 1 and by[("oob", "rj45")] == 3
    assert by[("power", "busbar")] == 1 and all(p.face == "front" for p in ports if p.fabric != "power")
    leaf = next(d for r in scene["racks"] for d in r["devices"] if d["type"] == "nvidia-q3400-rd" and d["role"] == "ib-compute-leaf")
    lp = L.device_ports(leaf, lib)
    assert sum(1 for p in lp if p.kind == "osfp_fin") == 72 and len({p.tie for p in lp if p.kind == "osfp_fin"}) == 1
    sn = next(d for r in scene["racks"] for d in r["devices"] if d["type"] == "nvidia-sn5600")
    assert 30 <= sum(1 for p in L.device_ports(sn, lib) if p.kind == "osfp") <= 64


def test_sockets_sit_on_their_units(scene, lib):
    for r in scene["racks"]:
        socks = C.unit_sockets(r, lib)
        assert set(socks) == {"SUPPLY", "RETURN"}
        env = L.box_to_world(r, L.rack_envelope(r, lib))
        for p in socks.values():
            assert env.x0 - 0.01 <= p[0] <= env.x1 + 0.01 and env.y0 - 0.01 <= p[1] <= env.y1 + 0.01
            assert abs(p[2] - L.rack_height(lib, r)) < 0.05
    for cdu in scene["cooling"]["cdus"]:
        for p in C.cdu_sockets(cdu).values():
            assert abs(p[0] - cdu["origin"][0]) <= cdu["width"] / 2 and p[2] == pytest.approx(cdu["height"])


def test_branches_hoses_and_network(scene, lib):
    runs, sockets = C.all_runs(scene, lib)
    hoses = [r for r in runs if r.kind == "hose"]
    assert len(hoses) == 2 * len(scene["racks"])
    for h in hoses:                                   # hose ends ON the socket (5 mm rule)
        assert L._len(L._sub(h.points[-1], sockets[(h.b, "SUPPLY" if h.fabric.endswith("supply") else "RETURN")])) < 0.005
        tee = h.points[0]
        hdr = next(r for r in runs if r.kind == "header" and r.a == h.a and r.fabric == h.fabric)
        assert hdr.points[0][2] - C.VALVE_DROP - 0.5 < tee[2] < hdr.points[0][2]
    for key in ("PRI-S", "SEC-S", "SEC-R"):
        assert any(r.b and r.b.startswith("cdu-") and r.kind == "drop" for r in runs)
    # the CDU heat exchangers separate each technology loop from the facility water: per
    # fabric, exactly one connected pipe network per loop plus one for the FWS mains
    comps = C.components(runs)
    want = set(scene["cooling"]["loops"]) | {"fws"}
    for fabric, groups in comps.items():
        seen = [{runs[i].loop for i in g} for g in groups]
        assert all(len(s) == 1 for s in seen), (fabric, seen)
        assert sorted(next(iter(s)) for s in seen) == sorted(want), (fabric, seen)


def test_door_clearance(scene, lib):
    assert C.door_clearance_ok(scene, lib) == []
    assert scene["hall"]["hot_aisle"] - 2 * 0.363 >= 1.219
