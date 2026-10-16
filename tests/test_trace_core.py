"""Pure tests of the DGX Trace add-on rules (blender/addon/dgx_trace/trace_core.py, no bpy):
a synthetic hall with two racks, a leaf, a node, a door, a header, a CDU and the plant."""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "blender", "addon", "dgx_trace"))
sys.path.insert(0, os.path.join(REPO, "blender"))

import trace_core as T  # noqa: E402

LINKS_COLS = ["a", "a_port", "b", "b_port", "fabric", "cable", "rail", "label"]


@pytest.fixture
def world():
    data = {
        "links_cols": LINKS_COLS,
        "links": [
            ["dgx-1", "OSFP4P2", "leaf-1", "P0.0", "compute", "mmf-om4", 1, "C-dgx-1-R1"],
            ["dgx-1", "OSFP3P2", "leaf-2", "P0.0", "compute", "mmf-om4", 2, "C-dgx-1-R2"],
            ["dgx-1", "Slot1P1", "sleaf-1", "P0.0", "storage", "mmf-om4", 0, "S-dgx-1-A"],
            ["dgx-1", "BMC", "oob-1", "swp1", "oob", "cat5e", 0, "O-dgx-1-BMC"],
            ["leaf-1", "P16.0", "spine-1", "P0.0", "compute", "mmf-om4", 1, "C-leaf-1-spine-1"],
            ["dgx-1", "PSU1", "r1-pdu-a", "C19-1", "power", "power", 0, "P-dgx-1-PSU1"],
            ["r1-rdhx", "FAN", "r1-pdu-a", "C13-1", "power", "power", 0, "P-r1-rdhx-FAN"],
        ],
        "rack_of": {"dgx-1": "r1", "leaf-1": "r2", "leaf-2": "r2", "sleaf-1": "r2", "oob-1": "r2",
                    "spine-1": "r2", "r1-pdu-a": "r1", "r1-rdhx": "r1"},
        "racks": {"r1": {"row": "A", "cooling": {"loop": "rdhx", "unit": "r1-rdhx"}, "devices": []},
                  "r2": {"row": "A", "cooling": {"loop": "rdhx", "unit": "r2-rdhx"}, "devices": []}},
        "cooling": {"pipes": [], "loops": {"rdhx": {"cdus": ["cdu-rdhx-01", "cdu-rdhx-02"], "headers": ["hdr-rdhx-a"]}},
                    "cdus": ["cdu-rdhx-01", "cdu-rdhx-02"],
                    "plant": {"header": "hdr-fws", "units": [{"name": "plant-01"}]}},
    }
    props = {
        "r1": {"dgx_kind": "rack"}, "r2": {"dgx_kind": "rack"},
        "dgx-1": {"dgx_kind": "device", "dgx_rack": "r1"}, "leaf-1": {"dgx_kind": "device", "dgx_rack": "r2"},
        "leaf-2": {"dgx_kind": "device", "dgx_rack": "r2"}, "sleaf-1": {"dgx_kind": "device", "dgx_rack": "r2"},
        "oob-1": {"dgx_kind": "device", "dgx_rack": "r2"}, "spine-1": {"dgx_kind": "device", "dgx_rack": "r2"},
        "r1-pdu-a": {"dgx_kind": "device", "dgx_rack": "r1"},
        "r1-rdhx": {"dgx_kind": "unit", "dgx_rack": "r1", "dgx_loop": "rdhx"},
        "r2-rdhx": {"dgx_kind": "unit", "dgx_rack": "r2", "dgx_loop": "rdhx"},
        "bundle_r1_r2_compute": {"dgx_kind": "bundle", "dgx_a": "r1", "dgx_b": "r2", "dgx_fabric": "compute"},
        "bundle_r1_r2_storage": {"dgx_kind": "bundle", "dgx_a": "r1", "dgx_b": "r2", "dgx_fabric": "storage"},
        "bundle_r1_r2_oob": {"dgx_kind": "bundle", "dgx_a": "r1", "dgx_b": "r2", "dgx_fabric": "oob"},
        "cord_dgx-1_0": {"dgx_kind": "power", "dgx_a": "dgx-1", "dgx_b": "r1-pdu-a", "dgx_fabric": "power"},
        "cord_r1-rdhx_0": {"dgx_kind": "power", "dgx_a": "r1-rdhx", "dgx_b": "r1-pdu-a", "dgx_fabric": "power"},
        "hose_1": {"dgx_kind": "hose", "dgx_a": "hdr-rdhx-a", "dgx_b": "r1-rdhx", "dgx_fabric": "coolant-supply", "dgx_loop": "rdhx"},
        "hose_2": {"dgx_kind": "hose", "dgx_a": "hdr-rdhx-a", "dgx_b": "r1-rdhx", "dgx_fabric": "coolant-return", "dgx_loop": "rdhx"},
        "hose_3": {"dgx_kind": "hose", "dgx_a": "hdr-rdhx-a", "dgx_b": "r2-rdhx", "dgx_fabric": "coolant-supply", "dgx_loop": "rdhx"},
        "drop_1": {"dgx_kind": "pipe", "dgx_pipe_kind": "drop", "dgx_a": "hdr-rdhx-a", "dgx_b": "r1-rdhx", "dgx_fabric": "coolant-supply", "dgx_loop": "rdhx"},
        "header_a": {"dgx_kind": "pipe", "dgx_pipe_kind": "header", "dgx_a": "hdr-rdhx-a", "dgx_b": "", "dgx_fabric": "coolant-supply", "dgx_loop": "rdhx"},
        "drop_cdu": {"dgx_kind": "pipe", "dgx_pipe_kind": "drop", "dgx_a": "hdr-rdhx-a", "dgx_b": "cdu-rdhx-01", "dgx_fabric": "coolant-supply", "dgx_loop": "rdhx"},
        "drop_pri": {"dgx_kind": "pipe", "dgx_pipe_kind": "drop", "dgx_a": "hdr-fws", "dgx_b": "cdu-rdhx-01", "dgx_fabric": "coolant-supply", "dgx_loop": "fws"},
        "main_s": {"dgx_kind": "pipe", "dgx_pipe_kind": "main", "dgx_a": "hdr-fws", "dgx_b": "", "dgx_fabric": "coolant-supply", "dgx_loop": "fws"},
        "drop_crah": {"dgx_kind": "pipe", "dgx_pipe_kind": "drop", "dgx_a": "hdr-fws", "dgx_b": "crah-01", "dgx_fabric": "coolant-supply", "dgx_loop": "fws"},
        "cdu-rdhx-01": {"dgx_kind": "cdu", "dgx_loop": "rdhx"}, "cdu-rdhx-02": {"dgx_kind": "cdu", "dgx_loop": "rdhx"},
        "crah-01": {"dgx_kind": "crah"}, "plant-01": {"dgx_kind": "plant"},
        "tie_bands": {"dgx_kind": "decor"},
    }
    return T.Index(data), props


ALL = {"compute", "storage", "inband", "oob", "nvlink", "power", "coolant-supply", "coolant-return", "storage-eth", "mgmt"}


def test_node_follow_everything(world):
    idx, props = world
    got = T.trace(idx, "dgx-1", props["dgx-1"], props, ALL, follow=True)
    assert {"leaf-1", "leaf-2", "sleaf-1", "oob-1"} <= got                 # far ends
    assert {"bundle_r1_r2_compute", "bundle_r1_r2_storage", "bundle_r1_r2_oob"} <= got
    assert "cord_dgx-1_0" in got and "cord_r1-rdhx_0" not in got           # its own cords only
    assert {"r1-rdhx", "hose_1", "hose_2", "drop_1", "header_a", "drop_cdu", "drop_pri", "main_s",
            "cdu-rdhx-01", "cdu-rdhx-02", "plant-01"} <= got                 # coolant chain to the plant
    assert "hose_3" not in got and "drop_crah" not in got and "spine-1" not in got
    assert "tie_bands" not in got and "r2" in got


def test_node_direct_only_and_filters(world):
    idx, props = world
    got = T.trace(idx, "dgx-1", props["dgx-1"], props, ALL, follow=False)
    assert {"leaf-1", "sleaf-1", "oob-1", "cord_dgx-1_0", "r1-rdhx", "hose_1", "hose_2"} <= got
    assert not {"header_a", "cdu-rdhx-01", "plant-01", "bundle_r1_r2_compute"} & got
    only_compute = T.trace(idx, "dgx-1", props["dgx-1"], props, {"compute"}, follow=True)
    assert {"leaf-1", "leaf-2", "bundle_r1_r2_compute"} <= only_compute
    assert not {"sleaf-1", "oob-1", "cord_dgx-1_0", "hose_1", "r1-rdhx"} & only_compute


def test_leaf_gives_down_and_up_links(world):
    idx, props = world
    got = T.trace(idx, "leaf-1", props["leaf-1"], props, {"compute"}, follow=True)
    assert {"dgx-1", "spine-1", "bundle_r1_r2_compute"} <= got and "r1" in got


def test_cdu_traces_its_loop(world):
    idx, props = world
    got = T.trace(idx, "cdu-rdhx-01", props["cdu-rdhx-01"], props, ALL, follow=True)
    assert {"drop_cdu", "drop_pri", "header_a", "main_s", "plant-01", "cdu-rdhx-02",
            "r1-rdhx", "r2-rdhx", "r1", "r2", "hose_1", "hose_3"} <= got
    assert "drop_crah" not in got and "dgx-1" not in got


def test_bundle_and_pipe_show_their_ends(world):
    idx, props = world
    assert T.trace(idx, "bundle_r1_r2_compute", props["bundle_r1_r2_compute"], props, ALL) == {"bundle_r1_r2_compute", "r1", "r2"}
    assert T.trace(idx, "drop_cdu", props["drop_cdu"], props, ALL) == {"drop_cdu", "cdu-rdhx-01"}


def test_index_on_the_real_scene():
    """The real mixed scene builds an index: every rack has a unit, loops and CDUs resolve."""
    import json
    s = json.load(open(os.path.join(REPO, "docs", "dgx-superpod-mixed", "scene.json")))
    data = {"links_cols": s["links_cols"], "links": s["links"],
            "rack_of": {d["name"]: r["name"] for r in s["racks"] for d in r["devices"]},
            "racks": s["racks"], "cooling": {"pipes": s["cooling"]["pipes"], "loops": s["cooling"]["loops"],
                                              "cdus": [c["name"] for c in s["cooling"]["cdus"]], "plant": s["cooling"]["plant"]}}
    idx = T.Index(data)
    assert len(idx.rack_unit) == len(s["racks"]) and set(idx.cdu_loop.values()) == {"rdhx", "dlc"}
    assert len([r for r in idx.links_of("ibc-su1-leaf-r1") if r["fabric"] == "compute"]) == 64   # 32 down + 32 up
    assert len(idx.links_of("dgx-su1-n01")) == 8 + 2 + 2 + 1 + 6
    assert len([r for r in idx.links_of("gb-su1-r01-t01") if r["fabric"] == "compute"]) == 4
