# Facility reference pack: racks, PDUs, power, cooling, containment (DGX SuperPOD H200, air-cooled)

Retrieved 2026-09-30. Public web sources only. Media in `media/` (36 MB), provenance in `SOURCES.csv`.
"DCG" = NVIDIA *DGX SuperPOD Data Center Design Featuring DGX H100 Systems* (HTML, last updated 2025-11-19); no separate H200 DCG was found, and the RA for H200 (RA-11336-001) points to the same physical design, so the H100 DCG is used as the H200 facility guide. Figures marked "derived" are my arithmetic on cited numbers.

Base URLs: DCG = `https://docs.nvidia.com/dgx-superpod/design-guides/dgx-superpod-data-center-design-h100/latest/` (pages `planning.html`, `infrastructure.html`, `electrical.html`, `cooling.html`, `layouts.html`, `networking.html`). LEG = Legrand/Raritan/Starline reference guide `https://www.raritan.com/assets/ram/documents/briefs/DGX-H100_Reference-Guide_R6_V2158.pdf`.

## 1. NVIDIA design guidance (DCG)

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| DGX H100/H200 cooling | Air | - | DCG planning.html (Table 1) | "Cooling Air"; rack units 8; 14 x 19.0 x 35.3 in (356 x 482.3 x 897.1 mm); 130.45 kg |
| DGX H200 power / cooling (datasheet) | 10.2 (std), 14.3 (CTS) | kW max | https://www.megware.com/fileadmin/user_upload/LandingPage%20NVIDIA/NVIDIA_DGX_H200_Datasheet.pdf | "10.2kW for standard configuration. DGX H200 CTS ... supports up to 14.3kW"; 5-30 C operating |
| DGX H100/H200 airflow | 1105 CFM front-to-back @ 80 % fan PWM; 38,557 BTU/hr | CFM | https://docs.nvidia.com/dgx/dgxh100-user-guide/introduction-to-dgxh100.html | "Airflow 1105 CFM Front-to-Back @ 80% fan PWM Heat Output 38,557 BTU/hr" |
| Airflow requirement | 157 (4.445 m3/min) | ft3/min per kW | DCG planning.html | "minimum airflow of 157 ft3/min (4.445 m3/min) per kilowatt"; depends on altitude and Delta T |
| Airflow per 20.4 kW rack (2 DGX) | ~3,203 | CFM | derived (20.4 x 157) | DCG quotes 6,437 CFM for the 40.8 kW (4-DGX) rack |
| Inlet temperature | Recommended ASHRAE 18-27 C (64.4-80.6 F); A1 allowable 15-32 C; DGX max 30 C | C | DCG planning.html (Table 4) | "must satisfy the Recommended requirements, and at the very least ... Class A1" |
| Hot-aisle temp rule | Hot aisle > 60 C (140 F) is "not typical"; above it move/derate cabling incl. power | C | DCG infrastructure.html | Example 70 F supply + 30 F Delta T = 100 F hot aisle |
| Filtration | MERV 13 (or EN779 M6/F7, ePM1-50 %), ISO 14644-1 Class 8 | - | DCG planning.html | only when airside economiser / contaminated source air |
| Rack size | >= 24 x 48 in (600 x 1200 mm), >= 48U; NVIDIA recommends 32 x 48 in (800 x 1200 mm) | mm | DCG infrastructure.html | "Racks must not have chimneys. Side walls must be installed in all racks." EIA-310, 19 in |
| Rack opening / rails | 450 mm min opening; 465.1 mm hole spacing; 1.75 in RU | mm | DCG infrastructure.html | EIA-310-D |
| Doors | Front and rear doors NOT recommended unless facility/security mandates | - | DCG infrastructure.html | "Eliminating the front and rear doors helps improve airflow and reduces cost" |
| Blanking / grommets | Blanking panels in every unused RU; brush grommets on all top/side/bottom cable ports | - | DCG infrastructure.html, cooling.html | needed so containment is effective |
| Floor fixing | Cabinets bolted to floor; seismic bracing in subfloor where AHJ requires | - | DCG infrastructure.html | raised-floor seismic note |
| Rack temp sensors | 2 per rack, at 4U and 42U, front, right side facing front, plugged into front-most PDU | - | DCG infrastructure.html | LEG p.11: Raritan DX2-T1H1 (temp + humidity) |
| Server placement | Bottom of rack from ~RU3 (server-lift reach); 2 servers low, 3 RU gap, 2 above; rPDUs horizontal near top | - | DCG infrastructure.html (Fig. 16) | "It is optional ... to have 1 RU between each server" |
| Server lift | Platform lift rated >= 350 lb (159 kg) | lb | DCG infrastructure.html | forks not suitable |
| Rack weight (2 DGX/rack) | 925 lb / 420 kg total; 308 lb point load | lb | DCG infrastructure.html (Table 16) | table prints "38" kg point load, which is a typo for ~140 kg; 4/rack = 1500 lb / 680 kg; unloaded IT cabinet avg 350 lb (158 kg) |
| Floor loading | Engineer slab / subfloor for rack weight; no kPa figure given | - | DCG infrastructure.html | kPa NOT FOUND |
| Rack power density | 2/rack = 20.4 kW; 4/rack = 40.8 kW; >4 not recommended | kW | DCG planning.html (Table 2), electrical.html | RA text says ">25 kW" per rack for Fig. 2 |
| Power | Preferred 415 V, 32 A, 3-phase, N+1 (3 circuits, none > 50 % load) | - | DCG electrical.html | 3 rPDUs per DGX rack, each feeding 2 of 6 PSUs; 4 of 6 PSUs must be live |
| Feed separation | rPDUs from separate floor PDUs or busways; "Enhanced N+1" = 3 discrete UPS paths | - | DCG electrical.html | "Color code the power cables (and associated rPDUs)" |
| rPDU vendors | Raritan, Vertiv/Geist, ServerTech; horizontal rPDUs may be required; max 2 vertical | - | DCG electrical.html | vertical PDUs at rearmost mounting points, only where they do not block chassis rear |
| Aisle widths | >= 36 in (914 mm) all aisles; cold aisle >= 48 in (1219 mm) strongly recommended | in | DCG cooling.html | for lifts and carts |
| Containment | Hot or cold aisle; clear acrylic panels + end doors (self-closing) | - | DCG cooling.html (Fig. 20) | stops recirculation |
| Cooling sizing | Size cooling to N (two circuits), not a single circuit | - | DCG cooling.html | example: 358 kW load vs 260 kW cooling; spacing one rack footprint gave 460 kW |
| Cabling route | Overhead ladder/tray over the rack rows; underfloor also possible | - | DCG infrastructure.html, layouts.html, networking.html | Figs 18/19 show overhead tray front/rear |
| IB cable length | <= 50 m (165 ft) path; 30 m for best performance; switch-switch SMF 500 m | m | DCG layouts.html | drives max row length and rack spacing |
| Tray fill | <= 50 % fill; min 11.5 in2 (7,419 mm2) cross-section per SU (3 mm AOC) | in2 | DCG networking.html | 508 cables x 0.009 kg/m = 4.57 kg/m per SU; supports every 5 ft |
| Cable weights | Copper 9.43 mm, 0.045 kg/m; AOC 3.0 mm, 0.009 kg/m | kg/m | DCG networking.html | Table 17 |
| Noise | DGX > 98 dB at 1 m; 97 dB(A) @25 C, 98.7 @30 C | dB | DCG planning.html, infrastructure.html | hearing protection |

## 2. Racks

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| APC NetShelter SX AR3307 (48U) | 2258 H x 600 W x 1200 D | mm | https://www.apcguard.com/netshelter-sx-48u-600x1200.asp ; https://se.com/us/en/product/AR3307/apc-netshelter-sx,-server-rack-enclosure,-48u,-black,-2258h-x-600w-x-1200d-mm | Black; end of commercialisation 2025-12-31, replaced by AR3307B2 (Gen 2) |
| AR3307 load | 1364 static / 1023 dynamic | kg | apcguard page above | 3000 / 2250 lb; shipping depth 1334 mm |
| AR3307 gauge | posts 16 ga, front door 16, rear 18, roof 18, rails 14, sides 18 | ga | apcguard page above | doors "perforated"; open-area % NOT FOUND on this page (a 3rd-party listing says ~72 % for the 42U AR3350, unverified) |
| AR3307 mounting depth | 191 to 1060 | mm | apcguard page above | |
| Legrand T-Series (used in LEG BOM) | 42-52U; width 24/30/31.5 in; depth 45.8/51.8/57.8 in; perf door 80 % open area; 5,000 lb static | - | LEG p.16-17 | tubular welded steel; split mesh or solid doors; brush top panel; Contain-IT Flex for containment |
| Lenovo 48U MGX rack (GB300) | 2294 H x 600 W x 1068 D (1200 with extension); 185 kg | mm | https://lenovopress.lenovo.com/lp2357.pdf | for contrast (liquid-cooled rack) |
| Vertiv VR / Rittal TS IT | NOT FOUND (not fetched) | - | - | not verified in this pass |

## 3. Rack PDUs

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| RA names | DGX racks PX3-5878I2R-P1Q2R1A15D5; mgmt racks PX3-5747V-V2 | - | ../../docs/ra-notes.md (RA Table 7) | exact-SKU spec sheet NOT FOUND (option codes P1Q2R1A15D5 not resolvable) |
| PX3-5747V-V2 form factor | 0U vertical, 1780 x 109 x 80 (H x W x D); 16.4 kg | mm | https://cdn.raritan.com/product-selector/pdus/PX3-5747V-V2/PX3-5747V-V2-spec.pdf | 70.1 x 4.3 x 3.1 in; tool-less button mount |
| PX3-5747V-V2 outlets | 36 x C13 (12 A) + 12 x C19 (16 A) = 48 | count | same | 12 Airpax 20 A branch breakers |
| PX3-5747V-V2 inlet | IEC 60309 3P+N+E "7h" 60 A (4P5W) IP67, 3 m cord, bottom feed; 34.5 kVA @ 415 V, 48 A | - | same | sheet states 60 A, not 32 A; DCG design circuit is 32 A (21.8 kW) |
| PX3-5747V-V2 colour / display | Black powder coat (custom colours available); colour matrix LCD, auto-flip | - | same | LCD position: see `media/raritan-px3-5747v-v2-spec-p1.jpg` line drawing (exact position NOT stated in text) |
| PX3-5878I2R-Q1 (nearest sibling) | Horizontal 3U: 440 x 293 x 132 (W x D x H); 16.0 kg | mm | https://cdn.raritan.com/product-selector/pdus/PX3-5878I2R-Q1/PX3-5878I2R-Q1-spec.pdf | 17.3 x 11.5 x 5.2 in; RACK-KIT-PX-3U |
| PX3-5878I2R-Q1 outlets | 18 x C19 (16 A) + 6 x C13 (12 A) = 24 | count | same | inlet IEC 60309 3P+N+E 6h 60 A, 3 m, front feed; 34.5 kVA @ 415 V; black |
| Form factor used in DCG/LEG | DGX racks use horizontal rPDUs near top of rack; LEG BOM uses PX3-5008I2R-Q1 x3 per DGX rack and PX3-5747V-V2 x2 per mgmt rack | - | DCG electrical.html; LEG p.3, 5, 11 | inference: P1Q2R1A15D5 SKU is the horizontal "5878" family; treat as estimate |
| IEC 60309 colour | Red for 380-415 V 3-phase (standard convention, not from a vendor sheet) | - | (general IEC 60309 convention) | 6h = 400 V red; the sheet's "7h" is unverified |
| A/B/C feed colours | A = red, B = blue (common practice; OCP cable schema: Red A-side, Blue B-side). C (third feed) has no standard; NOT FOUND | - | https://eepower.com/new-industry-products/color-pdus-and-cables-help-data-centers-identify-and-manage-power-feeds/ ; https://www.opencompute.org/documents/data-center-cable-infrastructure-color-schema-pdf | NVIDIA DCG only says "color code the power cables"; propose green or yellow for C (estimate) |
| Images | `media/legrand-raritan-px3-5008i2r-views-p11.jpg`, `media/raritan-px3-*-spec-p1.jpg` (line drawings), `media/commons-apc-rackmount-pdu.jpg` | - | SOURCES.csv | no product photo of the exact SKU found |

## 4. Cooling

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Is DGX H200 air-cooled? | YES | - | DCG planning.html Table 1; datasheet 1105 CFM | "Cooling: Air"; 8U; front-to-back airflow; 12 fan modules |
| CDU for H200? | NO, not applicable to the air-cooled H200 SuperPOD | - | DCG cooling.html | DCG cooling chapter covers only CRAH/aisle containment/oversubscription, no CDU or liquid loop |
| CDU for GB200/GB300 | YES, required (in-row or in-rack CDU, rear manifold, quick disconnects, cold plates); ~90 % liquid / 10 % air | - | https://lenovopress.lenovo.com/lp2357.pdf | "The liquid cooling solution consists of a coolant distribution unit (CDU)..." |
| RDHx for H200? | Optional mitigation, not required. LEG suggests ColdLogik CL20 to meet 157 CFM/kW; DCG itself does not mention RDHx | - | LEG p.3-4, 18-19 | DCG mitigation = spacing racks, containment, lower density |
| USystems ColdLogik CL20 | 62 (5 fan) / 93 (6 fan) kW; 6847 / 8217 m3/h | kW | LEG p.18 | water in 14 C, out 25 / 30 C; 1.4 l/s |
| CL20 size (48U 600 wide) | 2307 H x 596 W x 380 D; 94 kg dry, 134.3 kg wet; RAL 9003 white or RAL 9005 black | mm | LEG p.19 | 42U: 2040 H, 86 kg; also 800 wide variants |
| Vertiv Liebert DCD | 35 / 47 / 50 kW; widths 600/800 mm; heights 2000/2200 mm; DCD50 only 800 wide; passive door swings 180 deg | kW | https://www.vertiv.com/4aac8e/globalassets/products/thermal-management/high-density-solutions/vertiv-liebert-dcd-brochure-sl-70859.pdf | dims 600 x 120 x 1954 mm appear only in a search summary (unverified) |
| Motivair ChilledDoor | up to 75 kW; fits 42U/48U; 30 C water @ 23 GPM | kW | https://media.distrelec.com/Web/Downloads/_t/ds/Motivair-Liquid-Cooled-Doors_eng_tds.pdf | needs CDU if water <= dew point; dims NOT FOUND in this sheet (24 x 78.7 x 5.5 in from a search summary, unverified) |
| Vertiv CoolChip CDU 600 kW | 2000 x 600 x 1200 mm; 550 kg wet | kW | https://www.vertiv.com/493b1e/globalassets/shared/vertiv-coolchip-cdu-2300kw-data-sheet-sl-80005.pdf | 600 kW @ 4 C ATD; 9 kW power; 2.5 in flanges |
| Vertiv CoolChip CDU 1350 kW | 2122 x 900 x 1243 mm; 1086 kg wet | kW | same | 20.5 kW power |
| Vertiv CoolChip CDU 2300 kW | 2400 x 1200 x 1200 mm; 1793 kg wet | kW | same | 6 in flanges; front/rear service; CDU is a floor-standing tall cabinet (~1 rack footprint or larger) |
| Lenovo GB300 in-row CDU | 1.3 MW, max 8 racks (search summary) | MW | https://lenovopress.lenovo.com/lp2357.pdf | 1.3 MW figure not re-verified in the PDF |
| CRAH / fan wall | Vertiv Liebert CWA chilled-water thermal wall 200-500 kW; CW181 181 kW; dimensions NOT FOUND | kW | https://www.vertiv.com/4986a1/globalassets/products/thermal-management/room-cooling/vertiv-liebert-cwa-chilled-water-thermal-wall-unit-from-200-to-500kw/vertiv-liebert-cwa-brochure---english---emea_mka4l0ukcwa---rev.-3-02.2023-id-374354.pdf | not downloaded (no size/colour data fetched) |
| Facility heat load (derived) | 63 x 10.2 = 642.6 kW DGX; 32 racks x 20.4 = 652.8 kW incl. the empty slot | kW | derived | DCG example totals: 1,295,400 W for 127 nodes |

## 5. Containment, floor, overhead

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| Containment type | Legrand Contain-IT Flex: drop-away roof panels, sliding end doors, cabinet seals; airflow integrity > 97.5 %; roof light transmission up to 83 % | - | https://www.datacenterdynamics.com/en/news/legrand-launches-modular-aisle-containment-system/ | LEG BOM lists "Contain-IT Flex end-row sliding doors up to 52U" and cold-aisle containment |
| NVIDIA reference look | Clear acrylic partitions + self-closing end doors | - | DCG cooling.html Fig. 20 | `media/nvidia-dcg-h100-fig20-aisle-containment.jpg` |
| Overhead power | Starline T5 track busway, 800 A straight (US800T5H4S-...), end feed, joint kits, end caps; M70 tap-offs (415 V/60 A 3-ph, 3 per DGX rack, 2 per mgmt rack) | - | LEG p.5, 12-15 | two parallel busways (one per UPS path) in the "across the aisle" layout, p.7 |
| Starline T5 250 A housing | 111 wide x 128 high (4.36 x 5.05 in); extruded aluminium; 3 m = 23.1 kg | mm | https://www.newenglandlab.com/userfiles/files/resources/catalog%20sections/Media%20Ceiling/Starline-Track-Busway-PSG_T5-section_for-web-.pdf | 800 A housing dimensions NOT FOUND |
| Starline colours | Paint options UEC Black / Blue / White (RAL on request); tape marking black/white/blue; default finish NOT FOUND (a search summary says anodised silver, black, white, red, blue) | - | same | |
| Starline T3 (100-225 A) | housing 4.2 x 2.4 in (107 x 61 mm) | mm | https://starlinepower.com/products/track-busway/T3-100-225-amp-busway | from search summary; for contrast only |
| Fibre raceway | Panduit FiberRunner 6x4 yellow PVC: 4.44 x 6.58 in (112.8 x 167.3 mm); 4x4 = 4.10 x 4.25 in; 12x4 = 4.44 x 12.97 in; yellow or black | mm | https://www.panduit.com/content/dam/panduit/en/products/media/0/40/740/7740/110097740.pdf | material PVC (channel), PC/ABS (fittings); UL Listed |
| Ladder/tray | Legrand ladder racks and trays above racks; width/depth NOT FOUND | - | LEG p.7 | DCG supplies fill/weight rules only |
| Raised floor vs slab | DCG allows both (subfloor seismic, plenum perforated tiles, "overhead or underfloor cable trays"); no mandate | - | DCG cooling.html, layouts.html | tile dimensions/open area NOT FOUND (photo: `media/commons-perforated-floor-tile.jpg`) |
| Brush strips / blanking | BFPT blanking panels 1U/2U; brush grommet on top panel | - | LEG p.4, 17 | |

## 6. Shelves

| Item | Value | Unit | Source URL | Quote/note |
|---|---|---|---|---|
| H200 rail kit | Stationary shelf-type or sliding rail kits, 28-32 in extension range; must be used | in | DCG infrastructure.html (Fig. 15) | `media/nvidia-dcg-h100-fig14-dgx-in-rack.png` |
| 1U/2U generic shelf | NOT FOUND (no vendor spec fetched) | - | - | |
| GB300 power shelf | 1U, 33 kW, 6 x 5.5 kW PSUs, 50 VDC out; 448 W x 43.6 H x 718.5 D mm; 200-277 VAC, 1x 60 A IEC 60309 whip | mm | https://lenovopress.lenovo.com/lp2357.pdf | 6 or 8 shelves per rack (198/264 kW), top and bottom of rack; power shelf image page `media/lenovo-gb300-nvl72-rack-front-p6.jpg` |

## Hall layout guidance (for 32 DGX racks + 4 mgmt racks, 2 DGX/rack)

1. Rack: 600 x 1200 x 48U minimum (NVIDIA prefers 800 x 1200 for PDU/cable room); no chimneys, side panels on, doors removed (or perforated if mandated), blanking panels and brush grommets everywhere.
2. Rows: back-to-back racks form a hot aisle, fronts face a cold aisle; hot or cold aisle contained (acrylic panels, end doors). Aisles >= 914 mm, cold aisle >= 1219 mm.
3. Per-SU pattern (RA/LEG): DGX racks in a row with 2 mgmt racks; "across the aisle" puts 2 DGX racks + 2 mgmt racks per side. LEG p.7 shows management racks between groups of DGX racks and two parallel overhead Starline busways.
4. Power: three feeds per DGX rack (A/B/C), each <= 50 % load, 415 V/32 A/3ph; two feeds for mgmt racks (2N). Overhead busway with tap-off boxes, one busway per upstream path; each DGX rack needs 3 tap-offs.
5. Cabling: overhead ladder/tray above racks; fibre in yellow raceway; max 50 m IB path (30 m preferred), so keep each SU contiguous or split across two facing rows.
6. Thermal: 157 CFM/kW (~3,200 CFM per 20.4 kW rack, derived); supply within 18-27 C (30 C max for DGX); CRAH/fan-wall with containment; RDHx optional if the room cannot meet airflow (e.g. ColdLogik CL20, 62-93 kW). No CDU.
7. Loading: 420 kg per 2-DGX rack (+ rack and PDUs); server lift >= 159 kg; bolt racks to floor.

## Blender modelling notes (colours are estimates)

| Element | Dimensions (mm) | Colour (approx hex, estimate) | Material |
|---|---|---|---|
| Rack (APC SX 48U) | 600 x 1200 x 2258 | frame/doors matt black ~#1b1b1d (APC "Black"); rails zinc ~#9a9da0 | powder-coated steel, roughness ~0.5; perforated doors ~63-80 % open (alpha holes), 16 ga doors |
| DGX H200 | 482.6 x 897.1 x 356 (8U) | bezel gold-brown/dark grey ~#3b3b3b with brass-gold front grille ~#b08d57 (colour not in sources) | sheet metal with mesh |
| Horizontal PDU (PX3-5878 family) | 440 x 293 x 132 (3U) | black ~#141414, colour LCD | powder coat; red IEC 60309 plug ~#c8102e |
| Vertical PDU (PX3-5747V-V2) | 1780 x 109 x 80 | black ~#141414 | rear of rack at rearmost rails |
| Power cords A/B/C | C13/C19 | A red ~#c62828, B blue ~#1565c0, C (proposed) green ~#2e7d32 | PVC, sheen |
| Starline T5 busway | 111 x 128 cross-section (250 A); 800 A larger, NOT FOUND | silver/anodised ~#b8bcc0 or white ~#f0f0f0 | extruded aluminium, brushed |
| Fibre raceway | 113 x 167 (6x4) | yellow ~#f2c200 | PVC, satin |
| Ladder/tray | width NOT FOUND | galvanised ~#a8aaad or black | steel |
| Containment | roof transmission up to 83 % | clear/light-grey acrylic ~#dfe6ea alpha 0.3; frame white/black | acrylic/polycarbonate, door gaskets |
| Floor | slab or raised floor, tile size NOT FOUND | light grey ~#9c9c9c; perforated tiles dark grey | concrete or steel-encased tile |
| ColdLogik CL20 (optional) | 596 x 380 x 2307 | white RAL 9003 ~#f4f4f0 or black RAL 9005 ~#0e0e10 | powder coat |
| Blanking panels | 1U/2U | black ~#111 | plastic/steel |

Photos for look-and-feel: `commons-cern-datacenter-aisle.jpg`, `commons-datacenter-server-racks-row.jpg`, `commons-racks-amravati-datacenter.jpg`, `commons-nersc-rack-rear-closeup.jpg`, `commons-perforated-floor-tile.jpg`.

## Not found

- A dedicated DGX H200 data-centre design guide (H100 DCG used; RA H200 follows it).
- Exact PDU SKU spec: PX3-5878I2R-P1Q2R1A15D5 (only sibling -Q1 found); 32 A inlet variant; LCD position in text; C-feed colour convention.
- Perforated door open-area % for APC SX (Legrand T-Series 80 % only); APC SX side/rear photos; Vertiv VR and Rittal racks.
- kPa floor-loading figure, raised-floor tile size/open area, ceiling height requirements.
- Starline T5 800 A housing dimensions and default colour; ladder rack dimensions.
- Hot-aisle containment product dimensions (Contain-IT data sheet not downloaded); CRAH/fan-wall unit dimensions and colour.
- Motivair ChilledDoor official dimensions; Vertiv DCD dimensions (only unverified search summaries).
- Generic 1U/2U rack shelf specs.
- Photos of the exact Raritan SKUs, containment doors, and busway installed in a hall (vendor marketing pages blocked or image URLs not exposed).
