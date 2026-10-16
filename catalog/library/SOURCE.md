# Vendored device types

Copied verbatim from netbox-community/devicetype-library (CC0-1.0) at commit
`0451a7c5977351e7a43fbff54eb44f26ed85344f` (2026-09-29). Do not edit these files;
local fixes live in `../patches/<slug>.yaml` so the upstream copy stays diffable.

| File | Upstream path | Patched? |
|---|---|---|
| QM9700.yaml | device-types/Nvidia/QM9700.yaml | yes — missing P22.1/P23.0, mgmt port, PSU power ports |
| SN4600C.yml | device-types/Mellanox/SN4600C.yml | yes — PSU maximum_draw |
| SN2201.yaml | device-types/Nvidia/SN2201.yaml | yes — eth0 mgmt_only, PSU power ports |
| PowerEdge-R750.yml | device-types/Dell/PowerEdge-R750.yml | yes — PSU power ports, ConnectX-7 VPI ports |
| PX3-5730-V2.yaml | device-types/Raritan/PX3-5730-V2.yaml | yes — Ethernet mgmt port, inlet maximum_draw |
| SN5600.yaml | device-types/Nvidia/SN5600.yaml | yes — PSU power ports, 2x400G breakout lanes (GB300 design) |
