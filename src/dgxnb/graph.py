"""Topology exports for visual tools, built offline from the Design (same source as NetBox).

  graph_json(spec, design)   compact device/link graph for the web viewer (viewer/)
  air_json(spec, design)     NVIDIA Air (dsx-air.nvidia.com) import file: a scaled-down,
                             simulatable Ethernet slice of the design (Cumulus VX switches,
                             Ubuntu hosts). InfiniBand and NVLink cannot run in Air.

Air JSON format: https://docs.nvidia.com/dsx-air/custom-topology.md ("JSON Topology Example").
"""
from __future__ import annotations

from collections import defaultdict

from .model import Design

# Viewer tiers (0 = top of the drawing). Roles not listed sit on tier 2.
TIER = {
    "ib-compute-spine": 0, "ib-storage-spine": 0, "eth-inband-spine": 0, "eth-spine": 0,
    "eth-oob-spine": 0,
    "ib-compute-leaf": 1, "ib-storage-leaf": 1, "eth-inband-leaf": 1, "eth-compute-leaf": 1,
    "eth-storage-leaf": 1, "eth-mgmt-leaf": 1, "eth-oob": 1, "ufm": 1, "dc-demarc": -1,
    "dgx-compute": 2, "gb-compute-tray": 2, "mgmt-server": 2, "hps-storage": 2,
    "nas-storage": 2, "eth-storage-backend": 1,
    "gb-nvlink-switch": 3, "gb-power-shelf": 3, "pdu": 3,
}
# Endpoint roles the viewer may fold into one node per rack.
GROUPABLE = {"dgx-compute", "gb-compute-tray", "gb-nvlink-switch", "gb-power-shelf", "pdu"}

AIR_SWITCH_OS = "cumulus-vx-5.16.1"      # images named in the Air docs example
AIR_HOST_OS = "generic/ubuntu2404"


def graph_json(spec: dict, design: Design) -> dict:
    devices = []
    for o in design.all("dcim.devices"):
        dd = o.data
        role = dd["role"].key[0]
        devices.append([dd["name"], role, dd["device_type"].key[0],
                        dd["rack"].key[0] if "rack" in dd else "", TIER.get(role, 2),
                        (dd.get("custom_fields") or {}).get("dgx_su") or 0])
    links = []
    for o in design.all("dcim.cables"):
        cf = o.data["custom_fields"]
        if cf["dgx_fabric"] == "power":
            continue
        a, b = o.data["a_terminations"], o.data["b_terminations"]
        links.append([a[0].parent, "+".join(t.name for t in a), b[0].parent,
                      "+".join(t.name for t in b), cf["dgx_fabric"], o.data["type"],
                      cf.get("dgx_rail") or 0, o.data["label"]])
    return {"site": spec["site"]["slug"], "name": spec["site"]["name"], "tag": spec["tag"],
            "description": spec["description"],
            "devices_cols": ["name", "role", "type", "rack", "tier", "su"],
            "links_cols": ["a", "a_port", "b", "b_port", "fabric", "cable", "rail", "label"],
            "devices": devices, "links": links}


def air_json(spec: dict, design: Design, hosts_per_leaf: int = 2,
             max_parallel: int = 2) -> tuple[dict, list]:
    """Scaled Ethernet slice for NVIDIA Air.

    Keeps every Ethernet switch on the in-band / storage-Ethernet fabrics (spines, leaves)
    and the first `hosts_per_leaf` hosts per leaf, with at most `max_parallel` links between
    any two nodes (enough to exercise ECMP/MLAG without hundreds of simulated ports).
    Port names are renumbered to what the simulated OS expects (switch swpN, host ethN);
    Returns (air_topology, port_map); port_map rows are [node, simulated port, real port]
    and are written next to the JSON (Air rejects unknown keys, so they stay out of it).
    """
    fabrics = {"inband", "storage-eth"} if any(
        o.data["custom_fields"]["dgx_fabric"] == "storage-eth" for o in design.all("dcim.cables")
    ) else {"inband"}
    role = {o.data["name"]: o.data["role"].key[0] for o in design.all("dcim.devices")}
    switch_roles = {"eth-inband-spine", "eth-inband-leaf", "eth-spine", "eth-compute-leaf",
                    "eth-storage-leaf", "eth-mgmt-leaf"}
    host_roles = {"dgx-compute", "gb-compute-tray", "mgmt-server", "hps-storage"}
    cables = [o for o in design.all("dcim.cables") if o.data["custom_fields"]["dgx_fabric"] in fabrics]
    keep_hosts: set[str] = set()
    per_leaf: dict[str, list[str]] = defaultdict(list)
    for o in cables:
        a, b = o.data["a_terminations"][0].parent, o.data["b_terminations"][0].parent
        for host, sw in ((a, b), (b, a)):
            if role.get(host) in host_roles and role.get(sw) in switch_roles:
                if host not in per_leaf[sw]:
                    per_leaf[sw].append(host)
    for sw, hosts in per_leaf.items():
        keep_hosts.update(hosts[:hosts_per_leaf])
    nodes, links, mapping = {}, [], []
    next_port: dict[str, int] = defaultdict(int)

    def port(dev: str, real: str) -> str:
        next_port[dev] += 1
        sim = f"{'swp' if role[dev] in switch_roles else 'eth'}{next_port[dev]}"
        mapping.append([dev, sim, real])
        return sim

    pair_links: dict[frozenset, int] = defaultdict(int)
    for o in cables:
        a, b = o.data["a_terminations"], o.data["b_terminations"]
        da, db = a[0].parent, b[0].parent
        ok = lambda d: role.get(d) in switch_roles or d in keep_hosts  # noqa: E731
        if not (ok(da) and ok(db)):
            continue
        pair = frozenset((da, db))
        if pair_links[pair] >= max_parallel:   # e.g. 12 leaf->spine lanes -> 2 in the sim
            continue
        pair_links[pair] += 1
        for dname in (da, db):
            if dname not in nodes:
                sw = role[dname] in switch_roles
                nodes[dname] = {"os": AIR_SWITCH_OS if sw else AIR_HOST_OS, "cpu": 2,
                                "memory": 4096 if sw else 2048, "storage": 20 if sw else 10}
        links.append([{"node": da, "interface": port(da, "+".join(t.name for t in a))},
                      {"node": db, "interface": port(db, "+".join(t.name for t in b))}])
    return ({"format": "JSON", "title": f"{spec['tag']} Ethernet slice", "ztp": None,
             "content": {"nodes": dict(sorted(nodes.items())), "links": links}}, mapping)
