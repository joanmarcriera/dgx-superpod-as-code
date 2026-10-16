"""Cooling layer: per-rack door or manifold, per-row headers, N+1 CDUs per loop, the N+1
plant block behind one facility-water header, and the residual-air CRAHs — every hose /
header / primary run as a NetBox cable, all derived from spec["cooling"] and the racks'
peak power, so NetBox, the drawings and the 3D scene agree.

  model(spec, types, design) -> CoolingModel     pure sizing summary (loops, CDUs, loads)
  add_cooling(spec, types, design)               emits the NetBox objects into `design`
  hydraulic_edges(design)                        the coolant graph (tests, scene, add-on)

Spec (spec/superpod-mixed.yaml `cooling:`; every number cites reference/cooling-schneider):
  plant:        {header, type, units, kw_each, spare, fws_supply_c, fws_return_c, power_port}
  residual_air: {type, units, kw_each, spare, power_port}        CRAHs on facility water
  loops.<loop>: unit {kind door|manifold, type, suffix, kw?, fan_w?, liquid_fraction, max_lpm}
                racks {rows?, with_role?, without_role?}         membership rule (hall order)
                cdu {type, kw, spare, sec_lpm}                   N = ceil(load / kw) + spare
                tcs_supply_c, tcs_return_c, header {dn, rated_lpm}

NetBox modelling (CHOICE, docs/design-choices.md "Mixed pod"): NetBox has no pipe object, so
each supply and return run is a cable with blank `type`, custom field dgx_fabric =
coolant-supply / coolant-return, between `other` interfaces. Hydraulic graph:
  plant unit SUPPLY/RETURN <-> hdr-fws CDU-S-k/CDU-R-k        (sources on the FWS header)
  hdr-fws S-n/R-n <-> cdu PRI-S/PRI-R, crah SUPPLY/RETURN     (consumers of facility water)
  cdu SEC-S/SEC-R <-> loop header CDU-S-i/CDU-R-i             (technology loop)
  loop header S-n/R-n <-> door|manifold SUPPLY/RETURN         (branch + hose pair per rack)
Cable labels W-S-<a>-<b> / W-R-<a>-<b> (W = water). Flow: lpm = kW * 60 / (4.18 * dT) for
water (PG25 needs ~5 % more; noted in the docs).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import catalog as cat
from . import export
from .model import Design, Ref
from .topology import _Ctx, _power_device

ROLES_COOLING = {  # slug: (name, colour)
    "cooling-plant": ("Cooling plant module (chiller / free-cooler)", "1f77b4"),
    "cooling-cdu": ("Coolant distribution unit", "17becf"),
    "cooling-crah": ("CRAH (residual air)", "9edae5"),
    "cooling-header": ("Coolant header (mains)", "aec7e8"),
    "cooling-rdhx": ("Rear-door heat exchanger", "2ca02c"),
    "cooling-manifold": ("In-rack coolant manifold", "98df8a"),
}
HEADER = "generic-coolant-header"
UNIT_ROLE = {"door": "cooling-rdhx", "manifold": "cooling-manifold"}


def lpm(kw: float, dt_c: float) -> float:
    """Water flow (l/min) carrying `kw` at a `dt_c` supply/return split."""
    return kw * 60.0 / (4.18 * dt_c)


@dataclass
class Loop:
    key: str
    label: str
    unit_type: str
    unit_kind: str                       # door | manifold
    racks: list[str]                     # member racks, hall order
    rack_kw: dict[str, float]            # heat to liquid per rack (after liquid_fraction, + fans)
    unit_of: dict[str, str]              # rack -> unit device name
    header_of: dict[str, str]            # rack -> header device name
    branch_of: dict[str, int]            # rack -> S-n/R-n index on its header
    headers: dict[str, str]              # row -> header device name
    cdus: list[str]
    cdu_kw: float
    cdu_type: str
    cdu_sec_lpm: float
    tcs_supply_c: float
    tcs_return_c: float
    header_rated_lpm: float
    liquid_fraction: float
    unit_max_lpm: float

    @property
    def load_kw(self) -> float:
        return sum(self.rack_kw.values())

    @property
    def dt(self) -> float:
        return self.tcs_return_c - self.tcs_supply_c

    @property
    def flow_lpm(self) -> float:
        return lpm(self.load_kw, self.dt)

    def rack_lpm(self, rack: str) -> float:
        return lpm(self.rack_kw[rack], self.dt)

    def header_flow_lpm(self, header: str) -> float:
        return lpm(sum(kw for r, kw in self.rack_kw.items() if self.header_of[r] == header), self.dt)

    @property
    def capacity_n_minus_1_kw(self) -> float:
        return (len(self.cdus) - 1) * self.cdu_kw


@dataclass
class CoolingModel:
    fws_header: str
    plant_type: str
    plant_units: list[str]
    plant_kw_each: float
    fws_supply_c: float
    fws_return_c: float
    crah_type: str
    crah_units: list[str]
    crah_kw_each: float
    residual_air_kw: float
    aux_kw: float
    loops: dict[str, Loop] = field(default_factory=dict)

    @property
    def loop_load_kw(self) -> float:
        return sum(lp.load_kw for lp in self.loops.values())

    @property
    def plant_load_kw(self) -> float:
        """Everything the facility water carries: loops, residual air, CDU pump heat."""
        return self.loop_load_kw + self.residual_air_kw + self.aux_kw

    @property
    def plant_kw(self) -> float:
        return len(self.plant_units) * self.plant_kw_each

    @property
    def plant_n_minus_1_kw(self) -> float:
        return (len(self.plant_units) - 1) * self.plant_kw_each

    @property
    def crah_n_minus_1_kw(self) -> float:
        return (len(self.crah_units) - 1) * self.crah_kw_each


def _row_of(spec: dict) -> dict[str, tuple[str, int]]:
    """rack -> (row name, 1-based index in the row)."""
    return {r: (row["name"], i + 1) for row in spec["hall"]["rows"] for i, r in enumerate(row["racks"])}


def _members(spec: dict, design: Design, rule: dict) -> list[str]:
    """Racks selected by a loop's `racks` rule, in hall order."""
    roles_in: dict[str, set] = {}
    for o in design.all("dcim.devices"):
        if "rack" in o.data:
            roles_in.setdefault(o.data["rack"].key[0], set()).add(o.data["role"].key[0])
    rows = set(rule.get("rows") or [row["name"] for row in spec["hall"]["rows"]])
    out = []
    for row in spec["hall"]["rows"]:
        if row["name"] not in rows:
            continue
        for r in row["racks"]:
            have = roles_in.get(r, set())
            if rule.get("with_role") and rule["with_role"] not in have:
                continue
            if rule.get("without_role") and rule["without_role"] in have:
                continue
            out.append(r)
    return out


def model(spec: dict, types: dict, design: Design) -> CoolingModel:
    """Size the loops from the racks' peak power (export.rack_power) — pure, no side effects."""
    cs = spec["cooling"]
    kw = export.rack_power(types, design)
    row_of = _row_of(spec)
    pl, ra = cs["plant"], cs["residual_air"]
    m = CoolingModel(fws_header=pl["header"], plant_type=pl["type"], plant_units=list(pl["units"]),
                     plant_kw_each=pl["kw_each"], fws_supply_c=pl["fws_supply_c"],
                     fws_return_c=pl["fws_return_c"], crah_type=ra["type"],
                     crah_units=list(ra["units"]), crah_kw_each=ra["kw_each"], residual_air_kw=0.0,
                     aux_kw=cs.get("aux_kw", 0.0))
    residual = 0.0
    for key, ls in cs["loops"].items():
        unit = ls["unit"]
        racks = _members(spec, design, ls["racks"])
        if not racks:
            raise ValueError(f"loop {key}: no racks match {ls['racks']}")
        frac = unit.get("liquid_fraction", 1.0)
        fan = unit.get("fan_w", 0) / 1000.0           # door fans add their own heat to the loop
        rack_kw = {r: round(kw.get(r, 0.0) * frac + fan, 3) for r in racks}
        residual += sum(kw.get(r, 0.0) * (1 - frac) for r in racks)
        headers = {row_of[r][0]: f"hdr-{key}-{row_of[r][0].lower()}" for r in racks}
        n = math.ceil(sum(rack_kw.values()) / ls["cdu"]["kw"]) + ls["cdu"].get("spare", 1)
        lp = Loop(key=key, label=ls.get("label", key), unit_type=unit["type"],
                  unit_kind=unit["kind"], racks=racks, rack_kw=rack_kw,
                  unit_of={r: f"{r}-{unit['suffix']}" for r in racks},
                  header_of={r: headers[row_of[r][0]] for r in racks},
                  branch_of={r: row_of[r][1] for r in racks}, headers=headers,
                  cdus=[f"cdu-{key}-{i:02d}" for i in range(1, n + 1)],
                  cdu_kw=ls["cdu"]["kw"], cdu_type=ls["cdu"]["type"],
                  cdu_sec_lpm=ls["cdu"]["sec_lpm"],
                  tcs_supply_c=ls["tcs_supply_c"], tcs_return_c=ls["tcs_return_c"],
                  header_rated_lpm=ls["header"]["rated_lpm"], liquid_fraction=frac,
                  unit_max_lpm=unit.get("max_lpm", float("inf")))
        for r in racks:
            if unit.get("kw") and rack_kw[r] > unit["kw"]:
                raise ValueError(f"loop {key}: {r} needs {rack_kw[r]:.1f} kW > unit {unit['kw']} kW")
        m.loops[key] = lp
    m.residual_air_kw = round(residual, 3)
    return m


def add_cooling(spec: dict, types: dict, design: Design) -> CoolingModel:
    """Emit roles, device types, devices, power feeds and coolant cables for the model."""
    cs = spec["cooling"]
    m = model(spec, types, design)
    c = _Ctx(spec, types)
    c.d = design                                    # build into the composed design
    tags = c.tags
    # what the pods already built: device types/racks and the outlets their cords took
    for o in design.all("dcim.devices"):
        c.dev_type[o.data["name"]] = o.data["device_type"].key[0]
        if "rack" in o.data:
            c.dev_rack[o.data["name"]] = o.data["rack"].key[0]
    for o in design.all("dcim.cables"):
        for t in o.data["a_terminations"] + o.data["b_terminations"]:
            if t.kind == "dcim.poweroutlet":
                c.used.add((t.parent, t.name))
    for slug, (name, colour) in ROLES_COOLING.items():
        design.add("dcim.device_roles", slug, name=name, slug=slug, color=colour, tags=tags)
    slugs = {m.plant_type, m.crah_type, HEADER}
    for ls in cs["loops"].values():
        slugs |= {ls["unit"]["type"], ls["cdu"]["type"]}
    cat.add_to_design(design, types, sorted(slugs), tags)
    col = {k: v.lstrip("#").lower() for k, v in cs["colours"].items()}   # NetBox: lowercase hex

    # --- mechanical power panel: one feed per CDU, CRAH and plant module (CHOICE)
    panel = cs.get("panel", "PP-M")
    design.add("dcim.power_panels", panel, name=panel, site=c.site, location=c.location,
               tags=tags, description="Mechanical: CDUs, CRAHs and the cooling plant")

    def feed(dev: str, port: str, cls: str) -> None:
        pw, name = cs["feeds"][cls], f"{dev}-feed"
        design.add("dcim.power_feeds", name, name=name, power_panel=Ref("dcim.power_panels", (panel,)),
                   status="active", type="primary", supply="ac", phase=pw["phase"],
                   voltage=pw["voltage"], amperage=pw["amperage"], max_utilization=100,
                   tenant=c.tenant, tags=tags)
        c.power_cable(f"F-{dev}", "dcim.powerport", (dev, port), "dcim.powerfeed", (panel, name))

    def pipe(label: str, a: tuple, b: tuple, fabric: str) -> None:
        c.cable(label, a, b, "", fabric, color=col["supply" if fabric.endswith("supply") else "return"])

    # --- plant block + facility-water header; CRAHs hang off the header directly
    fws = m.fws_header
    c.device(fws, HEADER, "cooling-header", dgx_fabric="coolant-supply")
    for k, unit in enumerate(m.plant_units, start=1):
        c.device(unit, m.plant_type, "cooling-plant")
        feed(unit, cs["plant"]["power_port"], "plant")
        pipe(f"W-S-{unit}-{fws}", (unit, "SUPPLY"), (fws, f"CDU-S-{k}"), "coolant-supply")
        pipe(f"W-R-{fws}-{unit}", (fws, f"CDU-R-{k}"), (unit, "RETURN"), "coolant-return")
    n = 0                                            # consumer index on the FWS header
    for crah in m.crah_units:
        c.device(crah, m.crah_type, "cooling-crah")
        feed(crah, cs["residual_air"]["power_port"], "crah")
        n += 1
        pipe(f"W-S-{fws}-{crah}", (fws, f"S-{n}"), (crah, "SUPPLY"), "coolant-supply")
        pipe(f"W-R-{crah}-{fws}", (crah, "RETURN"), (fws, f"R-{n}"), "coolant-return")

    for lp in m.loops.values():
        ls = cs["loops"][lp.key]
        for hdr in lp.headers.values():              # one header per row the loop touches
            c.device(hdr, HEADER, "cooling-header", dgx_fabric="coolant-supply")
        # CDUs: primary pair to the FWS header; the single secondary pair to the loop's first
        # header (CDU-S-i / CDU-R-i). A loop that spans rows ties its headers together at
        # the CDU end (tee 6 of each header), so every rack still reaches every CDU.
        hs = list(lp.headers.values())
        for i, cdu in enumerate(lp.cdus, start=1):
            c.device(cdu, lp.cdu_type, "cooling-cdu")
            feed(cdu, ls["cdu"]["power_port"], "cdu")
            n += 1
            pipe(f"W-S-{fws}-{cdu}", (fws, f"S-{n}"), (cdu, "PRI-S"), "coolant-supply")
            pipe(f"W-R-{cdu}-{fws}", (cdu, "PRI-R"), (fws, f"R-{n}"), "coolant-return")
            pipe(f"W-S-{cdu}-{hs[0]}", (cdu, "SEC-S"), (hs[0], f"CDU-S-{i}"), "coolant-supply")
            pipe(f"W-R-{hs[0]}-{cdu}", (hs[0], f"CDU-R-{i}"), (cdu, "SEC-R"), "coolant-return")
        for a, b in zip(hs, hs[1:]):
            pipe(f"W-S-{a}-{b}", (a, "CDU-S-6"), (b, "CDU-S-6"), "coolant-supply")
            pipe(f"W-R-{b}-{a}", (b, "CDU-R-6"), (a, "CDU-R-6"), "coolant-return")
        # per-rack unit (door or manifold) + its hose pair to the header branch
        for r in lp.racks:
            unit = lp.unit_of[r]
            c.device(unit, lp.unit_type, UNIT_ROLE[lp.unit_kind], r, None,
                     dgx_su=design.get("dcim.racks", r).data["custom_fields"].get("dgx_su"))
            hdr, b = lp.header_of[r], lp.branch_of[r]
            pipe(f"W-S-{hdr}-{unit}", (hdr, f"S-{b}"), (unit, "SUPPLY"), "coolant-supply")
            pipe(f"W-R-{unit}-{hdr}", (unit, "RETURN"), (hdr, f"R-{b}"), "coolant-return")
            if types[lp.unit_type].get("power-ports"):   # door fans off the rack's rPDUs
                _power_device(c, unit)
    for (dev, ifc), cf in sorted(c.iface_cf.items()):
        design.add("dcim.interfaces", (dev, ifc), device=Ref("dcim.devices", (dev,)), name=ifc,
                   tags=tags, custom_fields=cf)
    return m


def hydraulic_edges(design: Design) -> list[tuple[str, str, str, str, str]]:
    """(a, a_port, b, b_port, fabric) for every coolant cable — the graph the tests, the
    scene and the tracing add-on walk."""
    out = []
    for o in design.all("dcim.cables"):
        f = o.data["custom_fields"]["dgx_fabric"]
        if f.startswith("coolant-"):
            a, b = o.data["a_terminations"][0], o.data["b_terminations"][0]
            out.append((a.parent, a.name, b.parent, b.name, f))
    return out
