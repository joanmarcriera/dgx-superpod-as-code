# Network equipment, optics and cabling reference (DGX SuperPOD H200, 2 SU / 63 nodes)

Retrieved 2026-09-30 from public NVIDIA documentation. Values are quoted from the source; anything not
found is written NOT FOUND. Colours are **estimates** from NVIDIA doc renders, not official specs.
Design context: RA-11336-001 V2 (DGX H200) "Major Components" names QM9700 (920-9B210-00FN-0M0, compute + storage),
SN4600C (in-band), SN2201 (OOB), UFM Appliance 3.1, and states "All networking components are multi-mode fiber."

Media are in `media/` (see `SOURCES.csv`). Vendor marketing/doc material, not redistributed here.

## 1. NVIDIA Quantum-2 QM9700 (NDR InfiniBand, 64 x 400G via 32 OSFP cages)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Rack units | 1 | U | https://docs.nvidia.com/networking/display/qm97x0pub/introduction | "64 ports of NDR 400Gb/s ... in a 1U standard chassis" |
| Dimensions H x W x D | 43.6 x 438 x 660 (660.4 in datasheet) | mm | https://docs.nvidia.com/networking/display/qm97x0pub/specifications | Manual text mislabels axes ("438mm (H) x 43.6mm (H)"); datasheet lists Height 43.6, Width 438, Depth 660.4 |
| Weight | 13.6 (1 PSU) / 14.8 (2 PSU); datasheet 14.5 | kg | same + media/quantum-2-qm9700-datasheet.pdf | |
| Ports | 32 OSFP cages = 64 x 400G NDR (twin-port), 51.2 Tb/s | - | same | "Connector cage: 32 OSFP"; port-split to 128 x 200G |
| Management ports | 1x RJ45 MGT, 1x RJ45 console (UART), 1x USB 3.0 type A, 1x USB for I2C | - | media/quantum-2-qm9700-datasheet.pdf | Manual table: MGT front, I2C front, USB front |
| Typical power | 747 (passive cables, ATIS) | W | specifications page | |
| Max power | 1,720 (active cables) | W | specifications page | QM9790: 640 / 1,610 W |
| PSUs | 2, 1+1 redundant, hot-swap, front-of-chassis = rear panel (power side) | - | introduction page, datasheet | Input 200-240 VAC, 10 A; C14-C15 cords |
| Fans | 7 hot-swap modules (datasheet "6+1") | - | introduction page | |
| Airflow | -F = power-side (rear) inlet to connector-side (front) outlet = P2C, **blue** dots; -R = connector-side inlet to power-side outlet = C2P, **red** dots | - | https://docs.nvidia.com/networking/display/qm97x0pub/installation | RA part 920-9B210-00FN-0M0 / MQM9700-NS2F: "F" airflow |
| Op. temp | 0-35 forward airflow, 0-40 reverse | C | specifications page | Noise 78.4 dBA |
| Thermal | All servers/switches in a rack must share airflow direction | - | installation page | |
| Faceplate colour (ESTIMATE) | bezel black ~#1A1A1A; OSFP cages dark metal ~#3A3F44; one render shows champagne/gold bezel ~#C9B88F | hex | media/qm9700-doc-img1.png, -img2.png | Estimate only |

Front/rear layout (from doc renders `qm9700-doc-img1.png`, `-img3`, `-img2`; rear `-img4`):
- Front: 2 rows x 16 cages; each cage is a twin-port housing (two 400G ports = one 2x400G OSFP), numbered "1 2 / 3 4 ... 31 32" under the **bottom** row edge of each cage pair (top row = odd/even pairs 1-32 silk printing shown below top row). Cages grouped in 4 blocks of 4 with gaps between blocks. Left edge: reset/ID button and small LED. Right edge: 4 status LEDs (warning, status, fan, PSU icons) in a column, USB-A above, dual RJ45 stack (MGT above console) on the far right, NVIDIA logo bottom right. Ventilation perforations at left and right ends.
- Rear (QM9700, `-img4`): PSU at each end (C14 inlet, green LED, blue release latch), 7 fan modules between, each with a tan/yellow pull handle label (estimate #C8A400) and numbered 1-7, LED + blue dot at bottom. Airflow marker dots on PSU face (blue = -F, red = -R).
- QM9701 (busbar DC variant, 854 mm deep, 16.88 kg, 720/1,660 W) has no PSUs; `-img5` shows its rear: fans left and right, central blind-mate busbar connector.

Blender modelling notes (QM9700): box 438 x 43.6 x 660 mm; front = two rows of 16 OSFP cage cut-outs (inner opening about 27 x 13 mm is an ESTIMATE, not found); use finned-top twin transceivers MMA4Z00-NS in the cages for populated ports; rear two PSU blocks (~ 80 mm wide ESTIMATE) + 7 fan modules; rack ears at front; 1U pitch 44.45 mm so leave 0.85 mm gap.

## 2. NVIDIA Spectrum SN4600C (100GbE in-band, 64 x QSFP28)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Rack units | 2 (88 mm) | U | https://networking-docs.nvidia.com/sn4000hw/specifications | |
| Dimensions H x W x D | 88 x 428 x 566.4 (datasheet 568) | mm | same, media/spectrum-sn4000-datasheet.pdf | |
| Weight | 14.64 (manual); 15 (datasheet) | kg | same | |
| Ports | 64 x QSFP28 (1/10/25/40/50/100GbE), 6.4 Tb/s; up to 128 x 25G/50G/100G via breakout | - | https://networking-docs.nvidia.com/sn4000hw/introduction | Datasheet also lists "6.4 Tb/s" |
| Mgmt | 1x 10/100/1000 RJ45 MGT, 1x RJ45 console, 1x USB (all front) | - | introduction + datasheet | |
| Typical power | 466 (passive, ATIS) | W | specifications page | |
| Max power | NOT FOUND | W | - | |
| PSUs | 2, 1+1 hot-swap, 100-127 VAC 10 A / 200-240 VAC 6 A | - | specs page | |
| Fans | 3 hot-swap, N+1 | - | datasheet | "Color-coded power supply units (PSUs) and fans" |
| Airflow | Reversible (P2C and C2P variants; RA names MSN4600-CS2FO/RO style OPNs on resellers only) | - | datasheet | Reseller OPNs not from NVIDIA docs |
| Faceplate colour (ESTIMATE) | black perforated ~#15171A; blue Mellanox logo badge #1B4F9C | hex | media/sn4600c-doc-front.png | Doc photo shows "Mellanox" badge |

Layout (`sn4600c-doc-front.png`, `-rear.png`): front = 4 rows x 16 columns of QSFP28 cages arranged as 2 rows of 16 double-stacked (2x2) cage blocks, silk "1/2 3/4 ... 61/62 63/64", perforated bezel all round; left edge small LEDs (warning, status, fan, PSU, temp icons), far right: RJ45 MGT, USB, RJ45 console stacked, model label SN4600C. Rear = PSU left, three large fan modules (blue latch tabs, black handles, fan icon + 1/2/3), PSU right; fans and PSU tabs are blue in the render (airflow/colour code; estimate #2B44C8).

Blender notes: 2U box 428 x 88 x 566 mm; cage grid pitch about 24 mm horizontally per 4-port block (ESTIMATE from image: 16 blocks across ~ 380 mm). Perforated bezel = hex/square hole alpha map.

## 3. NVIDIA SN2201 (1GbE out-of-band, 48 RJ45 + 4 QSFP28)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Rack units | 1 | U | https://networking-docs.nvidia.com/sn2201hw/specifications | |
| Dimensions H x W x D | 43.9 x 428 x 432 | mm | same | SN2201_M (busbar): 43.6 x 438 x 781 mm, 11.39 kg |
| Weight | 7.410 | kg | same | |
| Ports | 48 x RJ45 10/100/1000, 4 x QSFP28 100GbE, 448 Gb/s | - | same | |
| Mgmt | front: USB, RJ45 MGT, RJ45 console (1 port) | - | https://networking-docs.nvidia.com/sn2201hw/introduction | |
| Typical power | 98 (passive, ATIS) | W | specs page | SN2201_M 100 W |
| Max power | NOT FOUND | W | - | |
| PSUs | 2 AC hot-swap: 100-127 VAC 4 A / 200-240 VAC 2 A | - | specs page | |
| Fans | 4 hot-swap | - | introduction | |
| Airflow | direction options NOT FOUND in fetched pages | - | - | |
| Faceplate colour (ESTIMATE) | dark grey ~#2B2F33 front, NVIDIA logo top right | hex | media/sn2201-doc-front.png | |

Layout (`sn2201-doc-front.png`): 48 RJ45 in 2 rows x 24 (three groups of 8 columns, silk "1 2 .. 47 48"), link LEDs green/amber on top edge of each jack; 4 QSFP28 as a 2x2 block at right (silk 49/50, 51/52); then status LEDs column, then USB-A and two RJ45 (MGT, console). Vent slots along the top of the bezel. Rear (`sn2201-doc-rear.png`): left 4 fan modules (tan handles, red/green LEDs), blank panel, two PSUs at right with C14 inlets.

Blender notes: 1U 428 x 43.9 x 432 mm (short depth, rack ears forward). RJ45 jack 14 x 13 mm opening (industry standard, not from NVIDIA).

## 4. NVIDIA UFM Enterprise Appliance 3.1 (Gen 3.0 NDR; model MUA960B)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Rack units | 1 | U | https://docs.nvidia.com/networking/display/ufmenterprisendrhwum/Technical+Specifications | |
| Dimensions H x W x D | 42.8 x 482 x 809 (822.84 with bezel) | mm | same | |
| Weight | 17 | kg | same | |
| Power | max 689 W; PSU 1100 W 80 Plus Titanium 1+1 hot-swap, 100-240 VAC | W | same | typical NOT FOUND |
| Heat | 2241.8 BTU/hr max; airflow 52.1 CFM | - | same | |
| CPU / RAM / disk | 2x Xeon Silver 4314, 64 GB, 2x 1.92 TB SSD | - | same | |
| Ports | 2x ConnectX-7 NDR single-port OSFP (PCIe slots 1, 2), 2x 10GbE BASE-T (OCP), 2x 1GbE RJ45, iDRAC-style RJ45, DB9 serial, USB 2.0 + 3.0 | - | https://docs.nvidia.com/networking/display/ufmenterprisendrhwum/Hardware+Overview | Also "x5 RJ-45" total |
| Airflow options | NOT FOUND | - | - | |
| Colour (ESTIMATE) | black 1U server with silver chassis edge ~#1C1C1E | hex | media/ufm-ent-appliance-front.png | Looks like a Dell PowerEdge-class chassis |

Layout: front = left control panel (health/ID LED), 2 populated 2.5" SSD bays (1.9 TB SAS labels) + 2 empty blanks, pull-out info tab, right control panel with power button; top-edge vent grille. Rear (no image retrieved): PSU 1 | 2 low-profile ConnectX-7 OSFP cards | DB9, USB | PSU 2, with RJ45 iDRAC/ID button and OCP + embedded NIC. RA: 4 UFM appliances in the 4 SU design (RA Table 7); SN2201 OOB uses QSFP->SFP+ adapter + SFP BaseT module for UFM (RA Table 8).

## 5. ConnectX-7 (NDR 400G adapter)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Ports | 1/2/4 network ports; single/dual-port NDR (400G) or NDR200 OSFP; dual-port HDR QSFP | - | media/connectx-7-datasheet.pdf, https://www.nvidia.com/en-us/networking/quantum2/ | |
| Host interface | PCIe Gen5 up to x32 lanes | - | datasheet | |
| Form factors | HHHL, FHHL, Socket Direct, OCP3.0 TSFF/SFF | - | datasheet | |
| Cage on adapter | flat-top OSFP with riding heat sink (RHS) on cage; transceiver must be flat-top | - | https://docs.nvidia.com/mma4z00-ns400-400gb-s-single-port-osfp-400gb-s-multimode-sr4-50m-transceiver.pdf | "flat-top ... riding heat sink (cooling fins) on the ConnectX-7 connector cage" |
| Power | NOT FOUND in datasheet text | W | - | |
| In DGX H200 | 8 ConnectX-7 on two "Cedar-7" mezzanine boards routed to 4 twin-port OSFP cages on the front/rear panel | - | media/mma4z00-ns-twin-osfp-spec.pdf (DGX H100 text; RA says H200 same) | RA: "compute fabric ports in the middle use a two-port transceiver to access all eight GPUs"; in-band/storage = QSFP112 pairs; OOB BMC RJ45 |

Blender notes: DGX H200 has 4 flat-top twin OSFP (2 ports each = 8 x 400G), plus 2 x dual QSFP112 (storage + in-band), 1 OOB RJ45, see DGX worker's pack.

## 6. Optics and cabling table

Part numbers: NVIDIA RA H200 Table 8 (`980-9...`) and LinkX docs (MMA/MFP/MCP names). Mapping between 980- and marketing names comes from NVIDIA docs where noted; otherwise "mapping not verified".

| Link in SuperPOD | Item | Part number(s) | Jacket / body colour | Bend radius | Power | Source |
|---|---|---|---|---|---|---|
| Compute and storage, switch end | Twin-port 2x400G OSFP, SR8 multimode, **finned top (IHS)**, 2x MPO-12/APC, 850 nm, 50 m | MMA4Z00-NS (RA 980-9I510-00NS00 "Switch OSFP Transceivers", 1536 in 4 SU) | transceiver body metal; MM optics shown "tan and aqua" | - | 15 W typ / 17 W max, 1.5 W low-power; 3.3 V | media/mma4z00-ns-twin-osfp-spec.pdf |
| DGX end (Cedar-7 cages) | Twin-port OSFP **flat-top (RHS)** | MMA4Z00-NS-FLT (RA 980-9I51A-00NS00, 508 in 4 SU) | flat-top shell | - | same as above | same |
| UFM to leaf | UFM system transceivers | 980-9I51S-00NS00 (mapping not verified) | - | - | - | RA Table 8 |
| Storage-side DGX/CX7 single port | Single-port OSFP flat-top SR4 (and QSFP112 MMA1Z00-NS400) | MMA4Z00-NS400 (RA QSFP112 980-9I693-00NS00 mapping not verified) | - | - | 8.5 W max (4 ch), 5.5 W (2 ch) | media/mma4z00-ns400-single-osfp-spec.pdf |
| Switch to DGX, leaf-spine | MPO-12/APC multimode trunk, 8 fibres active, Type-B crossover, 3.0 mm | MFP7E10-N003/005/007/010/015/020/030/050; RA 980-9I570-00N030 = 30 m (2040 cables in 4 SU) | **Aqua**, LSZH-OFNR; "NVIDIA green connector shell denoting MPO-12/APC" | **30 mm** min anywhere | passive | media/mfp7e10-nxxx-spec.pdf |
| Splitter trunk (1 twin port to 2 single) | 4-ch MPO-12/APC to two 2-ch MPO/APC | MFP7E20-N003 ... | as above (assumed) | - | - | twin-port spec |
| 400G DAC (short, in rack) | 800G twin OSFP to 2x400G etc., passive copper up to 3 m | MCP7Y00-N001..N003, MCP7Y40/50/10 splitters, MCP4Y10 | Black ("Black = DAC") | 26 AWG: 71 mm min (FAQ) | <0.1 W | media/linkx-400g-ndr-portfolio.pdf |
| 400G ACC | linear active copper up to 5 m | MCA7J60-N004/N005, MCA4J80-N003..005 | black (assumed, NOT FOUND explicit) | - | ~1.5 W | LinkX portfolio |
| Storage / in-band DGX | 200G QSFP56 MMF AOC, 4 x 50G PAM4 | MFS1S00-HxxxV (RA 980-9I440-00H030 = 30 m, 254 in 4 SU; mapping not verified) | **Aqua**, 3 +/- 0.2 mm LSZH | 30 mm | 5.0 W max each end | https://networking-docs.nvidia.com/mfs1s00hxxxv10/specifications |
| In-band mgmt nodes, OOB uplinks, leaf-core | 100G QSFP28 MMF AOC | MFA1A00-C030 (RA 980-9I13N-00C030) | **Aqua**, 3 +/- 0.2 mm | 30 mm | 1.5 W typ / 1.8 max (no retime); 2.2/2.5 (retime) each end | https://networking-docs.nvidia.com/mfa1a00xxxxspec/specifications |
| In-band ISL | 100G QSFP28 passive DAC | RA 980-9I620-00C001 (1 m, MCP1600-C001 name NOT verified) | black (assumed) | - | ~0 | RA Table 8 |
| Uplink to core DC | 100G QSFP28 CWDM4 SMF transceiver | RA 980-9I17Q-00CM00 | SM = yellow per NVIDIA FAQ | - | NOT FOUND | RA Table 8 |
| OOB | 1 Gbps copper **Cat5e** (RA says Cat5e, not Cat6) | generic | colour NOT specified | standard ~4x OD (TIA) | - | RA Table 8 |
| UFM to OOB | QSFP->SFP+ adapter 980-9I71G-00J000 + SFP BaseT module 980-9I251-00IS00 | - | - | - | - | RA Table 8 |
| Storage, 400G to 2x200G | AOC splitter | 980-9I117-00H030 (200G NDR200 cables, 48) | aqua (assumed) | - | - | RA Table 8 |

Cable counts (RA Table 8, 4 SU/127-node; scale for 2 SU/63 nodes in the design): 254 in-band QSFP56 AOCs = 2 per DGX; 2040 NDR compute cables; 127 OOB Cat5e for DGX.
RA Table 4 (2 SU, 63 nodes): 16 leaf, 8 spine; compute cable counts 508 leaf, 512 spine-leaf.

## 7. Cable colour scheme — evidence

**NVIDIA verdict: there is NO NVIDIA per-fabric cable colour scheme** in the RA (H200), the DGX SuperPOD Data Center Design guide (DG-11301-001 v4) or the "Cabling Data Centers Design Guide" (DU-10438-001). Evidence in NVIDIA documents:
- Cabling guide (https://docs.nvidia.com/dgx-superpod/design-guide-cabling-data-centers/latest/cable-management-reqs.html): It recommends colour-coded cable ties that indicate the endpoints, with labels at both ends and along the run (paraphrased). No actual colours prescribed.
- Same guide (considerations page): "NVIDIA offers a unique option with cables, color-coded pull tabs. These tabs can assist the installer in identifying cables". Colours not specified.
- Labels must show source, destination/port, cable type and length, and BSN (bundling sequence number) (document-network page).
- Data Center Design guide: "Color code the power cables (and associated rPDUs) to help ensure that redundancy is maintained" (power only).
- LinkX portfolio deck (media/linkx-400g-ndr-portfolio.pdf): "Colors mean something! Black = DAC; Aqua = Multi-mode - short reach; Yellow = Single-mode - long reach."
- MFP7E10 spec: Aqua LSZH jacket (OM3 <=30 m, OM4 >30 m), connector shell NVIDIA green = MPO-12/APC (UPC typically blue shell). AOCs (MFS1S00-HxxxV, MFA1A00-Cxxx) specify "Cable color: Aqua".
- NVIDIA Cable Management FAQ: OM2 orange, OM3/OM4 aqua, OM5 aqua-green (sic), SMF yellow; "standards are not fully consistent".

Industry convention (TIA-598; secondary sources, https://www.truecable.com/blogs/cable-academy/what-do-all-the-colors-mean-fiber-optic-color-coding , https://www.dysfiber.com/blog/cable-selection/fiber-optic-color-code): OM1/OM2 orange, OM3 aqua, OM4 aqua or erika violet (heather violet), OM5 lime green, OS1/OS2 yellow; connector/boot colours: APC green, UPC blue (SM), multimode connectors often beige/aqua. Copper patch-cord colours by network (blue data, red/orange management, etc.) are site conventions, not standards.

**Conclusion:** because the physical products are fixed (all fibre aqua, DAC black), per-fabric differentiation in a render/model must be a **CHOICE** applied via the colour-coded cable ties / pull tabs / labels NVIDIA recommends. Proposed CHOICE (label as such): compute IB fabric = aqua jackets (as shipped) with orange/blue ties per rail group; storage fabric = aqua jackets with purple ties; in-band 100G = aqua AOC with green ties; OOB Cat5e = yellow or grey patch cords; DAC ISL = black; core uplink SMF = yellow; power = red/blue for A/B feeds.

## 8. Cable management and raceways

- NVIDIA options: fibre optic trays, basket trays/wire mesh, cable ladders (cabling guide, cable-management-guidance). Trapeze-hung single/dual/mixed layers (DU-10438-001 s7.5). Segregate power, copper data and fibre; fill at most 50%; tray minimum cross-section 11.5 in^2 (7,419 mm^2) for a 1-SU set of 3 mm AOCs; tray supports every 5 ft (DG-11301-001 v4 figs 18/19). Load estimate 380 cables x 0.009 kg/m = 3.42 kg/m.
- Panduit FiberRunner: yellow and black are the available colours ("yellow" is the standard; rigid PVC; 2 in minimum bend radius fittings; sizes 2x2, 4x4, 6x4, 12x4) - https://www.panduit.com/content/dam/panduit/en/products/media/8/28/828/8828/110098828.pdf (spec sheet, not downloaded). NVIDIA does not name a brand or colour; yellow FiberRunner is an industry convention.
- Ladder rack colour: NOT FOUND (typical black or grey powder-coat, colour unverified).
- Max point-to-point IB run 50 m (165 ft).

## 9. Blender modelling notes (summary and cables)

- Fibre cable: 3.0 mm diameter aqua (#00A7B5 ESTIMATE) jackets, MPO-12 connectors with green (#3DAE2B ESTIMATE) shell and a white/grey boot; min bend radius 30 mm (use >= 10 x OD) so keep curves >= 30 mm in Bezier profile.
- Twin-port OSFP finned top: transceiver ~ 2 x MPO exits from the front of a wide flat body; fins visible on the switch-side module, flat top on DGX.
- Passive DAC: black, thicker (~7-8 mm OD assumption, NOT FOUND), bend 71 mm for 26 AWG.
- Switch orientation: QM9700 -F units face connectors forward with PSUs at rear; in SuperPOD RA the switches are in the network/management racks (RA figure not parsed).

## 10. Not found

- Max power SN4600C, SN2201; UFM typical power; ConnectX-7 power.
- SN2201 airflow options; UFM airflow options.
- Official port-cage pixel dimensions and PSU/fan module dimensions for any device; official CAD/STEP models (none found; NVIDIA publishes none openly).
- Hex colours for any device (estimates only).
- UFM rear-panel image (retrieved crop was wrong and removed).
- Photographs (vs doc renders) of the switches and optics; product photos on nvidia.com require JS and were not retrieved.
- Explicit mapping of RA 980- part numbers to marketing names for 980-9I51S, 980-9I693, 980-9I440, 980-9I620, 980-9I117.
- Ladder rack colour; any NVIDIA per-fabric colour scheme.
- MMA4Z00-NS physical dimensions (may be in the twin-port spec PDF mechanical section; not extracted).
- Dedicated datasheet PDFs for SN2201 (only the SN2000-series brochure) and the DGX-specific cabling figure for H200.
