# RA notes — mixed pod (1 SU DGX H200 + 1 SU DGX GB300 NVL72), site dgx-lab-03

Companion to `docs/ra-notes.md` (H200 RA) and `docs/ra-notes-gb300.md` (GB300 RA). **No NVIDIA
reference architecture covers a mixed H200 + GB300 pod**, so this file records (a) what each
SU inherits unchanged from its own RA, (b) the few objects the two share, and (c) the derived
numbers of the composition. Every cooling number cites `reference/cooling-schneider/README.md`
(vendor datasheets) or the Schneider/NVIDIA reference-design notes (not published); the
modelling decisions are CHOICE rows in `docs/design-choices.md` "Mixed pod".

Spec: `spec/superpod-mixed.yaml` (composes `superpod.yaml` and `gb300-su.yaml` through
`src/dgxnb/specload.py`); builder `src/dgxnb/topology_mixed.py` + `cooling.py`.

## M. What each SU inherits (unchanged)

| # | SU | Inherited as-is | Source rows |
|---|---|---|---|
| M.1 | SU 1 — H200 | RA 1-SU row: **31 DGX H200 = 248 GPUs**, 8 rail leaves + 4 spines (QM9700), 252 node/UFM→leaf + 256 leaf→spine compute cables; UFM displaces node 32 | ra-notes 1.3, 1.4, 2.x; `tests/test_topology.py::test_ra_table4_compute_fabric[1-…]` |
| M.2 | SU 1 — H200 | Storage IB by the 4:3 / 1:1 rule: 2 DGX-facing leaves + 1 device leaf + 1 spine; 4 × DDN AI400X2T (tier 1); 5 mgmt servers; 2 + 2 UFM; in-band 1 MLAG pair + 2 spines; OOB 4 × SN2201 | ra-notes §9, H.1, H.5; design-choices §2 |
| M.3 | SU 1 — H200 | **3 management racks** (DCG: 2 per SU, ra-notes 8.5; +1 because the compute rack alone is 21.4 kW of 21.8): `mgmt-r01` compute IB + ufm-c-01, `mgmt-r02` in-band + BCM/Slurm + ufm-c-02, `mgmt-r03` storage IB + OOB + UFM-s | ra-notes 8.3, D4; `test_one_su_is_the_ra_1su_row_within_budget` |
| M.4 | SU 2 — GB300 | RA-GB300 1 SU: **8 × NVL72, 144 trays, 576 GPUs**; 8 Q3400-RD rail leaves (4 rails × 2) + 4 spines; 4 SN5600 compute leaves, 2 mgmt leaves, 2 spines, 2 OOB spines; 2 UFM; 5 mgmt servers; NVLink 1,296 in-rack links | ra-notes-gb300 G.1–G.16, D.1–D.3 |
| M.5 | SU 2 — GB300 | Elevation, power shelves (8 × 33 kW), tray/switch-tray power CHOICEs, 4 mgmt racks | ra-notes-gb300 C.1–C.8 |

## S. Shared between the SUs (and nothing else) — all CHOICE

| # | Shared object | How | Why |
|---|---|---|---|
| S.1 | Site, hall, tenant, tag | one site `dgx-lab-03`, tag `dgx-superpod-mixed`; SU numbers renumbered 1 (H200) / 2 (GB300) | one design, one tag-scoped reconciler run |
| S.2 | DC-core demarc | one `dc-core-demarc` (custom type widened to 16 ports): H200 in-band spines on core1–12 (RA H200 Table 8: 4 CWDM4 + 8 core), GB300 Ethernet spines on core13–14 (RA-GB300 "Customer Edge" ≥ 2 × 100GbE) | both pods exit through the customer core |
| S.3 | VAST tier 2 | stays in `stor-r02` on the H200 in-band spines (design-choices §2); the GB300 pod reaches it **through the DC core** — no new cables. The GB300 spec's 4 generic HPS appliances and its 2 storage leaves are dropped (`ethernet.hps_appliances: 0`, `storage_leaves: 0`) | RA-GB300: storage is vendor-specific; one NFS/S3 system for both pods |
| S.4 | Power distribution | panels PP-A/B/C shared by name (first pod's description); + `PP-M` (mechanical) for CDUs and the plant | one hall, one upstream |
| S.5 | Cooling plant | one Uniflair block outside the hall wall serves both technology loops via their own CDU sets | decision 2 of the brief |

Not shared: compute IB, storage IB / Ethernet, in-band, OOB, UFMs, BCM — each pod keeps its RA fabrics.

## D. Derived numbers of the composition

| # | Value | Rule |
|---|---|---|
| D.1 | **824 GPUs** = 248 + 576; 175 compute nodes (31 DGX + 144 trays) | M.1 + M.4 |
| D.2 | **33 racks** = 16 DGX + 3 mgmt + 2 storage (row A) + 8 NVL72 + 4 mgmt (row B) | M.3 + M.5; hall rows in the spec |
| D.3 | IT peak **1,530 kW**: row A 395 kW (16 × 20.4 + 68.7 mgmt/storage), row B 1,145 kW (8 × 135.3 + 62.9 mgmt) | `export.rack_power` on allocated draws (ra-notes 7.5, 8.10; ra-notes-gb300 C.4) |
| D.4 | Cables (IT): see `docs/dgx-superpod-mixed/bom-generated.md` (generated) | — |
| D.5 | Two IP containers, disjoint and **distinct from dgx-lab-01/02**: 10.220.0.0/14 (VRFs `mx-*`) and 10.224.0.0/15 (VRFs `mxgb-*`); VLAN IDs repeat per site (own VLAN group) | the pods' plans already exist in the shared NetBox under `enforce_unique` VRFs, so the mixed spec overrides `ipam` |

## C. Cooling — sizing inputs and citations

Filled from `reference/cooling-schneider/` (see that README's row numbers, cited as *cs:§n*).
Every value below is either a vendor figure with its row, DERIVED with the rule shown, or a
CHOICE recorded in `docs/design-choices.md` "Mixed pod".

| # | Item | Value | Source |
|---|---|---|---|
| C.1 | RDHx loop load (row A: 21 racks incl. door fans) | DERIVED = Σ rack peak (D.3) + fans | `cooling.model` |
| C.2 | DLC loop load (8 × NVL72 × liquid fraction) | DERIVED | liquid fraction: *cs* / ra-notes-gb300 |
| C.3 | Residual air of the NVL72 row | DERIVED = (1 − fraction) × 8 × 135.3 kW + gb-mgmt racks | — |
| C.4 | Door capacity at the RDHx supply temperature | see spec `cooling.loops.rdhx.unit.kw` | *cs* ChilledDoor row |
| C.5 | CDU capacity at the stated approach | see spec `cooling.loops.*.cdu.kw` | *cs* CDU row |
| C.6 | N+1 CDUs per loop | DERIVED = ceil(load / CDU kW) + 1 | `cooling.model`; `tests/test_cooling.py` |
| C.7 | Plant capacity | see spec `cooling.plant.kw` | *cs* Uniflair row |
| C.8 | Loop temperatures (FWS 10/15, TCS rdhx 18/28, TCS dlc 35/50 °C) | see spec | the reference-design notes §2–§3 and "Guidance summary"; NVIDIA / Schneider RD figures NOT FOUND |
| C.9 | Header flow = Σ kW × 60 / (4.18 × ΔT) l/min (water) | DERIVED; PG25 ≈ +5 % (noted) | — |

The table's "see spec" cells are deliberate: the spec is the single place the numbers live,
and each spec line carries its citation as a comment.
