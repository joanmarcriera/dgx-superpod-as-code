"""Offline tests of the cooling layer of the mixed pod: every rack has a supply AND a return
path to a CDU, every CDU to the plant, each loop carries its load with one CDU out, header
flow within rating, doors/manifolds on the right racks, colours and fabrics on the pipes."""
from collections import defaultdict
from pathlib import Path

import pytest

from dgxnb import catalog, cooling, export, specload, topology_mixed

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")
SPEC = specload.load(ROOT / "spec" / "superpod-mixed.yaml")


@pytest.fixture(scope="module")
def built():
    design = topology_mixed.build(SPEC, TYPES)
    return design, cooling.model(SPEC, TYPES, design)


def graph(design):
    """Undirected adjacency per fabric over the coolant cables."""
    adj = {"coolant-supply": defaultdict(set), "coolant-return": defaultdict(set)}
    for a, _ap, b, _bp, f in cooling.hydraulic_edges(design):
        adj[f][a].add(b)
        adj[f][b].add(a)
    return adj


def reach(adj, start):
    seen, todo = set(), [start]
    while todo:
        n = todo.pop()
        if n in seen:
            continue
        seen.add(n)
        todo += adj[n]
    return seen


def test_every_rack_is_on_exactly_one_primary_loop(built):
    design, m = built
    racks = [o.key[0] for o in design.all("dcim.racks")]
    on = defaultdict(list)
    for key, lp in m.loops.items():
        for r in lp.racks:
            on[r].append(key)
    assert set(on) == set(racks)
    assert all(len(v) == 1 for v in on.values()), {r: v for r, v in on.items() if len(v) != 1}
    assert set(m.loops["dlc"].racks) == {r for r in racks if r.startswith("gb-su1-")}
    assert m.loops["dlc"].unit_kind == "manifold" and m.loops["rdhx"].unit_kind == "door"


def test_every_rack_has_supply_and_return_paths_to_a_cdu_and_the_plant(built):
    design, m = built
    adj = graph(design)
    for lp in m.loops.values():
        for r in lp.racks:
            unit = lp.unit_of[r]
            for fabric in ("coolant-supply", "coolant-return"):
                seen = reach(adj[fabric], unit)
                assert set(lp.cdus) <= seen, (r, fabric, "no path to every CDU of its loop")
                assert set(m.plant_units) <= seen, (r, fabric, "no path to every plant module")
    for crah in m.crah_units:
        assert set(m.plant_units) <= reach(adj["coolant-supply"], crah)
    for lp in m.loops.values():          # loops are hydraulically separate below the FWS header
        other = [c for k, l2 in m.loops.items() if k != lp.key for c in l2.cdus]
        s = reach({k: v - {m.fws_header} for k, v in adj["coolant-supply"].items()}, lp.cdus[0])
        assert not (s & set(other))


def test_n_plus_1_capacity_and_flows(built):
    _, m = built
    for lp in m.loops.values():
        assert len(lp.cdus) >= 2
        assert lp.load_kw <= lp.capacity_n_minus_1_kw, (lp.key, lp.load_kw, lp.capacity_n_minus_1_kw)
        assert lp.load_kw > (len(lp.cdus) - 2) * lp.cdu_kw           # not over-provisioned
        assert lp.dt > 0
        # one CDU out: the survivors' secondary pumps still carry the loop's flow
        assert lp.flow_lpm <= (len(lp.cdus) - 1) * lp.cdu_sec_lpm, (lp.key, lp.flow_lpm)
        for hdr in lp.headers.values():
            assert lp.header_flow_lpm(hdr) <= lp.header_rated_lpm, (hdr, lp.header_flow_lpm(hdr))
        for r in lp.racks:                # every door / manifold within its rated flow
            assert lp.rack_lpm(r) <= lp.unit_max_lpm, (r, lp.rack_lpm(r))
    assert m.plant_load_kw <= m.plant_n_minus_1_kw, (m.plant_load_kw, m.plant_n_minus_1_kw)
    assert m.residual_air_kw <= m.crah_n_minus_1_kw, (m.residual_air_kw, m.crah_n_minus_1_kw)
    assert m.residual_air_kw > 0


def test_dlc_liquid_fraction_and_rdhx_door_limit(built):
    design, m = built
    kw = export.rack_power(TYPES, design)
    dlc, rdhx = m.loops["dlc"], m.loops["rdhx"]
    r = dlc.racks[0]
    assert dlc.rack_kw[r] == pytest.approx(kw[r] * dlc.liquid_fraction, abs=0.01)
    unit_kw = SPEC["cooling"]["loops"]["rdhx"]["unit"]["kw"]
    assert max(rdhx.rack_kw.values()) <= unit_kw


def test_netbox_objects_for_cooling(built):
    design, m = built                       # topology_mixed.build already added the cooling layer
    devs = {o.data["name"]: o for o in design.all("dcim.devices")}
    roles = defaultdict(int)
    for o in devs.values():
        roles[o.data["role"].key[0]] += 1
    n_racks = design.count("dcim.racks")
    assert roles["cooling-rdhx"] + roles["cooling-manifold"] == n_racks
    assert roles["cooling-cdu"] == sum(len(lp.cdus) for lp in m.loops.values())
    assert roles["cooling-plant"] == len(m.plant_units) == 3
    assert roles["cooling-crah"] == len(m.crah_units) == 2
    assert roles["cooling-header"] == 1 + sum(len(lp.headers) for lp in m.loops.values())
    for lp in m.loops.values():
        for r in lp.racks:
            u = devs[lp.unit_of[r]]
            assert u.data["rack"].key == (r,) and "position" not in u.data     # rear, like 0U PDUs
    pipes = [o for o in design.all("dcim.cables") if o.data["custom_fields"]["dgx_fabric"].startswith("coolant-")]
    assert pipes and all(o.data["type"] == "" for o in pipes)
    cols = {o.data["custom_fields"]["dgx_fabric"]: o.data["color"] for o in pipes}
    assert cols["coolant-supply"] != cols["coolant-return"]
    # door fans are powered from the rack rPDUs; the plant and CDUs from the mechanical panel
    door = next(n for n in devs if n.endswith("-" + SPEC["cooling"]["loops"]["rdhx"]["unit"]["suffix"]))
    cords = [o for o in design.all("dcim.cables") if o.data["a_terminations"][0].parent == door
             and o.data["custom_fields"]["dgx_fabric"] == "power"]
    assert cords and cords[0].data["b_terminations"][0].parent.endswith(("-pdu-a", "-pdu-b", "-pdu-c"))
    feeds = {o.key[0] for o in design.all("dcim.power_feeds")}
    assert all(f"{u}-feed" in feeds for u in m.plant_units + m.crah_units)
    assert all(f"{c}-feed" in feeds for lp in m.loops.values() for c in lp.cdus)
    # racks stay within budget with the door fans added
    kw = export.rack_power(TYPES, design)
    for rack, v in kw.items():
        assert v <= export.rack_budget(SPEC, rack), (rack, v)


def test_rear_aisle_stays_clear_behind_the_doors():
    hall, cs = SPEC["hall"], SPEC["cooling"]
    door_depth = cs["loops"]["rdhx"]["unit"]["depth_mm"]
    rows = {row["name"] for row in hall["rows"]}
    doors_per_aisle = sum(1 for lp in cs["loops"].values()
                          if lp["unit"]["kind"] == "door" for r in (lp["racks"].get("rows") or rows))
    assert hall["hot_aisle_mm"] - min(doors_per_aisle, 2) * door_depth >= hall["rear_aisle_clear_mm"] >= 1219
