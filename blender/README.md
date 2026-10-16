# Blender render — DGX H200 SuperPOD (2 SU, 63 × DGX H200, 504 GPUs)

Photoreal renders of the design in this repo, built by script from `docs/scene.json`. That file is
the same model as NetBox and `docs/superpod.drawio`, so a spec change re-renders correctly. No rack
or device position is hard-coded.

```bash
# 1. build the .blend (≈2 s), verify it, save blender/out/superpod.blend
blender -b -P blender/build_scene.py -- [--brand] [--hero dgx-su1-r01,mgmt-r01,stor-r01,stor-r02]

# 2. render (Cycles, Metal GPU, AgX, OIDN) to blender/out/<shot>.png
blender -b -P blender/render.py -- --quality draft            # 1280×720 @ 64 spp, ~5 s/shot
blender -b -P blender/render.py -- --quality final            # 3840×2160 @ 256 spp (product 4096²)
blender -b -P blender/render.py -- --shots a,c --samples 128  # subset / override

# 3. publish the finals (JPEG q90, committed)
for s in a_hero b_hotaisle c_fabric d_storage e_overview f_product; do
  sips -s format jpeg -s formatOptions 90 blender/out/$s.png --out docs/renders/$s.jpg; done
uv run pytest tests/test_blender_layout.py                     # offline geometry tests (no bpy)
```

`blender/out/` is gitignored. You need Blender ≥ 5.2. The Poly Haven floor texture comes from
`reference/brand-and-3d/media/` (rebuild with `python3 reference/fetch.py`); without it the
floor falls back to a procedural material. PyYAML is loaded from the repo `.venv` because
Blender's bundled Python doesn't ship it.

## Shots

| | File | What it shows | Final time (M5 Pro, 16-core GPU) |
|---|---|---|---|
| a | `a_hero` | The row-A cold aisle from its entrance at 1.6 m, 24 mm: DGX H200 champagne/metal-foam fronts receding, blanked U, mgmt/storage racks mid-row, overhead busways, raceway and ladder, CRAH fan wall at the far end | 2 min 50 s |
| b | `b_hotaisle` | Inside the contained hot aisle: DGX rears (hex GPU-tray grilles, PSUs), A/B/C cords in red/blue/green to the 0U rPDUs, aqua fibre lanes, acrylic roof and end doors | 2 min 21 s |
| c | `c_fabric` | `mgmt-r01` front: 8 rail leaves + 4 spines (QM9700, every cage populated), with twin-OSFP transceivers, green MPO shells and rail-coloured labels. `ufm-c-01` sits below them. `mgmt-r03` (in-band) is on the left | 2 min 30 s |
| d | `d_storage` | Split frame. Left: `stor-r01`, 4 × DDN AI400X2T (tier 1, storage IB). Right: `stor-r02`, 2 backend switches with black DAC, 5 VAST CBox and 4 Ceres DBox (tier 2, Ethernet) | 2 min 1 s (two halves) |
| e | `e_overview` | Orthographic top-down floor plan, same orientation as the draw.io plan (row A at the top facing up). Rack names are painted on the roofs; overhead paths are hidden so the racks show | 40 s |
| f | `f_product` | One DGX H200, bezel on, 3/4 front, studio three-point light on a dark cyclorama (4096²) | 1 min 58 s |

Why is d a split frame? The DDN and VAST racks sit **back to back** across the hot aisle
(`stor-r01` in row A, `stor-r02` in row B, `docs/design-choices.md` §3). No single real
viewpoint sees both fronts, so each half uses its own camera.

## How it is built

- `superpod/layout.py` is pure Python and unit-tested. It holds the rack-local frames (from
  `origin` and `facing`), device envelopes (from the library W×H×D), 0U PDU placement, per-type
  port maps (from the reference fractions), PSU-to-rPDU assignment and bundle routing. A bundle
  goes rack roof → row raceway (fibre) or ladder (copper) → hot-aisle crossover at the
  mid-row block → rack roof.
- `superpod/assets.py` models each device type **once** as a collection and places it as
  collection instances (63 DGX, 108 PDUs, 1,231 blanking panels, …). Transceivers and plugs
  belong to the asset: there is one variant per distinct cabled-port set, 17 in total.
- `superpod/hall.py` builds the racks, overhead (3 Starline busways per row with a tap-off per
  rPDU, yellow raceway, black ladder, crossovers), the containment, CRAH fan walls, LED
  fixtures with matching area lights, and all cables:
  - 138 inter-rack bundles as swept tubes, radius ∝ √count, with tie bands every 300 mm.
    Compute bundles get one band per rail they carry.
  - Individual cables in the hero racks.
  - Short tails plus a dressed lane bundle in the other racks.
  - 422 colour-coded power cords.
- `build_scene.py` checks the build and **exits 1** when:
  - an instance count doesn't match `scene.json`;
  - any device intersects another or leaves its rack. This is checked on the built geometry:
    asset chassis bounds × instance transform;
  - a built chassis drifts > 3 mm from its library envelope.

## Accurate vs simplified

**From the model (accurate):**
- Rack count, order, facing and aisle widths.
- Every device's type and U position, with 2 DGX per rack at U3/U14.
- PDU sides and feeds.
- Every cable bundle's endpoints, count, jacket and tie colour.
- Rail colours (Okabe-Ito, same as draw.io) and A/B/C power colours.

**From the reference packs (±0.02 of face size):** DGX front and rear layout, QM9700 cage
blocks, SN4600C/SN2201 port fields, DBox bays/fans, DDN oval bezel, rPDU envelope.

**Simplified or chosen for the render:**

| What | Choice | Why |
|---|---|---|
| Per-port cabling | Switch fill by role: compute IB 100 %, storage IB 75 %, in-band 50 %, OOB 80 % of RJ45 | `scene.json` bundles are per rack pair, not per port |
| Non-hero racks | Tails into a lane bundle instead of every cable to the roof | Poly budget; the hero racks carry the detail |
| DAC jacket (VAST backend) | Black, overriding `scene.json`'s aqua for `storage-eth` | A passive DAC is copper. `design-choices.md` §4 also says black; the exporter's colour looks like an oversight |
| 0U rPDUs | Rear corners, outlets facing the hot aisle. The 2nd PDU on a side (`slot` 1) sits inboard of the 1st. Cords route round the inboard edge to the outlets | Three 109 mm PDUs in a 600 mm rack can't all sit outside the 19" field. They cover part of each DGX rear, which is realistic. See the open rPDU question in design-choices §6.1 |
| Front rail plane | 100 mm behind the rack front | AR3307B2 rails are adjustable; not in `scene.json` |
| Overhead heights | Busway 2.56 m, raceway 2.60 m (y +0.05 of rack centre), ladder 2.92 m, ceiling 4.0 m, LED fixtures 3.3 m | DCG shows overhead paths but no heights |
| Room | 1.8 m walkway beyond each cold aisle; CRAH fan walls 0.9 m deep × 2.2 m high, 0.9 m from the row ends | CRAH size is NOT FOUND in the packs |
| DGX logo pad | Plain champagne pad; `--brand` adds the NVIDIA wordmark (and the DDN logo) | Trademarks |
| Metal foam | Voronoi distance-to-edge (two scales) driving colour, metalness and true displacement on a 1.6 mm grid | Procedural as briefed. Individual cells are slightly under-resolved in the 4K product close-up; the bump covers it |
| Hex grilles, perforations | Procedural hex-lattice mask (shader), not geometry | Keeps the poly count sane |

## Data gaps (library `NOT FOUND` / unverified) and the guesses used

- **VAST CBox**: dimensions not published, so the library CHOICE of 440 × 87 × 800 mm is used.
  The front is modelled as a generic 4-sled 2U. No image was found.
- **DDN AI400X2T**: no published envelope, so the AI400X3 chassis (446 × 87 × 856) is used.
- **UFM Enterprise Appliance 3.1**: no rear image was found. The rear is modelled as a generic
  1U with 2 OSFP cards + RJ45.
- **Dell R750**: the envelope is Dell's spec (not in the packs). The front is a plain honeycomb
  bezel.
- **CRAH / fan wall**: dimensions not found. A 2.2 m block with a 2×3 fan grid is used.
- **Ladder-rack width**: not found; 300 mm is used. **Starline T5 800 A section**: not found; the
  250 A section (111 × 128) is used.
- **Floor tile size**: not found. The floor is modelled as a painted slab (no raised floor).
- **rPDU**: modelled on the PX3-5747V-V2 envelope, standing in for the PX3-5730-V2 slug.

---

# Mixed pod — DGX H200 SU + DGX GB300 NVL72 SU, Schneider liquid cooling (site dgx-lab-03)

The same pipeline builds the third design from `docs/dgx-superpod-mixed/scene.json` (exported
by `bin/dgxnb export --spec spec/superpod-mixed.yaml`). Nothing about the mix is hard-coded:
rack kinds, doors, manifolds, CDUs, CRAHs, plant modules, headers and hoses all come from the
scene's `racks[*].cooling` and `cooling` sections.

```bash
blender -b -P blender/build_scene.py -- --scene docs/dgx-superpod-mixed/scene.json \
    --out blender/out/superpod-mixed.blend                     # ≈5 s, verifies, exits 1 on error
blender -b -P blender/render.py -- --quality final --shots a,b,c,d,e,f,g,h,i,j \
    --blend blender/out/superpod-mixed.blend --scene docs/dgx-superpod-mixed/scene.json \
    --out blender/out/mixed
for s in a_hero b_hotaisle c_fabric d_storage e_overview f_product g_rowb h_cdu i_rearaisle j_plant; do
  sips -s format jpeg -s formatOptions 90 blender/out/mixed/$s.png --out docs/renders/mixed/$s.jpg; done
uv run pytest tests/test_blender_mixed.py tests/test_trace_core.py            # pure parts
blender -b blender/out/superpod-mixed.blend --python tests/blender/test_trace.py -- --out docs/renders/mixed
```

## Extra shots

| | File | What it shows |
|---|---|---|
| g | `g_rowb` | Row-B cold aisle at eye height: 8 NVL72 fronts (champagne compute / NVLink trays, black power shelves, two TOR SN2201 in a shroud), the 4 GB300 management racks mid-row, the CDU block at the end |
| h | `h_cdu` | The CDU block from the row-B cold aisle: 2 × MCDU-40 (RDHx loop) + 2 × MCDU-45 (DLC loop), their secondary drops to the loop headers and primary drops to the FWS mains |
| i | `i_rearaisle` | Inside the uncontained rear aisle: ChilledDoors (stainless control strip, 5 EC fans, HMI) on row A, NVL72 rears with manifolds and red/blue QDs on row B, headers with colour bands and flow arrows, branch valves, drip trays, flex hoses to every door and manifold, the leak ropes |
| j | `j_plant` | Outside the pipe wall: 3 × Uniflair BCEF 0903A on their slab, FWS mains through the sleeved wall |

## New assets (one collection each, instanced)

NVL72 MGX rack (600 × 2236 × 1068 + 132 mm extension; busbar cover, 4 cable cartridges,
rear bezel fingers, wedge plinth) · GB300 compute tray · NVLink switch tray · 33 kW power
shelf · Q3400-RD (72 twin OSFP cages, FNM cage) · SN5600 (64 cages) · Motivair ChilledDoor M8
(363 mm deep, hinge on the left seen from the rear — CHOICE, side NOT FOUND; latch-side
stainless door; coil + 5 fans; top hose stubs; C14 fan inlet) · NVL72 coolant manifolds (two
stainless strips, 27 QD pairs, FD83 top fittings) · MCDU-40 / MCDU-45 cabinets · HDCV 4600A
HT CRAH · BCEF 0903A module (14 roof fans, louvred coil flanks). Face fractions and
dimensions: `docs/blender/device-library.yaml` → `reference/compute-dgx-gb300`,
`reference/cooling-schneider`.

## Verification added for the mix

Counts of doors, manifolds, CDUs, CRAHs and plant modules; no clash between racks (with their
doors), units and the overhead pipes; every hose ends within 5 mm of its socket; exactly one
connected pipe network per loop plus one for the facility water (the CDU heat exchangers are
the boundaries); rear-aisle clearance ≥ the door swing. The H200 scene still builds and
verifies with the same code (`blender -b -P blender/build_scene.py --`).

## Simplifications specific to the mix

| What | Choice | Why |
|---|---|---|
| Header routing | one supply/return pair per row and loop at 3.30 m, 460 / 610 mm behind the rear face, the DLC pair 300 mm further out; FWS mains at 3.55 m over the rear-aisle centre | CHOICE (design-choices §7.2); clears the 363 mm doors and the overhead power/fibre paths |
| Branch | tee → isolation valve 350 mm below → rigid drop → 1 in flex hose into the top of the door / the FD83 fitting of the manifold; drip tray under each valve pair | Motivair hoses/manifold page; valve make NOT FOUND |
| CDU / CRAH / plant connections | top stubs (CDU: "top or bottom"), CRAH top, plant low-level flank | positions NOT FOUND; stubs are where the drops land |
| Door fans | drawn as hub + 7 blades + guard rings behind the mesh | fan layout NOT FOUND (count/power are cited) |
| Plant | panel box with 14 roof fans and louvred coil flanks; outdoor slab + ground | photo-level only; weight NOT FOUND |
| NVL72 rails / tray set-back | the SX rule (100 mm) | flange set-back NOT FOUND |
| Containment | none (spec `hall.containment: none`) | design-choices §7.3 |

# Tracing (add-on `blender/addon/dgx_trace`)

Install once: `blender --python blender/addon/install.py` (symlinks the folder into the user
add-ons directory and enables it), or Preferences ▸ Add-ons ▸ Install from the folder. The
add-on needs only a `.blend` written by `build_scene.py`: every object carries `dgx_kind`,
`dgx_a`, `dgx_b`, `dgx_fabric`, `dgx_loop`, `dgx_rack` (and `dgx_labels` on bundles), and the
text datablock `dgx_links.json` holds the links table, the cooling graph, the rack frames and
the device library.

**Panel** — 3D viewport ▸ sidebar (N) ▸ **DGX**:

- *Active-object card*: name, kind, rack, role/type, peak kW, loop; for a cable/bundle/pipe its
  two ends and fabric, for a bundle how many cables it carries.
- *Auto-trace*: re-traces whenever the active object changes (msgbus on `LayerObjects.active`).
- *Mode* — **Highlight**: traced objects are selected (outline in every shading mode) and
  coloured by fabric / kind through their object colour; everything else turns into a dim
  wireframe (`display_type = WIRE`), which works in Solid and in Material Preview (set Solid
  shading colour to *Object* to see the fabric colours). **Isolate**: everything else is hidden.
- *Depth* — **Direct only**: the object's own cables, cords and hoses. **Follow**: bundles to
  their far-end racks and devices; hoses → branch → header → CDU → facility-water mains → plant.
- *Fabric filters*: compute IB, storage IB (incl. the VAST backend), in-band, OOB (incl. UFM HA),
  NVLink, power, coolant supply, coolant return.
- *Build per-port cables*: one curve per link of the active device from its port tip to the
  far-end port tip (via the row trays, `layout.py` port maps), in a `Trace` collection with a
  far-end label — a 64-port leaf fans out to its 32 nodes and spines.
- *Clear*: restores colours, display types, visibility and selection, drops the `Trace` collection.

**What the rules give** (checked headlessly by `tests/blender/test_trace.py`, six devices):

| Selected | Shown |
|---|---|
| QM9700 leaf `ibc-su1-leaf-r1` | its 32 node + 32 spine links' far ends, the 17 bundles that carry them, their racks; its OOB link; its rack's door and coolant path |
| DGX `dgx-su1-n01` | 8 compute + 2 storage + 2 in-band + 1 OOB far ends and 4 bundles, 6 power cords to the rPDUs, its door → hoses → branch → header → both RDHx CDUs → FWS mains → the 3 plant modules |
| GB300 tray `gb-su1-r01-t01` | 4 XDR leaves, 2 Ethernet leaves, the in-rack OOB switch, the 9 NVLink switch trays, 4 bundles, the rack manifold → DLC CDUs → plant |
| CDU `cdu-dlc-01` / `cdu-rdhx-01` | its primary and secondary drops, the loop header(s), every door/manifold and rack on the loop with their hoses, the other CDU, the FWS mains and plant |
| Door `gb-mgmt-r01-rdhx` | its fan cord, hoses, branch, header, CDUs, mains, plant |

`docs/renders/mixed/trace-*.png` are Workbench renders of those traced states (Isolate mode,
object colours): headless Blender has no viewport screenshot.

**Limits.** Per-port positions are the render's port-fill CHOICE, not NetBox's: the i-th link of
a fabric takes the i-th drawn port of that fabric (NetBox holds the real port names). Bundles
are per rack pair and fabric, so Follow lights the whole bundle the device's cables ride in.
The DC-core demarc has no 3D object, so uplinks to it show no far end. NVLink links are
in-rack blind-mate (no cable object); Follow shows the switch trays. Dimming in Material
Preview relies on wireframe display, not on object colour.
