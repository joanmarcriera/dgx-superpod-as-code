# RA notes — DGX SuperPOD H100, sizing extraction

Every number used by `spec/` is traced here. Tags: **RA** = stated verbatim in a source;
**DERIVED** = computed from RA values by the rule shown; **CHOICE** = a modelling decision the RA
leaves open (each one is listed under "Decisions" at the end).

> **Build basis (2026-09-30): DGX H200, RA-11336-001 V2** —
> https://docs.nvidia.com/dgx-superpod/reference-architecture/scalable-infrastructure-h200/latest/
> (dated 2025-04-14, pages last updated 2026-09-02). I chose 63 nodes (D1) and H200.
> The H200 RA repeats every H100 table used below (Table 4 identical: 2 SU = 63 nodes / 504
> GPUs, 16 leaf, 8 spine, 508 + 512 cables) except where the addendum says otherwise.

### H200 RA addendum (supersedes the H100 rows it names)

| # | Change vs H100 RA | H200 source | Effect on the build |
|---|---|---|---|
| H.1 | **5** management servers (was 4) | Table 7 "5 Management servers" | settles D2 → 5 × R750 |
| H.2 | "Rack design can support **two** DGX H200 systems per rack"; Fig. 2 = 16 racks per SU, 2 DGX + 3 PDUs each, "power consumption per rack exceeds 25 kW" | Components › System Design; Architecture Fig. 2 | 2 DGX/rack → 32 DGX racks. Budget stated: **25 kW** per DGX rack; 2 × 10.2 = 20.4 ✓, 3 × 10.2 = 30.6 ✗ |
| H.3 | Fig. 3 mgmt racks (4 SU): per compute rack 8 leaf + 8 spine + 1 UFM; 6 in-band leaves + 2 spines; 4 BCM nodes; 8 storage leaves + 4 storage spines; 8 SN2201 | Architecture Fig. 3 | confirms in-band = leaves + 2 spines (4.5) and OOB in a mgmt rack |
| H.4 | In-band: no "NFS storage" line; 8 × 100G "Core DC" + 4 CWDM4; ISL = passive DAC | Table 8 | no NFS appliance; 12 DC uplinks to a demarc device; ISL `dac-passive` |
| H.5 | Storage: 502 NDR400 (DGX→leaf + leaf→spine), no "Slurm management" splitter line | Table 8 | mgmt servers get 2 × NDR200 point-to-point to the storage leaf |
| H.6 | **Inconsistencies inside the H200 RA** (flagged, not resolved by NVIDIA): Table 7 still says 38 racks / 96+12 PDUs (a 4-per-rack count) while Fig. 2 shows 2 per rack; Fig. 3 shows 4 BCM nodes vs Table 7's 5; Fig. 3 shows 12 storage switches vs Table 7's 16; Fig. 2 ">25 kW" vs 2 × 10.2 = 20.4 kW | — | we follow text + figures for density (2/rack), Table 7 for server count (5), and the §9 rule for storage (7) |
| H.7 | DGX H200 node: same chassis/ports/power as H100 — 8U, 130.45 kg, 6 × 3.3 kW PSU (4+2), 10.2 kW max, C19/C20 cords | UG Tables 3, 5, 6 | custom type `nvidia-dgx-h200`; H100 `extends` it |

## Sources (retrieved 2026-09-30)

| Key | Document | URL |
|---|---|---|
| RA | *NVIDIA DGX SuperPOD: Next Generation Scalable Infrastructure for AI Leadership — Reference Architecture Featuring NVIDIA DGX H100 Systems*, RA-11333-001 **V11**, 2023-09-22 | https://docs.nvidia.com/dgx-superpod-reference-architecture-dgx-h100.pdf (web: https://docs.nvidia.com/dgx-superpod/reference-architecture-scalable-infrastructure-h100/latest/) |
| DCG | *NVIDIA DGX SuperPOD Data Center Design (DGX H100)*, DG-11301-001 **v4**, May 2023 | https://docs.nvidia.com/nvidia-dgx-superpod-data-center-design-dgx-h100.pdf |
| UG | *NVIDIA DGX H100/H200 User Guide* — hardware overview | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html |
| DTL | netbox-community/devicetype-library @ `0451a7c` (2026-09-29) | https://github.com/netbox-community/devicetype-library |

Page numbers are the PDF footer numbers. The `/latest/` web pages match RA V11; no newer revision
was found.

## 1. Scalable unit and node count

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 1.1 | SU size | 32 DGX H100 | RA Abstract; DCG §1.4 p.4 | "scalable units (SU), each containing 32 DGX H100 systems" |
| 1.2 | GPUs per node | 8 | RA p.1 | "eight GPU configuration" |
| 1.3 | **2-SU row** | **63 nodes / 504 GPUs**, 16 leaf, 8 spine, 508 compute+UFM cables, 512 spine-leaf cables | RA Table 4 "Compute fabric component count", p.11 | row `2 · 63 · 504 · 16 · 8 · 508 · 512` |
| 1.4 | Why 63, not 64 | UFM displaces one DGX per **pod** (31/63/95/127 = 32n−1) | RA Table 4 footnote 1; DCG §1.4 p.4 | "a DGX system must be removed to accommodate for UFM connectivity"; "A pair of NVIDIA Unified Fabric Manager (UFM) appliances displaces one DGX H100 system" |
| 1.5 | Build the full SU fabric even when nodes are missing | leaves + leaf-spine cables for all 32 slots | RA "Network Fabrics" p.9 | "the fabric should be designed to support the full SU, including leaf switches and leaf-spine cables, and leave the portion of the fabric unused" |
| 1.6 | Text/table inconsistency | p.9 prose says 4 SU = 128 nodes; Tables 4/7/8 say 127 | RA p.9 vs Table 4 | "focused on 4 SU units with 128 DGX nodes" |

**Consequence:** a 64-node / 512-GPU pod is **not an RA configuration**. At 2 SU every leaf is
32 down / 32 up and every spine port is used (8 × 64 = 512 = leaf-spine cables), so there is no
free port for UFM unless one DGX slot is given up. → Decision D1.

## 2. Compute fabric (NDR 400G InfiniBand)

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 2.1 | Topology | rail-optimised, full fat tree, 8 × NDR400 per node | RA Table 1 p.3; p.5 | "Rail-optimized, full fat-tree network with eight NDR400 connections per system" |
| 2.2 | Rails / leaves per SU | 8 rails, 8 leaves per SU (one per rail) | RA Table 4; p.11 | "Each group of 32 nodes is rail-aligned" |
| 2.3 | Switch | NVIDIA Quantum QM9700, 920-9B210-00FN-0M0 | RA Table 7 | — |
| 2.4 | QM9700 ports | 64 × 400G in 32 twin-port OSFP cages | DTL `device-types/Nvidia/QM9700.yaml` (not in RA) | — |
| 2.5 | 2-SU switches | 16 leaf + 8 spine = **24** | RA Table 4 | — |
| 2.6 | Node→leaf cables | 63 × 8 = **504** | DERIVED from Table 4 (508 − 4 UFM) | — |
| 2.7 | UFM→leaf links | **4** (NDR 200G) | RA Table 4 (508 − 504); Table 8 "2 NDR Cables, 200 Gbps, UFM to leaf ports" + "4 UFM System Transceivers" | — |
| 2.8 | Leaf→spine cables | **512** (each leaf 4 × 8 spines) | RA Table 4 | — |
| 2.9 | Node transceivers | 4 twin-port OSFP per DGX → 63 × 4 = **252** | RA Table 8 "508 System OSFP Transceivers" = 127 × 4 | — |
| 2.10 | Switch transceivers | every cage populated: 24 × 32 = **768** twin-port OSFP | DERIVED; reconciles RA Table 8 "1536 Switch OSFP Transceivers" = 48 switches × 32 cages | — |
| 2.11 | Cable type | NDR 400G, 980-9I570-00N030 (length-dependent) | RA Table 8 | — |

## 3. Storage fabric (NDR InfiniBand, separate from compute)

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 3.1 | Technology | InfiniBand, independent of compute | RA p.5, p.12 | "The storage fabric employs an InfiniBand network fabric" |
| 3.2 | Switch | QM9700 (MQM9700-NS2F) | RA p.12; Table 7 | "The storage fabric uses MQM9700-NS2F switches" |
| 3.3 | Ratios | storage 1:1 port:uplink; DGX ≈ 4:3 | RA p.12 | "storage devices are connected at a 1:1 port to uplink ratio. The DGX H100 system connections are slightly oversubscribed with a ratio near 4:3" |
| 3.4 | Storage ports per DGX | 2 | RA p.10 Fig. 4 text; Table 8 "254 DGX System Transceivers QSFP112" = 127 × 2 | "Each pair of in-band management and storage ports provide parallel pathways" |
| 3.5 | 4-SU reference | 16 QM9700; 494 NDR400 cables (DGX→leaf + leaf→spine); 48 × "NDR 2x200G" to storage | RA Tables 7, 8 | — |
| 3.6 | Check of the 4:3 rule on the 4-SU numbers | 494 − 254 DGX = 240 leaf-spine ≈ 254 × ¾ (190.5) + 48 storage (1:1) = 238.5 | DERIVED — confirms the rule reproduces the RA | — |
| 3.7 | 2-SU switch count | **not in RA** → 5 leaf + 2 spine = **7** | DERIVED (see §9) | — |
| 3.8 | Storage appliances | "Varies", typical example 6 units at 4 SU, 2,880 W EAP / 3,600 W EPP each | DCG Table 4 p.6 | "Varies¹ … 1. See NVIDIA DGX SuperPOD Reference Architecture. Typical example depicted." |
| 3.9 | Storage links per appliance | 48 splitter cables / 6 appliances = 8 × (400G → 2 × 200G) | DERIVED from RA Table 8 + DCG Table 4 | — |
| 3.10 | Mgmt servers on storage fabric | 4 × "HDR 400 Gbps to 2x200 Gbps, Slurm management" at 4 SU | RA Table 8 | — |
| 3.11 | Performance target | "Better": 40 GBps read per SU | RA Table 6 p.16 | — |

## 4. In-band management (Ethernet)

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 4.1 | Switch | SN4600C, 64 × QSFP28 100G, 920-9N302-00F7-0C2 | RA Table 1; Table 7 | — |
| 4.2 | Speed/bonding | 100 Gbps, bonded | RA p.5 | "operate at 100 Gbps and are bonded for resiliency" |
| 4.3 | DGX ports | 2 per node (254 at 4 SU) | RA Table 8 "254 · 200 Gbps QSFP56 AOC · DGX H100 system" | — |
| 4.4 | 4-SU reference | 8 switches; 24 leaf→core, 6 ISL, 4 CWDM4 DC uplinks, 8 → mgmt nodes, 8 → NFS, 16 OOB uplinks | RA Tables 7, 8 | — |
| 4.5 | Inferred 4-SU shape | 6 leaves (3 MLAG pairs, 2 ISL each = 6; 4 uplinks each = 24) + 2 core | DERIVED from 4.4 | — |
| 4.6 | 2-SU shape | 1 MLAG leaf pair per SU + 2 core = **6** | DERIVED (see §9) | — |

## 5. Out-of-band management (1 GbE)

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 5.1 | Switch | SN2201, 48 × RJ45 1G + 4 × 100G, 920-9N110-00F1-0C0 | RA Table 1; Table 7; DTL | — |
| 5.2 | Scope | BMCs, mgmt servers, storage, switches, rack PDUs | RA p.14 | "connects the management ports of all devices including DGX and management servers, storage, networking gear, rack PDUs" |
| 5.3 | DGX port | the BMC port only | RA p.10 | "The OOB port is used for BMC access. (The LAN port next to the BMC port is not used…)" |
| 5.4 | 4-SU reference | 8 switches; 2 × 100G uplinks each to in-band; 2 UFM back-to-back | RA Tables 7, 8 | "Two uplinks per OOB to in-band" |

## 6. Management plane

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 6.1 | UFM | 4 × UFM Appliance 3.1 (at 4 SU) | RA Table 7 | — |
| 6.2 | UFM per fabric | 2 compute + 2 storage (Table 8 lists 4 UFM transceivers under each fabric) | DERIVED from RA Table 8 | — |
| 6.3 | UFM HA | 2 back-to-back cables → one link per UFM pair | RA Table 8 | "UFM Back-to-Back" |
| 6.4 | BCM mgmt servers | **4** × 2-socket x86, 384 GB, 4 × HDR200 VPI | RA Table 7 | "4 BCM Management servers" |
| 6.5 | … conflicting count | **5** × Dell PowerEdge R750 | DCG Table 4 | — |
| 6.6 | Software | Base Command Manager, Slurm | RA Table 2; Table 7 title "…with SLURM" | — |

## 7. DGX H100 node

| # | Fact | Value | Source |
|---|---|---|---|
| 7.1 | Compute NICs | 4 OSFP cages → 8 single-port ConnectX-7 (NDR 400G) | RA p.2 "four OSFP ports serving eight single-port NVIDIA ConnectX-7 VPI" |
| 7.2 | Storage/in-band NICs | 2 × dual-port QSFP112 ConnectX-7 (4 ports: 2 storage + 2 in-band) | RA p.2, p.10 |
| 7.3 | BMC | 1 × 1GbE RJ45 | RA p.10; UG |
| 7.4 | Height | 8U (356 mm) | DCG Table 1 |
| 7.5 | Max power | **10.2 kW** | DCG Table 1; DCG Table 4 |
| 7.6 | PSUs | 6 × 3,300 W, C20 inlet (C19/C20 cord), 4 of 6 must be energised | UG; DCG §3.2 "Four power supply units must be energized" |
| 7.7 | Weight | 130.45 kg | DCG Table 3 |

## 8. Racks, power, cooling

| # | Fact | Value | Source | Quote |
|---|---|---|---|---|
| 8.1 | Density | 4 DGX / rack optimal; >4 not recommended | DCG §1.4 p.4; Table 8 note 3 | "optimally deployed at a rack density of four systems per rack" |
| 8.2 | Per-rack power at 4/rack | 40.8 kW | DCG Table 2 | — |
| 8.3 | Preferred supply | 415 VAC 32 A three-phase, N+1, 21.8 kW per circuit | DCG Table 8; p.11 | "The preferred power for high-density deployment patterns is 415 VAC, 32A, three-phase, N+1" |
| 8.4 | Provisioning | 3 circuits per DGX rack, none > 50 % of load; each rPDU feeds 2 of 6 PSUs | DCG Table 8 note 2 | "three circuit N+1 power provisioning scheme where no circuit carries more than 50% of the load" |
| 8.5 | Management racks | 2 per SU | DCG §1.4 p.4 | "every SU also requires two management racks" |
| 8.6 | … conflicting count | 38 racks at 4 SU = 32 DGX + **6** mgmt (PDUs: 96 = 32 × 3, 12 = 6 × 2) | RA Table 7 (DERIVED split) | — |
| 8.7 | rPDU models | Raritan PX3-5878I2R-P1Q2R1A15D5 (DGX racks), PX3-5747V-V2 (mgmt) | RA Table 7 | — |
| 8.8 | Rack size | ≥ 600 × 1200 mm, ≥ 48U | DCG §4 | — |
| 8.9 | Airflow | 157 ft³/min per kW | DCG §1.6 | — |
| 8.10 | Component peak power | QM9700 1,720 W · SN4600C 820 W · SN2201 135 W · R750 880 W · UFM 750 W · storage 3,600 W | DCG Table 4 | — |

### Per-rack budget (stated, drives nodes per rack)

- **DGX rack:** 3 × 415 V/32 A/3φ circuits (21.8 kW each), N+1, no circuit > 50 %.
  Usable = 2 × 21.8 = **43.6 kW**. 4 × 10.2 = 40.8 kW ≤ 43.6 ✓; 5 × 10.2 = 51 kW ✗ (and DCG note 3).
  → **4 DGX per rack**. Cooling 40.8 kW × 157 = **6,406 CFM** per rack.
- **Management rack:** 2 × 415 V/32 A/3φ circuits, 2N (one circuit carries it all) →
  **21.8 kW** budget per rack. Two rPDUs per mgmt rack matches RA Table 7 (12 PDUs / 6 racks).

## 9. Derivations for 2 SU (where the RA gives only the 4-SU figure)

**Storage fabric** (rule from 3.3, validated against the 4-SU numbers in 3.6):
- DGX storage ports: 63 × 2 = 126 → **4 DGX-facing leaves** (32 down / 24 up = exactly 4:3).
- Storage appliances: **3** (half of DCG's 6-at-4-SU example; ≈ 3 × 40 GBps comfortably exceeds
  RA Table 6 "Better", 80 GBps for 2 SU). 3 × 8 splitter ports = 24.
- **1 storage leaf**: 24 appliance ports + 4 UFM-storage + 4 mgmt-server splitter ports = 32 down,
  24 up (storage 1:1).
- Uplinks 4 × 24 + 24 = 120 → **2 spines** (128 ports). Total **7 QM9700**. Leaf-spine 120 cables.
- Cross-check the same rule at 4 SU: 8 DGX leaves + 2 storage leaves + 4 spines = 14 vs RA's 16
  (RA leaves headroom; rule is conservative-in-count, flagged).

**In-band:** per SU one MLAG pair of SN4600C leaves (each DGX: 1 link to leaf A, 1 to leaf B) +
2 core = **6**. Leaf→core 4 per leaf = 16; ISL 2 per pair × 3 pairs = 6; DC uplinks 4 (not
SU-scaled); mgmt servers 4 × 2 = 8; NFS appliance 4 (half of RA's 8); OOB uplinks 4 × 2 = 8.

**OOB:** ports = 63 DGX + 24 compute IB + 7 storage IB + 6 in-band + 4 mgmt + 4 UFM + 3 × 2 HPS
+ 2 NFS + 56 PDUs = **172** → ⌈172 / 48⌉ = **4 SN2201** (90 % fill; RA ratio is 2 per SU).

**Racks (H100-era text; H200 build = 32 DGX racks at 2/rack, see H.2):** 16 DGX racks (64 slots, 63 populated — the empty slot is SU2 node 32, displaced by
UFM) + 4 mgmt racks (DCG 2 per SU) = **20**. Mgmt rack power, packed against 21.8 kW:

| Rack | Contents | Peak kW |
|---|---|---|
| mgmt-01 | SU1 compute: 8 leaf + spines 1–4 (12 × QM9700) | 20.6 |
| mgmt-02 | SU2 compute: 8 leaf + spines 5–8 (12 × QM9700) | 20.6 |
| mgmt-03 | storage fabric 7 × QM9700, 4 UFM, 4 mgmt servers, 2 in-band core | 20.2 |
| mgmt-04 | 3 HPS + 1 NFS appliance, 4 in-band leaf, 4 OOB | 18.2 |

## Decisions (resolved 2026-09-30 — see addendum for the H200 basis)

| ID | Question | Recommendation |
|---|---|---|
| **D1** ✅ decided: 63 | 63 nodes / 504 GPUs (RA Table 4) vs 64 / 512 | **63 / 504** — RA-faithful; 64 needs a non-RA UFM attachment (the 2-SU fabric has zero free ports). Keep tag `dgx-superpod-512` as the name of the 2-SU/512-slot design; validation asserts 504 GPUs + 1 reserved slot. |
| D2 ✅ H.1 | Management servers | **5 × Dell R750**: `bcm-head-01/02`, `slurm-ctl-01`, `slurm-login-01/02` (roles are a CHOICE). |
| D3 | UFM appliances | **4** (2 compute pair + 2 storage pair), per RA Table 7/8. |
| D4 | Management racks: 2/SU (DCG) vs 6 at 4 SU (RA) | **4** (DCG). Built packing: mgmt-r01/r02 = SU compute leaves + 4 spines + 1 UFM (21.39 kW); r03 = in-band + 5 mgmt + 3 HPS (20.12 kW); r04 = storage IB + OOB + UFM-s (14.2 kW) — all ≤ 21.8 kW 2N. |
| D5 | Storage appliance | **Generic HPS appliance (custom type)**, 3 units, 16 × NDR200, DCG power figures — vendor-neutral like the RA. |
| D6 | rPDUs: RA's Raritan PX3-5878I2R / PX3-5747V-V2 are not in the library | **Library Raritan PX3-5730-V2** (415 V 3P+N+E, 12 × C19 + 24 × C13) as the stand-in for both; recorded as a substitution. |
| D7 | Storage switch count at 2 SU (not in RA) | **7** by the validated 4:3 / 1:1 rule (§9). |
