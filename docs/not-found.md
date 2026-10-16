# NOT FOUND register — every value the designs could not source, what we used, what to do

Scope: all three designs (`spec/superpod.yaml`, `spec/gb300-su.yaml`, `spec/superpod-mixed.yaml`).
Project rule: a value we cannot source is written as NOT FOUND with the estimate
used, never invented. This register gathers them from the reference packs ("Not found"
sections), `docs/design-choices.md`, `docs/ra-notes*.md` and `blender/README.md`, with
**Expected** = the range I would bet on from adjacent evidence, and **To do** = the cheapest
way to close it (a URL to open in a browser, a document to request, or a person to ask).
Date: 2026-10-01. Close a row by replacing the estimate in the file named under "Used in" and
deleting the row here.

## A. Cooling — Motivair / Schneider (mixed pod)

| # | Item | Used in | Estimate used | Expected | To do |
|---|---|---|---|---|---|
| A1 | ChilledDoor capacity vs water inlet temperature (curve) | spec rdhx `unit.kw: 30` at ≤ 18.3 °C; design-choices §7.2 | nominal 30 kW inside the printed 55–65 °F band only | ~22–26 kW at 20 °C and ~15 kW at 25 °C supply for an M8 at 24 °C room (capacity falls roughly linearly with air-to-water ΔT) | Motivair selection request via the Schneider rep: M8 48U/600, water 18/28 °C, room 24 °C / 50 % RH, 21.4 kW rack. Template: "Please run a ChilledDoor selection for 25 racks … and send the capacity-vs-EWT curve for the M8/M12." |
| A2 | ChilledDoor pressure drop at design flow | hydraulics not modelled | none; facility window 25–100 psi only | 0.3–1.0 bar at 30 l/min through a 1 in coil circuit | same request as A1 (ask for Δp at 30 and 50 l/min) |
| A3 | ChilledDoor dry / wet weight; external W × H | floor loading and the door asset (height assumed = rack 2258) | height = rack height; weight unmodelled | 90–130 kg dry, +15 kg wet for a 48U 600 (CL20 is 94/134 kg at a similar size) | same request; or the IOM PDF `Ch-Door-IOM-Rev-4.2.pdf` if Motivair re-hosts it (search "ChilledDoor IOM Rev 4.2 pdf") |
| A4 | ChilledDoor hinge side and open-door clearance | assets.build_door (hinge on the left seen from the rear), rear aisle 1,220 clear | CHOICE left; clearance ≥ door width | hinge side is ordered per rack (interface frame); clearance ≈ door width + 100 mm | ask Motivair which side the hose cut-out goes for an APC SX frame; read the IOM floor-cut-out drawing |
| A5 | ChilledDoor fan layout (positions) and LED strip | door asset (5 fans in a column) | column of 5 behind the mesh | 5 fans in one column is what the 2022 brochure photo suggests | brochure photo at higher resolution: https://www.motivaircorp.com/products/chilleddoor/ (open in a browser, save the hero image) |
| A6 | MCDU dry / wet weight (all models) | floor loading, slab | unmodelled | MCDU-40 ≈ 900–1,200 kg wet (Vertiv CoolChip 600 kW = 550 kg; MCDU-70 reseller 2,200 lb) | Motivair submittal drawings (ask with A1); se.com product pages once the Motivair range is listed there |
| A7 | MCDU rating at OUR conditions (10/15 °C primary; 18/28 and 35/50 °C secondary) | spec cdu.kw = R4 842.5 / 1,081 (lower bounds) | R4 column | MCDU-40 ≥ 842 kW (approach 8 K matches R4); MCDU-45 ≫ 1,081 kW at a 25 K approach (R1 prints 1,567) | A1 request (second paragraph); the 2026 brochure's R2 row is inconsistent — ask for a corrected sheet |
| A8 | MCDU pipe-connection standard, strainer mesh, noise for -45/-55/-70 | none | — | ANSI/Victaulic grooved; 1–2 mm strainer; 70–78 dBA | submittal drawings (A6) |
| A9 | Uniflair BCEF 0903A weight and panel colour | plant asset (#D6D6D2 est), slab | unmodelled; RAL 9022-ish | 7,500–9,000 kg (BREF 4812A at 1,183 kW is 9,893 kg) ; RAL 9022 | BCEF technical specification PDF (search "Uniflair BCEF technical specifications 990-" on se.com) |
| A10 | Uniflair XCA (1.2–2.5 MW) rating conditions, dimensions, weight | plant choice (design-choices §7.6-2) | not used | ~1.3–2.5 MW at 15/10 °C-class conditions; footprint ~12 × 2.4 m | se.com product page when published (ships June 2026): search "Uniflair XCA datasheet"; ask the Schneider rep |
| A11 | Schneider dry coolers as a product line | plant choice | BCEF free-cooling chiller used instead | none in the Uniflair catalogue (water-cooled chillers pair with third-party dry coolers) | confirm with the rep; otherwise keep BCEF |
| A12 | HDCV 4600A HT fan power; capacity at 10/15 °C water | plant load (0 kW added), CRAH sizing lower bound | 109.5 kW (20/30 °C) | ~115–125 kW net at 10/15 °C; fans 4–6 kW | Uniflair Room Cooling catalogue page 41 footnotes (the PDF is in reference/cooling-schneider/media/) + Schneider selection software (ask the rep) |
| A13 | InRow RC capacity vs water temperature; official weights | not used (CRAH chosen) | — | 70 kW at 7 °C falls to ~45 kW at 18 °C | only if InRow is reconsidered: se.com ACRC602 datasheet |
| A14 | Uniflair LE CW datasheet | not used | — | — | Arrow-hosted PDF timed out; try https://www.se.com/ww/en/product-range/… "Uniflair LE" in a browser |
| A15 | Motivair quick-disconnect brand, isolation-valve make, door-manifold dimensions | assets (generic valve/QD), hose BOM | generic | Stäubli SPC/UQD on NVIDIA racks; Motivair's own QDs on the door hoses; ball valves | ask Motivair; Stäubli UQD datasheet for the NVL72 side |
| A16 | EcoStruxure product name for CDU monitoring; NetBotz spot sensor model | not researched further | — | EcoStruxure IT Expert + NetBotz 750 (NBRK0750) with NBES0308 ropes | se.com NetBotz accessories page; ask the rep |
| A17 | Motivair water-quality limits (IOM table) | commissioning notes only | — | pH 7–9, conductivity limits, 25 % PG | IOM (A3) |
| A18 | Schneider RD loop temperatures, CDU placement, piping route, containment-with-RDHx guidance | design-choices §7.2–7.3 CHOICEs; reference-design notes §1 | CHOICEs recorded | RD 108/109: facility chilled water ~15–20 °C, TCS ~30–40 °C to the NVL72, in-row liquid-to-liquid CDUs, overhead piping, hot-aisle containment optional | se.com login → download RD 108, RD 109 and the GB300 RD |
| A19 | A Schneider/NVIDIA RD for the air-cooled DGX SuperPOD H100/H200 (with RDHx) | containment decision §7.3 | none | exists on se.com as an older "DGX SuperPOD" reference design (2023) | same login; search the RD library for "SuperPOD" |
| A20 | BS 1710:2014 general Table 1 code colour for chilled water | pipe bands (blue supply / red return CHOICE) | green basic only claimed | general table: white / emerald-green / white code band for chilled water (1984 edition); 2014 revised | buy or borrow BS 1710:2014 (BSI shop link in the reference-design notes §3) |

## B. NVIDIA DGX GB300 NVL72 geometry (gb300-su, mixed)

| # | Item | Used in | Estimate used | Expected | To do |
|---|---|---|---|---|---|
| B1 | NVIDIA's own TCS supply/return temperature and flow for DGX GB300 | spec dlc 35/50 °C | Lenovo GB300 water table (35 °C → ≥ 89 L/min) | NVIDIA allows up to 45 °C supply; typical design 30–40 °C, ΔT 15–20 K | NVIDIA DGX GB300 site-prep / data-centre design guide (docs.nvidia.com, HTML pages 404 on 2026-09-30 — retry; or NVIDIA partner portal) |
| B2 | DGX-branded tray / NVLink tray / power-shelf mm and weights | device-library (Lenovo values) | Lenovo 438 × 43.6 × 766/770/718.5 mm | identical (same MGX ODM family) | NVIDIA DGX GB300 datasheet PDF (resources.nvidia.com — login/JS) |
| B3 | Absolute U numbers of shelves/trays/switch trays; RU1 height; tray flange set-back; busbar W × D; manifold pipe Ø; QD part number | ra-notes-gb300 C.1 (elevation CHOICE), assets | SX rules, strips est | shelves U2–5 & U33–36 style layout is right; busbar ~36 × 60 mm; manifold DN25–32; UQD04/UQDB04 | OCP "MGX Accelerated Computing Rack and Trays Specification 1.1" (403 to curl → browser, prompt gb300-su/04) |
| B4 | Wet vs dry rack weight (≈1,580 kg one figure) | floor loading | — | ~1,450 kg dry / 1,580 wet | Lenovo LUG environmental section; NVIDIA datasheet |
| B5 | Any rear-door HX option for NVL72 | residual-air CHOICE (CRAH) | none | none exists (rear carries the 132 mm extension and manifolds) | confirm with the NVIDIA/Schneider rep; keep CRAH |
| B6 | Q3400-RD = Q3401-RD (naming), typical power; SN5600/SN5600D max power, noise, airflow | catalog Q3400-RD (3.6 kW CHOICE), SN5600 (1.5 kW) | inference | Q3401-RD typical ~3.0–3.5 kW; SN5600 max ~1.2–1.5 kW, P2C/C2P variants | NVIDIA networking docs "Specifications" pages (networking-docs.nvidia.com) — the power rows exist for Q3400-RA; ask NVIDIA for the -RD typical |
| B7 | Lenovo "Detailed dimensions" table (Xa–Ze) mapping | not used | — | enclosure drawing of the rack with the extension | Lenovo LP2357 figure next to Table 26 — open the PDF at the figure |

## C. DGX H200 SuperPOD (dgx-lab-01)

| # | Item | Used in | Estimate used | Expected | To do |
|---|---|---|---|---|---|
| C1 | Exact rPDU SKU spec PX3-5878I2R-P1Q2R1A15D5 (RA Table 7) | catalog stand-in PX3-5730-V2; design-choices §6.1 | vertical 0U stand-in | horizontal 3U, 18 C19 + 6 C13, 60 A inlet (the -Q1 sibling) | Raritan product selector with the option string; prompt h200-superpod/01 |
| C2 | DDN AI400X2T power, envelope, write bandwidth | catalog (DCG storage example 3,600 W; AI400X3 chassis) | 2,880/3,600 W; 446 × 87 × 856 | 2.4–3.0 kW; same 2U chassis; ~65 GB/s write per unit (DDN H100 RA) | DDN datasheet behind a form: https://www.ddn.com (request) ; prompt h200-superpod/02 |
| C3 | VAST CBox dimensions, PSU rating; VAST press kit | catalog (440 × 87 × 800; 2 × 1,300 W CHOICE) | generic 2U | 2U 4-node; 2 × 1,600 W | VAST Data documentation portal (login) |
| C4 | UFM 3.1 rear layout; Dell R750 (not in packs) | assets (generic rear) | generic | R750 rear: 2 PSUs, OCP NIC, 2 risers | NVIDIA UFM appliance HW manual (rear figure); Dell R750 spec sheet |
| C5 | APC AR3307B2 door open-area %, rear/side photos | rack asset (no doors) | doors removed per DCG | ~72–80 % | se.com AR3307B2 page in a browser (403 to curl) |
| C6 | Starline T5 800 A housing size and finish; ladder rack width; raised-floor tile size; CRAH fan-wall dimensions | overhead/room assets (250 A section, 300 mm ladder, slab floor, 2.2 m wall) | estimates | 800 A ≈ 150 × 180 mm; ladder 300–450 mm; 600 mm tiles | Starline T5 catalogue PDF (starlinepower.com), Legrand Cablofil; Vertiv CWA brochure |
| C7 | Floor-loading kPa, ceiling height | none | — | ≥ 12 kPa; ≥ 4 m clear | DCG has none; take from the building |
| C8 | C-feed colour convention (third power path) | render (green CHOICE) | green | no standard | keep CHOICE |
| C9 | Perforated-tile / containment product dimensions (Contain-IT) | containment asset | generic | 1,200 mm modules | Legrand Contain-IT Flex datasheet |

## D. Workflow and brand

| # | Item | Used in | Estimate used | Expected | To do |
|---|---|---|---|---|---|
| D1 | NVIDIA / DDN / VAST / Raritan logo usage permission | renders with `--brand` only | off by default | partner approval needed | NVIDIA partner brand portal; vendor press kits (reference/brand-and-3d/README.md) |
| D2 | Free DGX H100/H200/GB300 3D models in an open licence | procedural assets | none | none exist; SimReady NVL72 under an evaluation licence only | keep procedural |
| D3 | DGX H200 acoustic noise; CPU TDP; fan CFM per module | none | — | > 98 dB(A) at 1 m (DCG); 350 W | NVIDIA UG; Intel ark |
