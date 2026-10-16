"""Offline tests of the draw.io export: page set, one line per cable, valid references,
rack geometry, determinism, and that the GB300 design renders too."""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
import yaml

from dgxnb import catalog, drawio, topology, topology_gb300

ROOT = Path(__file__).resolve().parents[1]
TYPES = catalog.load(ROOT / "catalog")


def load(name, builder):
    spec = yaml.safe_load((ROOT / "spec" / name).read_text())
    return spec, builder(spec, TYPES)


@pytest.fixture(scope="module")
def h200():
    spec, design = load("superpod.yaml", topology.build)
    return spec, design, ET.fromstring(drawio.drawio_xml(spec, TYPES, design))


def cells(page):
    """(id, mxCell) for every cell on a page, unwrapping tooltip <object>s."""
    for el in page.iter():
        if el.tag == "object":
            yield el.get("id"), el.find("mxCell")
        elif el.tag == "mxCell" and el.get("id") not in (None, "0", "1"):   # skip root/layer
            yield el.get("id"), el


def page(mx, name):
    return next(d for d in mx.findall("diagram") if d.get("name") == name)


def test_pages(h200):
    _, _, mx = h200
    assert [d.get("name") for d in mx.findall("diagram")] == [
        "Compute fabric — SU 1", "Compute fabric — SU 2", "Storage fabric (InfiniBand)",
        "Storage fabric (Ethernet)", "In-band management network", "Out-of-band management network",
        "Rack elevations — SU 1", "Rack elevations — SU 2",
        "Rack elevations — management & storage", "Data hall floor plan"]


@pytest.mark.parametrize("name,fabric", [("Storage fabric (InfiniBand)", "storage"),
                                         ("In-band management network", "inband"),
                                         ("Out-of-band management network", "oob")])
def test_fabric_pages_cover_every_cable(h200, name, fabric):
    _, design, mx = h200
    pg = page(mx, name)
    ids = {i for i, _ in cells(pg)}
    edges = [(i, c) for i, c in cells(pg) if c.get("edge") == "1"]
    assert edges and all(c.get("source") in ids and c.get("target") in ids for _, c in edges)
    import re
    total = sum(int(re.search(r": (\d+) cable", el.get("tooltip")).group(1))
                for el in pg.iter("object") if el.find("mxCell").get("edge") == "1")
    assert total == sum(1 for o in design.all("dcim.cables")
                        if o.data["custom_fields"]["dgx_fabric"] == fabric)


def test_hall_places_every_rack_once(h200):
    spec, design, _ = h200
    placed = [r for row in spec["hall"]["rows"] for r in row["racks"]]
    assert sorted(placed) == sorted(o.key[0] for o in design.all("dcim.racks"))


@pytest.mark.parametrize("idx,nodes", [(0, 32), (1, 31)])   # SU2 slot 32 is UFM (ra-notes 1.4)
def test_compute_page_lines(h200, idx, nodes):
    _, _, mx = h200
    page = mx.findall("diagram")[idx]
    ids = {i for i, _ in cells(page)}
    edges = [(i, c) for i, c in cells(page) if c.get("edge") == "1"]
    assert all(c.get("source") in ids and c.get("target") in ids for _, c in edges)
    node_leaf = [i for i, _ in edges if i.split("-", 1)[1].startswith("d")]
    leaf_spine = [i for i, _ in edges if i.split("-", 1)[1].startswith("s")]
    assert len(node_leaf) == nodes * 8          # 8 rails per DGX (ra-notes 2.1)
    assert len(leaf_spine) == 8 * 8             # every leaf to every spine, 4 cables each


def test_rack_page_geometry(h200):
    spec, design, mx = h200
    pages = [d for d in mx.findall("diagram") if d.get("name").startswith("Rack elevations")]
    page = pages[0]
    placed = {o.data["name"] for o in design.all("dcim.devices")
              if o.data.get("rack") and o.data["rack"].key[0].startswith("dgx-su1-")}
    prefix = page.get("id") + "-"
    ids = {i[len(prefix):] for i, _ in cells(page)}
    assert placed <= ids
    frames = {i: c.find("mxGeometry") for i, c in cells(page) if i.endswith("-frame")}
    assert len(frames) == 16
    n_frames = sum(1 for d in pages for i, _ in cells(d) if i.endswith("-frame"))
    assert n_frames == design.count("dcim.racks")
    for fid, fg in frames.items():
        rack = fid[len(prefix):-len("-frame")]
        fy, fh = float(fg.get("y")), float(fg.get("height"))
        for o in design.all("dcim.devices"):
            if o.data.get("rack") and o.data["rack"].key[0] == rack and o.data.get("position"):
                g = dict(cells(page))[f"{prefix}{o.data['name']}"].find("mxGeometry")
                y, h = float(g.get("y")), float(g.get("height"))
                assert fy < y and y + h < fy + fh


def test_deterministic():
    spec, design = load("superpod.yaml", topology.build)
    again = topology.build(spec, TYPES)
    assert drawio.drawio_xml(spec, TYPES, design) == drawio.drawio_xml(spec, TYPES, again)


def test_mixed_renders_with_cooling_pages():
    from dgxnb import specload, topology_mixed
    spec = specload.load(ROOT / "spec" / "superpod-mixed.yaml")
    design = topology_mixed.build(spec, TYPES)
    mx = ET.fromstring(drawio.drawio_xml(spec, TYPES, design))
    names = [d.get("name") for d in mx.findall("diagram")]
    assert names[:2] == ["Compute fabric — SU 1", "Compute fabric — SU 2"]
    assert names[-2:] == ["Cooling — floor plan", "Cooling — hydraulic one-line"]
    hyd = page(mx, "Cooling — hydraulic one-line")
    ids = {i for i, _ in cells(hyd)}
    edges = [c for _, c in cells(hyd) if c.get("edge") == "1"]
    assert all(c.get("source") in ids and c.get("target") in ids for c in edges)
    n_pipes = sum(1 for o in design.all("dcim.cables")
                  if o.data["custom_fields"]["dgx_fabric"].startswith("coolant-"))
    assert len(edges) == n_pipes
    fl = page(mx, "Cooling — floor plan")
    boxes = {i for i, c in cells(fl) if c.get("vertex") == "1"}
    assert sum(1 for i in boxes if "-cdu-" in i) == 4 and sum(1 for i in boxes if "-plant-" in i) == 3


def test_gb300_renders():
    spec, design = load("gb300-su.yaml", topology_gb300.build)
    mx = ET.fromstring(drawio.drawio_xml(spec, TYPES, design))
    names = [d.get("name") for d in mx.findall("diagram")]
    assert names[0] == "Compute fabric"          # 144 trays: folded per rack
    assert "Storage fabric (Ethernet)" in names and "Rack elevations — SU 1" in names
