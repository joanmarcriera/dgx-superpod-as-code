# Reference packs — DGX H200 SuperPOD

Public-source material gathered on 2026-09-30 to (a) back every sizing and colour choice in
`spec/` and (b) feed the Blender render (`blender/`). Each pack has:

- `README.md`: facts tables (value · unit · source URL · quote), "Blender modelling notes"
  (dimensions, front/rear layout as fractions, materials, estimated hex colours) and a
  "Not found" list. Numbers are quoted, or marked DERIVED / ESTIMATE, never invented.
- `SOURCES.csv`: one row per downloaded file: `path,url,publisher,kind,terms,retrieved`.
- `media/`: the files themselves. **Not committed** (third-party copyright/trademark;
  not redistributed here). Rebuild on another machine with `python3 reference/fetch.py`.

| Pack | What's in it | Media |
|---|---|---|
| [compute-dgx-h200](compute-dgx-h200/README.md) | DGX H200: 8U 482.3×356×897.1 mm, 130.45 kg, 10.2 kW, 6 × 3.3 kW PSU (4+2), 12 front fans, 1,105 CFM; H200 141 GB/4.8 TB/s; 2 × Xeon 8480C; front/rear layout to ±2 %; LEDs | 12 files, 20 MB (UG figures, bezel texture, datasheet, RA PDF) |
| [network](network/README.md) | QM9700 1U 64×400G (1,720 W max), SN4600C 2U, SN2201 1U, UFM 3.1 1U; twin-port OSFP optics; MFP7E10 aqua fibre + green MPO/APC; cabling and colour evidence (NVIDIA: no per-fabric scheme) | 22 files, 41 MB (renders, 12 PDFs incl. cabling design guide) |
| [storage](storage/README.md) | NVIDIA's 7 certified SuperPOD storage partners; NVIDIA performance tiers (RA Table 5.2); DDN AI400X2T/X3 and VAST Ceres deep dives; 2-SU counts with arithmetic | 11 files, 11 MB (RAs, DDN/VAST images, logos) |
| [facility](facility/README.md) | DCG hall rules (cold aisle ≥ 1,219 mm, containment, 157 CFM/kW, 18–27 °C inlet), APC 48U 600×1200×2258 racks, Raritan PDUs, IEC 60309, A/B feed colours, RDHx/CDU (not needed for H200), busway, raceways | 41 files, 36 MB (DCG PDF + figures, spec sheets, CC photos) |
| [brand-and-3d](brand-and-3d/README.md) | Logos + trademark terms, NVIDIA switch Visio stencils, CC-BY/CC0 3D models, Poly Haven HDRIs, CC0 PBR textures, Omniverse SimReady verdict (GB300 only, eval licence) | 54 files, 56 MB |
| [workload](workload/README.md) | H200 vs H100, MLPerf training/inference, training-days and checkpoint arithmetic for 504 GPUs, power/energy, buyer profiles | — |

**Trademark caution.** NVIDIA, DGX, DDN, VAST and Raritan logos need the owner's
permission for use in published material (see brand-and-3d/README.md). Renders may show product
geometry; keep logos off published renders unless approved.
