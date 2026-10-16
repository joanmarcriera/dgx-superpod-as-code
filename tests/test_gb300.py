"""Offline tests of the GB300 NVL72 SU generator (RA-GB300 counts, fabric invariants)."""
from collections import Counter, defaultdict
from pathlib import Path

import pytest
import yaml

from dgxnb import catalog, export, topology_gb300

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = yaml.safe_load((ROOT / "spec" / "gb300-su.yaml").read_text())


@pytest.fixture(scope="module")
def design():
    return topology_gb300.build(SPEC, TYPES)


def cables(d, fabric):
    return [o for o in d.all("dcim.cables") if o.data["custom_fields"]["dgx_fabric"] == fabric]


def test_ra_counts(design):
    c = export.counts(SPEC, TYPES, design)
    assert c["dgx"] == 144 and c["gpus"] == 576            # 8 racks x 18 trays x 4 GPUs
    assert c["roles"]["gb-nvlink-switch"] == 72             # 9 per rack
    assert c["roles"]["gb-power-shelf"] == 64               # 8 per rack
    assert c["roles"]["ib-compute-leaf"] == 8               # "eight leaf switches ... 4 rails"
    assert c["roles"]["ib-compute-spine"] == 4              # 576 uplinks / 144 ports
    assert c["roles"]["eth-compute-leaf"] == 4              # "four leaf SN5600 switches"


def test_nvlink_full_mesh_per_rack(design):
    nv = cables(design, "nvlink")
    assert len(nv) == 8 * 18 * 9
    per_tray = Counter(o.data["a_terminations"][0].parent for o in nv)
    assert set(per_tray.values()) == {9}


def test_each_tray_one_link_per_rail_to_distinct_leaves(design):
    per = defaultdict(list)
    for o in cables(design, "compute"):
        a = o.data["a_terminations"][0].parent
        if "-t" in a and a.startswith("gb-su1"):
            per[a].append((o.data["b_terminations"][0].parent, o.data["custom_fields"]["dgx_rail"]))
    assert len(per) == 144
    for tray, links in per.items():
        assert sorted(r for _, r in links) == [1, 2, 3, 4]
        assert all(f"-r{r}-" in leaf for leaf, r in links), tray


def test_leaf_ports_and_oversubscription(design):
    down, up = Counter(), Counter()
    for o in cables(design, "compute"):
        a, b = o.data["a_terminations"][0].parent, o.data["b_terminations"][0].parent
        if "gb-ibs-" in b:
            up[a] += 1
        elif a.startswith("gb-su1"):
            down[b] += 1
    assert set(down.values()) == {72}
    assert sorted(up.values()) == [71, 71] + [72] * 6       # UFM takes 1 uplink on 2 leaves
    assert max(down[l] / up[l] for l in up) <= SPEC["validate"]["max_leaf_oversubscription"]


def test_rack_power_within_budget(design):
    for rack, kw in export.rack_power(TYPES, design).items():
        assert kw <= export.rack_budget(SPEC, rack), (rack, kw)


def test_every_cable_two_ends(design):
    assert all(o.data["a_terminations"] and o.data["b_terminations"] for o in design.all("dcim.cables"))
