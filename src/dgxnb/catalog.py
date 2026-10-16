"""Device-type catalog: vendored library files + local patches + custom types.

Layout (see catalog/*/README|SOURCE.md):
  catalog/library/*.y[a]ml   verbatim devicetype-library files (never edited)
  catalog/patches/<slug>.yaml overlays: `add` (append components), `update`
                              (merge fields into components by name)
  catalog/custom/*.yaml       our own definitions; may use `extends: <slug>`

Component names may use `{a..b}` numeric ranges, expanded here.
"""
from __future__ import annotations

import copy
import re
from pathlib import Path

import yaml

from .model import Design, Ref

# devicetype-library component sections -> (reconciler kind, fields copied)
SECTIONS = {
    "interfaces": ("dcim.interface_templates",
                   ("name", "label", "type", "mgmt_only", "description")),
    "power-ports": ("dcim.power_port_templates",
                    ("name", "label", "type", "maximum_draw", "allocated_draw", "description")),
    "power-outlets": ("dcim.power_outlet_templates",
                      ("name", "label", "type", "feed_leg", "description")),
    "console-ports": ("dcim.console_port_templates", ("name", "label", "type", "description")),
    "module-bays": ("dcim.module_bay_templates", ("name", "label", "position", "description")),
}
TOP_FIELDS = ("model", "slug", "part_number", "u_height", "is_full_depth", "airflow",
              "weight", "weight_unit", "comments", "subdevice_role")

_RANGE = re.compile(r"\{(\d+)\.\.(\d+)\}")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _expand(components: list[dict]) -> list[dict]:
    """Expand `{a..b}` in component names into one component per value."""
    out = []
    for comp in components:
        m = _RANGE.search(comp["name"])
        if not m:
            out.append(comp)
            continue
        lo, hi = int(m.group(1)), int(m.group(2))
        for i in range(lo, hi + 1):
            c = dict(comp, name=comp["name"][: m.start()] + str(i) + comp["name"][m.end():])
            out.extend(_expand([c]))
    return out


def _apply_patch(dt: dict, patch: dict) -> dict:
    dt = copy.deepcopy(dt)
    for section, comps in (patch.get("add") or {}).items():
        dt.setdefault(section, []).extend(copy.deepcopy(comps))
    for section, by_name in (patch.get("update") or {}).items():
        index = {c["name"]: c for c in dt.get(section, [])}
        for name, fields in by_name.items():
            if name not in index:
                raise KeyError(f"patch for {dt['slug']}: no {section} named {name!r}")
            index[name].update(fields)
    for k, v in (patch.get("set") or {}).items():
        dt[k] = v
    return dt


def load(root: Path) -> dict[str, dict]:
    """Return {slug: device-type dict} with patches, `extends` and ranges applied.

    Each entry gets `_source` = "library" | "custom" for the BOM/catalog report.
    """
    types: dict[str, dict] = {}
    for f in sorted((root / "library").glob("*.y*ml")):
        dt = yaml.safe_load(f.read_text())
        dt["_source"] = "library"
        types[dt["slug"]] = dt
    for f in sorted((root / "patches").glob("*.yaml")):
        slug = f.stem
        if slug not in types:
            raise KeyError(f"patch {f.name} targets unknown slug {slug}")
        types[slug] = _apply_patch(types[slug], yaml.safe_load(f.read_text()))
        types[slug]["_source"] = "library+patch"
    custom = [yaml.safe_load(f.read_text()) for f in sorted((root / "custom").glob("*.yaml"))]
    # Resolve `extends` after all bases are known (bases first).
    for dt in sorted(custom, key=lambda d: "extends" in d):
        if "extends" in dt:
            base = copy.deepcopy(types[dt.pop("extends")])
            base.update(dt)
            dt = base
        dt["_source"] = "custom"
        types[dt["slug"]] = dt
    for dt in types.values():
        for section in SECTIONS:
            if section in dt:
                dt[section] = _expand(dt[section])
                names = [c["name"] for c in dt[section]]
                dupes = {n for n in names if names.count(n) > 1}
                if dupes:
                    raise ValueError(f"{dt['slug']} {section}: duplicate names {sorted(dupes)}")
    return types


def component_names(dt: dict, section: str = "interfaces") -> list[str]:
    return [c["name"] for c in dt.get(section, [])]


def add_to_design(design: Design, types: dict[str, dict], slugs: list[str], tags: list[Ref]) -> None:
    """Emit manufacturers, device types and their component templates."""
    for slug in slugs:
        dt = types[slug]
        mslug = slugify(dt["manufacturer"])
        if (mslug,) not in design.objs["dcim.manufacturers"]:
            design.add("dcim.manufacturers", mslug, name=dt["manufacturer"], slug=mslug, tags=tags)
        data = {k: dt[k] for k in TOP_FIELDS if k in dt}
        data.update(manufacturer=Ref("dcim.manufacturers", (mslug,)), tags=tags)
        dtref = design.add("dcim.device_types", slug, **data)
        for section, (kind, fields) in SECTIONS.items():
            for comp in dt.get(section, []):
                d = {k: comp[k] for k in fields if k in comp}
                d["device_type"] = dtref
                if section == "power-outlets" and "power_port" in comp:
                    d["power_port"] = Ref("dcim.power_port_templates", (slug, comp["power_port"]))
                design.add(kind, (slug, comp["name"]), **d)
