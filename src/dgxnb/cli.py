"""dgxnb — reconcile the DGX SuperPOD design into NetBox.

Usage:
  dgxnb [plan]              diff only (default; read-only)
  dgxnb apply               create/update/prune to match the spec
  dgxnb destroy [--yes]     delete everything tagged with the design tag
                            (dry run without --yes)
  dgxnb export              write docs/cable-map.csv, docs/bom-generated.md,
                            docs/ip-plan.md, docs/superpod.drawio (+ graph/Air
                            JSON) from the spec (offline)
  dgxnb bom                 print generated BOM counts (offline)
  dgxnb elevations          fetch front rack elevations from NetBox as SVG into
                            docs/elevations/ (read-only)

Options:
  --spec PATH               spec file (default spec/superpod.yaml)

Environment (export both; never echo the token):
  NETBOX_URL, NETBOX_TOKEN — the API user needs object permissions on the design only.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import catalog, export, specload, topology_mixed

BUILDERS = {**topology_mixed.BUILDERS, "mixed": topology_mixed.build}

ROOT = Path(__file__).resolve().parents[2]


def load_design(spec_path: Path):
    spec = specload.load(spec_path)
    types = catalog.load(ROOT / "catalog")
    return spec, types, BUILDERS[spec.get("kind")](spec, types)


def docs_dir(spec: dict) -> Path:
    """Exports for the original design stay in docs/; any other spec gets docs/<name>/."""
    return ROOT / "docs" if spec["name"] == "dgx-superpod-512" else ROOT / "docs" / spec["name"]


def elevations(url: str, token: str, spec: dict, design) -> int:
    """Save NetBox's own front-elevation SVG for every design rack (docs/elevations/).

    Rack names come from a shared NetBox, so a file is written only for racks the spec
    defines, and only if the name is a plain filename (no path traversal).
    """
    import re

    import pynetbox
    import requests
    nb = pynetbox.api(url, token)
    out = docs_dir(spec) / "elevations"
    out.mkdir(parents=True, exist_ok=True)
    hdr = {"Authorization": f"Bearer {token}"}
    wanted = {k[0] for k in design.objs["dcim.racks"]}
    for rack in nb.dcim.racks.filter(tag=spec["tag"]):
        if rack.name not in wanted or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", rack.name):
            print(f"skipped rack {rack.name!r}: not in the spec or not a safe filename",
                  file=sys.stderr)
            continue
        r = requests.get(f"{url}/api/dcim/racks/{rack.id}/elevation/",
                         params={"face": "front", "render": "svg", "include_images": "false"},
                         headers=hdr, timeout=30)
        r.raise_for_status()
        (out / f"{rack.name}.svg").write_text(r.text)
        print(f"wrote {(out / rack.name).relative_to(ROOT)}.svg")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dgxnb", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", nargs="?", default="plan",
                    choices=["plan", "apply", "destroy", "export", "bom", "elevations"])
    ap.add_argument("--spec", type=Path, default=ROOT / "spec" / "superpod.yaml")
    ap.add_argument("--yes", action="store_true", help="really delete (destroy only)")
    args = ap.parse_args(argv)

    spec, types, design = load_design(args.spec)
    if args.mode == "bom":
        print(export.bom_markdown(spec, types, design))
        return 0
    if args.mode == "export":
        for path in export.write_all(docs_dir(spec), spec, types, design):
            print(f"wrote {path.relative_to(ROOT)}")
        return 0

    url, token = os.environ.get("NETBOX_URL"), os.environ.get("NETBOX_TOKEN")
    if not url or not token:
        print("NETBOX_URL / NETBOX_TOKEN not set — "
              "export both variables first", file=sys.stderr)
        return 2
    if args.mode == "elevations":
        return elevations(url, token, spec, design)
    from .reconcile import Reconciler  # import late: offline modes need no pynetbox
    rec = Reconciler(url, token, design, spec["tag"])
    if args.mode == "destroy":
        rec.destroy(execute=args.yes)
        if not args.yes:
            print("(dry run — re-run with --yes to delete)")
        return 0
    summary = rec.run(args.mode)
    pending = sum(n for ops in summary.values() for op, n in ops.items() if op != "conflict")
    conflicts = sum(ops.get("conflict", 0) for ops in summary.values())
    print(f"\n{args.mode}: {pending} change(s), {conflicts} conflict(s)")
    return 1 if conflicts else 0


if __name__ == "__main__":
    sys.exit(main())
