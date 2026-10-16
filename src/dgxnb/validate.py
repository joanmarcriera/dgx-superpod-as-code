"""Validate the live NetBox design against the spec-derived BOM and fabric invariants.

Usage:  bin/validate [--spec PATH]      exit 0 = all checks pass, 1 = failures

Checks (docs/ra-notes.md for the numbers):
  counts      DGX nodes, GPUs, devices by role, racks, feeds, cables by fabric, IPs
              all equal what the spec generates (docs/bom-generated.md)
  rails       each DGX has 8 compute cables to 8 distinct leaves, one per rail,
              each leaf serving that rail only
  leaves      no compute leaf has more connected downlinks than uplinks
  cables      every tagged cable has both A and B terminations
  tagging     every device/rack/cable/IP at the site carries the design tag
  power       peak (allocated) draw per rack within the spec budget
  ipam        no design prefix overlaps any non-design prefix (other tenants)
  access      the design user cannot read users/groups/permissions (403)
Runs read-only as the NETBOX_TOKEN user.
"""
from __future__ import annotations

import argparse
import ipaddress
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

import pynetbox
import requests

from . import export
from .cli import ROOT, load_design


def cf(obj, name):
    """Custom-field value; select fields come back as {"value", "label"}."""
    v = (obj.custom_fields or {}).get(name)
    return v.get("value") if isinstance(v, dict) else v


class Checker:
    def __init__(self):
        self.failures: list[str] = []

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}{': ' + detail if detail else ''}")
        if not ok:
            self.failures.append(name)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="validate", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--spec", type=Path, default=ROOT / "spec" / "superpod.yaml")
    args = ap.parse_args(argv)
    url, token = os.environ.get("NETBOX_URL"), os.environ.get("NETBOX_TOKEN")
    if not url or not token:
        print("NETBOX_URL / NETBOX_TOKEN not set", file=sys.stderr)
        return 2
    spec, types, design = load_design(args.spec)
    want = export.counts(spec, types, design)
    # Fabric rules per pod (a mixed design has one node role / rail count per SU type).
    pods = export.pod_specs(spec)
    rules = {}
    for p in pods.values():
        v = p.get("validate", {})
        rules[v.get("compute_role", "dgx-compute")] = (p["compute"]["rails"],
                                                       v.get("max_leaf_oversubscription", 1.0))
    node_roles = set(rules)
    leaf_role = next(iter(pods.values())).get("validate", {}).get("leaf_role", "ib-compute-leaf")
    spine_role = next(iter(pods.values())).get("validate", {}).get("spine_role", "ib-compute-spine")
    max_over = max(r[1] for r in rules.values())
    tag = spec["tag"]
    nb = pynetbox.api(url, token, threading=True)
    c = Checker()

    site = nb.dcim.sites.get(slug=spec["site"]["slug"])
    if site is None:
        c.check("site exists", False, spec["site"]["slug"])
        return 1
    sid = site.id
    devices = list(nb.dcim.devices.filter(site_id=sid, limit=1000))
    dev_by_id = {d.id: d for d in devices}
    cables = list(nb.dcim.cables.filter(site_id=sid, limit=1000))

    # ---- counts ---------------------------------------------------------------
    gpn = export.node_roles(spec)
    dgx = [d for d in devices if d.role.slug in node_roles]
    gpus = sum(gpn[d.role.slug] for d in dgx)
    c.check("compute nodes", len(dgx) == want["dgx"], f"{len(dgx)} (want {want['dgx']})")
    c.check("GPUs", gpus == want["gpus"], f"{gpus} (want {want['gpus']})")
    roles = Counter(d.role.slug for d in devices)
    c.check("devices by role", roles == want["roles"],
            ", ".join(f"{r}={n}" for r, n in sorted(roles.items())))
    racks = nb.dcim.racks.count(site_id=sid)
    c.check("racks", racks == want["racks"], f"{racks} (want {want['racks']})")
    feeds = nb.dcim.power_feeds.count(site_id=sid)
    c.check("power feeds", feeds == want["feeds"], f"{feeds} (want {want['feeds']})")
    fab = Counter(cf(cb, "dgx_fabric") for cb in cables)
    c.check("cables by fabric", fab == want["cables_by_fabric"],
            ", ".join(f"{f}={n}" for f, n in sorted(fab.items(), key=str)))
    ips = nb.ipam.ip_addresses.count(tag=tag)
    c.check("IP addresses", ips == want["ips"], f"{ips} (want {want['ips']})")

    # ---- cable ends + rails ---------------------------------------------------
    ifaces = {i.id: i for i in nb.dcim.interfaces.filter(site_id=sid, limit=1000)}
    one_sided = [cb.label for cb in cables if not cb.a_terminations or not cb.b_terminations]
    c.check("every cable has two ends", not one_sided, f"{len(cables)} cables, "
            f"{len(one_sided)} one-sided {one_sided[:5]}")

    def ends(cb):
        return ([t.object_id for t in cb.a_terminations if t.object_type == "dcim.interface"],
                [t.object_id for t in cb.b_terminations if t.object_type == "dcim.interface"])

    node_links = defaultdict(list)    # dgx name -> [(leaf name, rail)]
    leaf_rails = defaultdict(set)
    down, up = Counter(), Counter()
    for cb in cables:
        if cf(cb, "dgx_fabric") != "compute":
            continue
        a, b = ends(cb)
        da = dev_by_id[ifaces[a[0]].device.id]
        db = dev_by_id[ifaces[b[0]].device.id]
        rail = cf(cb, "dgx_rail")
        if da.role.slug in node_roles:
            node_links[da.name].append((db.name, rail, rules[da.role.slug][0]))
            leaf_rails[db.name].add(rail)
        if db.role.slug == spine_role:
            up[da.name] += 1
        elif db.role.slug == leaf_role and da.role.slug in node_roles:
            down[db.name] += 1
    bad = [n for n, links in node_links.items()
           if len(links) != links[0][2] or len({l for l, _, _ in links}) != links[0][2]
           or sorted(r for _, r, _ in links) != list(range(1, links[0][2] + 1))]
    rails_txt = "/".join(str(r[0]) for r in rules.values())
    c.check(f"each node: {rails_txt} compute cables to as many distinct rail leaves",
            len(node_links) == len(dgx) and not bad, f"{len(node_links)} nodes, bad={bad[:5]}")
    mixed = [l for l, rs in leaf_rails.items() if len(rs) != 1]
    c.check("each leaf serves exactly one rail", not mixed, f"{len(leaf_rails)} leaves {mixed[:5]}")
    over = [f"{l} {down[l]}>{up[l]}" for l in set(down) | set(up) if down[l] > up[l] * max_over]
    worst = max((down[l] / up[l] for l in up), default=0)
    c.check(f"no compute leaf oversubscribed (node links : uplinks <= {max_over})",
            not over and bool(up), f"worst {worst:.3f} over {len(up)} leaves {over[:3]}")

    # ---- tagging ------------------------------------------------------------------
    untagged = [d.name for d in devices if tag not in [t.slug for t in d.tags]]
    untagged += [cb.label or cb.id for cb in cables if tag not in [t.slug for t in cb.tags]]
    untagged += [r.name for r in nb.dcim.racks.filter(site_id=sid) if tag not in
                 [t.slug for t in r.tags]]
    c.check("everything at the site is tagged", not untagged, f"untagged: {untagged[:5]}")

    # ---- power ----------------------------------------------------------------
    draw = defaultdict(float)
    for pp in nb.dcim.power_ports.filter(site_id=sid, limit=1000):
        d = dev_by_id[pp.device.id]
        if d.rack and pp.allocated_draw:
            draw[d.rack.name] += pp.allocated_draw / 1000
    worst = []
    for rack, kw in draw.items():
        cap = export.rack_budget(spec, rack)
        if kw > cap:
            worst.append(f"{rack} {kw:.1f}>{cap}")
    c.check("rack peak draw within budget", not worst and bool(draw),
            f"max {max(draw.values()):.2f} kW over {len(draw)} racks {worst[:3]}")

    # ---- IPAM isolation -------------------------------------------------------
    ours = [ipaddress.ip_network(p.prefix) for p in nb.ipam.prefixes.filter(tag=tag)]
    others = [p for p in nb.ipam.prefixes.all(limit=1000) if tag not in [t.slug for t in p.tags]]
    clash = [f"{p.prefix}" for p in others
             if any(ipaddress.ip_network(p.prefix).overlaps(o) for o in ours)]
    c.check("no overlap with non-design (other tenants) prefixes", not clash,
            f"{len(ours)} design prefixes vs {len(others)} others; clashes={clash[:5]}")

    # ---- access ----------------------------------------------------------------
    hdr = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    codes = {p: requests.get(f"{url}/api/users/{p}/", headers=hdr, timeout=10).status_code
             for p in ("users", "groups", "permissions", "tokens")}
    c.check("design user cannot manage users", all(v == 403 for k, v in codes.items()
                                                    if k != "tokens"), str(codes))

    print(f"\n{len(c.failures)} failure(s)" + (f": {c.failures}" if c.failures else ""))
    return 1 if c.failures else 0


if __name__ == "__main__":
    sys.exit(main())
