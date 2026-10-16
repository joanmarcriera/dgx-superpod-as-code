"""Pure topology generator for one DGX SuperPOD SU built from DGX GB300 NVL72 racks.

Same contract as topology.build(): spec + catalog -> Design, deterministic, offline.
Numbers and their RA-GB300 citations live in spec/gb300-su.yaml and docs/ra-notes-gb300.md.

Naming (prefix gb- keeps it distinct from the H200 site):
  racks        gb-su1-r<nn> (NVL72), gb-mgmt-r<nn>
  NVL72 rack   gb-su1-r<nn>-t<tt> compute tray, -nvs<n> NVLink switch tray, -ps<n> power shelf,
               -oob-<a|b> in-rack SN2201
  IB           gb-ibl-r<rail>-cl<1|2> leaf (Fig. 8 "SU01-R01-CL01"), gb-ibs-<nn> spine
  Ethernet     gb-el-<nn> compute leaf, gb-esl-<nn> storage leaf, gb-eml-<nn> mgmt leaf,
               gb-es-<nn> spine, gb-oobs-<nn> OOB spine, gb-oob-mgmt-<nn>
Cable labels   N- NVLink, C- compute IB, E- Ethernet, O- OOB, P-/F- power, H- UFM HA
"""
from __future__ import annotations

import ipaddress
import math

from . import catalog as cat
from .model import Design, Ref
from .topology import (DEMARC, PDU, R750, ROLES, SN2201, SN4600C, UFM, _Ctx, _foundation,
                       _power_device, _topology_presets, ib_port, spine_count)

TRAY, NVS, SHELF = ("nvidia-dgx-gb300-compute-tray", "nvidia-dgx-gb300-nvlink-switch-tray",
                    "nvidia-dgx-gb300-power-shelf")
Q3400, SN5600, HPSE = "nvidia-q3400-rd", "nvidia-sn5600", "generic-hps-ethernet-appliance-2u"

ROLES_GB = {k: ROLES[k] for k in ("ib-compute-leaf", "ib-compute-spine", "eth-oob", "ufm",
                                  "mgmt-server", "pdu", "dc-demarc", "hps-storage")}
ROLES_GB.update({
    "gb-compute-tray": ("GB300 compute tray", "76b900"),
    "gb-nvlink-switch": ("NVLink switch tray", "2ca02c"),
    "gb-power-shelf": ("NVL72 power shelf", "d62728"),
    "eth-compute-leaf": ("Ethernet compute leaf", "ff7f0e"),
    "eth-storage-leaf": ("Ethernet storage leaf", "9467bd"),
    "eth-mgmt-leaf": ("Ethernet mgmt leaf", "ffbb78"),
    "eth-spine": ("Ethernet spine", "c49c94"),
    "eth-oob-spine": ("OOB spine", "8c564b"),
})

# CHOICE — NVL72 elevation is not in RA-GB300 (Fig. 1-2 are renderings). Common NVL72
# pattern, bottom-up: 4 power shelves, 8 trays, 9 NVLink switch trays, 10 trays, 4 shelves.
SHELF_U = [2, 3, 4, 5, 33, 34, 35, 36]
TRAY_U = [32 - i for i in range(10)] + [13 - i for i in range(8)]   # trays 1-10 top block
NVS_U = [22 - i for i in range(9)]
OOB_U = [38, 39]


def lane(i: int) -> str:
    """SN5600 400G breakout lane by 0-based index: swp<n>s<0|1> (2 lanes per 800G port)."""
    return f"swp{i // 2 + 1}s{i % 2}"


class _Lanes:
    """Hands out the next free breakout lane on each SN5600."""

    def __init__(self):
        self.next: dict[str, int] = {}

    def take(self, dev: str) -> str:
        i = self.next.get(dev, 0)
        self.next[dev] = i + 1
        return lane(i)


def build(spec: dict, types: dict[str, dict]) -> Design:
    c = _Ctx(spec, types)
    d, cp, et = c.d, spec["compute"], spec["ethernet"]
    if cp["sus"] != 1:
        raise ValueError("gb300 builder models one standalone SU (RA-GB300 has no 1-SU spine row "
                         "beyond it; multi-SU needs Table 3/4 spines)")
    _foundation(c, ROLES_GB)
    cat.add_to_design(d, types, [TRAY, NVS, SHELF, Q3400, SN5600, SN2201, SN4600C, R750, PDU,
                                 UFM, HPSE, DEMARC], c.tags)
    rk, pw = spec["racks"], spec["power"]

    # ------------------------------------------------------------------ racks + power
    racks = [f"gb-su1-r{k:02d}" for k in range(1, cp["racks_per_su"] + 1)]
    mgmt = [f"gb-mgmt-r{k:02d}" for k in range(1, rk["mgmt_racks"] + 1)]
    for name in racks + mgmt:
        su = 1 if name in racks else None
        d.add("dcim.racks", name, name=name, site=c.site, location=c.location, tenant=c.tenant,
              status="active", role=Ref("dcim.rack_roles", ("dgx-compute" if su else "dgx-management",)),
              u_height=rk["u_height"], width=19, outer_width=rk["width_mm"],
              outer_depth=rk["depth_mm"], outer_unit="mm", tags=c.tags, custom_fields={"dgx_su": su})
    for x in "ABC":
        d.add("dcim.power_panels", f"PP-{x}", name=f"PP-{x}", site=c.site, location=c.location,
              tags=c.tags, description=f"Source {x}")

    def feed(rack, name, panel, f):
        d.add("dcim.power_feeds", name, name=name, power_panel=Ref("dcim.power_panels", (panel,)),
              rack=Ref("dcim.racks", (rack,)), status="active", type="primary", supply="ac",
              phase=f["phase"], voltage=f["voltage"], amperage=f["amperage"], max_utilization=100,
              tenant=c.tenant, tags=c.tags)

    trays: list[tuple[str, int, int]] = []          # (name, rack index 1..8, tray 1..18)
    oob_ep: list[tuple[str, str]] = []
    in_rack_oob: dict[str, list[tuple[str, str]]] = {}
    for k, rack in enumerate(racks, start=1):
        eps: list[tuple[str, str]] = []
        for t in range(1, cp["trays_per_rack"] + 1):
            n = f"{rack}-t{t:02d}"
            c.device(n, TRAY, "gb-compute-tray", rack, TRAY_U[t - 1], dgx_su=1, dgx_fabric="compute")
            trays.append((n, k, t))
            eps += [(n, "BMC"), (n, "BF3-BMC"), (n, "LOM")]
        for s in range(1, cp["nvswitch_trays_per_rack"] + 1):
            n = f"{rack}-nvs{s}"
            c.device(n, NVS, "gb-nvlink-switch", rack, NVS_U[s - 1], dgx_su=1, dgx_fabric="nvlink")
            eps += [(n, "COMe1"), (n, "COMe2"), (n, "BMC")]
        for s in range(1, cp["power_shelves_per_rack"] + 1):
            n = f"{rack}-ps{s}"
            c.device(n, SHELF, "gb-power-shelf", rack, SHELF_U[s - 1], dgx_fabric="power")
            panel = "A" if s <= cp["power_shelves_per_rack"] // 2 else "B"
            fname = f"{rack}-feed-{s}"
            feed(rack, fname, f"PP-{panel}", pw["shelf_feed"])
            c.power_cable(f"F-{n}", "dcim.powerport", (n, "AC-IN"), "dcim.powerfeed",
                          (f"PP-{panel}", fname))
            eps.append((n, "BMC"))
        in_rack_oob[rack] = eps
        # NVLink: every tray to every switch tray (RA "NVLink Switch Tray": each GPU has one
        # link to each of the 18 chips; one NetBox link per tray/switch-tray pair).
        for t in range(1, cp["trays_per_rack"] + 1):
            for s in range(1, cp["nvswitch_trays_per_rack"] + 1):
                c.cable(f"N-{rack}-t{t:02d}-nvs{s}", (f"{rack}-t{t:02d}", f"NVL{s}"),
                        (f"{rack}-nvs{s}", f"NVL{t}"), "dac-passive", "nvlink", 1)

    for rack in mgmt:
        for i, x in enumerate("abc"[: pw["pdus_per_mgmt_rack"]]):
            fname, pdu = f"{rack}-feed-{x}", f"{rack}-pdu-{x}"
            feed(rack, fname, f"PP-{x.upper()}", pw["mgmt_feed"])
            c.device(pdu, PDU, "pdu", rack, None, dgx_fabric="power")
            c.power_cable(f"F-{pdu}", "dcim.powerport", (pdu, "Inlet I1"), "dcim.powerfeed",
                          (f"PP-{x.upper()}", fname))

    # ------------------------------------------------------------------ compute IB (Fig. 8)
    rails, per = cp["rails"], cp["leaves_per_rail"]
    leaves = {(r, l): f"gb-ibl-r{r}-cl{l}" for r in range(1, rails + 1) for l in range(1, per + 1)}
    racks_per_leaf = cp["racks_per_su"] // per
    down = racks_per_leaf * cp["trays_per_rack"]                     # 72
    up_total = len(leaves) * (cp["ib_ports"] - down)
    n_sp = spine_count(cp["ib_ports"] - down, up_total, cp["ib_ports"])
    spines = [f"gb-ibs-{i:02d}" for i in range(1, n_sp + 1)]
    for i, (r, l) in enumerate(sorted(leaves)):
        c.mount(mgmt[0] if r <= rails // 2 else mgmt[1], leaves[(r, l)], Q3400, "ib-compute-leaf",
                dgx_su=1, dgx_fabric="compute")
    for i, sp in enumerate(spines):
        c.mount(mgmt[0] if i < n_sp // 2 else mgmt[1], sp, Q3400, "ib-compute-spine",
                dgx_fabric="compute")
    for i, u in enumerate(cp["ufm"]):
        c.mount(mgmt[i % 2], u, UFM, "ufm", dgx_fabric="compute")

    for n, k, t in trays:
        l = (k - 1) // racks_per_leaf + 1
        idx = ((k - 1) % racks_per_leaf) * cp["trays_per_rack"] + (t - 1)
        for r in range(1, rails + 1):
            c.cable(f"C-{n}-R{r}", (n, f"CX8-{r}"), (leaves[(r, l)], ib_port(idx)), "mmf-om4",
                    "compute", 1, r)
    # UFM (Fig. 8: C-UFM-1/2 to rail leaves). Leaves have no spare port, so each UFM takes
    # the last uplink port of a rail-4 leaf (CHOICE, see spec validate note).
    ufm_leaf = {leaves[(rails, l)]: u for l, u in zip(range(1, per + 1), cp["ufm"])}
    for leaf, u in ufm_leaf.items():
        c.cable(f"C-{u}-ib1", (u, "ib1"), (leaf, ib_port(cp["ib_ports"] - 1)), "mmf-om4",
                "compute", 1, rails)
    sp_next = {sp: 0 for sp in spines}
    links = (cp["ib_ports"] - down) // n_sp
    for (r, l), leaf in sorted(leaves.items()):
        ports = list(range(down, cp["ib_ports"] - (1 if leaf in ufm_leaf else 0)))
        for j, p in enumerate(ports):
            sp = spines[min(j // links, n_sp - 1)]
            c.cable(f"C-{leaf}-{sp}-{p}", (leaf, ib_port(p)), (sp, ib_port(sp_next[sp])),
                    "mmf-om4", "compute", 1, r)
            sp_next[sp] += 1
    c.cable(f"H-{cp['ufm'][0]}-{cp['ufm'][1]}", (cp["ufm"][0], "ha0"), (cp["ufm"][1], "ha0"),
            "cat5e", "mgmt")

    # ------------------------------------------------------------------ Ethernet fabric
    el = [f"gb-el-{i:02d}" for i in range(1, et["compute_leaves"] + 1)]
    esl = [f"gb-esl-{i:02d}" for i in range(1, et["storage_leaves"] + 1)]
    eml = [f"gb-eml-{i:02d}" for i in range(1, et["mgmt_leaves"] + 1)]
    es = [f"gb-es-{i:02d}" for i in range(1, et["spines"] + 1)]
    oobs = [f"gb-oobs-{i:02d}" for i in range(1, et["oob_spines"] + 1)]
    net_rack, srv_rack = mgmt[2], mgmt[3]
    for n in el:
        c.mount(net_rack, n, SN5600, "eth-compute-leaf", dgx_fabric="inband")
    for n in esl:
        c.mount(net_rack, n, SN5600, "eth-storage-leaf", dgx_fabric="storage-eth")
    for n in eml:
        c.mount(net_rack, n, SN5600, "eth-mgmt-leaf", dgx_fabric="inband")
    for n in es:
        c.mount(net_rack, n, SN5600, "eth-spine", dgx_fabric="inband")
    for n in oobs:
        c.mount(net_rack, n, SN4600C, "eth-oob-spine", dgx_fabric="oob")
    for n in spec["mgmt_servers"]:
        c.mount(srv_rack, n, R750, "mgmt-server", dgx_fabric="inband")
    hps = [f"gb-hps-{i:02d}" for i in range(1, et["hps_appliances"] + 1)]
    for n in hps:
        c.mount(srv_rack, n, HPSE, "hps-storage", dgx_fabric="storage-eth")
    # The DC-core demarc: this SU's own by default; a mixed design shares one demarc between
    # pods and tells us which of its ports are ours (spec ethernet.demarc).
    dm = et.get("demarc") or {}
    demarc, core0 = dm.get("name", "gb-dc-core-demarc"), dm.get("first_port", 1)
    c.device(demarc, DEMARC, "dc-demarc")

    ln = _Lanes()
    half = len(el) // 2   # leaves 1..half serve racks 1-4 (P1 -> odd leaf, P2 -> even leaf)
    for n, k, t in trays:
        base = 0 if k <= cp["racks_per_su"] // 2 else half
        c.cable(f"E-{n}-P1", (n, "BF3-P1"), (el[base], ln.take(el[base])), "aoc", "storage-eth", 1)
        c.cable(f"E-{n}-P2", (n, "BF3-P2"), (el[base + 1], ln.take(el[base + 1])), "aoc",
                "inband", 1)
    for h in hps:
        for q in range(1, 5):
            leaf = esl[(q - 1) // 2 % len(esl)]
            c.cable(f"E-{h}-eth{q}", (h, f"eth{q}"), (leaf, ln.take(leaf)), "aoc", "storage-eth")
    for m in spec["mgmt_servers"]:
        for side, port in enumerate(("vpi3", "vpi4")):
            leaf = eml[side % len(eml)]
            c.cable(f"E-{m}-{port}", (m, port), (leaf, ln.take(leaf)), "aoc", "inband")
            c.iface_lag[(m, port)] = "bond0"

    def uplinks(leaf: str, count: int, fabric: str):
        for j in range(count):
            sp = es[j % len(es)]
            c.cable(f"E-{leaf}-{sp}-{j + 1}", (leaf, ln.take(leaf)), (sp, ln.take(sp)), "aoc", fabric)

    for leaf in el:
        uplinks(leaf, et["compute_leaf_uplinks"], "inband")
    for leaf in esl:   # storage leaves non-blocking: uplinks = downlinks
        uplinks(leaf, ln.next.get(leaf, 0), "storage-eth")
    for leaf in eml:
        uplinks(leaf, et["mgmt_leaf_uplinks"], "inband")
    for j in range(et["edge_links"]):   # "Customer Edge Connectivity": >= 2 x 100GbE
        sp = es[j % len(es)]
        c.cable(f"E-{sp}-edge{j + 1}", (sp, "swp64"), (demarc, f"core{core0 + j}"),
                "smf-os2", "inband")
    for i, o in enumerate(oobs):        # OOB rolled up into the spine layer (VXLAN)
        c.cable(f"E-{o}-{es[i % len(es)]}", (o, "swp64"), (es[i % len(es)], "swp63"), "aoc", "oob")

    # ------------------------------------------------------------------ OOB (SN2201)
    oob_switches: list[str] = []
    for k, rack in enumerate(racks, start=1):
        eps = in_rack_oob[rack]
        n_sw = math.ceil(len(eps) / 48)
        names = [f"{rack}-oob-{'ab'[i]}" for i in range(n_sw)]
        for i, n in enumerate(names):
            c.device(n, SN2201, "eth-oob", rack, OOB_U[i], dgx_su=1, dgx_fabric="oob")
        for i, (dev, ifc) in enumerate(eps):
            c.cable(f"O-{dev}-{ifc}", (dev, ifc), (names[i // 48], f"swp{i % 48 + 1}"), "cat5e", "oob")
        oob_switches += names
        oob_ep += eps
    mg_eps = [(n, "mgmt0") for n in c.dev_type if c.dev_type[n] == Q3400]
    mg_eps += [(n, "eth0") for n in c.dev_type if c.dev_type[n] in (SN5600, SN4600C)]
    mg_eps += [(n, "iDRAC9 1") for n in spec["mgmt_servers"]]
    mg_eps += [(u, "mgmt0") for u in cp["ufm"]]
    mg_eps += [(h, f"mgmt{q}") for h in hps for q in (1, 2)]
    mg_eps += [(n, "eth1") for n in c.dev_type if c.dev_type[n] == PDU]
    mg_sw = [f"gb-oob-mgmt-{i:02d}" for i in range(1, math.ceil(len(mg_eps) / 48) + 1)]
    for n in mg_sw:
        c.mount(net_rack, n, SN2201, "eth-oob", dgx_fabric="oob")
    for i, (dev, ifc) in enumerate(mg_eps):
        c.cable(f"O-{dev}-{ifc.replace(' ', '')}", (dev, ifc), (mg_sw[i // 48], f"swp{i % 48 + 1}"),
                "cat5e", "oob")
    oob_switches += mg_sw
    oob_ep += mg_eps
    sp_port = {o: 1 for o in oobs}
    for sw in oob_switches:   # 2 x 100G per SN2201 to the OOB spine pair
        for j, o in enumerate(oobs):
            c.cable(f"O-{sw}-{o}", (sw, f"swp{49 + j}"), (o, f"swp{sp_port[o]}"), "aoc", "oob")
            sp_port[o] += 1

    # ------------------------------------------------------------------ power (mgmt racks)
    for dev in sorted(c.dev_rack):
        if c.dev_rack[dev] in mgmt and c.dev_type[dev] != PDU:
            _power_device(c, dev)

    # ------------------------------------------------------------------ interface updates
    for (dev, ifc), cf in sorted(c.iface_cf.items()):
        data = dict(device=Ref("dcim.devices", (dev,)), name=ifc, tags=c.tags, custom_fields=cf)
        if (dev, ifc) in c.iface_lag:
            data["lag"] = Ref("dcim.interfaces", (dev, c.iface_lag[(dev, ifc)]))
        d.add("dcim.interfaces", (dev, ifc), **data)
    for dev in sorted({dv for (dv, _i) in c.iface_lag}):
        d.add("dcim.interfaces", (dev, "bond0"), device=Ref("dcim.devices", (dev,)), name="bond0",
              tags=c.tags, custom_fields={"dgx_fabric": "inband"})

    _ipam(c, trays, hps, oob_ep)
    roles = lambda *s: [Ref("dcim.device_roles", (x,)) for x in s]  # noqa: E731
    _topology_presets(c, {
        "rack-r01-nvlink": ("Rack r01 NVLink domain (18 trays x 9 switch trays)", {
            "role_id": roles("gb-compute-tray", "gb-nvlink-switch"),
            "rack_id": [Ref("dcim.racks", (racks[0],))]}),
        "compute-fabric": ("Compute IB fabric (rails, spines, UFM)", {
            "role_id": roles("ib-compute-leaf", "ib-compute-spine", "ufm")}),
        "rack-r01-to-rails": ("Rack r01 trays + their IB/Ethernet leaves", {
            "role_id": roles("gb-compute-tray", "ib-compute-leaf", "eth-compute-leaf"),
            "rack_id": [Ref("dcim.racks", (racks[0],))], "show_neighbors": True}),
        "ethernet-fabric": ("Ethernet fabric (leaves, spines, storage, mgmt)", {
            "role_id": roles("eth-compute-leaf", "eth-storage-leaf", "eth-mgmt-leaf", "eth-spine",
                             "eth-oob-spine", "hps-storage", "mgmt-server", "dc-demarc")}),
        "whole-site": ("Whole site (heavy)", {}),
    })
    return d


def _ipam(c: _Ctx, trays, hps, oob_ep) -> None:
    s, d = c.spec["ipam"], c.d
    net = ipaddress.ip_network
    site = c.spec["site"]["slug"]
    d.add("ipam.vlan_groups", site, name=c.spec["site"]["name"], slug=site, scope_type="dcim.site",
          scope=c.site, tags=c.tags)
    for key in ("oob", "inband", "storage"):
        d.add("ipam.vlans", (s[key]["vlan"],), vid=s[key]["vlan"], name=s[key]["vrf"],
              group=Ref("ipam.vlan_groups", (site,)), tenant=c.tenant, status="active", tags=c.tags)
    d.add("ipam.prefixes", (None, s["container"]), prefix=s["container"], status="container",
          tenant=c.tenant, tags=c.tags, description="DGX GB300 SU allocation")

    def vrf(name):
        if (name,) not in d.objs["ipam.vrfs"]:
            d.add("ipam.vrfs", name, name=name, enforce_unique=True, tenant=c.tenant, tags=c.tags)
        return Ref("ipam.vrfs", (name,))

    def prefix(v, p, desc, vlan=None, status="active"):
        data = dict(prefix=p, vrf=vrf(v), status=status, tenant=c.tenant, tags=c.tags,
                    description=desc)
        if vlan:
            data["vlan"] = Ref("ipam.vlans", (vlan,))
        d.add("ipam.prefixes", (v, p), **data)

    def assign(v, pool, hosts, first=10):
        refs = {}
        if first + len(hosts) >= pool.num_addresses - 1:
            raise ValueError(f"{pool} too small for {len(hosts)} hosts — widen it in the spec")
        for i, (dev, ifc) in enumerate(hosts):
            a = f"{pool.network_address + first + i}/{pool.prefixlen}"
            refs[(dev, ifc)] = d.add("ipam.ip_addresses", (v, a), address=a,
                                     vrf=Ref("ipam.vrfs", (v,)), status="active", tenant=c.tenant,
                                     tags=c.tags, assigned_object=Ref("dcim.interfaces", (dev, ifc)))
        return refs

    dev_ips: dict[str, dict] = {}
    o = s["oob"]
    prefix(o["vrf"], o["prefix"], "Out-of-band (BMC, BF3 BMC, LOM, COMe, shelves, switches)", o["vlan"])
    for (dev, _i), ref in assign(o["vrf"], net(o["prefix"]), oob_ep).items():
        dev_ips.setdefault(dev, {}).setdefault("oob_ip", ref)
    ib = s["inband"]
    prefix(ib["vrf"], ib["prefix"], "In-band (BF3 p2, mgmt bond0)", ib["vlan"])
    hosts = [(n, "BF3-P2") for n, _k, _t in trays] + [(m, "bond0") for m in c.spec["mgmt_servers"]]
    for (dev, _i), ref in assign(ib["vrf"], net(ib["prefix"]), hosts).items():
        dev_ips.setdefault(dev, {})["primary_ip4"] = ref
    st = s["storage"]
    prefix(st["vrf"], st["prefix"], "Storage RoCEv2 (BF3 p1, HPS)", st["vlan"])
    assign(st["vrf"], net(st["prefix"]), [(n, "BF3-P1") for n, _k, _t in trays]
           + [(h, f"eth{q}") for h in hps for q in range(1, 5)])
    ic = s["ib_compute"]
    rails = c.spec["compute"]["rails"]
    prefix(ic["vrf"], ic["prefix"], "IPoIB compute fabric", status="container")
    for r, sub in enumerate(list(net(ic["prefix"]).subnets(prefixlen_diff=math.ceil(math.log2(rails))))[:rails], 1):
        prefix(ic["vrf"], str(sub), f"IPoIB rail {r}")
        assign(ic["vrf"], sub, [(n, f"CX8-{r}") for n, _k, _t in trays])
    for dev, fields in sorted(dev_ips.items()):
        d.add("dcim.device_ips", dev, device=Ref("dcim.devices", (dev,)), **fields)
