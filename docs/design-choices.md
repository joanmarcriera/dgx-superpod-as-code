# Design choices — what was chosen and why

Companion to `docs/ra-notes.md`. The RA notes record what NVIDIA specifies; this file records
every **CHOICE** made where the RA is silent or leaves it to the buyer, and the reason for
each. Evidence lives in `reference/<pack>/README.md` (cited as *ref:pack*). Last updated
2026-09-30.

## 1. The target buyer and the workload (opinion)

**Target buyer (hypothetical):** an enterprise or sovereign foundation-model team (the profile *ref:workload §8*
finds buying ~500-GPU H200 clusters: sovereign AI programmes, neoclouds, research labs).

**Workload: training-first.** About 80 % of the time goes to continued pre-training /
domain adaptation of 8B–70B dense and MoE models plus post-training (SFT, DPO, RL). The
other 20 % is evaluation and batch inference. Production serving is **not** this system's
job.

Why:
- **The fabric says training.** A full non-blocking, rail-optimised NDR400 fat tree with
  8 NICs per node exists for collectives (all-reduce, MoE all-to-all). MLPerf Llama 3.1
  405B scales 1.97× from 512 to 1,024 Hopper GPUs on this kind of fabric *(ref:workload
  §2, §4)*. An inference buyer would take Spectrum-X Ethernet and skip the 1:1 bisection.
- **The size says continued pre-training, not frontier from scratch.** At 35–50 % MFU:
  - 504 H200 pre-train an 8B model on 15T tokens in 33–48 days (feasible).
  - A 70B model on 15T tokens takes 293–418 days, which is not a business plan.
  - A 70B model on 2–3T tokens fits in 2–3 months, and fine-tuning runs are hours to
    days *(ref:workload §5, DERIVED)*.
- **H200 memory helps both, but a serving fleet would be sized differently.** H200 has the
  same FLOPS as H100 with +76 % HBM and +43 % bandwidth. That gives about 14–16 % for
  training and up to 1.5× for inference *(ref:workload §1, §3)*. A 70B model fits
  inside one node's 1.1 TB HBM, so inference replicas stay node-local and don't need the
  fabric.

**How the choice is applied:**

| Area | Consequence |
|---|---|
| Compute fabric | Kept exactly as the RA (rail-optimised, 1:1). No change. |
| Storage | Sized for **checkpoints**: write bandwidth matters as much as read (RA: write ≥ ½ read for LLM checkpoints). Two tiers (§2). |
| UFM | 2 per fabric (RA). Training needs fabric telemetry, congestion and adaptive routing. |
| Scheduling (not modelled) | BCM + Slurm (RA Table 2). Partitions: `train` (whole SUs, rail-aligned), `post` (single nodes), `eval`. Containers with NeMo, Pyxis/Enroot. |
| Power | Plan for sustained ~80 % draw. 63 × 10.2 kW = 643 kW DGX peak; a 30-day run at 80 % ≈ 370 MWh for the DGX alone *(ref:workload §7)*. |

## 2. Storage: two systems from two vendors

| Tier | Choice | Where | Why |
|---|---|---|---|
| 1 — hot (training data streaming, checkpoints) | **4 × DDN AI400X2T** (EXAScaler/Lustre), 2U each | storage IB fabric (QM9700), 8 × NDR200 per unit via 4 splitters; rack `stor-r01` | The DDN model NVIDIA certifies for **Hopper** SuperPODs. The AI400X3 is certified only for the B200/GB200 RAs, so it is not used here *(ref:storage §2)*. Parallel FS on the dedicated IB fabric is what the RA assumes. |
| 2 — warm/capacity (home dirs, tokenised dataset lake, S3 model registry, checkpoint retention) | **VAST Data**: 5 CBox (20 CNodes) + 4 Ceres DBox DF-3015V2 + 2 backend switches | CNode client ports on the **in-band spines** (100G, NFS/S3); private NVMe-oF backend pair; rack `stor-r02` | Certified for DGX SuperPOD since 2023. One system for NFS + S3. The RA already puts NFS on the in-band network (ra-notes 4.4). A second vendor gives tier and failure-domain diversity. |

**Sizing arithmetic:**
- NVIDIA RA Table 5.2 per SU is Good 15/7, Better 40/20, Best 125/62 GB/s (read/write).
  At 2 SU (linear, DERIVED) that is Better 80/40, **Best 250/124**.
- DDN's H100 RA sizing table gives 4 × AI400X2 = 360 R / 260 W GB/s.
- **Tier 1 = 4 × AI400X2T ≥ Best on read and 2× Best on write.** I chose four over the
  eight in DDN's rule (1 GB/s per GPU, 4 per 32 DGX): NVIDIA's "Best" is already met, and
  the money is better spent on GPUs. Scale-out to 8 is a rack-space-only change
  (`storage.hps_appliances`).
- **Checkpoint check:**
  - A 70B model with Adam at 16 B/param is a 1.12 TB checkpoint: 4.3 s at 260 GB/s,
    ~15 s at a realistic 30 % efficiency.
  - A 405B fine-tune is 6.5 TB: ~25 s theoretical, ~80 s realistic.
  - Both are well under a 5-minute budget, so checkpoint every 15–30 min *(ref:workload §6)*.
- **Tier 2 = VAST NCP RA "Better" (10 CBox + 8 DBox at 4 SU) halved:** 5 + 4.
  That is 4 × 338 TB = 1.35 PB raw before VAST's data reduction.
- Power: `stor-r01` 14.4 kW, `stor-r02` 15.5 kW peak (budget 21.8 kW, 2N like the
  management racks).

**Why not the others:** WEKA would also fit tier 1 or 2 but duplicates what VAST gives on
Ethernet. NetApp AFF A90, Pure FlashBlade//S, Dell PowerScale F710 and IBM SSS 6000 are all
certified, but their tier-2 story is weaker for S3 + NFS at this scale, or their per-unit
specs are incomplete in public sources *(ref:storage §3)*.

**Data gaps accepted:** DDN's AI400X2T power is not published (the datasheet is behind a
form), so the DCG storage example is used: 2,880 W avg / 3,600 W peak. VAST CBox PSU rating
is not published: 2 × 1,300 W CHOICE against VAST's 2.1 kW active.

## 3. Data hall

| Choice | Value | Why |
|---|---|---|
| Rows | 2 rows × 19 racks, one row per SU, **back to back around one contained hot aisle** | DCG: keep each SU contiguous or split across facing rows to stay within cable length *(ref:facility §1)*. |
| Mid-row racks | Row A: `mgmt-r01` (SU1 leaves + spines 1–4), `mgmt-r03` (in-band, BCM/Slurm), `stor-r01` (DDN). Row B: `mgmt-r02`, `mgmt-r04` (storage IB, OOB, UFM-s), `stor-r02` (VAST) | Worst node→leaf run ≈ 6 m along the row + 2 × ~2.5 m up/down ≈ 11 m. NDR MMF limit is 50 m, preferred 30 m *(ref:facility)*. |
| Aisles | cold 1,220 mm, hot 1,200 mm | DCG: cold aisle ≥ 1,219 mm, any aisle ≥ 914 mm. |
| Cooling | **Air only; no CDU, no rear-door HX** | DGX H200 is air-cooled (1,105 CFM, 18–27 °C inlet). 20.4 kW/rack × 157 CFM/kW ≈ 3,200 CFM, which containment plus CRAH/fan walls at the row ends handle. CDUs are for liquid-cooled GB200/GB300. RDHx (e.g. ColdLogik CL20) stays an option only if the room can't deliver the airflow *(ref:facility §4)*. |
| Overhead | Starline busway per power path (A/B/C), ladder rack, yellow fibre raceway per row | DCG / Legrand DGX guide: overhead power and cabling, segregated. |
| Racks | APC NetShelter SX **AR3307B2** (48U, 600 × 1200 × 2258 mm, black) | DCG ≥ 48U, 600 × 1200. AR3307 reached end of sale 2025-12-31; B2 is its successor. Side panels on, blanking panels everywhere, no chimneys. |

## 4. Cable and power colours

NVIDIA prescribes **no per-fabric colours**. It says to colour-code ties and labels by
endpoint *(ref:network §7)*. So jackets are as shipped, and fabrics are told apart by
tie/label colour matching the draw.io palette:

| Fabric | Jacket (as shipped) | Tie / label |
|---|---|---|
| Compute IB | aqua MMF `#00A7B5`, green MPO/APC shells | **rail colour** (Okabe-Ito, same as the drawings) |
| Storage IB | aqua | purple `#9467BD` |
| In-band 100G | aqua AOC | orange `#FF7F0E` |
| VAST backend | black DAC (in-rack) | purple |
| OOB | grey Cat5e (RA says Cat5e) | brown `#8C564B` |
| DC uplinks | yellow single-mode | — |
| Power | cords and rPDU tags A red / B blue (OCP convention), **C green** (no standard exists) | — |

## 5. Drawings

- **draw.io** (`docs/superpod.drawio`, generated): per-SU compute fabric, storage IB,
  VAST backend, in-band, OOB, rack elevations for every rack, and the floor plan to scale.
  Why draw.io: SAs can open and polish a copy, and it exports to PDF/SVG. See the
  tool comparison in the plan that preceded it.
- **Blender** (`blender/`) builds from `docs/scene.json`, so the render
  cannot drift from NetBox.

## 6. Decisions on the RA ambiguities (decided 2026-10-16)

1. **DGX-rack rPDU form factor — DECIDED: 3 × 3U horizontal (9U).** RA Table 7 names Raritan
   PX3-5878I2R-P1Q2R1A15D5; the model is not published, but its nearest sibling (-Q1) is a
   horizontal 3U unit with 18 × C19 + 6 × C13. The DGX racks now carry three of them
   (`catalog/custom/Raritan-PX3-5878I2R-3U.yaml`, `spec/superpod.yaml` `power.dgx_pdu_*`) at
   RU40/43/46 (the top 9U), each feeding 2 of a DGX's 6 PSUs (DCG Table 8 note 2). The DGX
   systems keep DCG §4.8's positions (RU3 and RU14, 3U gap), so nothing collides. Management and
   storage racks keep the 0U vertical stand-in (library PX3-5730-V2). Why: it is the RA's part
   and it explains DCG's "start at RU3" better than a 0U PDU does.
2. **Apply to NetBox? — OPEN, my call.** The storage tiers, storage racks, hall and PDU
   change alter the NetBox model. `bin/dgxnb plan` shows the diff; `apply` needs a snapshot of
   the NetBox database and a go-ahead first.
3. **Tier-1 count — DECIDED: 4 × DDN AI400X2T (NVIDIA "Best").** 4 × (≥90 GB/s read, 65 GB/s
   write) meets NVIDIA's "Best" tier for 2 SU (RA Table 5.2 × 2) and keeps the storage rack within
   its power budget. **Documented alternative:** DDN's own sizing of 8 appliances
   (1 GB/s per GPU, 504 GB/s). Choose it when the workload is checkpoint- or dataloader-bound
   beyond the RA's guidance; it doubles tier-1 ports, rack U and switch splitters
   (`storage.hps_appliances: 8`; re-check storage-rack power and U).

## 7. Mixed pod (site `dgx-lab-03`, spec `spec/superpod-mixed.yaml`) — 2026-10-01

**No NVIDIA RA covers a mixed H200 + GB300 pod**, so the whole composition is a CHOICE.
Each pod is built by its own unchanged builder (`docs/ra-notes-mixed.md` M.1–M.5); the rows
below are the decisions on top. Vendor evidence: *cs* = `reference/cooling-schneider/README.md`
(section numbers), *rd* = the Schneider/NVIDIA reference-design notes (not published), *gb* =
`reference/compute-dgx-gb300/README.md`.

### 7.1 The pod reading

| Choice | Value | Why |
|---|---|---|
| Two RA-pure pods, one site | SU 1 = H200 1-SU row (31 DGX, 248 GPUs), SU 2 = GB300 1-SU (8 × NVL72, 576 GPUs); **824 GPUs** | my decision 1: never a federated single fabric; each pod keeps its RA compute / storage / management fabrics, UFMs and BCM |
| Shared and nothing else | site/hall, power distribution (PP-A/B/C + a mechanical panel PP-M), the cooling plant, one DC-core demarc (16 ports: H200 core1–12, GB300 core13–14), VAST tier 2 | ra-notes-mixed S.1–S.5 |
| GB300 storage | the spec's 4 generic HPS appliances **and its 2 storage leaves are dropped**; the GB300 pod reaches VAST (NFS/S3 on the H200 in-band spines) through the DC core; its storage segment still rides its own compute leaves → spines → edge | RA-GB300: storage is vendor-specific; "starting at 2" storage leaves exist only to attach in-pod appliances — with none they would be two idle SN5600D (3 kW). **Open question 7.6-1** |
| H200 management racks at 1 SU | 3 (DCG 2 per SU + 1); ufm-c-02 moves from the compute rack to the in-band rack | the compute rack (12 QM9700 + 2 UFM) would be 22.1 kW > 21.8 kW 2N (`test_one_su_is_the_ra_1su_row_within_budget`) |
| SU numbering | H200 = SU 1, GB300 = SU 2 (`dgx_su` renumbered in the merge; device names keep their pod prefixes `dgx-/mgmt-/stor-` vs `gb-`) | one design tag, unique SU per fabric page |

### 7.2 Cooling architecture

| Choice | Value | Why / source |
|---|---|---|
| Row A (H200): RDHx on every rack | **Motivair ChilledDoor M8** (30 kW nominal at 12.8–18.3 °C water, 100 % water; 363 mm deep; 5 EC fans ≤ 840 W; 0–23 GPM) on the 16 DGX racks, 3 mgmt racks and both storage racks | *cs §1*; worst rack 21.4 kW (mgmt-r01) → 1.4× margin. The M4 (12 kW) is too small; M12 (45 kW) is the same depth and a spare option |
| GB300 management racks (row B) | also ChilledDoor M8, on the RDHx loop | 22.4 kW each (gb-mgmt-r01/02); keeps the residual-air load to the NVL72 10 % only |
| Row B (NVL72): direct liquid | the racks' own rear supply/return manifolds + blind-mate QDs (~90 % liquid), modelled as `nvidia-nvl72-coolant-manifold` per rack | *gb* "Manifolds": 2 vertical blind-mate strips, UQDB04 QDs, FD83 hose fittings to the CDU; liquid fraction from `reference/facility` §4 (Lenovo LP) |
| NVL72 residual air (~10 % = 108 kW) | **2 × Uniflair HDCV 4600A HT** perimeter CRAHs (N+1), one at the far end of each cold aisle, on facility water directly | *cs §4*: HT coil 109.5 kW net sensible at 20/30 °C — a lower bound at our 10/15 °C water. Not an RDHx: **no rear-door option for NVL72 was found** (*gb* "Rear-door HX": NOT FOUND; the rear carries the 132 mm extension frame, cable bracing and manifold fittings). Not InRow: 600 mm InRow units would take row-B slots the CDUs need |
| CDUs, RDHx loop | **2 × Motivair MCDU-40** (N+1): load 469 kW (395 kW IT + 25 × 0.84 kW fan max + GB300 mgmt 63 kW) vs 842.5 kW each at R4 | *cs §2* R4 (7.2 °C primary, 15.6/28.9 °C secondary, ~8.3 K approach) is the printed rating nearest this loop. Also fits 3 × MCDU-25 (421 kW); two larger units use less floor (2 × 914 mm) |
| CDUs, DLC loop | **2 × Motivair MCDU-45** (N+1): load 974 kW (8 × 135.3 × 0.9) vs 1,081 kW each at R4 | *cs §2* R4 used as a **lower bound**: the DLC approach (10 → 35 °C) is far larger than R4's 8.3 K, and R1 (32 °C primary) prints 1,567 kW. Secondary pump 308 GPM = 1,166 l/min ≥ 932 l/min loop flow |
| Plant | **3 × Uniflair BCEF 0903A** free-cooling chillers (N+1), one block outside the +X hall wall, FWS 15/10 °C: 965.1 kW each at 15/10 °C / 20 % glycol / 35 °C; N−1 = 1,930 kW ≥ 1,600 kW plant load | *cs §3*. The FWS temperature is set by the RDHx loop (door rated ≤ 18.3 °C, CDU approach ~8 K); the DLC loop simply runs a bigger approach on the same water. The BCEF **1103A** (1,279 kW) would need 2 without redundancy; Uniflair **XCA** (1.2–2.5 MW) has no published rating conditions. **Open question 7.6-2** |
| Plant load | 1,600 kW = 1,530 IT + 21 door fans + 49.6 CDU pumps/parasitics (FLA-derived) + 0 CRAH fans (NOT FOUND) | `cooling.model` |
| Door fans and the rack budget | the door's C14 cord goes to the rack's rPDU but its 840 W max is **not** counted in the IT circuit budget (`maximum_draw` only); its heat is added to the loop | mgmt-r01 is at 21.39 of 21.8 kW; the fans modulate and sit far below max at 21 kW of rack heat. Tight spot recorded — **open question 7.6-3** |
| Loop temperatures | RDHx TCS **18 / 28 °C** (≤ 18.3 °C rating band; ≥ dew point + 2 K per the HPE QuickSpecs); DLC TCS **35 / 50 °C** (Lenovo GB300 table: 35 °C supply needs ≥ 89 L/min per rack; the model gives 116); FWS **10 / 15 °C** | *rd* §2–§3. NVIDIA's own NVL72 TCS figure and the Schneider RD loop temperatures are **NOT FOUND** (RD documents need a login); the door's kW-vs-water-temperature curve is **NOT FOUND**, so the design stays inside the printed 55–65 °F band instead of extrapolating |
| Flow rule | l/min = kW × 60 / (4.18 × ΔT) for water; PG25 needs ~5 % more | derived; door ≤ 87 l/min (33 needed), NVL72 manifold ≤ 177 l/min at 45 °C (117 needed) |
| Headers | one overhead supply/return pair per row and loop, DN125 (≤ 1.5 m/s = 1,104 l/min) at 3.30 m, 460 / 610 mm behind the rear face (clear of the 363 mm doors), the DLC pair 300 mm outboard of the RDHx pair behind row B; FWS mains at 3.55 m over the rear-aisle centre; branch = isolation valve + 1 in flex hose pair per rack, drip pan | overhead (busway 2.56, raceway 2.60, ladder 2.92 m; `blender/README.md`); Motivair supplies the door hoses, manifolds with per-port isolation valves and drip pans (*cs §5*); pipe DN and heights are CHOICE |
| CDU placement | the 9 rack positions row B leaves free (5.4 m): 2 × MCDU-40 (914 mm) + 2 × MCDU-45 (915 mm) with 300 mm gaps = 4.96 m, facing the row-B cold aisle | *rd* placement guidance where available; Motivair's own MCDU-30 release quotes a 600 × 1200 rack footprint for the smaller model |
| Leak detection | NetBotz leak rope NBES0308 (+ NBES0309 extensions) along each row rear at floor level; every door and CDU has its own WDS | *cs §5* |
| Power for the mechanical kit | panel **PP-M**: one 415 V feed per CDU (32 A; FLA 15.4 / 20.3 A), per CRAH (32 A; fan power NOT FOUND) and per chiller (630 A; 284 kW absorbed) | CHOICE; NetBox needs a feed per device |
| NetBox modelling of pipes | NetBox has no pipe object: every hose, header run and primary run is a **cable with blank `type`**, custom field `dgx_fabric = coolant-supply / coolant-return`, between `other` interfaces (`SUPPLY/RETURN`, `S-n/R-n`, `CDU-S-k/CDU-R-k`, `PRI-*/SEC-*`); headers and the FWS mains are non-racked "devices" of a stand-in type | keeps the hydraulic graph inside NetBox so the tracing add-on and `bin/validate` can walk it |

### 7.3 Containment and the rear aisle

| Choice | Value | Why |
|---|---|---|
| Containment | **none** — no roof, no end doors | With an active RDHx on every air-cooled rack the exhaust is room-neutral (the door cools the rack's own exhaust before it leaves), and the NVL72 racks reject only ~10 % to air; the CRAHs handle that plus room gains. *rd* guidance recorded there if it differs |
| Rear aisle | 1,950 mm between rack envelopes = 1,220 clear + 2 × 363 mm doors (both rows carry doors: row A everywhere, row B on the 4 mgmt racks) | DCG cold aisle ≥ 1,219 mm applied to the rear aisle as well (lifts and door swing); `test_rear_aisle_stays_clear_behind_the_doors` |
| Door swing | 95° (CD25) / 0–90° (IOM); hinge side NOT FOUND → CHOICE: hinged on the left seen from the rear | *cs §1* |
| Room | 3.2 m clear beyond each row end (the +X end is the pipe wall), 1.8 m walkway beyond each cold aisle, 200 mm wall, plant block 1.5 m outside the wall | as the H200 render (`blender/README.md`), now spec-driven (`hall.end_clear_mm` …) |

### 7.4 CDU and plant sizing table

| Loop / unit | Load (kW) | Unit rating (kW) | Rating condition | N | +1 | N−1 capacity (kW) | Flow (l/min) |
|---|---|---|---|---|---|---|---|
| RDHx — Motivair MCDU-40 | 468.8 | 842.51 | *cs §2* R4: 7.2 °C primary, 15.6/28.9 °C secondary | 1 | 1 | 842.5 | 673 (≤ 908 secondary pump) |
| DLC — Motivair MCDU-45 | 974.0 | 1,081 | *cs §2* R4 (lower bound; R1 1,567) | 1 | 1 | 1,081 | 932 (≤ 1,166) |
| Residual air — Uniflair HDCV 4600A HT | 108.2 | 109.5 | *cs §4* HT coil, 20/30 °C water (lower bound at 10/15) | 1 | 1 | 109.5 | — |
| Plant — Uniflair BCEF 0903A | 1,600.5 | 965.1 | *cs §3* 15/10 °C, 20 % glycol, 35 °C ambient | 2 | 1 | 1,930.2 | — |

All four rows are asserted by `tests/test_cooling.py` (load ≤ N−1 capacity, flows within the
unit, header and pump ratings). Re-rating at the exact plant temperatures with Motivair is
the next real-world step: the printed R2 row is internally inconsistent (*cs §2*).

### 7.5 Colour convention for supply / return

BS 1710:2014 (verified from the Water Regs UK leaflet, *rd* §3) gives **every water service a
green basic identification colour (BS 4800 12 D 45)** with a code band for the water source,
and tells flow from return by **text and arrows, not colour**. The model therefore paints the
headers' bands green and — as a CHOICE for legibility — adds a blue `#1565C0` band on supply
and a red `#C62828` band on return runs plus flow arrows; the NetBox cable colours use the
same two codes. The chilled-water code colour of the standard's general table could not be
verified (paywalled), so it is not claimed.

### 7.6 Open questions (mixed pod)

1. **GB300 storage leaves:** keep the RA's 2 SN5600D storage leaves idle (RA-literal, 3 kW of
   unused switches) or drop them as done here (VAST via the DC core)?
2. **Plant redundancy:** 3 × BCEF 0903A (N+1, 32 m of chiller, 71 m²) as modelled, or 2 ×
   BCEF 1103A (N, 24 m) — or the new Uniflair XCA once Schneider publishes rating conditions?
3. **mgmt-r01 electrical margin:** 21.39 kW of 21.8 with the door fan on the same rPDUs. A third
   rPDU / circuit on the compute management rack, or feed the door fans from PP-M?
4. **ChilledDoor capacity curve** (kW vs water inlet temperature) is NOT FOUND: the design stays
   inside the rated 12.8–18.3 °C band. Worth a Motivair selection run before any warmer loop.
