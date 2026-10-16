# Brand, icon and 3D asset pack (retrieved 2026-09-30)

Public sources only. Per-file terms are in `SOURCES.csv`. Media total about 56 MB (54 files). Where a licence was not found it says "unclear - do not redistribute".

## Logos
| Asset | Format | License/terms | Size | Source URL | Notes |
|---|---|---|---|---|---|
| media/logos/nvidia.svg | SVG | simple-icons CC0 for the file; NVIDIA trademark applies | 0.9 KB | https://github.com/simple-icons/simple-icons | Simple mono glyph+wordmark |
| media/logos/wikimedia_nvidia_logo.svg | SVG | Commons "public domain" + trademarked | 3 KB | https://commons.wikimedia.org/wiki/File:Nvidia_logo.svg | Old-style logo; verify it is the current one before use |
| media/logos/wikimedia_NVIDIA_logo_apache.svg | SVG | Commons "Apache-2.0" + trademarked | 4 KB | https://commons.wikimedia.org/wiki/File:NVIDIA_logo.svg | Colour logo |
| media/logos/wikimedia_VAST_Data_logo.svg | SVG | Commons "public domain" + trademarked; unclear - do not redistribute | 4 KB | https://commons.wikimedia.org/wiki/File:VAST_Data_logo.svg | Prefer VAST official press kit for client use |
| media/logos/wikimedia_Legrand_SA_logo.svg | SVG | Commons "public domain" + trademarked; unclear - do not redistribute | 4 KB | https://commons.wikimedia.org/wiki/File:Logo_Legrand_SA.svg | Legrand parent, NOT Raritan |
| DDN logo (not downloaded) | SVG/PNG/JPEG | Official page; terms unclear - do not redistribute | - | https://www.ddn.com/company/brand-assets/ | Links are JS-loaded; download by browser; contact brand@ddn.com |
| NVIDIA brand guidelines | web/PDF | Every use needs NVIDIA written approval | - | https://www.nvidia.com/en-us/about-nvidia/legal-info/logo-brand-usage/ | Partner PDF: https://www.nvidia.com/content/dam/en-zz/Solutions/about-us/NVIDIA-Brand-Guidelines-for-NVIDIA-Partner-Network-v03-3-5-19.pdf |

## Icons / stencils
| Asset | Format | License/terms | Size | Source URL | Notes |
|---|---|---|---|---|---|
| media/icons/nvidia_visio/QM97X0.vssx | Visio | Free on NVIDIA site; no licence text found - unclear - do not redistribute | 1.8 MB | https://developer.nvidia.com/networking/visio-stencils | Quantum-2 QM9700/9790 |
| .../SN4600C_Stencils.vssx, SN4600_Stencils.vssx | Visio | same | 2.2 / 2.6 MB | same page | Spectrum-3 SN4600C / SN4600 |
| .../SN2201_Stencils.vssx | Visio | same | 8.7 MB | same page | OOB 1G switch |
| .../SN5600_Stencils.vssx | Visio | same | 2.5 MB | same page | extra |
| media/icons/drawio/Sidebar-Rack.js | JS | Apache-2.0 | small | https://github.com/jgraph/drawio | draw.io built-in Rack libraries (Rack/General, Cisco etc.); no NVIDIA shapes in it |
| DGX H200 stencils (not bought) | Visio | Paid subscription; price not published (Sales@VisioStencils.com) | - | https://www.visiostencils.com/product/products/Nvidia.html | EQIDs NVID142 H200, NVID143 H100, NVID144 bezel, NVID145 controller card; also DGX B200/B300 |
| Lenovo / Dell stencils (not downloaded) | Visio | Free via VisioCafe; terms not reviewed | - | https://lenovopress.lenovo.com/lp1599-visio-stencils , http://www.visiocafe.com/dell.htm | For comparison only |

Not usable directly in draw.io: .vssx are Visio only. draw.io can IMPORT .vssx (File > Import) and keep the shapes as images; open one and copy shapes into a custom library. jgraph/drawio-libs (Apache-2.0) has no NVIDIA/Mellanox set (arista, fortinet, tp-link, etc. only).

## 3D, HDRI, textures
| Asset | Format | License/terms | Size | Source URL | Notes |
|---|---|---|---|---|---|
| media/3d/polypizza_server_rack_JeremyEyring.glb | glb | CC-BY 3.0, credit Jeremy Eyring | 1.8 MB | https://poly.pizza/m/6ijQclm8jxw | 17 meshes, generic server rack + console; low fidelity starting point |
| media/3d/polypizza_computer_room_BrunoOliveira.glb | glb | CC-BY 3.0, credit Bruno Oliveira | 2.4 MB | https://poly.pizza/m/cA_lcvRC4NA | 670 meshes room with racks; obj2gltf export, check scale |
| media/3d/polyhaven_modular_electric_cables_1k.blend | blend (zstd) | CC0, Kuutti Siitonen | 0.9 MB | https://polyhaven.com/a/modular_electric_cables | Cable run pieces |
| media/hdri/empty_warehouse_01_2k.hdr | HDR | CC0, Sergej Majboroda | 6.6 MB | https://polyhaven.com/a/empty_warehouse_01 | Best data-hall proxy: flat overhead artificial light |
| media/hdri/small_hangar_01_2k.hdr | HDR | CC0, Sergej Majboroda | 6.7 MB | https://polyhaven.com/a/small_hangar_01 | Alternative |
| media/textures/polyhaven_concrete_floor_painted/ | jpg/png 1K | CC0, Rob Tuytel | ~3 MB | https://polyhaven.com/a/concrete_floor_painted | Painted floor (diff, arm, nor_gl, disp) |
| media/textures/ambientcg_Metal009_1K-JPG/ | jpg+blend+usdc | CC0 | ~4 MB | https://ambientcg.com/a/Metal009 | Brushed metal (aluminium proxy) |
| media/textures/ambientcg_SheetMetal001_1K-JPG/ | same | CC0 | ~6.5 MB | https://ambientcg.com/a/SheetMetal001 | Perforated metal, has Opacity map |
| media/textures/ambientcg_Plastic012B_1K-JPG/ | same | CC0 | ~6.5 MB | https://ambientcg.com/a/Plastic012B | Black scratched plastic/powder-coat proxy |

### Omniverse / SimReady verdict (documented, not downloaded)
- `dsx_dataset` (Omniverse DSX Blueprint for AI Factories, v2.1, 32.69 GB, far over the 200 MB limit): https://catalog.ngc.nvidia.com/orgs/nvidia/omniverse/resources/dsx_dataset/-
  Fetch: `ngc registry resource download-version "nvidia/omniverse/dsx_dataset:2.1"` (command inferred from the NGC resource path; confirm the version tag on the page; needs a free NGC API key).
- Contents documented: SimReady OpenUSD assets for the **DGX GB300 NVL72 rack** and the **Vertiv XDU2300 CDU**, plus GB200/GB300 NVL72 sample compute configurations. **No DGX H100/H200, QM9700, SN4600C or Raritan assets are documented.**
- Licence: NVIDIA Sample Data License for Evaluation, "demonstration, not for production". Repo: NVIDIA Software License Agreement + Omniverse product terms. Treat as internal evaluation; not for published renders or redistribution without reading the licence.
- Blender: NVIDIA docs do not mention Blender. Blender's USD importer reads UsdPreviewSurface/basic geometry but NVIDIA SimReady uses payloads, variants, MDL/OmniPBR materials and references; expect to re-do materials and possibly flatten the stage first (`usdcat --flatten`). Unverified.
- NVIDIA also publishes PhysicalAI-SimReady-Materials (1,705 MaterialX/OpenPBR materials): https://github.com/NVIDIA-Omniverse/PhysicalAI-SimReady-Materials (licence not checked).

## Trademark caution
- **Do not redistribute:** all NVIDIA Visio stencils (no licence text found), the Wikimedia-sourced logos (copyright-free tag does not cancel the trademark), DSX dataset (evaluation licence), anything marked "unclear".
- **Published renders and decks:** NVIDIA, DGX, InfiniBand, Quantum and Spectrum marks all need NVIDIA written approval under its guidelines (no recolour, clear space, no implied endorsement). Safe practice: name products in plain text, use an approved co-brand logo only after permission, and get DDN/VAST/Raritan logos from each vendor's own press kit with terms. Product renders that show the NVIDIA bezel or logo are also trademark use. Credit CC-BY items (Eyring, Oliveira). CC0 items (Poly Haven, ambientCG) need no credit.

## How to use in Blender
- **glb/gltf:** File > Import > glTF 2.0. glTF is metres, Y-up; importer converts to Z-up. Check the rack is about 2.2 m tall (42U = 1.91 m inside) and set Scene Units to Metric, unit scale 1.0. Apply scale (Ctrl+A) before modifiers.
- **.blend (zstd):** Blender 3.0+ reads it; use File > Append > Object/Collection.
- **USD/USDC/USDZ:** File > Import > Universal Scene Description (Blender 4+). Scale follows `metersPerUnit`; check the stage value. MDL/OmniPBR materials are not converted, so rebuild with Principled BSDF.
- **HDRI:** World > Color > Environment Texture > the .hdr; 2K is enough for lighting. Strength 0.5 to 1.5; rotate with a Mapping node. Hide background from camera with a Light Path node if using area lights for the hot aisle.
- **Textures:** add Image Texture nodes: Color (sRGB) > Base Color; Roughness/Metalness/ARM (Non-Color); use **NormalGL** with a Normal Map node (Blender is OpenGL); Displacement via Bump or a Displacement node. For ambientCG the bundled `.blend` already has a material you can Append. Perforated metal: wire Opacity to Alpha or use as a Mix Shader factor. Brushed aluminium: Metalness 1, anisotropic 0.4 with a tangent.
- **Polycount:** the 670-mesh room is for layout reference; build DGX/QM9700 as simple boxes with bevels and apply the bezel as a texture.

## Not found
- Free NVIDIA logo SVG directly from NVIDIA (permission required) and DGX / Quantum / InfiniBand product logos.
- Raritan-specific logo (only Legrand parent on Commons); Raritan/Legrand brand usage terms.
- DDN direct SVG link (page is JS-rendered) and VAST Data official press kit (search surfaced vast.ai, a different company, not VAST Data).
- Free DGX H100/H200 3D model in any open licence; Sketchfab CC-BY racks exist (for example https://sketchfab.com/3d-models/none-01b49d9d1f694ba5b41e4b2b0e10d16e by EntropyNine, 27k faces; https://sketchfab.com/3d-models/none-d51a1a12281a416398e8a72988cb03f9 by urbanmasque) but download needs a login/API token, so none fetched. BlenderKit and CGTrader/GrabCAD not attempted (login required).
- NVIDIA-published VisioCafe/drawio NVIDIA shape library (none exists in jgraph/drawio-libs).
- Poly Haven has no brushed aluminium or perforated metal (ambientCG used instead).
