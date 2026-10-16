"""Pure topology generator: spec (dict) + catalog -> Design.

Deterministic: the same spec always yields the same names, ports, cable labels and
IPs, so re-running apply is a no-op. No NetBox access here — everything is tested
offline (tests/test_topology.py). Sizing rules and their RA citations live in
docs/ra-notes.md; the comments below name the row they implement.

Naming scheme
  racks        dgx-su<s>-r<nn>, mgmt-r<nn>
  DGX          dgx-su<s>-n<nn>                 (node slot nn = 1..32 within SU s)
  compute IB   ibc-su<s>-leaf-r<rail>, ibc-spine-<nn>
  storage IB   ibs-leaf-<nn>, ibs-spine-<nn>
  in-band      inb-su<s>-leaf-<a|b>, inb-spine-<nn>
  OOB          oob-sw-<nn>
  PDUs/feeds   <rack>-pdu-<a|b|c>, <rack>-feed-<a|b|c>
  cable labels <fabric letter>-<endpoint summary>, unique across the design
"""
from __future__ import annotations

import ipaddress
import math

from . import catalog as cat
from .model import Design, Ref, Term

# Shared by every design in this repo (one choice set in NetBox) — only ever append.
FABRICS = [("compute", "Compute IB"), ("storage", "Storage IB"), ("inband", "In-band Ethernet"),
           ("oob", "Out-of-band"), ("power", "Power"), ("mgmt", "Management HA"),
           ("nvlink", "NVLink"), ("storage-eth", "Storage Ethernet"),
           ("coolant-supply", "Coolant supply"), ("coolant-return", "Coolant return")]

ROLES = {  # slug: (name, colour)
    "dgx-compute": ("DGX compute", "76b900"),
    "ib-compute-leaf": ("IB compute leaf", "1f77b4"),
    "ib-compute-spine": ("IB compute spine", "17becf"),
    "ib-storage-leaf": ("IB storage leaf", "9467bd"),
    "ib-storage-spine": ("IB storage spine", "c5b0d5"),
    "eth-inband-leaf": ("In-band leaf", "ff7f0e"),
    "eth-inband-spine": ("In-band spine", "ffbb78"),
    "eth-oob": ("OOB switch", "8c564b"),
    "ufm": ("UFM appliance", "e377c2"),
    "mgmt-server": ("Management server", "7f7f7f"),
    "hps-storage": ("HPS storage", "bcbd22"),
    "nas-storage": ("NAS storage (VAST)", "dbdb8d"),
    "eth-storage-backend": ("Storage backend switch", "f7b6d2"),
    "pdu": ("Rack PDU", "d62728"),
    "dc-demarc": ("DC core demarc", "aec7e8"),
}

# Static device-type choices (library slugs / custom slugs).
QM9700, SN4600C, SN2201 = "nvidia-qm9700", "mellanox-sn4600c", "nvidia-sn2201"
R750, PDU, UFM = "dell-poweredge-r750", "raritan-px3-5730-v2", "nvidia-ufm-appliance-3-1"
# DGX racks (when spec power.dgx_pdu_type is set): horizontal 3U rPDU of RA Table 7
PDU_H = "raritan-px3-5878i2r-3u"
PDU_TYPES = {PDU, PDU_H}
HPS, DEMARC = "generic-hps-appliance-2u", "generic-dc-core-demarc"
CBOX, DBOX = "vast-cbox", "vast-dbox-df3015v2"

# Rail r (1..8) = GPU r-1; port per UG Table 6 (GPU affinity of each OSFP port).
RAIL_PORT = {1: "OSFP4P2", 2: "OSFP3P2", 3: "OSFP3P1", 4: "OSFP4P1",
             5: "OSFP1P2", 6: "OSFP2P2", 7: "OSFP2P1", 8: "OSFP1P1"}
DGX_STORAGE = ("Slot1P1", "Slot2P1")  # P1 defaults to IB (UG Table 5)
DGX_INBAND = ("Slot1P2", "Slot2P2")   # P2 defaults to Ethernet


def ib_port(i: int) -> str:
    """QM9700 port by 0-based index: cage i//2, lane i%2 (library naming P<cage>.<lane>)."""
    return f"P{i // 2}.{i % 2}"


def spine_count(uplinks_per_leaf: int, total_uplinks: int, ports: int = 64) -> int:
    """Smallest spine count that (a) divides each leaf's uplinks evenly, so every leaf
    reaches every spine with the same number of links, and (b) has enough ports.
    Reproduces RA Table 4: 1 SU -> 4, 2 -> 8, 3 -> 16, 4 -> 16."""
    for s in range(1, uplinks_per_leaf + 1):
        if uplinks_per_leaf % s == 0 and s * ports >= total_uplinks:
            return s
    raise ValueError("fabric exceeds a two-tier design")


class _Ctx:
    """Mutable build state shared by the section builders."""

    def __init__(self, spec: dict, types: dict[str, dict]):
        self.spec, self.types, self.d = spec, types, Design()
        self.tag = spec["tag"]
        self.tags = [Ref("extras.tags", (self.tag,))]
        self.tenant = Ref("tenancy.tenants", (spec["tenancy"]["tenant"],))
        self.site = Ref("dcim.sites", (spec["site"]["slug"],))
        self.location = Ref("dcim.locations", (spec["site"]["location"],))
        self.dev_type: dict[str, str] = {}          # device name -> type slug
        self.dev_rack: dict[str, str] = {}          # device name -> rack name
        self.iface_cf: dict[tuple, dict] = {}       # (device, iface) -> custom fields
        self.iface_lag: dict[tuple, str] = {}       # (device, iface) -> lag iface name
        self.used: set[tuple] = set()               # (device, component) already cabled
        self.rack_cursor: dict[str, int] = {}

    # --- devices -------------------------------------------------------------
    def device(self, name, type_slug, role, rack=None, position=None, **cf):
        data = dict(name=name, device_type=Ref("dcim.device_types", (type_slug,)),
                    role=Ref("dcim.device_roles", (role,)), site=self.site,
                    location=self.location, tenant=self.tenant, status="active",
                    tags=self.tags, custom_fields={k: v for k, v in cf.items()})
        if rack:
            data["rack"] = Ref("dcim.racks", (rack,))
            if position is not None:
                data.update(position=position, face="front")
        self.d.add("dcim.devices", name, **data)
        self.dev_type[name] = type_slug
        if rack:
            self.dev_rack[name] = rack

    def mount(self, rack: str, name: str, type_slug: str, role: str, **cf):
        """Stack a device top-down in a management rack (starting 4U below the top)."""
        h = self.types[type_slug]["u_height"]
        top = self.rack_cursor.setdefault(rack, self.spec["racks"]["u_height"] - 4)
        pos = top - h + 1
        if pos < 1:
            raise ValueError(f"rack {rack} is full")
        self.rack_cursor[rack] = pos - 1
        self.device(name, type_slug, role, rack, pos, **cf)

    # --- cables --------------------------------------------------------------
    def _claim(self, dev: str, comp: str, section: str) -> None:
        names = cat.component_names(self.types[self.dev_type[dev]], section)
        if comp not in names:
            raise KeyError(f"{dev} has no {section[:-1]} {comp!r}")
        if (dev, comp) in self.used:
            raise ValueError(f"{dev}:{comp} is already cabled")
        self.used.add((dev, comp))

    def cable(self, label, a, b, ctype, fabric, su=None, rail=None, *, color=None):
        """Data cable between interfaces. `a`/`b` are (device, iface) or lists of them
        (a list on one side models a breakout/splitter cable)."""
        a_list = a if isinstance(a, list) else [a]
        b_list = b if isinstance(b, list) else [b]
        cf = {"dgx_fabric": fabric, "dgx_su": su, "dgx_rail": rail}
        for dev, ifc in a_list + b_list:
            self._claim(dev, ifc, "interfaces")
            self.iface_cf[(dev, ifc)] = cf
        data = dict(label=label, type=ctype, status="connected", tenant=self.tenant,
                    tags=self.tags, custom_fields=cf,
                    a_terminations=[Term("dcim.interface", *x) for x in a_list],
                    b_terminations=[Term("dcim.interface", *x) for x in b_list])
        if color:
            data["color"] = color
        self.d.add("dcim.cables", label, **data)

    def power_cable(self, label, a_kind, a, b_kind, b):
        for kind, (dev, comp) in ((a_kind, a), (b_kind, b)):
            if kind == "dcim.powerport":
                self._claim(dev, comp, "power-ports")
            elif kind == "dcim.poweroutlet":
                self._claim(dev, comp, "power-outlets")
        self.d.add("dcim.cables", label, label=label, type="power", status="connected",
                   tenant=self.tenant, tags=self.tags,
                   custom_fields={"dgx_fabric": "power", "dgx_su": None, "dgx_rail": None},
                   a_terminations=[Term(a_kind, *a)], b_terminations=[Term(b_kind, *b)])


def _foundation(c: _Ctx, roles: dict | None = None) -> None:
    s, d = c.spec, c.d
    d.add("extras.tags", c.tag, name=c.tag, slug=c.tag, color="76b900",
          description=s["description"])
    d.add("extras.custom_field_choice_sets", "dgx-fabric", name="dgx-fabric",
          extra_choices=[[k, v] for k, v in FABRICS], order_alphabetically=False)
    common = dict(group_name="DGX SuperPOD", required=False, ui_visible="always")
    d.add("extras.custom_fields", "dgx_su", name="dgx_su", label="SU", type="integer",
          object_types=["dcim.device", "dcim.rack", "dcim.interface", "dcim.cable"],
          description="Scalable Unit number", **common)
    d.add("extras.custom_fields", "dgx_rail", name="dgx_rail", label="Rail", type="integer",
          object_types=["dcim.interface", "dcim.cable"],
          description="Compute rail (1-8 = GPU0-7)", **common)
    d.add("extras.custom_fields", "dgx_fabric", name="dgx_fabric", label="Fabric role",
          type="select", choice_set=Ref("extras.custom_field_choice_sets", ("dgx-fabric",)),
          object_types=["dcim.device", "dcim.interface", "dcim.cable"],
          description="Which SuperPOD network/fabric", **common)
    t = s["tenancy"]
    d.add("tenancy.tenant_groups", t["group"], name=t["group"].title(), slug=t["group"], tags=c.tags)
    d.add("tenancy.tenants", t["tenant"], name=t["tenant_name"], slug=t["tenant"],
          group=Ref("tenancy.tenant_groups", (t["group"],)), tags=c.tags)
    st = s["site"]
    d.add("dcim.regions", st["region"], name=st["region_name"], slug=st["region"], tags=c.tags)
    d.add("dcim.sites", st["slug"], name=st["name"], slug=st["slug"], status="active",
          region=Ref("dcim.regions", (st["region"],)), tenant=c.tenant, tags=c.tags,
          description=s["description"])
    d.add("dcim.locations", st["location"], name=st["location_name"], slug=st["location"],
          site=c.site, tenant=c.tenant, status="active", tags=c.tags)
    for slug, name in (("dgx-compute", "DGX compute"), ("dgx-management", "DGX management"),
                       ("dgx-storage", "DGX storage")):
        d.add("dcim.rack_roles", slug, name=name, slug=slug, color="76b900", tags=c.tags)
    for slug, (name, color) in (roles or ROLES).items():
        d.add("dcim.device_roles", slug, name=name, slug=slug, color=color, tags=c.tags)


def _racks_and_power(c: _Ctx) -> tuple[list[str], list[str], list[str]]:
    """Racks, power panels/feeds and rPDUs. Storage racks (spec racks.storage_racks) are
    powered like management racks: two rPDUs, 2N (ra-notes 8.3)."""
    s, d = c.spec, c.d
    r, p, cmp = s["racks"], s["power"], s["compute"]
    per_su = math.ceil(cmp["nodes_per_su"] / r["dgx_per_rack"])
    dgx_racks = [f"dgx-su{su}-r{i:02d}" for su in range(1, cmp["sus"] + 1)
                 for i in range(1, per_su + 1)]
    mgmt_racks = [f"mgmt-r{i:02d}" for i in range(1, r["mgmt_racks"] + 1)]
    stor_racks = list(r.get("storage_racks", []))
    for name in dgx_racks + mgmt_racks + stor_racks:
        su = int(name[6]) if name.startswith("dgx-su") else None
        rrole = "dgx-compute" if su else "dgx-storage" if name in stor_racks else "dgx-management"
        d.add("dcim.racks", name, name=name, site=c.site, location=c.location, tenant=c.tenant,
              status="active", role=Ref("dcim.rack_roles", (rrole,)),
              u_height=r["u_height"], width=19, outer_width=r["width_mm"],
              outer_depth=r["depth_mm"], outer_unit="mm", tags=c.tags,
              custom_fields={"dgx_su": su})
    for x in p["panels"]:
        d.add("dcim.power_panels", f"PP-{x}", name=f"PP-{x}", site=c.site,
              location=c.location, tags=c.tags, description=f"Source {x} (discrete upstream path)")
    for rack in dgx_racks + mgmt_racks + stor_racks:
        n = p["pdus_per_dgx_rack"] if rack.startswith("dgx") else p["pdus_per_mgmt_rack"]
        for i in range(n):
            x = p["panels"][i % len(p["panels"])]
            feed, pdu = f"{rack}-feed-{x.lower()}", f"{rack}-pdu-{x.lower()}"
            d.add("dcim.power_feeds", feed, name=feed,
                  power_panel=Ref("dcim.power_panels", (f"PP-{x}",)),
                  rack=Ref("dcim.racks", (rack,)), status="active", type="primary",
                  supply="ac", phase=p["phase"], voltage=p["voltage"],
                  amperage=p["amperage"], max_utilization=p["max_utilization"],
                  tenant=c.tenant, tags=c.tags)
            # DGX racks: 3 x 3U horizontal rPDUs at power.dgx_pdu_positions (RA Table 7,
            # design-choices §6.1); everything else keeps the 0U vertical stand-in.
            if rack in dgx_racks and p.get("dgx_pdu_type"):
                c.device(pdu, p["dgx_pdu_type"], "pdu", rack, p["dgx_pdu_positions"][i],
                         dgx_fabric="power")
            else:
                c.device(pdu, PDU, "pdu", rack, None, dgx_fabric="power")
            c.power_cable(f"F-{pdu}", "dcim.powerport", (pdu, "Inlet I1"),
                          "dcim.powerfeed", (f"PP-{x}", feed))
    return dgx_racks, mgmt_racks, stor_racks


def _outlets(c: _Ctx, pdu: str, outlet_type: str) -> list[str]:
    dt = c.types[c.dev_type[pdu]]
    return [o["name"] for o in dt["power-outlets"]
            if o["type"] == outlet_type and (pdu, o["name"]) not in c.used]


def _power_device(c: _Ctx, dev: str) -> None:
    """Cable every PSU of `dev` to its rack's PDUs: PSU k -> PDU (k // per_pdu).
    DGX: 6 PSUs over 3 PDUs, two each (DCG Table 8 note 2 / 8.4); others: 1 per PDU."""
    rack = c.dev_rack[dev]
    pdus = sorted(n for n in c.dev_rack if n.startswith(f"{rack}-pdu-"))
    ports = c.types[c.dev_type[dev]].get("power-ports", [])
    per_pdu = math.ceil(len(ports) / len(pdus))
    for k, pp in enumerate(ports):
        pdu = pdus[k // per_pdu]
        otype = "iec-60320-c19" if pp["type"] == "iec-60320-c20" else "iec-60320-c13"
        free = _outlets(c, pdu, otype)
        if not free and otype == "iec-60320-c13":   # C13 exhausted: C13–C20 cord into a C19
            free = _outlets(c, pdu, "iec-60320-c19")
        if not free:
            raise ValueError(f"{pdu}: no free {otype} outlet for {dev}")
        c.power_cable(f"P-{dev}-{pp['name']}", "dcim.powerport", (dev, pp["name"]),
                      "dcim.poweroutlet", (pdu, free[0]))


def build(spec: dict, types: dict[str, dict]) -> Design:
    c = _Ctx(spec, types)
    d, cmp = c.d, spec["compute"]
    sus, rails, nps = cmp["sus"], cmp["rails"], cmp["nodes_per_su"]
    if not 1 <= sus <= 4:
        raise ValueError("two-tier RA design covers 1-4 SUs (RA Table 4)")
    dgx_type = f"nvidia-dgx-{cmp['gpu_gen']}"
    if dgx_type not in types:
        raise ValueError(f"no device type {dgx_type} in catalog")

    _foundation(c)
    st, nas = spec["storage"], spec.get("nas")
    hps_type = st.get("appliance_type", HPS)
    cat.add_to_design(d, types, [dgx_type, QM9700, SN4600C, SN2201, R750, PDU, UFM, hps_type,
                                 DEMARC] + ([PDU_H] if spec["power"].get("dgx_pdu_type") else []) + ([CBOX, DBOX] if nas else []), c.tags)
    _dgx_racks, mgmt, _stor = _racks_and_power(c)

    # --- DGX nodes: 2 per rack at DCG positions; last slot(s) of the pod go to UFM (1.4)
    rk = spec["racks"]
    total_slots = sus * nps
    displaced = set(range(total_slots - cmp["ufm_displaced_nodes"], total_slots))
    nodes: list[tuple[str, int, int]] = []       # (name, su, slot 1..32)
    for su in range(1, sus + 1):
        for n in range(1, nps + 1):
            if (su - 1) * nps + (n - 1) in displaced:
                continue
            rack = f"dgx-su{su}-r{(n - 1) // rk['dgx_per_rack'] + 1:02d}"
            pos = rk["dgx_positions"][(n - 1) % rk["dgx_per_rack"]]
            name = f"dgx-su{su}-n{n:02d}"
            c.device(name, dgx_type, "dgx-compute", rack, pos, dgx_su=su, dgx_fabric="compute")
            nodes.append((name, su, n))

    # --- Management-rack contents (layout mirrors RA H200 Fig. 3, packed per ra-notes §9)
    leaves_c = {(su, r): f"ibc-su{su}-leaf-r{r}" for su in range(1, sus + 1)
                for r in range(1, rails + 1)}
    n_spine_c = spine_count(nps, sus * rails * nps)
    spines_c = [f"ibc-spine-{i:02d}" for i in range(1, n_spine_c + 1)]
    # Compute switches split across the first `sus` mgmt racks, UFM-c alongside.
    for su in range(1, sus + 1):
        rack = mgmt[(su - 1) % len(mgmt)]
        for r in range(1, rails + 1):
            c.mount(rack, leaves_c[(su, r)], QM9700, "ib-compute-leaf", dgx_su=su,
                    dgx_fabric="compute")
        per = math.ceil(n_spine_c / sus)
        for sp in spines_c[(su - 1) * per: su * per]:
            c.mount(rack, sp, QM9700, "ib-compute-spine", dgx_fabric="compute")
    # rack for in-band + servers + storage, rack for storage IB + OOB + UFM-s
    rack_inb, rack_stor = mgmt[min(sus, len(mgmt) - 2)], mgmt[-1]
    ufm = spec["ufm"]
    for i, name in enumerate(ufm["compute"]):
        # One UFM-c per compute rack (RA H200 Fig. 3). At 1 SU there is a single compute
        # rack and 12 QM9700 + 2 UFM = 22.1 kW > the 21.8 kW 2N budget (ra-notes 8.3), so
        # the second UFM-c goes to the in-band rack instead.
        rack = mgmt[i % sus] if sus > 1 or i == 0 else rack_inb
        c.mount(rack, name, UFM, "ufm", dgx_fabric="compute")
    ib = spec["inband"]
    leaves_inb = {(su, x): f"inb-su{su}-leaf-{x}" for su in range(1, sus + 1) for x in "ab"}
    spines_inb = [f"inb-spine-{i:02d}" for i in range(1, ib["spines"] + 1)]
    for n in list(leaves_inb.values()) + spines_inb:
        c.mount(rack_inb, n, SN4600C, "eth-inband-leaf" if "leaf" in n else "eth-inband-spine",
                dgx_fabric="inband")
    for n in spec["mgmt_servers"]:
        c.mount(rack_inb, n, R750, "mgmt-server", dgx_fabric="inband")
    # Tier-1 storage: parallel-FS appliances on the storage IB fabric (DDN AI400X2T in the
    # spec; generic HPS when no type is given), in their own rack when the spec names one.
    prefix = st.get("appliance_prefix", "hps")
    hps = [f"{prefix}-{i:02d}" for i in range(1, st["hps_appliances"] + 1)]
    for n in hps:
        c.mount(st.get("rack", rack_inb), n, hps_type, "hps-storage", dgx_fabric="storage")
    # Tier-2 storage: VAST cluster (CBoxes + DBoxes + its own backend switch pair); the
    # CNodes' client ports land on the in-band spines, where the RA puts NFS (ra-notes 4.4).
    cboxes = dboxes = backend = []
    if nas:
        backend = [f"vast-be-{x}" for x in "ab"[:nas["backend_switches"]]]
        cboxes = [f"vast-cbox-{i:02d}" for i in range(1, nas["cbox"] + 1)]
        dboxes = [f"vast-dbox-{i:02d}" for i in range(1, nas["dbox"] + 1)]
        for n in backend:
            c.mount(nas["rack"], n, SN4600C, "eth-storage-backend", dgx_fabric="storage-eth")
        for n in cboxes:
            c.mount(nas["rack"], n, CBOX, "nas-storage", dgx_fabric="storage-eth")
        for n in dboxes:
            c.mount(nas["rack"], n, DBOX, "nas-storage", dgx_fabric="storage-eth")
    c.device("dc-core-demarc", DEMARC, "dc-demarc")

    # Storage IB (§9): 2 DGX-facing leaves per SU (A/B), device leaves for HPS/UFM/mgmt.
    leaves_sd = [f"ibs-leaf-{i:02d}" for i in range(1, 2 * sus + 1)]
    hps_ports = st["hps_appliances"] * st["hps_switch_ports"]
    dev_down = hps_ports + 2 * len(ufm["storage"]) + 2 * len(spec["mgmt_servers"])
    n_sdev = 1
    while math.ceil(dev_down / n_sdev) + math.ceil(hps_ports / n_sdev) > 64:
        n_sdev += 1
    leaves_ss = [f"ibs-leaf-{i:02d}" for i in range(2 * sus + 1, 2 * sus + 1 + n_sdev)]
    ss_up = math.ceil(hps_ports / n_sdev)
    total_up_s = len(leaves_sd) * st["dgx_leaf_uplinks"] + n_sdev * ss_up
    n_spine_s = spine_count(math.gcd(st["dgx_leaf_uplinks"], ss_up), total_up_s)
    spines_s = [f"ibs-spine-{i:02d}" for i in range(1, n_spine_s + 1)]
    for n in leaves_sd + leaves_ss:
        c.mount(rack_stor, n, QM9700, "ib-storage-leaf", dgx_fabric="storage")
    for n in spines_s:
        c.mount(rack_stor, n, QM9700, "ib-storage-spine", dgx_fabric="storage")
    for n in ufm["storage"]:
        c.mount(rack_stor, n, UFM, "ufm", dgx_fabric="storage")

    # ------------------------------------------------------------------ compute IB
    mmf = "mmf-om4"  # RA Table 8: "All networking components are multi-mode fiber"
    for name, su, n in nodes:
        for r in range(1, rails + 1):
            c.cable(f"C-{name}-R{r}", (name, RAIL_PORT[r]), (leaves_c[(su, r)], ib_port(n - 1)),
                    mmf, "compute", su, r)
    # UFM-c takes the displaced slot's leaf ports, rails 1.. in order (2.7)
    slot = total_slots - 1
    su_d, n_d = slot // nps + 1, slot % nps + 1
    ufm_ports = [(u, p) for u in ufm["compute"] for p in ("ib1", "ib2")]
    for r, (u, p) in enumerate(ufm_ports, start=1):
        c.cable(f"C-{u}-{p}", (u, p), (leaves_c[(su_d, r)], ib_port(n_d - 1)), mmf,
                "compute", su_d, r)
    k = nps // n_spine_c   # links from each leaf to each spine
    for li, ((su, r), leaf) in enumerate(sorted(leaves_c.items())):
        for si, sp in enumerate(spines_c):
            for j in range(k):
                up = nps + si * k + j
                c.cable(f"C-{leaf}-{sp}-{j + 1}", (leaf, ib_port(up)), (sp, ib_port(li * k + j)),
                        mmf, "compute", su, r)

    # ------------------------------------------------------------------ storage IB
    for name, su, n in nodes:
        for side, port in enumerate(DGX_STORAGE):
            leaf = leaves_sd[2 * (su - 1) + side]
            c.cable(f"S-{name}-{'AB'[side]}", (name, port), (leaf, ib_port(n - 1)), mmf,
                    "storage", su)
    free_ss = {l: 0 for l in leaves_ss}   # next free down-port per storage-device leaf

    def ss_port(i: int) -> tuple[str, str]:
        leaf = leaves_ss[i % n_sdev]
        idx = free_ss[leaf]
        free_ss[leaf] += 1
        return leaf, ib_port(idx)

    i = 0
    for h in hps:  # 8 splitters per appliance: 1 switch port -> 2 NDR200 ports (3.9)
        for j in range(st["hps_switch_ports"]):
            ports = [(h, f"ib{2 * j + q + 1}") for q in range(st["hps_ports_per_switch_port"])]
            c.cable(f"S-{h}-{j + 1}", ss_port(i), ports, mmf, "storage")
            i += 1
    for u in ufm["storage"]:
        for p in ("ib1", "ib2"):
            c.cable(f"S-{u}-{p}", (u, p), ss_port(i), mmf, "storage")
            i += 1
    for m in spec["mgmt_servers"]:
        for p in ("vpi1", "vpi2"):
            c.cable(f"S-{m}-{p}", (m, p), ss_port(i), mmf, "storage")
            i += 1
    spine_next = {sp: 0 for sp in spines_s}
    for leaf in leaves_sd + leaves_ss:
        up = st["dgx_leaf_uplinks"] if leaf in leaves_sd else ss_up
        first = 64 - up          # uplinks take the top of the port range
        if leaf in leaves_ss and free_ss[leaf] > first:
            raise ValueError(f"{leaf}: downlinks collide with uplinks")
        per = up // n_spine_s
        for si, sp in enumerate(spines_s):
            for j in range(per):
                c.cable(f"S-{leaf}-{sp}-{j + 1}", (leaf, ib_port(first + si * per + j)),
                        (sp, ib_port(spine_next[sp])), mmf, "storage")
                spine_next[sp] += 1

    # ------------------------------------------------------------------ in-band Ethernet
    aoc, dac = "aoc", "dac-passive"
    inb_next = {n: 1 for n in leaves_inb.values()}

    def inb(leaf: str) -> str:
        p = inb_next[leaf]
        inb_next[leaf] += 1
        return f"swp{p}"

    for name, su, n in nodes:  # bonded pair, one link to each leaf of the SU's MLAG pair
        for side, port in enumerate(DGX_INBAND):
            c.cable(f"I-{name}-{'AB'[side]}", (name, port), (leaves_inb[(su, "ab"[side])],
                                                             f"swp{n}"), aoc, "inband", su)
            c.iface_lag[(name, port)] = "bond0"
    for n in leaves_inb.values():
        inb_next[n] = nps + 1
    for k_, m in enumerate(spec["mgmt_servers"]):
        su = k_ % sus + 1
        for side, port in enumerate(("vpi3", "vpi4")):
            leaf = leaves_inb[(su, "ab"[side])]
            c.cable(f"I-{m}-{port}", (m, port), (leaf, inb(leaf)), aoc, "inband")
            c.iface_lag[(m, port)] = "bond0"
    isl = ib["isl_per_pair"]
    pairs = [(leaves_inb[(su, "a")], leaves_inb[(su, "b")]) for su in range(1, sus + 1)]
    pairs.append((spines_inb[0], spines_inb[1]))
    for a, b in pairs:  # ISLs on the top ports
        for j in range(isl):
            p = f"swp{64 - j}"
            c.cable(f"I-ISL-{a}-{b}-{j + 1}", (a, p), (b, p), dac, "inband")
    spn_next = {sp: 1 for sp in spines_inb}

    def spn(sp: str) -> str:
        p = spn_next[sp]
        spn_next[sp] += 1
        return f"swp{p}"

    upl = ib["leaf_uplinks_per_spine"]
    for leaf in leaves_inb.values():
        for si, sp in enumerate(spines_inb):
            for j in range(upl):
                p = f"swp{64 - isl - si * upl - j}"
                c.cable(f"I-{leaf}-{sp}-{j + 1}", (leaf, p), (sp, spn(sp)), aoc, "inband")
    for j in range(ib["dc_uplinks"]):
        sp = spines_inb[j % len(spines_inb)]
        ctype = "smf-os2" if j < 4 else aoc  # RA H200 Table 8: 4 CWDM4, rest AOC
        c.cable(f"I-{sp}-core{j + 1}", (sp, spn(sp)), ("dc-core-demarc", f"core{j + 1}"),
                ctype, "inband")
    # VAST: CNode front port 1 -> spine 1, port 2 -> spine 2 (client/NFS side, in-band);
    # back ports and DBox canisters -> the VAST backend pair (storage-eth), which is
    # VAST's private NVMe-oF fabric. In-rack backend runs are DAC (CHOICE).
    vast_front: list[tuple[str, str]] = []
    if nas:
        for cb in cboxes:
            for k in range(1, 5):
                for j, sp in enumerate(spines_inb[:2]):
                    ifc = f"cn{k}-fe{j + 1}"
                    c.cable(f"I-{cb}-{ifc}", (cb, ifc), (sp, spn(sp)), aoc, "inband")
                    vast_front.append((cb, ifc))
        be_next = {b: 1 for b in backend}

        def be(sw: str) -> str:
            p = be_next[sw]
            be_next[sw] += 1
            return f"swp{p}"

        for cb in cboxes:
            for k in range(1, 5):
                for j, sw in enumerate(backend):
                    c.cable(f"V-{cb}-cn{k}-be{j + 1}", (cb, f"cn{k}-be{j + 1}"), (sw, be(sw)),
                            dac, "storage-eth")
        for db in dboxes:
            for can in (1, 2):
                for j, sw in enumerate(backend):
                    c.cable(f"V-{db}-c{can}-p{j + 1}", (db, f"c{can}-p{j + 1}"), (sw, be(sw)),
                            dac, "storage-eth")
        if len(backend) == 2:
            for j in range(isl):
                p = f"swp{64 - j}"
                c.cable(f"V-ISL-{j + 1}", (backend[0], p), (backend[1], p), dac, "storage-eth")

    # ------------------------------------------------------------------ out-of-band
    oob_ep: list[tuple[str, str]] = [(n, "BMC") for n, _, _ in nodes]
    oob_ep += [(m, "iDRAC9 1") for m in spec["mgmt_servers"]]
    oob_ep += [(u, "mgmt0") for u in ufm["compute"] + ufm["storage"]]
    oob_ep += [(h, f"mgmt{q}") for h in hps for q in (1, 2)]
    oob_ep += [(cb, f"cn{k}-bmc") for cb in cboxes for k in range(1, 5)]
    oob_ep += [(db, f"c{k}-bmc") for db in dboxes for k in (1, 2)]
    oob_ep += [(n, "mgmt0") for n in c.dev_type if c.dev_type[n] == QM9700]
    oob_ep += [(n, "eth0") for n in c.dev_type if c.dev_type[n] == SN4600C]
    oob_ep += [(n, "eth1") for n in c.dev_type if c.dev_type[n] in PDU_TYPES]
    per_sw = spec["oob"]["ports_per_switch"]
    n_oob = math.ceil(len(oob_ep) / per_sw)
    oob_names = [f"oob-sw-{i:02d}" for i in range(1, n_oob + 1)]
    for n in oob_names:
        c.mount(rack_stor, n, SN2201, "eth-oob", dgx_fabric="oob")
    for i, (dev, ifc) in enumerate(oob_ep):
        sw = oob_names[i // per_sw]
        c.cable(f"O-{dev}-{ifc.replace(' ', '')}", (dev, ifc), (sw, f"swp{i % per_sw + 1}"),
                "cat5e", "oob")
    for sw in oob_names:  # "Two uplinks per OOB to in-band" (5.4): swp49 -> spine 1, swp50 -> 2
        for j in range(spec["oob"]["uplinks_per_switch"]):
            sp = spines_inb[j % len(spines_inb)]
            c.cable(f"I-{sw}-{sp}", (sw, f"swp{49 + j}"), (sp, spn(sp)), aoc, "oob")
    for pair in (ufm["compute"], ufm["storage"]):  # UFM back-to-back (6.3)
        c.cable(f"H-{pair[0]}-{pair[1]}", (pair[0], "ha0"), (pair[1], "ha0"), "cat5e", "mgmt")

    # ------------------------------------------------------------------ power
    for dev in sorted(c.dev_rack):
        if c.dev_type[dev] not in PDU_TYPES:
            _power_device(c, dev)

    # ------------------------------------------------------------------ interface updates
    for (dev, ifc), cf in sorted(c.iface_cf.items()):
        data = dict(device=Ref("dcim.devices", (dev,)), name=ifc, tags=c.tags,
                    custom_fields=cf)
        if (dev, ifc) in c.iface_lag:
            data["lag"] = Ref("dcim.interfaces", (dev, c.iface_lag[(dev, ifc)]))
        d.add("dcim.interfaces", (dev, ifc), **data)
    for dev in sorted({dv for (dv, _i) in c.iface_lag}):
        d.add("dcim.interfaces", (dev, "bond0"), device=Ref("dcim.devices", (dev,)),
              name="bond0", tags=c.tags, custom_fields={"dgx_fabric": "inband"})

    _ipam(c, nodes, oob_ep, vast_front)
    _topology_presets(c)
    return d


def _topology_presets(c: _Ctx, presets: dict | None = None) -> None:
    """Saved device filters that netbox-topology-views reads via ?filter_id=<id>.

    The plugin draws nothing unless show_cables is set (its default is off), so every
    preset turns it on. Slugs are prefixed with the design tag = ownership marker.
    """
    def role_ids(*slugs):
        return [Ref("dcim.device_roles", (s,)) for s in slugs]

    presets = presets or {
        "compute-fabric": ("Compute IB fabric (leaf/spine)",
                           {"role_id": role_ids("ib-compute-leaf", "ib-compute-spine", "ufm")}),
        "su1-rails": ("SU1 DGX -> rail leaves", {
            "role_id": role_ids("dgx-compute", "ib-compute-leaf"), "cf_dgx_su": [1]}),
        "storage-fabric": ("Storage IB fabric", {
            "role_id": role_ids("ib-storage-leaf", "ib-storage-spine", "hps-storage", "ufm")}),
        "vast": ("VAST cluster (tier-2 storage)", {
            "role_id": role_ids("nas-storage", "eth-storage-backend", "eth-inband-spine")}),
        "inband-oob": ("In-band + OOB management", {
            "role_id": role_ids("eth-inband-leaf", "eth-inband-spine", "eth-oob",
                                "mgmt-server", "dc-demarc")}),
        "whole-site": ("Whole site (heavy: ~220 nodes)", {}),
    }
    for key, (label, params) in presets.items():
        slug = f"{c.tag}-{key}"
        params = dict(params, site_id=[c.site], show_cables=True, group_racks=False)
        c.d.add("extras.saved_filters", slug, name=f"{c.spec['site']['slug']}: {label}",
                slug=slug, object_types=["dcim.device"], parameters=params, shared=True,
                enabled=True, description="netbox-topology-views preset (bin/dgxnb)")


def _ipam(c: _Ctx, nodes, oob_ep, vast_front=()) -> None:
    """VRFs, VLANs, prefixes and one IP per connected L3 interface (docs/ip-plan.md)."""
    s, d = c.spec["ipam"], c.d
    net = ipaddress.ip_network
    d.add("ipam.vlan_groups", c.spec["site"]["slug"], name=c.spec["site"]["name"],
          slug=c.spec["site"]["slug"], scope_type="dcim.site", scope=c.site, tags=c.tags)
    vg = Ref("ipam.vlan_groups", (c.spec["site"]["slug"],))
    for key, vname in (("inband", "dgx-inband"), ("oob", "dgx-oob")):
        d.add("ipam.vlans", (s[key]["vlan"],), vid=s[key]["vlan"], name=vname, group=vg,
              tenant=c.tenant, status="active", tags=c.tags)
    d.add("ipam.prefixes", (None, s["container"]), prefix=s["container"], status="container",
          tenant=c.tenant, tags=c.tags, description="DGX SuperPOD allocation")

    def vrf(name: str) -> Ref:
        if (name,) not in d.objs["ipam.vrfs"]:
            d.add("ipam.vrfs", name, name=name, enforce_unique=True, tenant=c.tenant, tags=c.tags)
        return Ref("ipam.vrfs", (name,))

    def prefix(v: str, p: str, desc: str, vlan=None, status="active"):
        data = dict(prefix=p, vrf=vrf(v), status=status, tenant=c.tenant, tags=c.tags,
                    description=desc)
        if vlan:
            data["vlan"] = Ref("ipam.vlans", (vlan,))
        d.add("ipam.prefixes", (v, p), **data)

    def ip(v: str, addr, plen: int, dev: str, ifc: str, desc: str = "") -> Ref:
        a = f"{addr}/{plen}"
        return d.add("ipam.ip_addresses", (v, a), address=a, vrf=Ref("ipam.vrfs", (v,)),
                     status="active", tenant=c.tenant, tags=c.tags, description=desc,
                     assigned_object=Ref("dcim.interfaces", (dev, ifc)))

    def take(pool: ipaddress.IPv4Network, i: int, first: int = 10):
        if first + i >= pool.num_addresses - 1:
            raise ValueError(f"{pool} too small for the design — widen it in spec")
        return pool.network_address + first + i

    dev_ips: dict[str, dict] = {}

    # In-band: DGX + mgmt server bond0
    ib_ = s["inband"]
    prefix(ib_["vrf"], ib_["prefix"], "In-band management (bonded 2x100G)", ib_["vlan"])
    pool = net(ib_["prefix"])
    inband_hosts = [n for n, _, _ in nodes] + list(c.spec["mgmt_servers"])
    for i, dev in enumerate(inband_hosts):
        ref = ip(ib_["vrf"], take(pool, i), pool.prefixlen, dev, "bond0")
        dev_ips.setdefault(dev, {})["primary_ip4"] = ref
    for i, (dev, ifc) in enumerate(vast_front, start=len(inband_hosts)):   # VAST client ports
        ref = ip(ib_["vrf"], take(pool, i), pool.prefixlen, dev, ifc, "VAST CNode client port")
        dev_ips.setdefault(dev, {}).setdefault("primary_ip4", ref)

    # OOB: /22 in the VRF, three /24 ranges (BMC, network devices, PDUs)
    ob = s["oob"]
    prefix(ob["vrf"], ob["prefix"], "Out-of-band management", ob["vlan"], status="container")
    rng = {k: net(v) for k, v in ob["ranges"].items()}
    for k, p in rng.items():
        prefix(ob["vrf"], str(p), f"OOB {k} range", ob["vlan"])
    counters = {k: 0 for k in rng}
    for dev, ifc in oob_ep:
        t = c.dev_type[dev]
        k = ("pdu" if t in PDU_TYPES else "bmc" if ifc in ("BMC", "iDRAC9 1") or ifc.endswith("bmc")
             else "netdev")
        ref = ip(ob["vrf"], take(rng[k], counters[k]), rng[k].prefixlen, dev, ifc)
        counters[k] += 1
        dev_ips.setdefault(dev, {}).setdefault("oob_ip", ref)

    # IPoIB compute: one subnet per rail (same host index on every rail)
    ic = s["ib_compute"]
    rails = c.spec["compute"]["rails"]
    base = net(ic["prefix"])
    subs = list(base.subnets(prefixlen_diff=math.ceil(math.log2(rails))))[:rails]
    prefix(ic["vrf"], ic["prefix"], "IPoIB compute fabric", status="container")
    for r, sub in enumerate(subs, start=1):
        prefix(ic["vrf"], str(sub), f"IPoIB compute rail {r}")
        for i, (dev, _su, _n) in enumerate(nodes):
            ip(ic["vrf"], take(sub, i), sub.prefixlen, dev, RAIL_PORT[r], f"rail {r}")

    # IPoIB storage: DGX A/B ports, then mgmt server storage ports
    is_ = s["ib_storage"]
    sp = net(is_["prefix"])
    prefix(is_["vrf"], is_["prefix"], "IPoIB storage fabric")
    hosts = [(n, p) for n, _, _ in nodes for p in DGX_STORAGE]
    hosts += [(m, p) for m in c.spec["mgmt_servers"] for p in ("vpi1", "vpi2")]
    for i, (dev, ifc) in enumerate(hosts):
        ip(is_["vrf"], take(sp, i), sp.prefixlen, dev, ifc)

    for dev, fields in sorted(dev_ips.items()):
        d.add("dcim.device_ips", dev, device=Ref("dcim.devices", (dev,)), **fields)
