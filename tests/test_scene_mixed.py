"""Offline tests of the mixed design's 3D scene: doors/manifolds mounted at the rack rear,
CDUs in row B's free positions without touching a rack, the plant beyond the wall, headers
above the overhead paths, every coolant pipe present in `pipes`."""
from pathlib import Path

import pytest

from dgxnb import catalog, scene, specload, topology_mixed

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = specload.load(ROOT / "spec" / "superpod-mixed.yaml")


@pytest.fixture(scope="module")
def s():
    return scene.scene_json(SPEC, TYPES, topology_mixed.build(SPEC, TYPES))


def test_every_rack_has_one_rear_cooling_unit_and_a_cooling_summary(s):
    for r in s["racks"]:
        mounts = [d["mount"] for d in r["devices"]]
        assert mounts.count("rear-door") + mounts.count("rear-manifold") == 1, r["name"]
        assert r["cooling"]["loop"] in s["cooling"]["loops"] and r["cooling"]["kw"] > 0
        assert r["cooling"]["unit"] in {d["name"] for d in r["devices"]}


def test_cdus_sit_in_row_b_free_slots_clear_of_racks(s):
    cs = s["cooling"]
    row_b = [r for r in s["racks"] if r["row"] == "B"]
    y_b = row_b[0]["origin"][1]
    x_last = max(r["origin"][0] + r["width"] / 2 for r in row_b)
    x_row_end = max(r["origin"][0] + r["width"] / 2 for r in s["racks"])
    for c in cs["cdus"]:
        assert c["origin"][1] == pytest.approx(y_b) and c["facing"] == row_b[0]["facing"]
        assert c["origin"][0] - c["width"] / 2 >= x_last + 0.29
        assert c["origin"][0] + c["width"] / 2 <= x_row_end + 1e-6, "CDU block longer than row A"
    xs = sorted((c["origin"][0] - c["width"] / 2, c["origin"][0] + c["width"] / 2) for c in cs["cdus"])
    assert all(b[0] >= a[1] for a, b in zip(xs, xs[1:]))


def test_plant_outside_the_wall_and_crahs_at_the_far_end(s):
    cs = s["cooling"]
    wall = cs["plant"]["wall_x"]
    assert len(cs["plant"]["units"]) == 3
    for u in cs["plant"]["units"]:
        assert u["origin"][0] - u["width"] / 2 > wall + 0.2
    x_start = min(r["origin"][0] - r["width"] / 2 for r in s["racks"])
    assert len(cs["crahs"]) == 2
    for c in cs["crahs"]:
        assert c["origin"][0] + c["depth"] / 2 < x_start


def test_headers_run_above_the_overhead_paths_and_reach_the_cdus(s):
    cs = s["cooling"]
    for h in cs["headers"]:
        assert 3.0 < h["z"] < 3.9 and h["kind"] in ("supply", "return")
        assert len(h["polyline"]) >= 3 and h["flow_lpm"] <= h["rated_lpm"]
        cdu_x = [c["origin"][0] for c in cs["cdus"] if c["loop"] == h["loop"]]
        assert min(cdu_x) - 0.5 <= h["polyline"][-1][0] <= max(cdu_x) + 0.5
    assert {m["kind"] for m in cs["fws_mains"]} == {"supply", "return"}
    assert all(m["z"] > max(h["z"] for h in cs["headers"]) for m in cs["fws_mains"])


def test_pipes_match_the_netbox_coolant_cables(s):
    pipes = s["cooling"]["pipes"]
    links = [l for l in s["links"] if l[4].startswith("coolant-")]
    assert len(pipes) == len(links) and len(pipes) > 80
