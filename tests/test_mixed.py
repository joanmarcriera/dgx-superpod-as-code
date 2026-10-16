"""Offline tests of the mixed pod (spec/superpod-mixed.yaml): both SUs RA-pure, one site,
shared demarc/VAST only, no name collisions, budgets, determinism."""
from collections import Counter
from pathlib import Path

import pytest

from dgxnb import catalog, export, specload, topology_mixed

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = specload.load(ROOT / "spec" / "superpod-mixed.yaml")


@pytest.fixture(scope="module")
def design():
    return topology_mixed.build(SPEC, TYPES)


def devices(d):
    return {o.data["name"]: o for o in d.all("dcim.devices")}


def test_pods_resolve_from_their_own_specs():
    h, g = SPEC["pods"]["h200"]["spec"], SPEC["pods"]["gb300"]["spec"]
    assert h["compute"]["sus"] == 1 and h["compute"]["nodes_per_su"] == 32      # base kept
    assert "hall" not in h                                                        # null deletes
    assert g["ethernet"]["hps_appliances"] == 0 and g["compute"]["racks_per_su"] == 8


def test_headline_counts(design):
    c = export.counts(SPEC, TYPES, design)
    roles = c["roles"]
    assert roles["dgx-compute"] == 31 and roles["gb-compute-tray"] == 144
    assert c["dgx"] == 31 + 144 and c["gpus"] == 248 + 576 == 824
    assert c["racks"] == 21 + 12
    assert roles["ib-compute-leaf"] == 8 + 8 and roles["ib-compute-spine"] == 4 + 4
    assert roles["ufm"] == 4 + 2 and roles["mgmt-server"] == 5 + 5
    assert "hps-storage" in roles and c["types"]["ddn-ai400x2t"] == 4      # DDN tier 1 stays (H200 pod)
    assert "generic-hps-ethernet-appliance-2u" not in c["types"]           # GB300 HPS dropped for VAST
    assert c["types"]["vast-cbox"] == 5 and c["roles"]["eth-storage-backend"] == 2
    assert roles["dc-demarc"] == 1                                         # ONE shared demarc


def test_shared_demarc_carries_both_pods_uplinks(design):
    core = [o for o in design.all("dcim.cables")
            if any(t.parent == "dc-core-demarc" for t in o.data["b_terminations"])]
    ports = sorted((t.name for o in core for t in o.data["b_terminations"]),
                   key=lambda p: int(p[4:]))
    assert ports == [f"core{i}" for i in range(1, 15)]                       # 12 H200 + 2 GB300
    a_sides = {o.data["a_terminations"][0].parent for o in core}
    assert {"inb-spine-01", "inb-spine-02", "gb-es-01", "gb-es-02"} <= a_sides


def test_su_numbers_unique_across_pods(design):
    su = {o.data["name"]: o.data["custom_fields"]["dgx_su"] for o in design.all("dcim.devices")
          if o.data.get("custom_fields", {}).get("dgx_su")}
    assert su["dgx-su1-n01"] == 1 and su["gb-su1-r01-t01"] == 2
    assert {o.data["custom_fields"]["dgx_su"] for o in design.all("dcim.racks")
            if o.data["custom_fields"]["dgx_su"]} == {1, 2}


def test_no_name_collisions_between_pods(design):
    racks = [o.key[0] for o in design.all("dcim.racks")]
    assert Counter(topology_mixed.pod_of_rack(SPEC, r) for r in racks) == {"h200": 21, "gb300": 12}
    names = [o.data["name"] for o in design.all("dcim.devices")]
    assert len(names) == len(set(names))
    with pytest.raises(ValueError):
        topology_mixed.pod_of_rack(SPEC, "zz-r01")


def test_hall_places_every_rack_once(design):
    placed = [r for row in SPEC["hall"]["rows"] for r in row["racks"]]
    assert sorted(placed) == sorted(o.key[0] for o in design.all("dcim.racks"))
    rows = {row["name"]: row["racks"] for row in SPEC["hall"]["rows"]}
    assert all(topology_mixed.pod_of_rack(SPEC, r) == "h200" for r in rows["A"])
    assert all(topology_mixed.pod_of_rack(SPEC, r) == "gb300" for r in rows["B"])


def test_rack_power_within_each_pods_budget(design):
    kw = export.rack_power(TYPES, design)
    assert kw["dgx-su1-r01"] == pytest.approx(20.4) and kw["gb-su1-r01"] > 100
    for rack, v in kw.items():
        assert v <= export.rack_budget(SPEC, rack), (rack, v)


def test_every_cable_has_two_ends(design):
    assert all(o.data["a_terminations"] and o.data["b_terminations"] for o in design.all("dcim.cables"))


def test_one_site_one_tag(design):
    assert [o.key for o in design.all("dcim.sites")] == [("dgx-lab-03",)]
    assert [o.key for o in design.all("extras.tags")] == [("dgx-superpod-mixed",)]
    for kind in ("dcim.devices", "dcim.racks", "dcim.cables"):
        for o in design.all(kind):
            assert o.data["tags"][0].key == ("dgx-superpod-mixed",), (kind, o.key)


def test_ip_space_disjoint_between_pods(design):
    import ipaddress
    conts = [ipaddress.ip_network(o.data["prefix"]) for o in design.all("ipam.prefixes")
             if o.data["status"] == "container" and "vrf" not in o.data]
    assert len(conts) == 2 and not conts[0].overlaps(conts[1])


def test_deterministic():
    a, b = topology_mixed.build(SPEC, TYPES), topology_mixed.build(SPEC, TYPES)
    for k in a.objs:
        assert list(a.objs[k]) == list(b.objs[k])
        assert [o.data for o in a.all(k)] == [o.data for o in b.all(k)]
