# Storage reference pack — 2-SU DGX SuperPOD H200 (63 nodes, 504 GPUs, RA-11336-001 V2)

Retrieved 2026-09-30, public sources only. Numbers marked *(derived)* are my arithmetic; NOT FOUND means not located. Vendor "up to" figures are marketing peaks, not certified results (NVIDIA's certification benchmarks are not public — Blocks & Files 2024-09-03).

## 1. What the NVIDIA RA itself says (RA-11336-001, release 2025-04-14)
Source: `media/nvidia-ra-11336-001-dgx-superpod-h200.pdf` (also https://docs.nvidia.com/dgx-superpod/reference-architecture/scalable-infrastructure-h200/latest/storage-architecture.html).
- Sec 2.5.6: SuperPOD uses **two separate storage systems**: *High-Performance Storage (HPS)* = POSIX parallel FS, **native InfiniBand**, RDMA, on the storage fabric (QM9700, >=40 GBps per DGX); and *User storage* = high metadata/IOPS, "key enterprise features such as checkpointing", over **Ethernet** (in-band network) as a secondary path. This matches your two-system plan.
- Table 5.2 (GBps):

| Metric | Good | Better | Best |
|---|---|---|---|
| Single node read / write | 4 / 2 | 8 / 4 | 40 / 20 |
| Single SU aggregate read / write | 15 / 7 | 40 / 20 | 125 / 62 |
| 4 SU aggregate read / write | 60 / 30 | 160 / 80 | 500 / 250 |

  Table 5.1 maps "Better" to "Compressed Images, Compressed Audio and Text Data, such as **LLM Training**". IOPS are NOT in the RA table. A 2-SU row is not tabulated; linear 2 SU *(derived)*: Better 80 R / 40 W, Best 250 R / 124 W.
- Checkpoints (Ch. 5): "terabytes in size ... written synchronously that blocks forward progress"; "Consider at least 1/2 of the read performance as recommended write performance for LLM and large model use cases." GDS over storage fabric >27 GBps into GPUs. Best category: single-node read should approach 80 GBps (network max).
- Certification gate (VAST RA-11389-001 v1, June 2023): current testing requires the "Best" criteria; 1 SU hero test >65 GiB/s read, >20 GiB/s write; pass = >=80% good, none poor.

## 2. Certification table (NVIDIA lists 7 storage partners on https://www.nvidia.com/en-us/data-center/dgx-superpod/ — DDN, IBM, Dell, NetApp, Pure, VAST, WEKA)

| Vendor | Certified product (as publicly stated) | Fabric | Date / source | Level |
|---|---|---|---|---|
| DDN | A3I AI400X2 / AI400X2 Turbo (H100 RA); AI400X3 listed for B200/GB200 SuperPOD RAs; "A1400X2T" per B&F | IB / RoCE / Ethernet | DDN H100 SuperPOD RA (2024, ddn.com PDF); B&F 2024-09-03 | DGX SuperPOD certified |
| VAST Data | VAST Data Platform (Ceres DBox + CBox/CNode) | Ethernet NFS (also IB/RDMA-capable) | 2023-05-17 press release; RA-11389-001 v1 (H100/A100) June 2023 | SuperPOD certified, "first enterprise NAS" |
| WEKA | WEKApod (8-node 1 PB start, later Prime/Nitro) | IB (CX-7 400G) / Ethernet | B&F 2024-03-19 | SuperPOD certified |
| NetApp | EF600 + BeeGFS (2022-05); AFF A90 + ONTAP validated for DGX SuperPOD (2025-03-18) | IB (BeeGFS) / Ethernet (ONTAP) | B&F 2022-05-10; NetApp PR 2025-03-18 | SuperPOD certified/validated |
| Pure Storage | FlashBlade//S500 (Ethernet); //EXA announced separately | Ethernet | B&F 2024-11-18 (7th supplier) | SuperPOD certified |
| IBM | Storage Scale System 6000 | IB / Ethernet | IBM community blog 2025-03-18; B&F 2024-09 | SuperPOD certified; "NVIDIA-Certified Storage" |
| Dell | PowerScale (F710 nodes; 16-node cluster for SuperPOD) | Ethernet | 2024-09-13 (marketscreener/Dell) | "world's first Ethernet-based" SuperPOD storage |

Which DGX generations (H100 vs H200) each cert covers: NOT FOUND for most (NVIDIA does not publish per-vendor H200 cert letters). Project Lightning (Dell): NOT FOUND. FlashBlade//EXA SuperPOD cert: NOT FOUND (only NCP/GB200 mentions).

## 3. Comparison table (per unit, vendor "up to" figures)

| Product | U | Read GB/s | Write GB/s | Capacity | Network | Power W | Source |
|---|---|---|---|---|---|---|---|
| DDN AI400X2 (H100 RA) | 2 | >90 (DDN RA sizing table: 4 units = 360 R / 260 W) | 65 *(derived 260/4)* | 60/120/250/500 TB usable | HDR200 IB x8 (RA) / Ethernet / RoCE | NOT FOUND | DDN H100 SuperPOD RA |
| DDN AI400X3(i) | 2 | 140 | 110 | 120/250/500 TB, 1/2 PB usable | 4x 400G OSFP or 8x 200G QSFP112 (X3M page) | 2400 | DDN MLPerf blog; Boston Ltd listing; ddn.com/products/ai400x3m |
| DDN AI400X3M (GA Q3 2026) | 2 | 190 | 110 | 120 TB-2 PB usable | 4x XDR/400GbE OSFP or 8x NDR200 | NOT FOUND | ddn.com/products/ai400x3m; StorageReview ISC 2026 |
| VAST Ceres DBox DF-3015V2 | 1 | >60 per enclosure (Ceres v1, StorageReview; v2 NOT FOUND) | NOT FOUND | 338 TB raw (+6.4 TB SCM); DF-3060V2 1352 TB | 4x 200GbE/HDR200 (BF3, 2 canisters x 2 QSFP112) | idle 368 / active 400-728 / max 850 | kb.vastdata.com DF-3015V2 datasheet |
| VAST CBox (4 CNodes) | 2 | NOT FOUND | NOT FOUND | stateless | CX-7 front 2p + CX-6 back 2p per CNode | 2100 active | VAST NCP RA June 2024 |
| WEKApod (8-node, 1 PB) | 1 per node (2U/4 nodes in Prime/Nitro) | 720 per 8 nodes (90/node) | 186 per 8 nodes (23.3/node) | 1 PB start; Nitro 20 SSD 1U | CX-7 400G IB; Nitro CX-8 800G | NOT FOUND | B&F 2024-03-19; weka.io datasheets |
| IBM SSS 6000 | 4 | 340 | 155 (B&F quotes 175) | up to 4,791.68 TB raw; 48 NVMe | NOT FOUND (IB/Ethernet) | 2000 max | ibm.com/products/storage-scale-system; StorageNewsletter |
| Dell PowerScale F710 | 1 | NOT FOUND per node (16-node cluster meets SuperPOD) | NOT FOUND | 38 TB-1.2 PB raw/node | 100/200GbE | 769 (25C) / 887 (35C) max | Dell F710 spec sheet h15963 |
| NetApp EF600 + BeeGFS | 2 | 76 per building block | 23 per building block | 1.4 PB usable start | IB | NOT FOUND | B&F 2022-05-10 / StorageReview |
| NetApp AFF A90 | NOT FOUND | NOT FOUND | NOT FOUND | NOT FOUND | NOT FOUND | NOT FOUND | NetApp PR 2025-03-18 (netapp.com 403) |
| Pure FlashBlade//S500 | 5 (chassis) *(unverified)* | NOT FOUND | NOT FOUND | NOT FOUND | 100/400GbE | //EXA metadata chassis 2600 | B&F 2024-11-18 |

Weights/dimensions found: DDN AI400X3 98 lb empty / 108 lb max (44/49 kg), 87 x 446 x 856 mm (895 with bezel) [Boston/StorageReview summaries, secondary]; VAST DBox 29.5 kg max; F710 22.5 kg; IBM SSS6000 46 kg.

## 4. Recommended counts for 2 SU / 63 nodes / 504 GPUs

**Fabric 1 — HPS on NDR IB (DDN AI400X3).**
- Targets (RA Table 5.2, 2 SU linear): Better 80 R / 40 W; Best 250 R / 124 W.
- Best: read ceil(250/140)=2; write ceil(124/110)=2 -> **2 appliances meet Best on paper**. Better: 1 appliance on bandwidth.
- DDN's own rule (H100 RA sizing table): 4 AI400X2 per 32 DGX, "at least 1 GB/s read and write per GPU"; 64 DGX row = 8 AI400X2. 504 GPUs x 1 GB/s = 504 GB/s; write ceil(504/110)=5 -> **5 AI400X3** (4 by read 504/140).
- Recommendation: **4-6 AI400X3**; 4 gives 560 R / 440 W peak, which also covers HA/capacity headroom. DDN's official AI400X3 count for a DGX H200 SuperPOD: NOT FOUND (DDN RA list has DGX B200/GB200 only; datasheet is form-gated).

**Fabric 2 — VAST on Ethernet (NFS/S3).** Source: VAST NCP RA (June 2024, 4 SU = 127 HGX H100): Good 4 CBox + 3 DBox; Better 10 + 8; Best 30 + 25 (8 SU: 8+6 / 20+16 / 62+50). Halving to 2 SU *(derived, linear)*: Good 2 CBox + 2 DBox; **Better 5 CBox + 4 DBox** (their diagram shows 10+8 as 2 x (5+4)); Best 15 + 13. Footnote: VAST 5.2 cuts hardware ~40% for writes. Minimal supported cluster (CBox/DBox floor): NOT FOUND — the smallest published design is Good at 4 SU.
Verdict: the user-storage tier is not a bandwidth problem (Good/Better is ample); size it for capacity. One DF-3015V2 = 338 TB raw.

## 5. Checkpoint guidance
- NVIDIA RA: write >= 1/2 of read; synchronous, stops training. -> 2 SU Better write 40 GB/s, Best 124.
- VAST NCP RA Table 4 (assumes 14 bytes/param, checkpoint writes <= 1% of training time, hourly = 3600 s => 36 s budget): 175B = 2.4 TB -> 68 GB/s (4.25/node); 530B = 7.2 TB -> 206 GB/s; 1T = 13.7 TB -> 389 GB/s. For 504 GPUs, a 175B-class model fits ~68 GB/s; write 40 GB/s (Better) would give ~60 s per hourly checkpoint (~1.7%) *(derived 2.4 TB/40)*. Plan >=70 GB/s sustained write on the HPS for up to ~175B; 5 X3 (550 GB/s write peak) is ample; 2 is marginal.
- DDN: 1 GB/s write per GPU rule (504 GB/s for this pod).
- Dedicated "checkpoint time vs bandwidth" NVIDIA statement beyond the above: NOT FOUND.

## 6. DDN deep dive (AI400X3 family)
Facts: 2U, 24x 2.5" dual-port hot-swap PCIe Gen5 NVMe, AMD Genoa, 140/110 GB/s (X3/X3i), 190/110 (X3M), 4M IOPS (X3i), 8M (X3M); EXAScaler (Lustre); up to 64 appliances/namespace, 32 PB; 200-240 V dual redundant PSU; 5-30 C. Datasheet `https://www.ddn.com/download/ai400x3m-datasheet/` is gated by a web form (not downloaded). Media: `media/ddn-ai400x3-series-product.png` (angled front), `media/ddn-logo-black.svg`. Front-straight and rear photos: NOT FOUND. Older AI400X2 RA (`media/ddn-h100-superpod-reference-architecture.pdf`) Fig 1 has a chassis picture.

### Blender modelling notes — DDN AI400X3 (all colours estimates)
- Box: 446 W x 87 H x 856 D mm (895 with bezel) — secondary source, verify on datasheet. 2U, front-to-rear airflow.
- Bezel (from photo): glossy black, sculpted; 5 elongated oval/elliptical cutouts filled with amber perforated mesh, left to right decreasing/varying size, last larger oval holds white "ddn" logo plate; small "ai400x3" etched text lower centre. Estimate: body #141414, mesh amber #C98A1E, logo white #FFFFFF. Rack ears/sides bare steel #8C8F93 with vertical vent slots on the side.
- Drive bays: 24x 2.5" NVMe behind the bezel (layout NOT FOUND; assume 1x24 front row, 2U => vertical-ish 2.5" slots in 24 columns is unlikely; use two horizontal rows of 12 as placeholder).
- Rear: NOT FOUND. From spec: 2 controllers, each with host ports (4x OSFP 400G total or 8x QSFP112 200G), management "M" and BMC "B" RJ45 per controller (DDN RA), 2 PSUs.

## 7. VAST deep dive
Ceres DBox DF-3015V2 (338 TB raw, 6.4 TB SCM) / DF-3060V2 (1352 TB, 12 TB SCM): 1U, 438 W x 43.5 H x 900 D mm (+65.15 mm handles; chassis depth 971.85; rack depth >=1080), 29.5 kg max, 2x 1600 W PSU; 22x E1.L 9.5 mm NAND (PCIe 4) front + 8x U.2 SCM; 2 BF3 canisters, each 2x 200GbE/NDR200 QSFP112 + 2x RJ45 + USB-C. Datasheet: https://kb.vastdata.com/docs/dbox-df-3015v2df-3060v2-ceres-datasheet (updated 2026-07-24). Earlier DF-3015/3060 (BF1, 8x100G). CBox: 2U, 4 CNodes, 2.1 kW; dimensions NOT FOUND. Newer EBox/Cisco-UCS/HPE options exist; not assessed.
Media: front, open-top, rear, dimension drawings (technical diagrams, not photos), white logo PNG. VAST photo/SVG logo: NOT FOUND (logo PNG only).

### Blender modelling notes — VAST Ceres v2 (colours estimates)
- Box 438 x 43.5 x 900 mm, handles/ears +65.15 mm at rear. Front (from diagram): left ear, 11 vertical E1.L bays, central 3-fan module (3 round fans with guards, 2 yellow + 1 yellow LEDs), 11 more bays, right ear. Bays black #0B0B0B, fan module grey #555A5F, ears light grey #9A9A9A, LEDs #E6D800.
- Rear: two identical BF3 canisters (pink/salmon handle colour #E8A8A0, green PCB accents) centred-left/right, each with 2 QSFP112 (Port 1/2), USB-C, 2 RJ45 (LAN1/LAN2), lock bolt; PSUs at outer left and right ends with C19-type inlets; power LED lower left.
- Bezel: no bezel shown (diagram); VAST brand colour blue (~#1F67FF, estimate) only on logo.

## 8. Not found
- NVIDIA per-vendor H200 certification letters/dates; NVIDIA IOPS guidance; 2-SU row in RA.
- DDN AI400X3 official DGX SuperPOD H200 appliance count; DDN datasheet PDF (web-form gate; Cloudflare blocks curl); rear/front-straight photos; AI400X3 power beyond 2400 W and confirmed 140/110 from datasheet.
- VAST minimum cluster; CBox dimensions/photo; DBox write GB/s; vector logo.
- NetApp AFF A90, Pure FlashBlade//S500, Dell F710 per-node GB/s and power for SuperPOD certs; Project Lightning; WEKA 1U power/weight; IBM SSS6000 network ports.
- Images for WEKA/IBM/Dell/NetApp/Pure were not collected (scope: DDN and VAST).
