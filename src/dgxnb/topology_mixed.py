"""Mixed-pod generator: compose the H200 and GB300 SU builders under one site.

  build(spec, types) -> Design      same contract as topology.build (pure, deterministic)

A `kind: mixed` spec (spec/superpod-mixed.yaml) lists `pods`, each pointing at an existing
design spec (resolved by specload.py). Every pod is built by its own builder — unchanged, so
the pods stay RA-pure — with the mixed spec's site / tenant / tag substituted, and the two
Designs are merged by natural key:

  * an object present in both pods with identical data is created once (the foundation:
    tag, custom fields, tenant, site, roles, shared device types, the DC-core demarc);
  * `dcim.power_panels` are shared by name (PP-A/B/C), first pod wins the description;
  * anything else with the same key but different data is a real collision -> error.
  * SU numbers are renumbered so they are unique across the pod (pod 2's SU 1 -> SU 2).

Naming contract (asserted): H200 racks are `dgx-*` / `mgmt-*` / `stor-*`, GB300 racks are
`gb-*`, so nothing in one pod can shadow the other. The cooling layer (doors, manifolds,
headers, CDUs, plant and the coolant "cables") is added on top by cooling.py.
"""
from __future__ import annotations

import copy

from . import topology, topology_gb300
from .model import STAGES, Design, Ref

BUILDERS = {None: topology.build, "h-series": topology.build, "gb300-nvl72": topology_gb300.build}

# rack-name prefixes per pod: the assertion that the two pods cannot collide
RACK_PREFIX = {"h200": ("dgx-", "mgmt-", "stor-"), "gb300": ("gb-",)}
FIRST_WINS = {"dcim.power_panels"}          # shared by name; descriptions differ per builder
REBUILT = {"extras.saved_filters"}          # per-pod presets collide by slug: rebuilt for the mix


def pod_spec(spec: dict, name: str) -> dict:
    """The pod's own spec with the mixed design's identity substituted."""
    p = copy.deepcopy(spec["pods"][name]["spec"])
    for k in ("name", "tag", "description", "tenancy", "site"):
        p[k] = copy.deepcopy(spec[k])
    return p


def pod_of_rack(spec: dict, rack: str) -> str:
    hits = [pod for pod, pre in RACK_PREFIX.items() if pod in spec["pods"] and rack.startswith(pre)]
    if len(hits) != 1:
        raise ValueError(f"rack {rack!r} matches {len(hits)} pod naming prefixes")
    return hits[0]


def _renumber_su(design: Design, offset: int) -> None:
    """Shift every dgx_su custom field by `offset` (new dicts: cable and interface entries
    share the same cf dict object in the builders, so mutating in place would double-shift)."""
    if not offset:
        return
    for kind in STAGES:
        for o in design.all(kind):
            cf = o.data.get("custom_fields")
            if cf and cf.get("dgx_su") is not None:
                o.data["custom_fields"] = {**cf, "dgx_su": cf["dgx_su"] + offset}


def merge(into: Design, other: Design, label: str) -> None:
    for kind in STAGES:
        if kind in REBUILT:
            continue
        for key, obj in other.objs[kind].items():
            have = into.objs[kind].get(key)
            if have is None:
                into.objs[kind][key] = obj
            elif have.data == obj.data or kind in FIRST_WINS:
                continue
            else:
                raise ValueError(f"{label}: {kind} {key} collides with a different definition")


def build(spec: dict, types: dict[str, dict]) -> Design:
    if spec.get("kind") != "mixed":
        raise ValueError("topology_mixed.build expects kind: mixed")
    d = Design()
    su_offset = 0
    for name, pod in spec["pods"].items():
        ps = pod_spec(spec, name)
        sub = BUILDERS[ps.get("kind")](ps, types)
        _renumber_su(sub, su_offset)
        su_offset += ps["compute"]["sus"]
        for o in sub.all("dcim.racks"):
            if pod_of_rack(spec, o.key[0]) != name:
                raise ValueError(f"pod {name} built rack {o.key[0]} outside its naming prefix")
        merge(d, sub, name)
    for kind in REBUILT:
        d.objs[kind].clear()
    if spec.get("cooling"):
        from . import cooling
        cooling.add_cooling(spec, types, d)
    _presets(spec, d)
    return d


def _presets(spec: dict, d: Design) -> None:
    """netbox-topology-views presets for the mix (see topology._topology_presets)."""
    site = Ref("dcim.sites", (spec["site"]["slug"],))
    roles = lambda *s: [Ref("dcim.device_roles", (x,)) for x in s]   # noqa: E731
    presets = {
        "h200-compute-fabric": ("SU 1 (H200) compute IB fabric", {
            "role_id": roles("dgx-compute", "ib-compute-leaf", "ib-compute-spine", "ufm"),
            "cf_dgx_su": [1]}),
        "gb300-compute-fabric": ("SU 2 (GB300) compute IB fabric", {
            "role_id": roles("ib-compute-leaf", "ib-compute-spine", "ufm"), "cf_dgx_su": [2]}),
        "gb300-rack-r01-nvlink": ("GB300 rack r01 NVLink domain", {
            "role_id": roles("gb-compute-tray", "gb-nvlink-switch"),
            "rack_id": [Ref("dcim.racks", ("gb-su1-r01",))]}),
        "shared-core": ("Shared DC core, in-band spines, VAST tier 2", {
            "role_id": roles("dc-demarc", "eth-inband-spine", "eth-spine", "nas-storage",
                             "eth-storage-backend")}),
        "cooling": ("Cooling: plant, CDUs, headers, doors and manifolds", {
            "role_id": roles("cooling-plant", "cooling-cdu", "cooling-header", "cooling-rdhx",
                             "cooling-manifold")}),
        "whole-site": ("Whole site (heavy)", {}),
    }
    for key, (label, params) in presets.items():
        slug = f"{spec['tag']}-{key}"
        params = dict(params, site_id=[site], show_cables=True, group_racks=False)
        d.add("extras.saved_filters", slug, name=f"{spec['site']['slug']}: {label}", slug=slug,
              object_types=["dcim.device"], parameters=params, shared=True, enabled=True,
              description="netbox-topology-views preset (bin/dgxnb)")
