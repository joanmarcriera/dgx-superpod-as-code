"""Offline tests for blender/superpod/layout.py — the pure-Python geometry behind the Blender
render (no bpy needed). Run: uv run pytest tests/test_blender_layout.py
"""
import os
import sys
from collections import Counter

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "blender"))

from superpod import layout as L  # noqa: E402


@pytest.fixture(scope="module")
def scene():
    return L.load_scene(os.path.join(REPO, "docs", "scene.json"))


@pytest.fixture(scope="module")
def lib():
    return L.load_library(os.path.join(REPO, "docs", "blender", "device-library.yaml"))


def test_every_device_fits_its_rack_without_intersections(scene, lib):
    assert L.check_scene(scene, lib) == []


def test_every_device_type_has_a_library_envelope(scene, lib):
    types = {d["type"] for r in scene["racks"] for d in r["devices"]}
    assert types <= set(lib)


def test_blanks_fill_exactly_the_empty_units(scene):
    for r in scene["racks"]:
        assert len(L.empty_units(r)) + len(L.occupied_units(r)) == r["u_height"]


def test_rack_frame_follows_facing(scene):
    rb = L.racks_by_name(scene)
    for r in scene["racks"]:
        front = L.rack_to_world(r, (0.0, 0.5, 0.0))
        fy = r["facing"][1]
        assert (front[1] - r["origin"][1]) * fy > 0.49
    # a rack facing -Y maps rack-local +X onto world -X
    back = next(r for r in scene["racks"] if r["facing"][1] < 0)
    assert L.rack_to_world(back, (1.0, 0.0, 0.0))[0] == pytest.approx(back["origin"][0] - 1.0)
    assert rb  # sanity


def test_rows_face_a_shared_hot_aisle(scene, lib):
    x0, y0, x1, y1 = L.hot_aisle(scene, lib)
    assert y1 - y0 == pytest.approx(scene["hall"]["hot_aisle"], abs=1e-6)
    for row in scene["hall"]["rows"]:
        c = L.cold_aisle(scene, lib, row["name"])
        assert c[3] - c[1] == pytest.approx(scene["hall"]["cold_aisle"])


def test_dgx_ports_cover_eight_rails_and_six_psus(scene, lib):
    dgx = next(d for r in scene["racks"] for d in r["devices"] if d["type"] == "nvidia-dgx-h200")
    ports = L.device_ports(dgx, lib)
    assert sorted(p.tie for p in ports if p.fabric == "compute") == list(range(1, 9))
    assert Counter(p.fabric for p in ports)["power"] == 6
    assert all(p.face == "rear" for p in ports)


def test_port_tips_stay_inside_the_rack(scene, lib):
    for r in scene["racks"]:
        box = L.rack_interior(r, lib)
        ry = L.rail_y(r)
        for d in r["devices"]:
            for p in L.device_ports(d, lib):
                assert box.y0 < ry + p.y < box.y1, (d["name"], p)
                assert box.x0 < p.x < box.x1


def test_psu_cords_do_not_cross(scene, lib):
    r = next(r for r in scene["racks"] if any(d["type"] == "nvidia-dgx-h200" for d in r["devices"]))
    dgx = next(d for d in r["devices"] if d["type"] == "nvidia-dgx-h200")
    pairs = L.power_assignments(r, dgx, lib)
    assert len(pairs) == 6
    feeds = [L.feed_letter(pdu) for _, pdu in pairs]
    pdu_x = [L.pdu_place(r, pdu, lib).x for _, pdu in pairs]
    assert pdu_x == sorted(pdu_x)                   # PSU order left->right == PDU order
    assert Counter(feeds) == {"A": 2, "B": 2, "C": 2}


def test_bundles_run_roof_to_roof_inside_the_hall(scene, lib):
    rb = L.racks_by_name(scene)
    hx0, hy0, hx1, hy1 = L.hall_extent(scene, lib)
    H = L.rack_height(lib)
    routed = 0
    for i, b in enumerate(scene["cable_bundles"]):
        path = L.bundle_path(b, scene, lib, i)
        if b["a"] == b["b"]:
            assert path is None
            continue
        routed += 1
        for end, rack in ((path[0], rb[b["a"]]), (path[-1], rb[b["b"]])):
            assert end[2] == pytest.approx(H)
            box = L.box_to_world(rack, L.rack_interior(rack, lib))
            assert box.x0 <= end[0] <= box.x1 and box.y0 <= end[1] <= box.y1
        for p in path:
            assert hx0 - 0.5 <= p[0] <= hx1 + 0.5 and hy0 - 0.5 <= p[1] <= hy1 + 0.5
            assert H - 1e-9 <= p[2] <= L.LADDER_Z + 0.1
    assert routed > 100


def test_fillet_keeps_endpoints_and_rounds_corners():
    pts = [(0, 0, 0), (1, 0, 0), (1, 1, 0)]
    f = L.fillet(pts, 0.2, samples=4)
    assert f[0] == (0, 0, 0) and f[-1] == (1, 1, 0)
    assert (1, 0, 0) not in f                        # the sharp corner is gone
    assert L.path_length(f) < L.path_length(pts)


def test_ties_are_evenly_spaced():
    pts = [(0, 0, 0), (3, 0, 0)]
    s = L.sample_along(pts, 0.3, 0.15)
    xs = [p[0][0] for p in s]
    assert xs[0] == pytest.approx(0.15) and all(b - a == pytest.approx(0.3) for a, b in zip(xs, xs[1:]))
    assert xs[-1] <= 3 - 0.15 + 1e-9
