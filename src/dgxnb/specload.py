"""Spec loader: a spec file plus the pod specs it composes.

  load(path) -> dict     the spec with every `pods.<name>.from` resolved

A `kind: mixed` spec does not restate a pod's design; it points at the pod's own spec file
and overrides a few keys (RA row, rack count, what is shared):

    pods:
      h200:
        from: superpod.yaml          # relative to this spec's directory
        override: {compute: {sus: 1}, racks: {mgmt_racks: 3}}

`override` is deep-merged onto the referenced spec (dict into dict; any other value replaces;
`null` deletes the key). The resolved pod spec is stored as `pods.<name>.spec`, so builders
and tests see plain dicts and never touch the filesystem. `superpod.yaml` and `gb300-su.yaml`
therefore stay the single source of truth for what an H200 SU and a GB300 SU are.
"""
from __future__ import annotations

import copy
from pathlib import Path

import yaml


def deep_merge(base: dict, override: dict) -> dict:
    """Return a copy of `base` with `override` merged in (recursive on dicts; None deletes)."""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if v is None:
            out.pop(k, None)
        elif isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load(path: Path) -> dict:
    path = Path(path)
    spec = yaml.safe_load(path.read_text())
    for name, pod in (spec.get("pods") or {}).items():
        if "spec" in pod:                       # already resolved (tests may inline it)
            continue
        base = yaml.safe_load((path.parent / pod["from"]).read_text())
        pod["spec"] = deep_merge(base, pod.get("override") or {})
    return spec
