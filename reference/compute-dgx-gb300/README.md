# DGX GB300 NVL72 rack + Q3400-RD / SN5600(D) — reference pack (retrieved 2026-09-30)

Sources (short names used below):
- **RA** = NVIDIA DGX SuperPOD GB300 Reference Architecture, https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf (`media/nvidia-dgx-spod-gb300-ra.pdf`; page numbers are PDF pages).
- **DGXUG** = NVIDIA DGX GB Rack Scale Systems User Guide, https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html (GB300 figures = `*-gb300.png`).
- **HC25** = John Norton (NVIDIA), *Case Study: NVIDIA GB200/300*, Hot Chips 2025, https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S5.Norton.pdf.
- **BLOG** = NVIDIA, "NVIDIA Contributes NVIDIA GB200 NVL72 Designs to Open Compute Project", https://developer.nvidia.com/blog/nvidia-contributes-nvidia-gb200-nvl72-designs-to-open-compute-project
- **LP** = Lenovo Press LP2357 product guide, https://lenovopress.lenovo.com/lp2357.pdf; **LUG** = Lenovo GB300 NVL72 User Guide, https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf. Lenovo ships the same NVIDIA MGX rack and tray family (machine types 7DJV/7DLZ/7DJY); NVIDIA publishes **no mm dimensions for the DGX-branded trays**, so tray/shelf sizes below are the Lenovo ones (the trays are the same MGX form factor; the DGX bezel/colour differs).
- **CHEVAL** = Cheval Group "Open Rack V3 NVIDIA MGX Rack (for GB200 NVL72)", https://chevalstore.com/nvidia_mgx_rack/ (also listed at https://www.opencompute.org/products/525/cheval-group-open-rack-v3-nvidia-mgx-rack-for-gb200-nvl72 — that page returned 403 to curl/WebFetch; its text was seen only via a search summary, the Cheval store page is the fetched copy).
- **QXDR** = NVIDIA Q32xx/Q34xx XDR InfiniBand Switch Systems User Manual, https://networking-docs.nvidia.com/xdrswitcheshw/Specifications ; **SN5K** = NVIDIA Spectrum-4 SN5000 2U Hardware User Manual, https://networking-docs.nvidia.com/sn5000hw/specifications.
- Facility numbers already in `reference/facility/README.md` §2 and §6 are reused, not contradicted (see the 2294 vs 2236 mm note).

## Facts

### Rack (NVL72, MGX)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Width | 600 | mm | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG p.6 "Width: 600 mm"; HC25 slide "GB200/300 Rack Overview" labels 600mm; CHEVAL "600 mm wide" |
| Depth | 1068 without extension; 1200 with 132 mm bolt-on rear extension frame | mm | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG "Depth: 1,068 mm (Expands to 1,200 mm with extension frame)"; HC25 labels 1068mm and 132mm; CHEVAL "Bolt on 132 mm deep Extension frame extends overall depth to 1,200 mm" |
| Extension frame size | 132 deep; labels "597mm" and "2234mm" on the frame drawing | mm | https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S5.Norton.pdf | HC25 slide "GB200/300 Rack Overview", "Extension Frame": 597 and 2234 printed next to the frame (read as width x height; not spelled out). Purpose (BLOG): "rear rack extensions to safeguard cable bracings and manifold fittings" |
| Height | 2236 (LUG, HC25, CHEVAL) vs 2294 (LP) | mm | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf ; https://lenovopress.lenovo.com/lp2357.pdf | **Conflict between two Lenovo docs.** LUG p.6 "Height: 2,236 mm"; LP p.36 "Height: 2,294 mm (90.3 inches)" (the figure in facility/README.md §2). NVIDIA's own slide says 2236. Use 2236; 2294 may include something (feet, top) — not explained |
| Rack height in units | "48U" (LP, LUG) / "48RU" (HC25) / "ORV3 44 0U Rack" (CHEVAL) | U | https://hc2025.hotchips.org/assets/program/tutorials/HC2025.T1DCRacks.S5.Norton.pdf | HC25 slide "Compute and Cable Density": "48RU vs 44OU units yields more node density". Mounting is 19" RU pitch (44.45 mm), 48 RU; the 44 OU figure is the plain ORV3 rack it is derived from. NOTE the NVIDIA front renders show only ~43-44 RU of interior (see Blender notes) |
| Rack type | OCP ORV3-derived frame (600 mm wide, deeper busbar), but trays mount on **19" EIA** full-length rails, not 21" OU | - | https://developer.nvidia.com/blog/nvidia-contributes-nvidia-gb200-nvl72-designs-to-open-compute-project | BLOG: "Adaptations to support 19” EIA gear in a 1 RU form factor within the rack"; HC25: "Deployable in enterprise EIA 19” ecosystems", "19” Systems can fit into EIA and OCP infrastructure"; STH: "NVIDIA took an OCP ORv3 Rack and enhanced it for its NVL72 designs" (https://www.servethehome.com/this-is-the-nvidia-mgx-44ru-manifold-for-liquid-cooling/); CHEVAL: "Full length EIA 19″ Mounting Rails / 21″ 0U Mounting". LUG/LP: "integrates seamlessly into a standard 19" rack cabinet"; LP Table 21 lists "Rack adapters: Adapters to mount 19” IT gear in ORV3 rack" |
| Tray flange width | 483 (EIA flange outer) / chassis body 438 | mm | https://lenovopress.lenovo.com/lp2357.pdf | LP Table 26 "Xa = 483 mm width to the outsides of the front EIA flanges"; chassis 438 mm (LP p.36). The rest of Table 26 (Xb 448, Xc 540, Ya 572, Za 1062, Zb 1076, Zc 1114, Zd/Ze 226) refers to an "Enclosure dimensions" drawing I could not tie to tray or rack (Ya 572 mm fits neither) — NOT used |
| Weight, rack structure | 185 | kg | https://lenovopress.lenovo.com/lp2357.pdf | LP p.36 "Weight: 185 kg (407.8 lbs)" (the "48U MGX Rack") |
| Weight, full solution | ~1580 ("depending on the configuration") | kg | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG p.6 "Approximately 1,580 kg (3,483.3 lbs)". Dry vs wet NOT stated |
| Rack load rating | 1600 | kg | https://chevalstore.com/nvidia_mgx_rack/ | CHEVAL "1,600 KG Load rated" (bare rack) |
| Structural | >100 lb steel reinforcement; 6000 lb mating force | - | https://developer.nvidia.com/blog/nvidia-contributes-nvidia-gb200-nvl72-designs-to-open-compute-project | BLOG: "over 100 lbs of steel reinforcements ... withstand the 6,000 lbs of mating force" |
| Doors / panels | Side panels + "Door and Side Panels available"; DGX renders show black solid side panels, **no front or rear door**, a black rear "bezel" (cable-management fingers) and a wedge-shaped "Seismic bracing" plinth | - | https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html | CHEVAL "Door and Side Panels available"; DGXUG rear figure labels "Rear Bezel", "Power Cable management", "Seismic bracing" |
| Rear-door HX | NOT FOUND | - | - | No source fetched mentions an RDHx on NVL72; LP: ~90 % liquid / ~10 % air with the remainder handled by room air conditioning |
| Rack power | 135 TDP, up to 155 peak (Lenovo); ~120 kW (DGXUG); 120-130 kW cooling capacity (BLOG/figure) | kW | https://lenovopress.lenovo.com/lp2357.pdf | LP "Each rack consumes 135 kW TDP; up to 155 kW peak"; DGXUG "approximately 120kW"; sources disagree — cite RA G.6 for the SU figure |
| Busbar | one, 1400 A, vertical, centre of the rear; same width as ORV3 but deeper | A | https://lenovopress.lenovo.com/lp2357.pdf | LP Table 1 "Supports single 1400A bus bar in the middle rear"; BLOG "maintains the same width as the existing ORV3 but features a deeper profile ... 1,400 amp"; 50 V DC (LP: "50V power shelves delivering power to the bus bar ... MGX v1.1"). Busbar width/depth in mm NOT FOUND |
| Cable cartridges | 4, vertical, rear centre either side of the busbar; >5000 coax copper cables | count | https://developer.nvidia.com/blog/nvidia-contributes-nvidia-gb200-nvl72-designs-to-open-compute-project | BLOG "four NVLink cartridges mounted vertically at the rear of the rack ... over 5,000 active copper cables"; HC25 photo: two cable bundles either side of the dark busbar strip |
| Manifolds | 2 vertical (rear-left and rear-right), blind-mate; top-feed (CA40) or bottom-feed (C5RN) variants | count | https://lenovopress.lenovo.com/lp2357.pdf | LP Table 1 "Liquid Cool Manifolds 2 Rear Left and Rear Right (Inlet and Outlet), top and bottom feed manifolds are available"; BLOG "Blind Mate Liquid Cooling Manifold ... Floating Blind Mate Tray connection" |
| Manifold material / QDs | 304L or 316L austenitic stainless steel (spec requirement); QD type UQDB04; bleed valve UQD04 on top; hose adaption by tri-clamp; to CDU "1” FD83 BSPP"; 30 psi static at QD | - | https://lenovopress.lenovo.com/lp2357.pdf | LP Table 18 "Manifold shall be made from 304L or 316L austenitic stainless steel"; "QD Type UQDB04"; "Manifold shall use tri-clamp connectors"; "QD Type to CDU 1” FD83 BSPP"; DGXUG rear figure: "FD83 connectors for liquid cooling hoses". Manifold pipe diameter NOT FOUND |
| Coolant flow | 59 LPM @25 C, 71 @30, 89 @35, 119 @40, 177 @45 C supply (rack) | LPM | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG "Water requirements" table (pressure drop 2.3-18.4 psi) |
| Elevation (front, top to bottom) | 2 x TOR mgmt switch; 4 x power shelf; 10 x compute; 9 x NVLink switch; 8 x compute; 4 x power shelf; blank filler ("Seismic bracing" label in the render) | RU counts | https://docs.nvidia.com/dgx/dgxgb200-user-guide/_images/hardware-rack-configuration-gb300.png | DGXUG figure legend "2 x Management top of rack Ethernet switches / 4 x Power shelves / 10 x Compute Nodes / 9 x NVLink switches / 8 x Compute Nodes / 4 x Power shelves"; RA Fig 2 (p.8) same; HC25 "Rack Layout" same list; LP Fig 2 adds "3x or 4x" shelves (6- or 8-shelf models). LUG Fig 11 adds a **leakage drip pan** between the lowest compute tray and the lower power shelves |
| Absolute U numbers | NOT FOUND | - | - | No source prints U numbers. `docs/ra-notes-gb300.md` C.1 (shelves U2-5 / U33-36, compute U6-13 / U23-32, NVLink U14-22, SN2201 U38-39) is consistent with the top-down order above |

### Compute tray (DGX GB300 / MGX 1RU)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Size | 438 W x 43.6 H x 766 D (799 D including the rear water connections) | mm | https://lenovopress.lenovo.com/lp2357.pdf | LP p.36 "Depth: 766 mm (799 mm, including the water connections at the rear of the server)"; 1U; Lenovo 7DLZ. NVIDIA DGX-branded dimensions NOT FOUND |
| Weight | 29 | kg | https://lenovopress.lenovo.com/lp2357.pdf | "Weight: 29 kg (63.93 lbs)" |
| Front I/O | 4 x XDR OSFP (800G, ConnectX-8), 2 x QSFP (BlueField-3, 2 x 400G), BF BMC RJ45, in-band/LOM RJ45, tray BMC RJ45, USB, DisplayPort, 4 x E1.S populated of 8 bays, LEDs | - | https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf | RA Fig 3 (p.9) labels "Compute XDR OSFP" (x2 left, x2 right), "LOM NIC", "E.1 Storage", "BMC", "Bluefield BMC", "Bluefield QSFP". DGXUG Fig labels the LOM as "In-band 10GbE Ethernet" and the IO board "BMC management, USB, DisplayPort, and console"; LP: "Up to 8x E1.S", "1x 1G RJ45" |
| Drives | 8 E1.S cage positions in front; 4 x 3.84 TB populated in DGX + 1 x 1.92 TB M.2 (internal) | - | https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf | RA "4x 3.84TB E1.S NVMe as RAID0 ... 1x 1.92TB M.2" |
| Rear | 4 blind-mate NVLink connector blocks (2 + 2), centre DC busbar clip, coolant outlet QD far left, inlet QD far right (as seen from the rear) | - | https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf | RA Fig 4 (p.9) labels "Hot water outlet | DC power connectors | Cold water inlet | NVLink connectors"; LP Fig 4 "QD out Water outlet / Busbar Clip / QD in Water inlet" |
| Coolant connection | 2 QDs per tray (one supply, one return), floating blind-mate, cold plates on CPUs/GPUs/CX-8 | - | https://developer.nvidia.com/blog/nvidia-contributes-nvidia-gb200-nvl72-designs-to-open-compute-project | BLOG "Floating Blind Mate Tray connection"; LP "rear manifold, quick disconnects, and cold plates for the CPUs, GPUs, ConnectX-8 network adapters, and all NVSwitch components". Tray-side QD model NOT FOUND (manifold side is UQDB04 per LP) |
| Fans | 8 x 40 x 56 mm dual-rotor, inside the tray | - | https://lenovopress.lenovo.com/lp2357.pdf | Table 2 "Eight 1U Dual Rotor 40x56 Fans"; air path is front-to-back through the tray |
| Power in | 50 V DC (47.5-51.5 V) from the busbar | V | https://lenovopress.lenovo.com/lp2357.pdf | Table 2 |
| Handles | Champagne/bronze bent-loop handle at each end of the faceplate | - | https://docs.nvidia.com/dgx/dgxgb200-user-guide/_images/hardware-compute-tray-gb300.png | NVIDIA render; Lenovo trays have black handles (`lenovo` LP Fig 3) |

### NVLink switch tray

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Size / weight | 438 W x 43.6 H x 770 D; 17 kg | mm, kg | https://lenovopress.lenovo.com/lp2357.pdf | LP p.36 "Depth: 770 mm", "Weight: 17 kg" (excludes EIA flanges, bezel, handles); Lenovo 7DJY |
| Count | 9 per rack, 2 NVLink switch chips each | - | https://docs.nvidia.com/dgx/dgxgb200-user-guide/hardware.html | DGXUG "Each switch tray has 2x NVLink switches"; LP "14.4 TB/s" per tray |
| Front | power/reset/ID buttons+LEDs, status LED, 4 NVLink-health LEDs, USB-A, then RJ45 x5: console serial, BMC, ComE x2, leak-detection; large blank panel; pull tab at far right | - | https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf | RA Fig 6 (p.11) labels "Power Button, Reset, ID, Status LEDs, NVLink health, USB Storage, ConsoleSerial, BMC, ComE, Leak Detection, Pull tab"; LP Fig 7 "RS232 RJ45, Local BMC Eth, CPU Eth1, CPU Eth0, Link Group RJ45". **No OSFP/front NVLink ports** (LP "no OSPF front connections"; RA: all NVLink via rear blind-mate) |
| Rear | same pattern as the compute tray: coolant return (left), 2 + 2 cartridge connector blocks, busbar clip centre, coolant supply (right) | - | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG Fig 8 "NVLink switch tray rear view" (items: Coolant return, Cable cartridge connectors, Coolant supply, Busbar connector) |
| Position | middle block, 9 consecutive RU between a 10-tray compute block (above) and an 8-tray compute block (below) | - | https://docs.nvidia.com/dgx/dgxgb200-user-guide/_images/hardware-rack-configuration-gb300.png | see Elevation row. This is NOT the "9 / 9 / 9" split some GB200 material shows |

### Power shelf

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Size | 448 W x 43.6 H x 718.5 D | mm | https://lenovopress.lenovo.com/lp2357.pdf | LP p.36, same figure as facility/README.md §6. Weight NOT FOUND |
| Count / position | DGX: 8 per rack, 4 at the top (below the TOR switches) and 4 at the bottom; Lenovo: 6 or 8 (3-4 each end) | count | https://docs.nvidia.com/pdf/dgx-spod-gb300-ra.pdf | RA "eight total power shelves in a single DGX GB300 NVL72 rack system"; render legend "4 x Power shelves" top and bottom |
| Capacity | 6 x 5.5 kW hot-swap PSUs = 33 kW, 50 V DC out (up to 660 A); PSUs described as air-cooled | - | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG "Output current: Up to 660 A"; DGXUG "six air-cooled 5.5kW PSUs in eight power shelves" (LP also says "water-cooled power conversion stations" once — conflicting; DGX doc says air-cooled) |
| AC in | LUG: 3-phase Delta 180-305 VAC or Wye 311-528 VAC, 60 A; LP: 200-277 VAC, 1 x 60 A IEC 60309 7-pin whip per shelf | - | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | two Lenovo docs word the input differently; reuse facility/README.md §6 |
| Front | power-management board (PMC) at far left with one RJ45 (BMC port, PoE-capable per LUG) + reset pin + status LED; 6 PSU modules each with round fan behind square-hole mesh, two green LEDs (power, health) top-left of each, black pull handle between modules | - | https://docs.nvidia.com/dgx/dgxgb200-user-guide/_images/hardware-power-shelf.png | LUG Fig 9 items: "PMC module, Power supply units, PSU power status LED, PSU health status LED, PMC module reset button, PMC module status LED" |
| Rear | 7-pin AC whip connector (left third), 50 V busbar connector (centre), 2 x RJ45 (far right, daisy-chain for current sharing) | - | https://pubs.lenovo.com/gb300-nvl72/gb300-nvl72_user_guide.pdf | LUG Fig 10 / Table 10: "Power whip connector, Busbar connector, RJ-45 ports ... daisy-chaining of multiple power shelves to enable current sharing" |

### TOR management switch (in the NVL72 rack)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| SN2201 | 2 per rack at the top; 438 x 43.6 x 781 (LP prints "(28.3 inches)" which is 719 mm — the two values disagree); 11.39 kg | mm | https://lenovopress.lenovo.com/lp2357.pdf | LP p.36; in DGX renders the two are wrapped in a champagne shroud (RA Fig 2) |

### Q3400-RD (Quantum-X800, 144 x 800G)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Naming | RA calls it "Q3400-RD". NVIDIA's hardware manual lists **Q3400-RA** (air, AC) and **Q3401-RD** (DC/busbar). RA Fig 10 (p.21) caption says Q3400-RD but its faceplate reads "Q3400-RA". Treating Q3400-RD = Q3401-RD is an inference | - | https://networking-docs.nvidia.com/xdrswitcheshw/introduction | "The Q3400-RA is an air-cooled system designed for standard 19-inch rack cabinets, while the Q3401-RD offers the same air-cooled design with support for rack cabinets utilizing DC power" |
| Height | 4U | U | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | |
| Q3401-RD size / weight | 175 H x 438 W x 852 D; 57.20 kg | mm, kg | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | "4U, 6.89" (H) x 17.24" (W) x 33.54" (D) 175 mm (H) x 438 mm (W) x 852 mm (D)", "19” MGX rack mount" |
| Q3400-RA size / weight | 177.8 H x 438 W x 850 D; 60 kg with 8 PSUs | mm, kg | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | |
| Power | RD: 48-54 V DC, max 6327 W with active cables (typical NOT FOUND); RA: 2,900 W typical (passive), 7,000 W max | W | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | |
| Ports | 72 OSFP cages (twin-port) = 144 x 800G XDR, plus one separate FNM (UFM) OSFP | - | https://networking-docs.nvidia.com/xdrswitcheshw/introduction | "144 ports at 800Gb/s distributed across 72 octal small form-factor pluggable (OSFP) cages" |
| Airflow | spec lists "Operational: Reverse air flow"; direction beyond that NOT FOUND | - | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | -RA/-RD: likely "reverse airflow" (inference from the name) |
| Noise | 78.4 | dBA | https://networking-docs.nvidia.com/xdrswitcheshw/Specifications | |
| Rear | RD: 8 replaceable fans (2 x 4), no PSUs, one busbar connector in the centre block; RA: 8 PSUs (4 each end, C14-style inlets) + 10 fans (5 x 2) | - | https://networking-docs.nvidia.com/xdrswitcheshw/introduction | "Replaceable PSU: Q3400-RA Yes, 8; Q3401-RD No, Busbar powered; Replaceable Fan RA 10, RD 8" |

### SN5600 / SN5600D (Spectrum-4, 64 x 800G)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Height | 2U | U | https://networking-docs.nvidia.com/sn5000hw/specifications | 88 mm |
| SN5600 (AC) | 88 H x 438 W x 720 D (745 with fan levers); 23.5 kg; 220-240 VAC; typical 940 W (passive cables, ATIS); 4 fans, 2 PSUs; 0-35 C | mm, kg, W | https://networking-docs.nvidia.com/sn5000hw/specifications | "88mm (H) × 438mm (W) × 720mm (D) / 745mm with fan levers"; "Weight: 23.5 kg" |
| SN5600D (DC, the RA name) | 88 H x 438 W x 781 D (853 with busbar plug); 18.5 kg; 48 VDC (40-60); typical 940 W; 4 fans, no PSU | mm, kg, W | https://networking-docs.nvidia.com/sn5000hw/specifications | "88mm (H) × 438mm (W) × 781mm (D) / 853mm with busbar plug", "19” MGX rack mount", "The SN5600D system is powered by a DC busbar assembly" |
| Ports | 64 x OSFP 800GbE + 1 x SFP28; USB-A, RJ45 MGT, RJ45 console on the front | - | https://networking-docs.nvidia.com/sn5000hw/introduction | |
| Max power, noise, airflow | NOT FOUND in the NVIDIA spec page (only typical power is given) | - | - | a reseller SKU title says "C2P airflow" — not verified |

## Blender modelling notes

All positions are estimates measured by overlaying a 0.025 grid on the figures named (displayed-pixel fractions): x from the left edge as seen from that side, y from the top of the unit. Treat as +/-0.02 (+/-0.03 for the rack-level drawings). "Face" = the whole front including the end handles unless stated.

**Rack envelope:** 600 W x 2236 H x 1068 D mm, plus an optional 132 mm rear extension frame (600 x 1200 D overall with it; model the extension ON for a cabled rack, it carries the cable bracing and the manifold fittings). Mounting rails: EIA 19", RU pitch 44.45 mm, 48 RU. Tray flange plane: set-back from the rack front NOT FOUND numerically; geometric constraint: 1068 - 799 (tray incl. QD) = 269 mm is shared between front set-back and rear clearance. Base: black plinth with wedge "seismic bracing" plates front and rear (DGXUG exploded view `nvidia-dgx-gb300-rack-rear-exploded.png`). Side panels black solid; no doors.

**Front elevation, top to bottom** (`nvidia-dgx-gb300-rack-front-elevation.png`; same in HC25 and RA Fig 2): ~2 RU blank; 2 x SN2201 (1U each, champagne shroud); 4 x 1U power shelf; 10 x 1U compute; 9 x 1U NVLink switch; 8 x 1U compute; leakage drip pan (LUG Fig 11); 4 x 1U power shelf; ~4 RU blank filler panels (four visible rows). Tray count check: 10 + 9 + 8 = 27 RU (= 1200 mm) continuous with no gaps. In the NVIDIA render the 27 RU of trays sit inside ONE champagne-bronze rounded-rectangle bezel shroud (trays visually merge: the NVLink trays show a long blank panel, compute trays show the IO).

**Compute tray front** (`nvidia-dgx-gb300-compute-tray-front.png`; RA Fig 3; 483 W face, 43.6 H). Ears/handles: left x 0-0.075, right x 0.935-1.0, full height, champagne bent loops. Left module (square-hole perforated mesh plate) x 0.075-0.33: XDR OSFP #1 x 0.103-0.150, OSFP #2 x 0.193-0.240 (both y 0.62-0.875 i.e. bottom row), in-band/LOM RJ45 x 0.272-0.308 (y 0.60-0.89). E1.S block x 0.347-0.590: 8 slim vertical carrier slots in 4 pairs (y 0.05-0.92). Front-IO board x 0.600-0.660: BMC RJ45 x 0.602-0.629, y 0.18-0.55, below it a second port (USB-A), LEDs/buttons above at y 0.05-0.15, USB/DisplayPort column x 0.637-0.657, black pull tab at x ~0.66. BlueField module x 0.669-0.93: BF BMC RJ45 x 0.715-0.751 (y 0.10-0.36), 2 x QSFP x 0.785-0.825 and 0.828-0.868 (y 0.13-0.38), then XDR OSFP #3 x 0.700-0.746 and #4 x 0.788-0.834 (y 0.62-0.87), square-hole mesh around. Cages are plain black metal, transceivers not shown in the render.

**Compute tray rear** (`lenovo-gb300-nvl72-product-guide-lp2357.pdf` p.7 Fig 4; LUG Fig 3; body 438 mm = 1.0, no ears): coolant outlet QD x ~0.04 (centre; ~20 mm round knob on a plate x 0.0-0.075, y centre ~0.37); NVLink blind-mate blocks x 0.095-0.234, 0.262-0.408, 0.579-0.727, 0.751-0.900 (y 0.15-0.87; each block ~65 mm wide, black housing, two round guide recesses on top, contact strip below); busbar clip x 0.458-0.524 (~29 mm wide, y 0.05-1.0, protrudes full height); coolant inlet QD x ~0.96 (plate x 0.93-1.0). Seen from the rear: LEFT = outlet (hot), RIGHT = inlet (cold). Silver/white rear plate (light, perforated between connectors).

**NVLink switch tray front** (RA Fig 6; 483 W face, handles x 0-0.058 and 0.94-1.0): top row (y ~0.25) power / reset / ID LEDs at x 0.085, 0.105, 0.127; status + 4 NVLink LEDs x 0.154-0.186; USB-A x 0.278-0.305 (y 0.18-0.33). RJ45 row (y 0.57-0.85): console x 0.081-0.114, BMC x 0.127-0.163, ComE1 x 0.175-0.212, ComE0 x 0.225-0.261, leak-detect x 0.275-0.309. Blank champagne panel x 0.332-0.935; pull tab x ~0.93, y 0.28-0.75. The RJ45s for BMC/ComE have red+green lamps.

**NVLink switch tray rear:** as compute tray rear (LUG Fig 8): outlet QD left, 2 + 2 connector blocks, clip centre, inlet QD right; the top view (`nvidia-dgx-gb300-nvlink-switch-tray-top.png`) shows the hot outlet at the top-left, power connector mid-left, cold inlet bottom-left of the rear edge, silver sheet-metal lid.

**Power shelf front** (`nvidia-dgx-gb-power-shelf-front.png`; face incl. ears = 1.0, y body): black ears x 0-0.06 and 0.95-1.0; PMC board x 0.06-0.10: RJ45 x 0.069-0.092, y 0.29-0.64, red reset pin x 0.085, y 0.79. Six PSU modules, centres at x 0.169, 0.308, 0.448, 0.589, 0.73, 0.876 (each ~0.135 wide, black pull handle on the right edge of each); two green LEDs in the top-left corner of each module (y 0.12-0.45). All black with square-hole mesh and a round fan.

**Power shelf rear** (LUG Fig 10, body = 1.0): 7-pin whip connector x 0.17-0.31 (y 0.3-0.6; 7 round studs in a rectangular housing); busbar clip x 0.46-0.52, full height; 2 stacked RJ45 x 0.86-0.89 at far right.

**Rack rear** (LUG Fig 12 `lenovo-gb300-nvl72-user-guide.pdf` p.30; x of the 600 mm frame, y of the height): busbar = single vertical strip centred at x 0.50, ~0.06 wide (~36 mm estimate), running almost full height (~y 0.06-0.93), dark ridged cover; cable cartridge cage x 0.12-0.88 over the tray block (y 0.24-0.76) with 5 cross-bars and two vertical cartridges each side of the busbar; manifolds are two vertical strips at x ~0.11 (left, return/hot — inferred from the tray QD sides) and ~0.885 (right, supply/cold) from the rear, each a column of QD pairs (one per tray = 18 + 9 pairs, plus the upper/lower power-shelf zone has none); bottom-feed layout has 4 large FD83 hose connectors at y 0.84-0.97 (2 per manifold, stacked; knob centres at x ~0.36 and ~0.64, each with a squarer fitting block reaching outward to x ~0.22 / ~0.78), top-feed moves them to the top (LUG Fig 13 item 2 shows both ends with large hose fittings). HC25 rear photo (`nvidia-hotchips2025-norton-gb200-gb300-case-study.pdf` p.5): white/grey cable bundles drape to each side of the dark busbar; the NVIDIA renders show the rear with black cable-management "bezel" fingers along the outside.

**Q3400-RD front** (`nvidia-q3401-rd-front.png`; RA Fig 10; face = 1.0 of 438 x 175): 3 groups of 4 cage-columns, x 0.145-0.361, 0.396-0.611, 0.646-0.861; 3 tiers of 2 rows each: y 0.087-0.169 / 0.192-0.272, 0.411-0.498 / 0.517-0.603, 0.741-0.820 / 0.843-0.922 (= 3 x 3 x 2 x 4 = 72 twin-port cages; gold pairs of port numbers printed under each tier). Between tiers: dense square-hole vent bands (y 0.28-0.40, 0.61-0.73). FNM OSFP single cage x 0.052-0.107, y 0.85-0.93. USB-A + console RJ45 + 2 mgmt RJ45 bottom-right x 0.89-0.94 / 0.96, y 0.79-0.92; LED cluster x 0.90-0.93, y 0.70-0.73. Left margin x 0-0.145 is a blank plate (RA figure shows NVIDIA logo + "Q3400-RA" at x 0.06-0.12, y 0.76-0.92).

**Q3400-RD rear** (`nvidia-q3401-rd-rear.png`): 8 black fan modules 2 rows x 4 (x 0.013-0.20, 0.21-0.395, 0.61-0.79, 0.805-0.99; rows y 0-0.48, 0.50-0.96), teal LED at each module's bottom-left, centre block x 0.40-0.60 black with one busbar connector at x 0.47-0.53, y 0.16-0.39 (upper half only). `-RA` rear: 4 PSUs each end + 10 fans 5 x 2 with champagne pull tabs (`nvidia-q3400-ra-rear.png`).

**SN5600(D) front** (`nvidia-sn5600d-front.png`; 438 x 88): 4 groups x 4 cell-columns at x 0.05-0.273, 0.28-0.495, 0.503-0.715, 0.7225-0.9375; two cell rows y 0.17-0.52 and 0.59-0.92, each cell holds 2 stacked OSFP cages (split at y ~0.34 / 0.76) = 16 x 2 x 2 = 64 OSFP; SFP28 #65 at x 0.01-0.05, y 0.59-0.70; USB-A x 0.945 (y 0.38-0.47); 2 stacked RJ45 (MGT, console) x 0.96-0.99, y 0.35-0.65; LED/button cluster top-right x 0.94-0.97. **SN5600D rear** (`nvidia-sn5600d-rear.png`): 4 fan modules x 0.022-0.208, 0.218-0.39, 0.59-0.77, 0.78-0.965 and a centre panel x 0.41-0.59 with one busbar plug x 0.46-0.54, y 0.01-0.47. AC SN5600 rear: PSU at each end (black C20-style inlet, green LED) + 4 fans with champagne pull bars (`nvidia-sn5600-rear.png`).

**Colours (visual estimates from figures, NOT NVIDIA specs):** rack frame, side panels, base, rear bezel #1E1E20 (black, satin powder-coat look; HC25/DGX renders; Cheval bare frame photo reads #504C4F under studio light); tray faceplates, ears/handles, TOR shroud champagne-bronze mid-tone #85765C with highlights #B5A58A and shadow #625443 (sampled from RA Fig 3/6; same family as the DGX H200 bezel #B5A58A — NOT black with green accents); Lenovo trays instead use black handles; power shelves black #2E2E2E with green LEDs #8BC34A-ish; Q3400/SN5600 faces black #202121 in the RA figures but light gold #DBBC93 in the newer Q3401-RD/SN5600D doc renders (render lighting differs; the SN5600 end ears are champagne #857A60); switch fan modules black #353433 with champagne pull tabs #D9C9A0; rear plates of trays light silver #D4D6D8; busbar: dark grey-black ridged cover #2A2A2C (no bare copper is visible in any source, so do not model copper); manifolds black in NVIDIA renders (the Lenovo spec says stainless, which a physical build would show as brushed steel #B8BCC0 — pick one, flagged); hose/QD collars inside the tray: red #D32F2F on the hot line, blue #1E63D6 on the cold line (NVLink tray top view), in-tray tubing light grey/white #DCDCDC; LEDs: green (power/PSU/OK), amber (fault/PSU health), blue (UID), red dots on fan modules and RJ45 activity lamps.

**Elements table**

| Element | Dimensions (mm) | Colour (est hex) | Material |
|---|---|---|---|
| NVL72 rack | 600 W x 2236 H x 1068 D (+132 ext.) | #1E1E20 | black powder-coated steel, perforated front/rear posts |
| Compute tray | 438 W (483 flange) x 43.6 x 766 (799 w/ QD) | #85765C faceplate, #D4D6D8 lid/rear | champagne painted/anodised sheet metal, square-hole mesh, silver lid |
| NVLink switch tray | 438 (483) x 43.6 x 770 | #85765C | same as compute; blank front panel |
| Power shelf | 448 x 43.6 x 718.5 | #2E2E2E | black sheet metal, mesh PSU faces |
| SN2201 (TOR) | 438 x 43.6 x 781 | #2B2F33 (RA render: silver faceplate in champagne shroud) | sheet metal |
| Busbar | ~36 W (estimate) x ~2000 H, depth NOT FOUND | #2A2A2C | insulated cover over copper (copper not visible) |
| Manifolds | pipe diameter NOT FOUND; 2 vertical strips ~1900 H | #1E1E20 (render) / #B8BCC0 (stainless spec) | 304L/316L stainless per Lenovo spec |
| QD (tray rear) | ~20 round, tray-side floating blind-mate | #C9CCD0 | machined metal |
| Q3400-RD | 438 W x 175 H x 852 D | #202121 (RA) / #DBBC93 (doc render) | sheet metal, 72 OSFP cages |
| SN5600D | 438 W x 88 H x 781 D (853 w/ plug) | #202121 | sheet metal, 64 OSFP |

## Not found
- NVIDIA-published mm dimensions and weights for the DGX-branded compute tray, NVLink tray and power shelf (Lenovo values used). Power shelf weight from any source.
- Busbar width/depth in mm; manifold pipe diameter; tray-side QD part number; flange-plane set-back from the rack front; absolute RU numbers of any tray; bottom-of-rack height of RU 1 above the floor.
- Wet vs dry weight split for the ~1580 kg rack (Lenovo gives one figure). Rack-level dry weight for NVIDIA's own DGX GB300 rack.
- Any rear-door heat exchanger option for NVL72 (nothing in the fetched sources).
- Q3401-RD typical power; SN5600/SN5600D maximum power, noise and airflow direction; the exact relationship "Q3400-RD = Q3401-RD".
- The OCP MGX Accelerated Computing Rack and Trays Specification 1.1 PDF (https://www.opencompute.org/documents/mgx-accelerated-computing-rack-and-trays-specification-1-1-pdf-1) returned HTTP 403 to curl (and the OCP product page 403); Scribd copy not fetched. It likely holds the busbar/manifold/blind-mate mm positions. Try it in a browser.
- NVIDIA DGX GB300 datasheet PDF (resources.nvidia.com) and docs.nvidia.com GB300 site-prep pages were not located (the RA HTML pages 404, per docs/ra-notes-gb300.md); rack weight and footprint for the DGX-branded rack therefore come from Lenovo.
- Free 3D model: not searched beyond the pack scope.
