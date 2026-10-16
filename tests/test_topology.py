"""Offline tests of the generator: RA sizing rules, fabric invariants, determinism."""
import copy
from collections import defaultdict
from pathlib import Path

import pytest
import yaml

from dgxnb import catalog, export, topology

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = yaml.safe_load((ROOT / "spec" / "superpod.yaml").read_text())


def build(**over):
    spec = copy.deepcopy(SPEC)
    for path, v in over.items():
        node = spec
        *parents, leaf = path.split("__")
        for p in parents:
            node = node[p]
        node[leaf] = v
    return spec, topology.build(spec, TYPES)


@pytest.fixture(scope="module")
def design():
    return topology.build(SPEC, TYPES)


def test_catalog_patches_fix_qm9700():
    names = catalog.component_names(TYPES["nvidia-qm9700"])
    ib = [n for n in names if n.startswith("P")]
    assert len(ib) == 64 and len(set(ib)) == 64
    assert "P22.1" in ib and "P23.0" in ib and "mgmt0" in names
    assert len(TYPES["nvidia-qm9700"]["power-ports"]) == 2


def test_h100_extends_h200():
    h100, h200 = TYPES["nvidia-dgx-h100"], TYPES["nvidia-dgx-h200"]
    assert h100["interfaces"] == h200["interfaces"] and h100["model"] == "DGX H100"


def test_headline_counts(design):
    c = export.counts(SPEC, TYPES, design)
    assert c["dgx"] == 63 and c["gpus"] == 504           # RA Table 4, 2 SU row
    assert c["roles"]["ib-compute-leaf"] == 16            # RA Table 4
    assert c["roles"]["ib-compute-spine"] == 8            # RA Table 4
    assert c["roles"]["ib-storage-leaf"] + c["roles"]["ib-storage-spine"] == 7
    assert c["roles"]["eth-inband-leaf"] + c["roles"]["eth-inband-spine"] == 6
    assert c["roles"]["ufm"] == 4 and c["roles"]["mgmt-server"] == 5
    assert c["racks"] == 38                   # 32 DGX (2/rack) + 4 mgmt + 2 storage (CHOICE)


def test_two_storage_tiers(design):
    """Tier 1 DDN on the storage IB fabric, tier 2 VAST on in-band + its own backend."""
    c = export.counts(SPEC, TYPES, design)
    assert c["types"]["ddn-ai400x2t"] == 4 and c["roles"]["hps-storage"] == 4
    assert c["types"]["vast-cbox"] == 5 and c["types"]["vast-dbox-df3015v2"] == 4
    assert c["roles"]["eth-storage-backend"] == 2
    ends = lambda o: {t.parent for t in o.data["a_terminations"] + o.data["b_terminations"]}
    cables = design.all("dcim.cables")
    ddn = [o for o in cables if any(e.startswith("ddn-") for e in ends(o))
           and o.data["custom_fields"]["dgx_fabric"] == "storage"]
    assert sum(len(o.data["b_terminations"]) for o in ddn) == 4 * 8   # 8 × NDR200 each
    front = [o for o in cables if o.data["label"].startswith("I-vast-cbox")]
    assert len(front) == 5 * 4 * 2 and all(
        any(e.startswith("inb-spine") for e in ends(o)) for o in front)
    kw = c["rack_kw"]
    assert all(kw[r] <= 21.8 for r in SPEC["racks"]["storage_racks"])


@pytest.mark.parametrize("sus,nodes,leaf,spine,cmp_ufm,spine_leaf", [
    (1, 31, 8, 4, 252, 256), (2, 63, 16, 8, 508, 512),
    (3, 95, 24, 16, 764, 768), (4, 127, 32, 16, 1020, 1024)])
def test_ra_table4_compute_fabric(sus, nodes, leaf, spine, cmp_ufm, spine_leaf):
    _, d = build(compute__sus=sus, racks__mgmt_racks=max(4, sus + 2),
                 ipam__ib_compute={"vrf": "dgx-ib-compute", "prefix": "10.202.0.0/21"})
    c = export.counts(SPEC, TYPES, d)
    assert c["dgx"] == nodes
    assert c["roles"]["ib-compute-leaf"] == leaf and c["roles"]["ib-compute-spine"] == spine
    cmp = [o for o in d.all("dcim.cables") if o.data["custom_fields"]["dgx_fabric"] == "compute"]
    to_spine = [o for o in cmp if "spine" in o.data["b_terminations"][0].parent]
    assert len(cmp) - len(to_spine) == cmp_ufm and len(to_spine) == spine_leaf


def test_one_su_is_the_ra_1su_row_within_budget():
    """1 SU = 31 DGX (UFM displaces one, ra-notes 1.4); 3 mgmt racks all inside 21.8 kW:
    the second UFM-c leaves the compute rack for the in-band rack."""
    spec, d = build(compute__sus=1, racks__mgmt_racks=3, hall=None)
    c = export.counts(spec, TYPES, d)
    assert c["dgx"] == 31 and c["gpus"] == 248
    assert c["racks"] == 16 + 3 + 2
    for rack, kw in c["rack_kw"].items():
        assert kw <= export.rack_budget(spec, rack), (rack, kw)
    rack_of = {o.data["name"]: o.data["rack"].key[0] for o in d.all("dcim.devices") if "rack" in o.data}
    assert rack_of["ufm-c-01"] == "mgmt-r01" and rack_of["ufm-c-02"] == "mgmt-r02"


def test_each_dgx_has_8_rails_to_8_distinct_leaves(design):
    per = defaultdict(list)
    for o in design.all("dcim.cables"):
        a = o.data["a_terminations"][0]
        if o.data["custom_fields"]["dgx_fabric"] == "compute" and a.parent.startswith("dgx-"):
            per[a.parent].append((o.data["b_terminations"][0].parent,
                                  o.data["custom_fields"]["dgx_rail"]))
    assert len(per) == 63
    for node, links in per.items():
        leaves = {l for l, _ in links}
        assert len(links) == 8 and len(leaves) == 8
        assert sorted(r for _, r in links) == list(range(1, 9))
        assert all(l.endswith(f"-r{r}") for l, r in links), node   # rail-aligned leaf


def test_no_leaf_oversubscribed(design):
    down, up = defaultdict(int), defaultdict(int)
    for o in design.all("dcim.cables"):
        if o.data["custom_fields"]["dgx_fabric"] != "compute":
            continue
        a, b = o.data["a_terminations"][0].parent, o.data["b_terminations"][0].parent
        if "spine" in b:
            up[a] += 1
        else:
            down[b] += 1
    for leaf in up:
        assert down[leaf] <= up[leaf] == 32, leaf           # non-blocking fat tree


def test_every_cable_has_two_ends(design):
    for o in design.all("dcim.cables"):
        assert o.data["a_terminations"] and o.data["b_terminations"], o.key


def test_rack_power_within_budget(design):
    kw = export.rack_power(TYPES, design)
    for rack, v in kw.items():
        cap = SPEC["racks"]["budget_kw_dgx_rack" if rack.startswith("dgx") else "budget_kw_mgmt_rack"]
        assert v <= cap, (rack, v)
    assert kw["dgx-su1-r01"] == pytest.approx(20.4)          # 2 x 10.2 kW


def test_ips_unique_and_inside_container(design):
    import ipaddress
    cont = ipaddress.ip_network(SPEC["ipam"]["container"])
    seen = set()
    for o in design.all("ipam.ip_addresses"):
        vrf, addr = o.key
        ip = ipaddress.ip_interface(addr).ip
        assert ip in cont and (vrf, ip) not in seen
        seen.add((vrf, ip))


def test_deterministic():
    a, b = topology.build(SPEC, TYPES), topology.build(SPEC, TYPES)
    for k in a.objs:
        assert list(a.objs[k]) == list(b.objs[k])
        assert [o.data for o in a.all(k)] == [o.data for o in b.all(k)]


def test_h100_variant_is_a_spec_change():
    _, d = build(compute__gpu_gen="h100")
    types = {o.data["device_type"].key[0] for o in d.all("dcim.devices")}
    assert "nvidia-dgx-h100" in types and "nvidia-dgx-h200" not in types


def test_dgx_rack_pdus_are_three_horizontal_3u(design):
    """RA Table 7 rPDUs (design-choices §6.1): 3 x 3U per DGX rack = 9U, nothing overlaps,
    DGX stay at DCG's RU3/RU14, every DGX PSU lands on a C19 of a distinct-pair PDU."""
    t = TYPES["raritan-px3-5878i2r-3u"]
    assert t["u_height"] == 3
    kinds = [o["type"] for o in t["power-outlets"]]
    assert kinds.count("iec-60320-c19") == 18 and kinds.count("iec-60320-c13") == 6
    devs = {o.key[0]: o for o in design.all("dcim.devices")}
    used = defaultdict(list)                       # rack -> [(start, end)]
    for name, o in devs.items():
        rack = o.data.get("rack")
        pos = o.data.get("position")
        if rack and pos and rack.key[0].startswith("dgx-su"):
            used[rack.key[0]].append((pos, pos + TYPES[o.data["device_type"].key[0]]["u_height"] - 1))
    assert len(used) == 32
    for rack, spans in used.items():
        spans.sort()
        assert all(a[1] < b[0] for a, b in zip(spans, spans[1:])), (rack, spans)   # no collisions
        assert spans[-1][1] <= SPEC["racks"]["u_height"]
        pdus = [s for s in spans if s[1] - s[0] == 2 and s[0] >= 40]
        assert len(pdus) == 3 and sum(b - a + 1 for a, b in pdus) == 9
    r1 = {n: devs[n].data["position"] for n in devs if n.startswith("dgx-su1-r01-pdu")}
    assert sorted(r1.values()) == [40, 43, 46]
    assert devs["dgx-su1-n01"].data["position"] == 3 and devs["dgx-su1-n02"].data["position"] == 14
    cords = [o for o in design.all("dcim.cables") if o.data["label"].startswith("P-dgx-su1-n01-")]
    assert len(cords) == 6
    assert len({o.data["b_terminations"][0].parent for o in cords}) == 3   # 2 PSUs per PDU
    assert all(o.data["b_terminations"][0].name.startswith("C19-") for o in cords)


def test_mgmt_racks_keep_zero_u_pdus(design):
    for o in design.all("dcim.devices"):
        if o.key[0].startswith("mgmt-r01-pdu"):
            assert "position" not in o.data
