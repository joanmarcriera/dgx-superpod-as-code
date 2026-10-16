"""Desired-state model: what the generator emits and the reconciler consumes.

The topology builder is pure — it produces `Obj` records with natural keys and
symbolic references (`Ref`) to other objects. The reconciler resolves refs to
NetBox ids at apply time, so the whole design can be built, counted and tested
offline without a NetBox instance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Ref:
    """Symbolic pointer to another object in the design (or an existing one).

    `kind` is a reconciler endpoint name (e.g. "dcim.devices"); `key` is that
    object's natural key tuple.
    """

    kind: str
    key: tuple

    def __repr__(self) -> str:  # compact in plan output
        return f"<{self.kind}:{'/'.join(map(str, self.key))}>"


@dataclass(frozen=True)
class Term:
    """A cable termination: `kind` is "dcim.interface", "dcim.powerport",
    "dcim.poweroutlet", "dcim.powerfeed" or "dcim.frontport"; `parent` names the
    device (or panel for feeds) and `name` the component."""

    kind: str
    parent: str
    name: str


@dataclass
class Obj:
    """One desired NetBox object. `data` holds API fields; values may be Refs."""

    kind: str
    key: tuple
    data: dict[str, Any] = field(default_factory=dict)


# Order in which object kinds are created (reverse for destroy). Each entry is a
# reconciler endpoint name; see reconcile.ENDPOINTS for the natural-key rules.
STAGES: list[str] = [
    "extras.tags",
    "extras.custom_field_choice_sets",
    "extras.custom_fields",
    "tenancy.tenant_groups",
    "tenancy.tenants",
    "dcim.regions",
    "dcim.sites",
    "dcim.locations",
    "dcim.rack_roles",
    "dcim.device_roles",
    "dcim.manufacturers",
    "dcim.device_types",
    "dcim.interface_templates",
    "dcim.power_port_templates",
    "dcim.power_outlet_templates",
    "dcim.console_port_templates",
    "dcim.module_bay_templates",
    "dcim.racks",
    "dcim.power_panels",
    "dcim.power_feeds",
    "dcim.devices",
    "dcim.interfaces",          # updates to template-created interfaces (+ virtual)
    "ipam.vrfs",
    "ipam.vlan_groups",
    "ipam.vlans",
    "ipam.prefixes",
    "ipam.ip_addresses",
    "dcim.cables",
    "extras.saved_filters",     # topology-views presets (needs roles/site ids)
    "dcim.device_ips",          # pseudo-stage: set oob_ip / primary_ip4 on devices
]


class Design:
    """Ordered collection of desired objects, indexed by (kind, key)."""

    def __init__(self) -> None:
        self.objs: dict[str, dict[tuple, Obj]] = {k: {} for k in STAGES}

    def add(self, kind: str, key: tuple | str, **data: Any) -> Ref:
        key = key if isinstance(key, tuple) else (key,)
        bucket = self.objs[kind]
        if key in bucket:
            raise ValueError(f"duplicate natural key {kind} {key}")
        bucket[key] = Obj(kind, key, data)
        return Ref(kind, key)

    def get(self, kind: str, key: tuple | str) -> Obj:
        key = key if isinstance(key, tuple) else (key,)
        return self.objs[kind][key]

    def all(self, kind: str) -> list[Obj]:
        return list(self.objs[kind].values())

    def count(self, kind: str) -> int:
        return len(self.objs[kind])
