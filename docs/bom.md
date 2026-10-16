# BOM — DGX SuperPOD H200, 2 SU (as built)

Basis: RA-11336-001 V2 (DGX H200) + DCG DG-11301-001 v4. Refs are rows in `ra-notes.md`.
The machine-generated counterpart is `bom-generated.md` (`bin/dgxnb export`); `bin/validate`
asserts both against live NetBox. Decisions D1–D7 are resolved (see `ra-notes.md`).

## Nodes and servers

| Item | Model | Qty | Ref |
|---|---|---|---|
| Compute nodes | NVIDIA DGX H200 (8 × H200 141 GB) | **63** (64 slots; SU2 node 32 displaced by UFM) | 1.3, 1.4, D1 |
| GPUs | H200 | **504** | 1.3 |
| UFM appliances | NVIDIA UFM Appliance 3.1 | 4 (2 compute, 2 storage) | 6.1, 6.2 |
| Mgmt servers | Dell PowerEdge R750 | 5 (2 BCM head, Slurm ctl, 2 login) | H.1 |
| HPS storage | Generic HPS appliance, 2U, 16 × NDR200 | 3 | 3.8, 3.9, D5 |

## Switches by role (41)

| Fabric | Role | Model | Qty | Ref |
|---|---|---|---|---|
| Compute IB | leaf (8 rails × 2 SU) | QM9700 | 16 | 2.5 |
| Compute IB | spine | QM9700 | 8 | 2.5 |
| Storage IB | leaf (4 DGX-facing A/B + 1 device leaf) | QM9700 | 5 | §9 |
| Storage IB | spine | QM9700 | 2 | §9 |
| In-band Eth | leaf (MLAG pair per SU) / spine | SN4600C | 4 / 2 | 4.5, H.3 |
| OOB Eth | access (219 ports / 48) | SN2201 | 5 | §9 |

## Cables (2,295) and transceivers

| Fabric | Link | Type | Qty |
|---|---|---|---|
| Compute | DGX → rail leaf | NDR400 MMF | 504 |
| Compute | UFM → leaf (displaced slot, rails 1–4) | NDR200 MMF | 4 |
| Compute | leaf → spine (4 per pair) | NDR400 MMF | 512 |
| Storage | DGX → leaf (A/B) | NDR400 MMF | 126 |
| Storage | leaf → spine | NDR400 MMF | 120 |
| Storage | HPS → leaf (400G → 2 × 200G splitter) | MMF | 24 |
| Storage | UFM-s + mgmt servers → leaf | NDR200 MMF | 4 + 10 |
| In-band | DGX bond (A+B) + mgmt servers | 100G AOC | 126 + 10 |
| In-band | leaf → spine, MLAG ISL, DC uplinks (4 CWDM4 + 8 AOC) | AOC / DAC / SMF | 16 + 6 + 12 |
| OOB | device mgmt → SN2201 · SN2201 → in-band spine | Cat5e · 100G AOC | 219 · 10 |
| HA | UFM back-to-back | Cat5e | 2 |
| Power | PDU inlet → feed · DGX PSU → C19 · other PSU → C13 | power | 104 · 378 · 108 |

Transceivers: 252 DGX twin-port OSFP, 768 switch twin-port OSFP (every compute cage),
126 DGX QSFP112 (storage), 8 UFM.

## Racks and power

| Item | Qty | Detail |
|---|---|---|
| DGX racks | 32 | 2 DGX each (su2-r16 holds 1); 20.4 kW peak ≤ 25 kW budget (H.2) |
| Mgmt racks | 4 | 21.39 / 21.39 / 20.12 / 14.22 kW ≤ 21.8 kW 2N (D4) |
| rPDUs | 104 | Raritan PX3-5730-V2 (stand-in for RA models, D6): 3 per DGX rack, 2 per mgmt rack |
| Power feeds / panels | 104 / 3 | 415 V 32 A 3φ from panels A/B/C (8.3, 8.4) |
| Peak IT load | **719.7 kW** | 63 × 10.2 + 77.1 mgmt (matches bom-generated.md) |

## IPAM

`10.200.0.0/14` (global container) → VRFs `dgx-inband` 10.200.0.0/22 (VLAN 100),
`dgx-oob` 10.201.0.0/22 (VLAN 200; BMC / netdev / PDU /24s), `dgx-ib-compute` 10.202.0.0/22
(one /25 per rail), `dgx-ib-storage` 10.203.0.0/23. 1,003 addresses (generator count, see `bom-generated.md`) — see `ip-plan.md`.

## Device-type sources

| Type | Source |
|---|---|
| QM9700, SN4600C, SN2201, Dell R750, Raritan PX3-5730-V2 | devicetype-library @ `0451a7c` (CC0), vendored in `catalog/library/`, fixed via `catalog/patches/` |
| DGX H200 (+ H100 via `extends`), UFM 3.1, HPS appliance, DC core demarc | custom, `catalog/custom/` |

---

# BOM — mixed pod (site dgx-lab-03), 1 SU H200 + 1 SU GB300, liquid-cooled

Basis: `spec/superpod-mixed.yaml` (composes the two RA designs) + `docs/ra-notes-mixed.md` +
`docs/design-choices.md` §7. Generated counterpart: `docs/dgx-superpod-mixed/bom-generated.md`.

| Item | Model | Qty | Ref |
|---|---|---|---|
| Compute nodes | DGX H200 · DGX GB300 compute trays | **31 · 144** (824 GPUs) | ra-notes-mixed M.1, M.4 |
| NVL72 racks | 8 × (18 trays, 9 NVLink switch trays, 8 power shelves, 2 in-rack SN2201) | 8 | M.4 |
| IB switches | QM9700 (H200: 8 leaf + 4 spine + 3 storage leaf + 1 spine) · Q3400-RD (GB300: 8 leaf + 4 spine) | 16 · 12 | M.1, M.2, M.4 |
| Ethernet | SN4600C (H200 in-band 2 leaf + 2 spine, VAST backend 2; GB300 OOB spines 2) · SN5600 (GB300 4 compute leaf + 2 mgmt leaf + 2 spine) · SN2201 (4 + 16 in-rack + 1) | 8 · 8 · 21 | — |
| UFM · mgmt servers | UFM 3.1 (2 + 2 + 2) · Dell R750 (5 + 5) | 6 · 10 | — |
| Storage | DDN AI400X2T (tier 1, H200 storage IB) · VAST 5 CBox + 4 DBox (tier 2, shared) | 4 · 9 | S.3 |
| DC-core demarc | 16-port stand-in, shared | 1 | S.2 |
| Racks | 21 (row A) + 12 (row B) = **33**, 600 × 1200 × 48U | 33 | D.2 |
| rPDUs · power feeds | 70 rPDUs · 143 feeds (PP-A/B/C + PP-M) | — | S.4 |
| **Cooling** | Motivair ChilledDoor M8 · NVL72 manifolds · Motivair MCDU-40 · MCDU-45 · Uniflair HDCV 4600A HT · Uniflair BCEF 0903A · coolant headers (stand-in) | **25 · 8 · 2 · 2 · 2 · 3 · 4** | design-choices §7.2, §7.4 |
| Coolant runs | supply · return (hoses, header runs, primaries; NetBox untyped cables) | 47 · 47 | §7.2 |
| Cables (IT) | see bom-generated.md | 5,216 + 94 coolant = 5,310 | — |
| Peak IT load · plant load | **1,530 kW** · **1,600 kW** (incl. door fans and CDU parasitics) | — | D.3, §7.4 |
