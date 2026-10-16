# DGX H200 system — reference pack (retrieved 2026-09-30)

Sources: NVIDIA DGX H100/H200 User Guide (UG, https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html), NVIDIA DGX H200 datasheet (DS, mirror https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf), NVIDIA H200 page (https://www.nvidia.com/en-us/data-center/h200/). The UG covers H100 and H200 together; the H200 shares the chassis and figures.

## Facts

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Form factor | 8U rackmount | U | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | "Form Factor 8U Rackmount" |
| Height | 356 (14.0) | mm (in) | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | UG and DS agree |
| Width | 482.3 (UG) / 482.2 (DS) max | mm | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | "19” (482.3 mm) max"; includes rack ears |
| Depth | 897.1 (35.3) max | mm | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| System weight | 130.45 (287.6 lb) max | kg | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | DS same |
| Packaged weight | 170.45 (376 lb) | kg | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | |
| Max system power | 10.2 | kW | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | "10.2kW max*" standard config; CTS variant up to 14.3 kW (DS footnote) |
| PSUs | 6 x 3.3 kW hot-swap | count x W | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | "6 x 3.3 kW"; 3300 W @ 200-240 V, 16 A, 50-60 Hz each |
| PSU redundancy | 4+2 (UG wording; not literally "N+N") | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | Boots only if >=3 PSUs operational; <3 = BMC only |
| Inlet / cords | IEC C19/C20 locking cords, 250 VAC 20 A, 1200 mm, 6 supplied | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | Twist-lock on PSU side |
| Airflow | 1105 CFM front-to-back @ 80% fan PWM | CFM | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| Heat output | 38,557 | BTU/hr | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| Fans | 12 front fan modules (4x3 grid) | count | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html (figure labels) | Figure: "12 x Fan Modules" |
| Operating temp | 5-30 (41-86 F) | C | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| Humidity | 20-80 non-condensing | % RH | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| Noise | NOT FOUND | dBA | - | |
| GPU | 8 x H200 SXM, 141 GB HBM3e each; 1,128 GB total | GB | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | |
| GPU memory bandwidth | 4.8 | TB/s per GPU | https://www.nvidia.com/en-us/data-center/h200/ | |
| GPU max TDP | up to 700 (configurable) | W | https://www.nvidia.com/en-us/data-center/h200/ | |
| GPU TFLOPS (per GPU) | FP64 34; FP64 TC 67; FP32 67 | TFLOPS | https://www.nvidia.com/en-us/data-center/h200/ | |
| GPU TFLOPS sparse (per GPU) | TF32 989; BF16 1,979; FP16 1,979; FP8 3,958; INT8 3,958 | TFLOPS | https://www.nvidia.com/en-us/data-center/h200/ | NVIDIA footnote: tensor values are "with sparsity" |
| GPU TFLOPS dense (per GPU) | TF32 494.5; BF16/FP16 989.5; FP8 1,979 | TFLOPS | derived | DERIVED = sparse/2 (standard 2:4 sparsity ratio); not printed in fetched page |
| NVLink per GPU | 900 | GB/s | https://www.nvidia.com/en-us/data-center/h200/ | |
| NVSwitch | 4 x (UG: "4 x 4th generation NVLinks that provide 900 GB/s GPU-to-GPU") | count | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | DS: "NVIDIA NVSwitch 4x" |
| System NVLink aggregate | NOT FOUND (8 x 900 = 7.2 TB/s is arithmetic, not a NVIDIA quote) | TB/s | - | |
| System AI perf | 32 | PFLOPS FP8 (sparse) | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | "32 petaFLOPS FP8" |
| CPU | 2 x Intel Xeon Platinum 8480C, 56 cores each (112), 2.0 base / 2.9 all-core / 3.8 max GHz | GHz | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | PCIe Gen5 |
| CPU TDP | NOT FOUND in NVIDIA docs (Intel spec for 8480+ is 350 W, not verified for 8480C) | W | - | |
| System memory | 2 TB, 32 x 64 GB DIMMs | TB | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | MB tray figure: "32 x 64GB DIMMs" |
| OS storage | 2 x 1.92 TB NVMe M.2, RAID 1 | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| Data cache | 8 x 3.84 TB NVMe U.2 SED, RAID 0 | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | Front bays |
| Cluster NICs | 8 x ConnectX-7 single-port, via 4 x twin-port OSFP cages, up to 400 Gb/s IB/Eth | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | Two "network modules", 4 CX7 each, DensiLink cables to OSFP |
| Storage / in-band NICs | 2 x dual-port ConnectX-7 (QSFP112) in slots 1,2; plus dual-port 100GbE NIC in slot 3; 10GbE RJ45 onboard | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html, https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | UG table: Slot1/2 CX7 (mlx5), Slot3 irdma (100GbE) |
| BMC | 1 GbE RJ45; Redfish/IPMI/SNMP/KVM/web | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| BlueField | NOT PRESENT in H100/H200 spec (no DPU listed) | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | |
| OSFP port map | OSFP1P1..OSFP4P2 -> mlx5_11, 6, 10, 9, 4, 3, 5, 0 | - | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | See UG Table 5/6 (GPU pairing) |
| Rack use in SuperPOD | 2 DGX H200 per rack; SU = 32 systems | - | RA-11336-001 (media/) | |

## Blender modelling notes

All positions are estimates measured from the NVIDIA figures in media/ (displayed-pixel fractions), as fraction of unit body: x from left edge as seen from that side, y from top. Treat as +/-0.02.

**Envelope:** 482.3 W x 356 H x 897.1 D mm (8U = 355.6 mm). Front-to-back airflow. Rack ears flush front, 3 screws per side (6 total): x 0.02 and 0.98, y 0.10, 0.48, 0.90 (of height).

**Front, bezel ON** (front-with-bezel.png; texture: nvidia-dgx-bezel-metal-foam-texture.jpg): full-face metal-foam / reticulated-foam-look panel spanning x 0.06-0.95, y 0.03-0.97, slightly recessed between the ears. NVIDIA logo plate = rounded-rectangle pad, x 0.075-0.22, y 0.03-0.97 (tall, logo rotated 90 deg reading bottom-to-top). Power button/LED, UID button/LED, fault LED (triangle icon) are on the right ear, x ~0.98, y ~0.21, 0.27, 0.325.

**Front, bezel OFF** (front-bezel-removed.png): black chassis; 4 x 3 grid of 12 fan modules covering x 0.077-0.928, y 0.03-0.87; each module is black with hex-mesh guard, a champagne/tan pull handle in its centre, a tiny red LED top-right. Bottom strip y 0.88-0.975: 8 U.2 NVMe drive bays as 4 stacked pairs (x 0.07-0.23, 0.24-0.40 left; 0.60-0.76, 0.77-0.93 right), black slotted carriers; centre console board x 0.41-0.60 with 2 x USB-A (3.1), 1 x VGA (DE-15) and ambient-temp sensor.

**Rear** (rear-panel-modules.png; body in that figure is ~1154x911 px, aspect 1.27, so the rear figure omits/foreshortens the ears - scale to 482 W anyway):
- GPU tray: top, y 0.00-0.595, full width; silver/white aluminium hex-perforated exhaust grille, two thumbscrews (yellow-green) at x 0.47-0.52, y 0.53.
- Motherboard tray: y 0.60-0.86. Left third (x 0.02-0.31): 2 stacked dual-port QSFP112/100GbE cards + perforated filler; centre (x 0.37-0.61): 4 twin-port OSFP cages in one row (OSFP1..4, each 2 ports side by side, labelled P1/P2) at y ~0.71 from top of body; right third (x 0.62-0.90): dual-port card (slot 2) + perforated filler; bottom strip y ~0.80-0.85: 2 x USB-A + VGA (x 0.12-0.28), BMC RJ45 (x 0.38), in-band LAN RJ45 (x 0.43), UID button (x 0.47), PWR LED (x 0.52), BMC reset, 7-seg code display (x 0.55-0.63), COM DB9 (x 0.79). Two yellow-green thumbscrews at x 0.47-0.52. Note: UG slot 1/3 and 2/4 are riser positions; fig shows 3 populated cards.
- PSUs: bottom row y 0.875-0.995, 6 equal modules across x 0.015-0.985 (each ~0.16 wide), black C20 inlet (centre), perforated silver body, yellow-green release tab on right edge, black pull handle at bottom. Pull-out serial-number tab at bottom-left.

**Colours (visual estimates from figures, NOT NVIDIA specs):** ears and bezel frame champagne/tan #B5A58A; bezel foam face #6B5636 with #CDBFA5 highlights (photo reads dark olive-bronze #3B382C); chassis/fan frame black #1C1C1E; fan handles #B8A888; rear grille and PSU body light silver #D4D6D8; release tabs / thumbscrews yellow-green #B5D335 (NVIDIA-green accent #76B900 for arrows only in figure, not hardware); PSU inlet black #111.

**LEDs (UG):** power: green 1 Hz blink = standby (BMC up), 4 Hz blink = POST, solid = on. UID: blue, on or blink via BMC. Fault: amber solid = fault. BMC RJ45: left LED solid green = 100M, amber = 1G; right green blinks for activity. Fan module LEDs: small red dot (state meaning NOT FOUND).

## Not found
- Acoustic noise level.
- Official angled/3/4-view and internal product photos at usable URLs (nvidia.com pages are JS-rendered; only bezel texture OG image retrieved). Use the UG renders + topology diagrams.
- Official datasheet PDF direct from NVIDIA (resources.nvidia.com returned HTML); the MEGWARE-hosted copy is the NVIDIA-authored PDF.
- CPU TDP and system NVLink aggregate quote; fan CFM per module.
- Free 3D model: only Sketchfab "NVIDIA DGX H100" by rs4868782 (https://sketchfab.com/3d-models/nvidia-dgx-h100-16fff7cf8d9848e18edf4484acf395b7) — 12 triangles (a plain box), no license stated, not downloaded. No NVIDIA SimReady/USD or GrabCAD DGX H100/H200 found.
- User-guide PDF: not attempted; HTML guide is the source (figures saved).
