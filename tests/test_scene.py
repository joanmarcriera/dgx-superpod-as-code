"""Offline tests of the 3D scene export: every rack placed once without overlap, every
device inside its rack, cable bundles account for every racked non-power cable."""
from pathlib import Path

import pytest
import yaml

from dgxnb import catalog, scene, topology

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = yaml.safe_load((ROOT / "spec" / "superpod.yaml").read_text())


@pytest.fixture(scope="module")
def built():
    design = topology.build(SPEC, TYPES)
    return design, scene.scene_json(SPEC, TYPES, design)


def test_racks_placed_without_overlap(built):
    design, s = built
    assert len(s["racks"]) == design.count("dcim.racks")
    boxes = [(r["origin"][0], r["origin"][1], r["width"], r["depth"]) for r in s["racks"]]
    for i, (x1, y1, w, d) in enumerate(boxes):
        for x2, y2, _, _ in boxes[i + 1:]:
            assert abs(x1 - x2) >= w - 1e-6 or abs(y1 - y2) >= d - 1e-6


def test_devices_inside_rack(built):
    _, s = built
    u0 = SPEC["racks"].get("rack_u0_mm", 100) / 1000
    top = u0 + SPEC["racks"]["u_height"] * scene.U_MM / 1000
    for r in s["racks"]:
        for d in r["devices"]:
            if d["mount"] == "front":
                assert u0 <= d["z_bottom"]
                assert d["z_bottom"] + d["u_height"] * scene.U_MM / 1000 <= top + 1e-6


def test_links_list_every_cable_with_both_ends(built):
    design, s = built
    assert len(s["links"]) == design.count("dcim.cables")
    cols = s["links_cols"]
    assert cols == ["a", "a_port", "b", "b_port", "fabric", "cable", "rail", "label"]
    labels = [row[cols.index("label")] for row in s["links"]]
    assert len(set(labels)) == len(labels)
    devs = {o.data["name"] for o in design.all("dcim.devices")}
    panels = {o.key[0] for o in design.all("dcim.power_panels")}
    for row in s["links"]:
        assert row[0] in devs and row[2] in devs | panels and row[1] and row[3], row
    one = next(r for r in s["links"] if r[0] == "dgx-su1-n01" and r[4] == "compute" and r[6] == 1)
    assert one[1] == "OSFP4P2" and one[2] == "ibc-su1-leaf-r1"      # rail 1 = GPU0 port


def test_bundles_cover_racked_cables(built):
    design, s = built
    racked = {o.data["name"] for o in design.all("dcim.devices") if "rack" in o.data}
    expected = sum(1 for o in design.all("dcim.cables")
                   if o.data["custom_fields"]["dgx_fabric"] != "power"
                   and o.data["a_terminations"][0].parent in racked
                   and o.data["b_terminations"][0].parent in racked)
    assert sum(b["count"] for b in s["cable_bundles"]) == expected
