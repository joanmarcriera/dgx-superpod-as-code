"""Reconcile NetBox to a Design: plan (diff only), apply, destroy.

Safety model (see the README):
  * An existing object is OWNED only if it carries the design tag (or, for kinds
    without tags, belongs to an owned parent / is a `dgx_*` custom field). Only
    owned objects are ever updated or deleted.
  * An existing UNOWNED object with the same natural key (e.g. a neighbouring tenant
    manufacturer "Dell") is ADOPTED read-only: its id is used for references,
    it is never modified, and any field difference is reported as a conflict.
  * Destroy deletes owned objects only, in reverse dependency order.

Everything is keyed by natural key (see KEYS), so apply is idempotent: a second
run reports zero changes.
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

import pynetbox

from .model import STAGES, Design, Obj, Ref, Term

CHUNK = 200
# Deleting a device cascades to all its components (a QM9700 has 65+ interfaces), so a
# 200-device batch outlives the reverse proxy's 60 s timeout (HTTP 504). Smaller batches
# for heavy kinds keep every request well inside it.
CHUNK_BY_KIND = {("dcim.devices", "delete"): 20, ("dcim.device_types", "delete"): 3,
                 ("dcim.devices", "create"): 50}
CF_GROUP = "DGX SuperPOD"

# kind -> (pynetbox app, endpoint attr)
EP = {k: tuple(k.split(".")) for k in STAGES if k != "dcim.device_ips"}
EP["dcim.device_ips"] = ("dcim", "devices")

# Natural key of an existing record (dict form). Must match topology keys.
_slug = lambda r: (r["slug"],)
KEYS: dict[str, Callable[[dict], tuple]] = {
    "extras.tags": _slug,
    "extras.custom_field_choice_sets": lambda r: (r["name"],),
    "extras.custom_fields": lambda r: (r["name"],),
    "tenancy.tenant_groups": _slug, "tenancy.tenants": _slug, "dcim.regions": _slug,
    "dcim.sites": _slug, "dcim.locations": _slug, "dcim.rack_roles": _slug,
    "dcim.device_roles": _slug, "dcim.manufacturers": _slug, "dcim.device_types": _slug,
    "dcim.racks": lambda r: (r["name"],), "dcim.power_panels": lambda r: (r["name"],),
    "dcim.power_feeds": lambda r: (r["name"],), "dcim.devices": lambda r: (r["name"],),
    "dcim.device_ips": lambda r: (r["name"],),
    "dcim.interfaces": lambda r: (r["device"]["name"], r["name"]),
    "ipam.vrfs": lambda r: (r["name"],), "ipam.vlan_groups": _slug,
    "ipam.vlans": lambda r: (r["vid"],),
    "ipam.prefixes": lambda r: ((r["vrf"] or {}).get("name"), r["prefix"]),
    "ipam.ip_addresses": lambda r: ((r["vrf"] or {}).get("name"), r["address"]),
    "dcim.cables": lambda r: (r["label"],),
    "extras.saved_filters": _slug,
}
for _t in ("interface", "power_port", "power_outlet", "console_port", "module_bay"):
    KEYS[f"dcim.{_t}_templates"] = lambda r: (r["device_type"]["slug"], r["name"])

TEMPLATE_KINDS = [k for k in STAGES if k.endswith("_templates")]
# Kinds whose objects NetBox creates implicitly (from device-type templates):
# we only ever update them, never create or delete them directly.
UPDATE_ONLY = {"dcim.interfaces", "dcim.device_ips"}
# Kinds deleted implicitly with their parent on destroy.
CASCADED = set(TEMPLATE_KINDS) | UPDATE_ONLY


def norm(v: Any) -> Any:
    """Normalise an API value for comparison: nested object -> id, choice -> value."""
    if isinstance(v, dict):
        if "value" in v and "label" in v and len(v) <= 3:
            return v["value"]
        if "id" in v:
            return v["id"]
        return {k: norm(x) for k, x in v.items()}
    if isinstance(v, list):
        return [norm(x) for x in v]
    if isinstance(v, str):
        return v.strip()  # NetBox strips text fields; YAML block scalars end in "\n"
    return v


# List fields that are sets (order-insensitive); every other list keeps its order.
SET_FIELDS = {"tags", "object_types"}


@dataclass
class Change:
    kind: str
    op: str                  # create | update | delete | conflict
    key: tuple
    diff: dict = field(default_factory=dict)


class Reconciler:
    def __init__(self, url: str, token: str, design: Design, tag: str, out=sys.stdout):
        self.nb = pynetbox.api(url, token, threading=True)
        self.d, self.tag, self.out = design, tag, out
        self.ids: dict[str, dict[tuple, int]] = defaultdict(dict)
        self.existing: dict[str, dict[tuple, dict]] = {}
        self.site_id: int | None = None
        self.tag_id: int | None = None
        # component lookups for cable terminations: (device, name) -> id
        self.comp: dict[str, dict[tuple, int]] = defaultdict(dict)

    # ------------------------------------------------------------------ fetch
    def _ep(self, kind: str):
        app, attr = EP[kind]
        return getattr(getattr(self.nb, app), attr)

    def _fetch(self, kind: str) -> list[dict]:
        """Fetch the candidate existing records for `kind`, scoped as narrowly as the
        natural key allows (never the whole shared instance when a site/tag filter exists)."""
        ep = self._ep(kind)
        want = self.d.objs[kind]
        if kind in TEMPLATE_KINDS:
            dt_ids = [i for i in self.ids["dcim.device_types"].values()]
            return [dict(r) for r in ep.filter(device_type_id=dt_ids)] if dt_ids else []
        if kind in ("dcim.racks", "dcim.power_panels", "dcim.power_feeds", "dcim.devices",
                    "dcim.device_ips", "dcim.interfaces", "dcim.cables", "dcim.locations"):
            if self.site_id is None:
                return []
            return [dict(r) for r in ep.filter(site_id=self.site_id, limit=1000)]
        if kind == "ipam.vlans":
            gid = next(iter(self.ids["ipam.vlan_groups"].values()), None)
            return [dict(r) for r in ep.filter(group_id=gid)] if gid else []
        if kind in ("ipam.prefixes", "ipam.ip_addresses"):
            # ours are tagged; untagged look-alikes are found by exact match below
            return [dict(r) for r in ep.filter(tag=self.tag, limit=1000)] if self.tag_id else []
        if kind == "extras.custom_fields":
            return [dict(r) for r in ep.filter(name=[k[0] for k in want])]
        if kind in ("extras.tags", "tenancy.tenant_groups", "tenancy.tenants", "dcim.regions",
                    "dcim.sites", "dcim.rack_roles", "dcim.device_roles", "dcim.manufacturers",
                    "dcim.device_types", "ipam.vlan_groups", "extras.saved_filters"):
            keys = [k[0] for k in want]
            return [dict(r) for r in ep.filter(slug=keys)] if keys else []
        if kind in ("extras.custom_field_choice_sets", "ipam.vrfs"):
            keys = [k[0] for k in want]
            return [dict(r) for r in ep.filter(name=keys)] if keys else []
        raise KeyError(kind)

    def _owned(self, kind: str, rec: dict) -> bool:
        if kind in TEMPLATE_KINDS:
            return rec["device_type"]["id"] in self.owned_dt
        if kind == "extras.custom_fields":
            return rec.get("group_name") == CF_GROUP
        if kind == "extras.custom_field_choice_sets":
            return rec["name"].startswith("dgx-")
        if kind == "extras.saved_filters":   # no tags on saved filters; slug prefix marks ours
            return rec["slug"].startswith(f"{self.tag}-")
        if kind == "extras.tags":
            return rec["slug"] == self.tag
        if kind == "dcim.device_ips":
            return any(t["slug"] == self.tag for t in rec.get("tags", []))
        return any(t["slug"] == self.tag for t in rec.get("tags") or [])

    def _sibling(self, rec: dict) -> bool:
        """True if another design from this repo owns `rec` (a `dgx-*` tag). Shared
        foundation objects (tenant, region, roles, common device types) are created by
        whichever design applies first and adopted read-only by the others."""
        return any(t["slug"].startswith("dgx-") and t["slug"] != self.tag
                   for t in rec.get("tags") or [])

    def load(self, kind: str) -> None:
        recs = self._fetch(kind)
        idx = {}
        for r in recs:
            try:
                idx[KEYS[kind](r)] = r
            except (KeyError, TypeError):
                continue
        self.existing[kind] = idx
        for key, r in idx.items():
            self.ids[kind][key] = r["id"]
        if kind == "extras.tags" and (self.tag,) in idx:
            self.tag_id = idx[(self.tag,)]["id"]
        if kind == "dcim.sites":
            site = next(iter(self.d.objs[kind]))
            rec = idx.get(site)
            if rec is not None and not self._owned(kind, rec):
                # Everything below is scoped by site: refuse to touch a site we don't own.
                raise RuntimeError(f"site {site[0]} exists but is not tagged {self.tag}; aborting")
            self.site_id = rec["id"] if rec else None
        if kind == "dcim.device_types":
            self.owned_dt = {r["id"] for r in idx.values() if self._owned(kind, r)}

    def load_components(self) -> None:
        """Index interfaces / power ports / outlets / feeds for cable terminations."""
        if self.site_id is None:
            return
        for kind, ep in (("dcim.interface", self.nb.dcim.interfaces),
                         ("dcim.powerport", self.nb.dcim.power_ports),
                         ("dcim.poweroutlet", self.nb.dcim.power_outlets)):
            self.comp[kind] = {(r.device.name, r.name): r.id
                               for r in ep.filter(site_id=self.site_id, limit=1000)}
        self.comp["dcim.powerfeed"] = {(r.power_panel.name, r.name): r.id for r in
                                       self.nb.dcim.power_feeds.filter(site_id=self.site_id)}

    # ------------------------------------------------------------------ resolve
    def resolve(self, v: Any) -> Any:
        """Replace Refs/Terms with ids. Unresolvable (not yet created) -> None marker."""
        if isinstance(v, Ref):
            if v.kind == "extras.tags":
                return self.ids[v.kind].get(v.key)
            if v.kind == "dcim.interfaces":
                return self.comp["dcim.interface"].get(v.key)
            return self.ids[v.kind].get(v.key)
        if isinstance(v, Term):
            oid = self.comp[v.kind].get((v.parent, v.name))
            return {"object_type": v.kind, "object_id": oid}
        if isinstance(v, list):
            return [self.resolve(x) for x in v]
        if isinstance(v, dict):
            return {k: self.resolve(x) for k, x in v.items()}
        return v

    def payload(self, obj: Obj) -> dict:
        data = dict(obj.data)
        if "assigned_object" in data:
            data["assigned_object_type"] = "dcim.interface"
            data["assigned_object_id"] = data.pop("assigned_object")
        if "scope" in data:
            data["scope_id"] = data.pop("scope")
        if obj.kind == "dcim.device_ips":
            data.pop("device")
        return self.resolve(data)

    # ------------------------------------------------------------------ diff
    def diff(self, obj: Obj, rec: dict, want: dict) -> dict:
        out = {}
        for k, v in want.items():
            if k in ("a_terminations", "b_terminations"):
                have = sorted((t["object_type"], t["object_id"]) for t in rec.get(k) or [])
                new = sorted((t["object_type"], t["object_id"]) for t in v)
                if have != new:
                    out[k] = (have, new)
                continue
            if k == "custom_fields":
                have_cf = rec.get("custom_fields") or {}
                d = {f: (norm(have_cf.get(f)), x) for f, x in v.items() if norm(have_cf.get(f)) != x}
                if d:
                    out[k] = d
                continue
            have, v = norm(rec.get(k)), norm(v)
            if have in (None, "") and v in (None, ""):
                continue   # a blank choice (e.g. a coolant "cable" with no type) reads back as null
            if k in SET_FIELDS and isinstance(have, list) and isinstance(v, list):
                have, v = sorted(have, key=repr), sorted(v, key=repr)
            if isinstance(have, float) and isinstance(v, (int, float)):
                have, v = float(have), float(v)
            if isinstance(v, (int, float)) and isinstance(have, str):
                try:
                    have = type(v)(have)
                except ValueError:
                    pass
            if have != v:
                out[k] = (have, v)
        return out

    def plan_kind(self, kind: str, prune: bool = True) -> list[Change]:
        changes = []
        have = self.existing.get(kind, {})
        for key, obj in self.d.objs[kind].items():
            want = self.payload(obj)
            rec = have.get(key)
            if rec is None:
                op = "update" if kind in UPDATE_ONLY else "create"
                changes.append(Change(kind, op, key, want))
                continue
            delta = self.diff(obj, rec, want)
            if not delta:
                continue
            if not self._owned(kind, rec) and kind != "dcim.interfaces" and not (
                    kind == "dcim.device_ips" and self._owned("dcim.devices", rec)):
                if set(delta) <= {"tags"} and self._sibling(rec):
                    continue   # shared with another design in this repo: adopt as-is
                changes.append(Change(kind, "conflict", key, delta))
            elif kind == "dcim.cables" and ("a_terminations" in delta or "b_terminations" in delta):
                changes.append(Change(kind, "replace", key, delta))
            else:
                changes.append(Change(kind, "update", key, delta))
        if prune and kind not in CASCADED:
            for key, rec in have.items():
                if key not in self.d.objs[kind] and self._owned(kind, rec):
                    changes.append(Change(kind, "delete", key))
        return changes

    # ------------------------------------------------------------------ apply
    def _bulk(self, kind: str, op: str, items: list) -> list:
        ep = self._ep(kind)
        done = []
        size = CHUNK_BY_KIND.get((kind, op), CHUNK)
        for i in range(0, len(items), size):
            chunk = items[i:i + size]
            if op == "create":
                res = ep.create(chunk)
                done.extend(res if isinstance(res, list) else [res])
            elif op == "update":
                ep.update(chunk)
            elif op == "delete":
                ep.delete(chunk)
        return done

    def apply_kind(self, kind: str, changes: list[Change]) -> None:
        by = defaultdict(list)
        for ch in changes:
            by[ch.op].append(ch)
        have = self.existing.get(kind, {})
        dels = [have[c.key]["id"] for c in by["delete"] + by["replace"]]
        if dels:
            self._bulk(kind, "delete", dels)
        creates = [self.payload(self.d.objs[kind][c.key]) for c in by["create"] + by["replace"]
                   if kind not in UPDATE_ONLY]
        for p in creates:
            missing = _nulls(p)
            if missing:
                raise RuntimeError(f"{kind}: unresolved reference(s) {missing} in {p}")
        created = self._bulk(kind, "create", creates) if creates else []
        ups = []
        for c in by["update"]:
            rec = have.get(c.key)
            if rec is None:
                raise RuntimeError(f"{kind} {c.key}: expected NetBox to have created it")
            ups.append({"id": rec["id"], **{k: self.payload(self.d.objs[kind][c.key])[k]
                                             for k in c.diff}})
        if ups and kind == "ipam.ip_addresses":
            self._undesignate(ups, have)
        if ups:
            self._bulk(kind, "update", ups)
        if created or ups or dels:
            self.load(kind)   # refresh ids for later stages
        for ch in by["conflict"]:
            self.say(f"  ! conflict (left untouched, not owned): {kind} {ch.key} {ch.diff}")

    def _undesignate(self, ups: list[dict], have: dict) -> None:
        """NetBox refuses to move an IP that is a device's oob_ip / primary_ip4 ("Cannot
        reassign IP address while it is designated as the OOB IP"). When a spec change shifts
        addresses between interfaces, clear those designations first; the device_ips stage
        sets the new ones afterwards."""
        moving = {u["id"] for u in ups if "assigned_object_id" in u}
        if not moving:
            return
        by_id = {r["id"]: r for r in have.values()}
        dev_ids = set()
        for ip_id in moving:
            ao = (by_id.get(ip_id) or {}).get("assigned_object") or {}
            dev = ao.get("device") or {}
            if dev.get("id"):
                dev_ids.add(dev["id"])
        if not dev_ids:
            return
        patches = []
        for d in self.nb.dcim.devices.filter(id=list(dev_ids), limit=1000):
            p = {}
            if d.oob_ip and d.oob_ip.id in moving:
                p["oob_ip"] = None
            if d.primary_ip4 and d.primary_ip4.id in moving:
                p["primary_ip4"] = None
            if p:
                patches.append({"id": d.id, **p})
        if patches:
            self.say(f"    un-designating {len(patches)} device OOB/primary IPs before moving addresses")
            self._bulk("dcim.devices", "update", patches)

    # ------------------------------------------------------------------ drivers
    def say(self, msg: str) -> None:
        print(msg, file=self.out, flush=True)

    def run(self, mode: str) -> dict[str, dict[str, int]]:
        """mode: plan | apply. Returns {kind: {op: count}}."""
        summary: dict[str, dict[str, int]] = {}
        for kind in STAGES:
            if kind in ("dcim.interfaces", "dcim.cables", "dcim.device_ips", "ipam.ip_addresses"):
                self.load_components()
            self.load(kind)
            changes = self.plan_kind(kind)
            counts: dict[str, int] = defaultdict(int)
            for ch in changes:
                counts[ch.op] += 1
            summary[kind] = dict(counts)
            total = self.d.count(kind)
            line = ", ".join(f"{op} {n}" for op, n in sorted(counts.items())) or "in sync"
            self.say(f"{kind:34s} desired {total:5d}  {line}")
            for ch in [c for c in changes if c.op in ("update", "replace", "conflict")][:3]:
                self.say(f"    {ch.op} {ch.key}: {_short(ch.diff)}")
            if mode == "apply" and changes:
                self.apply_kind(kind, changes)
        return summary

    def destroy(self, execute: bool) -> dict[str, int]:
        """Delete every owned object, reverse stage order. execute=False = dry run."""
        counts = {}
        for kind in STAGES:
            self.load(kind)
        for kind in reversed(STAGES):
            if kind in CASCADED:
                continue
            owned = [r["id"] for r in self.existing.get(kind, {}).values() if self._owned(kind, r)]
            if kind in ("ipam.prefixes", "ipam.ip_addresses", "dcim.cables"):
                # also catch owned rows outside our natural keys (e.g. after a spec change)
                owned = [r.id for r in self._ep(kind).filter(tag=self.tag, limit=1000)] \
                    if self.tag_id else []
            counts[kind] = len(owned)
            self.say(f"{kind:34s} delete {len(owned)}")
            if execute and owned:
                try:
                    self._bulk(kind, "delete", owned)
                except pynetbox.RequestError:
                    # Usually a shared object still referenced by a sibling design (e.g. the
                    # tenant). Retry one by one and keep whatever NetBox protects.
                    kept = 0
                    for oid in owned:
                        try:
                            self._bulk(kind, "delete", [oid])
                        except pynetbox.RequestError:
                            kept += 1
                    self.say(f"    kept {kept} still referenced by another design")
        return counts


def _nulls(v, path="") -> list[str]:
    if v is None:
        return [path]
    if isinstance(v, dict):
        out = []
        for k, x in v.items():
            if k in ("dgx_su", "dgx_rail", "description", "label", "position", "face",
                     "part_number", "comments", "vlan", "rack"):
                continue
            out += _nulls(x, f"{path}.{k}")
        return out
    if isinstance(v, list):
        return [p for i, x in enumerate(v) for p in _nulls(x, f"{path}[{i}]")]
    return []


def _short(d: dict, n: int = 160) -> str:
    s = repr(d)
    return s if len(s) <= n else s[: n - 3] + "..."
