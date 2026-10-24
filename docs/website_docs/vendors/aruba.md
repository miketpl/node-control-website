# Aruba (CX, OS-Switch)

Aruba sells two switch operating systems. Same brand, different CLIs. Node Control treats them separately.

## Two Aruba OSes

| OS | Background | Driver |
|---|---|---|
| **Aruba AOS-CX** | Modern OS for the CX 6000, 8000, and 10000 series. Its own platform from 0.9.42. | `aruba_os` |
| **Aruba OS-Switch** | Legacy OS from the HPE ProCurve line. Includes 2530, 2920, 2930F/M, and 5400zl. | `aruba_osswitch` (alias `hp_procurve_cli`) |

AOS-CX is documented on its own page: [Aruba AOS-CX](aruba-aos-cx.md).

For OS-Switch, see [HP ProCurve](hp-procurve.md). The same parsers and notes apply.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| AOS-CX detected as ProCurve or Cisco | An older build used the banner, or the banner had no vendor name | 0.9.42 reads `show version` and `show system` and records the device as AOS-CX |
| VLAN reports differ between CX and OS-Switch | Different VLAN models | Expected. They are different operating systems |
| An OS-Switch parser looked up as `aruba_os` | Wrong driver | Use `aruba_osswitch` (or `hp_procurve_cli`) for OS-Switch, not `aruba_os` |

## Wireless (Aruba IAP, Aruba Controller)

Wireless products (IAP, ArubaOS-controlled APs, Mobility Controllers) are partially supported:

- **Controllers (Mobility Master / Mobility Controller)**: SSH inventory works. Topology and reports are limited
- **Aruba IAP**: managed via the cluster. Inventory works through the master IAP CLI
- **AP-205, AP-505, and similar** in a CAPWAP design: managed through the controller. Individual APs are not opened over SSH

For Aruba wireless management, Aruba Central or AirWave is the vendor tool. In Node Control, wireless coverage is Meraki and basic Aruba IAP. See [Meraki](meraki.md).

## Next steps

- [Aruba AOS-CX](aruba-aos-cx.md)
- [HP ProCurve](hp-procurve.md)
- [Meraki](meraki.md)
