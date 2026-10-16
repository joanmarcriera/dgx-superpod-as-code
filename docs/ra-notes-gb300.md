# RA notes — DGX SuperPOD with DGX GB300 (NVL72), one SU

Source **RA-GB300**: *NVIDIA DGX SuperPOD: Next Generation Scalable Infrastructure for AI
Factories — Reference Architecture Featuring NVIDIA DGX GB300 Systems*,
https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf (retrieved 2026-09-30; the HTML pages under
`.../scalable-infrastructure-gb300/latest/` return 404). Quotes verified against the PDF text.
Tags: **RA** stated · **DERIVED** computed from RA values · **CHOICE** modelling decision the RA
leaves open. Spec: `spec/gb300-su.yaml`; builder: `src/dgxnb/topology_gb300.py`.

## Stated by the RA

| # | Fact | Value | RA section | Quote |
|---|---|---|---|---|
| G.1 | Racks per SU | 8 NVL72 | Abstract, Table 1 | "each SU contains 8 DGX GB300 systems" |
| G.2 | Trays per rack | 18 | Compute Tray | "18 compute nodes (aka. compute trays)" |
| G.3 | GPUs | 4 per tray (2 Superchips × 2 B300), 72/rack, **576/SU** | Compute Tray; Fig. 8 title | "Compute fabric for full 576 GPUs" |
| G.4 | NVLink switch trays | 9 per rack, 2 chips each | NVLink Switch Tray | "nine NVLink switches (aka. NVLink switch tray)" |
| G.5 | Power shelves | 8 per rack, 6 × 5.5 kW, 33 kW | DGX Power Shelves | "six 5.5kW PSUs configured as N redundant and can deliver up to 33kW" |
| G.6 | SU power | 1.2 MW TDP | DGX SuperPOD Architecture | "Each SU requires a Thermal Design Power (TDP) of 1.2 Megawatts" |
| G.7 | Compute NICs | 4 × ConnectX-8, XDR 800G, one per rail | Table 1; Compute Tray | "four Quantum X-800 connections per system" |
| G.8 | IB switch | Q3400-RD, 144 ports | Compute Fabric, Fig. 10 | "enhanced port radix if 144 port for Q3400-RD" |
| G.9 | IB leaves | 8 per SU, 4 rails × 2 | Compute Fabric | "eight leaf switches distributed in 4 rails, with each rail having 2 leaf switches" |
| G.10 | Rack → leaf | 18 × XDR per rack per rail leaf; racks 1–4 → CL01, 5–8 → CL02 | Fig. 8 legend + drawing | "18x XDR 800Gbps" |
| G.11 | IB spines (multi-SU) | 2 SU → 8, 4 → 18, 8 → 36, 16 → 72 | Table 3 | — |
| G.12 | UFM | C-UFM-1/2, links to rail leaves | Fig. 8 | "1x XDR" / "Fabric Management" |
| G.13 | Ethernet | SN5600(D): 4 compute leaves per SU on BF3 at 400G; storage leaves "starting at 2"; 2 mgmt leaves; 2 OOB spines | Ethernet Fabric | "Each SU contains four leaf SN5600 switches … BlueField BF3240 dual-port card at a 400Gbps" |
| G.14 | Uplinks | compute leaf 24 × 400G; storage "72 non-blocking"; mgmt 24 × 400G | Ethernet Fabric | "each compute leaf connects via 24 links at 400 Gbps, supporting a 1:3 blocking ratio" |
| G.15 | Tray Ethernet | BF3: 400G storage + ≥ 200G in-band, not bonded | Storage and In-band Network | "dedicates a 400Gbps port to the storage network segment and a dedicated link that provides at least 200Gbps to the inband" |
| G.16 | OOB | SN2201 + OOB spines; BMC, BF BMC, COMe, PDUs, switches | Out-of-Band Management | "connects the management ports of all devices including DGX GB300 compute trays, switch trays…" |
| G.17 | Tray front panel | 4 XDR OSFP, 2 BF QSFP, BF BMC, BMC, LOM (RJ45) | Fig. 3 | — |
| G.18 | NVLink tray mgmt | 2 COMe RJ45 + 1 BMC RJ45 | NVLink Switch Tray | "two COMe RJ45 ports for NVOS and one BMC module" |

## Derived

| # | Value | Rule |
|---|---|---|
| D.1 | **4 IB spines** for a standalone SU | 8 leaves × 72 up = 576 = 4 × 144 (the same rule reproduces Table 3's 2-SU row: 1,152 / 144 = 8) |
| D.2 | 1,152 compute-IB links | 576 tray→leaf + 574 leaf→spine + 2 UFM (see C.2) |
| D.3 | 1,296 NVLink links | 8 racks × 18 trays × 9 switch trays (one NetBox link per tray pair; physically 8 lanes each) |
| D.4 | Rack budget **150 kW** | 1.2 MW / 8 racks |

## Choices (not in RA-GB300)

| # | Choice | Why |
|---|---|---|
| C.1 | Rack elevation: shelves U2–5 & U33–36, trays U23–32 & U6–13, NVLink trays U14–22, 2 × SN2201 at U38–39 | Fig. 1–2 are renderings; common NVL72 pattern |
| C.2 | Each UFM takes the last uplink port of a rail-4 leaf → those 2 leaves run 72:71 | Fig. 8 draws UFM→leaf links but a Q3400-RD leaf is exactly 72 + 72; validate allows ≤ 1.02 |
| C.3 | 2 Ethernet spines | Table 4 starts at 2 SU (4 spines) |
| C.4 | Power: tray 7.0 kW, NVLink tray 1.0 kW (→ 135.3 kW/rack); Q3400-RD 3.6 kW; SN5600 1.5 kW | RA gives only SU TDP |
| C.5 | One 415 V/63 A 3φ feed per 33 kW shelf; busbar draw carried on the trays' DC-IN ports | NetBox cannot cable a busbar one-to-many |
| C.6 | 5 management servers (R750), 4 generic RoCE storage appliances (4 × 400G) | Fig. 14 shows BCM ×2 + control plane, no counts; storage is vendor-specific |
| C.7 | BF3 p1 → odd compute leaf (storage), p2 → even leaf (in-band); SN5600 2 × 400G breakout lanes `swpNs0/1` | "at a 400Gbps for best performance and redundancy" |
| C.8 | OOB spines = SN4600C, rolled up to the Ethernet spines | RA: OOB "rolled up into the aggregation layer … as a dedicated VXLAN"; model unnamed |

## Inconsistencies in RA-GB300

"NVL32 topology" in the Compute Tray text (system is NVL72); Table 1 "Q3400" vs text "Q3400-RD";
"SN5600" vs "SN5600D"; Fig. 12 labels SPINE-26 vs "up to 24 spine switches"; repeated figure
numbers (two Fig. 10/16/17).
