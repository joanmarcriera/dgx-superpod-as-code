# Custom device types

Written here only where netbox-community/devicetype-library has no definition
(checked at commit 0451a7c). Each file cites its sources in its header.

| File | Why custom |
|---|---|
| DGX-H200.yaml | no DGX H100/H200 in the library |
| DGX-H100.yaml | same; `extends` the H200 (identical chassis) |
| UFM-3.1.yaml | no UFM appliance in the library |
| HPS-Appliance-2U.yaml | RA storage is vendor-specific; generic stand-in |
| DC-Core-Demarc.yaml | modelling stand-in for the DC core (uplink far end) |

Loader extensions (see `src/dgxnb/catalog.py`): `extends: <slug>` inherits another
definition; `{a..b}` in a component name expands to a numeric range.

## NetBox Labs NDX (checked 2026-09-30, after the build)

https://netboxlabs.com/ndx/ has `nvidia-dgx-h200` (plus B200/B300/GB300 — useful for a
future Blackwell variant). **Not used, and must not be vendored here:** NDX YAML is under
the *NetBox Limited Use License v1.0* (no redistribution; use only inside a NetBox Labs
install). It also differs from NVIDIA's own docs, which we follow:

| Field | NDX `nvidia-dgx-h200` | Ours (source) |
|---|---|---|
| Compute ports | `OSFP1`–`OSFP8` (flat) | `OSFP1P1`…`OSFP4P2` = 4 twin-port cages, label = netdev + GPU (UG Tables 5/6) — needed for rail mapping |
| Slot 1/2 ports | `200gbase-x-qsfp56` | `400gbase-x-qsfp112` (RA "2x dual-port QSFP112") |
| PSU inlet | 6 × `iec-60320-c22`, 2,550 W max | 6 × `iec-60320-c20`, 3,300 W (UG: 3.3 kW PSUs, C19/C20 cords) |
| 10GbE LAN port | absent | present, marked unused (RA Fig. 4) |

NDX's `nvidia-qm9700` carries the same missing-P22.1/P23.0 bug as the community library;
NDX has no SN4600C or UFM appliance.

## Mixed pod (cooling and NVL72 additions, 2026-10-01)

| File | Why custom |
|---|---|
| Motivair-ChilledDoor-M8.yaml | active RDHx (0U, rear-door mount); cs §1 |
| Motivair-MCDU-40.yaml, Motivair-MCDU-45.yaml | floor-standing CDUs (non-racked); cs §2 |
| Uniflair-BCEF-0903A.yaml | plant module (non-racked, outside); cs §3 |
| Uniflair-HDCV-4600A-HT.yaml | perimeter CRAH for the NVL72 residual air; cs §4 |
| Coolant-Header.yaml | modelling stand-in for a row's supply/return mains (NetBox has no pipe object) |
| NVL72-Coolant-Manifold.yaml | the NVL72 rack's own rear manifolds + QDs, as a 0U rear-mounted device |

Coolant runs are cables with a blank `type` and `dgx_fabric` = `coolant-supply` /
`coolant-return` between `other` interfaces (see `src/dgxnb/cooling.py`).
