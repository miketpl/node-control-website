# Aruba (CX, OS-Switch)

Aruba sells two distinct switch operating systems. Same brand, completely different CLIs — Node Control treats them separately.

## Two Aruba OSes

| OS | Background | Driver |
|---|---|---|
| **Aruba CX** | Modern OS for CX 6000 / 8000 / 10000-series — built ground-up by Aruba post-HP merger. JSON-aware CLI. | `aruba_os` |
| **Aruba OS-Switch** | Legacy OS from the HPE ProCurve line, rebranded after Aruba acquisition. Includes 2530, 2920, 2930F/M, 5400zl. | `aruba_osswitch` (alias `hp_procurve_cli`) |

For OS-Switch specifically, see the [HP ProCurve page](hp-procurve.md). The same parsers and notes apply.

## Aruba CX — what works

- Detection via SSH banner sniff + post-connect probe
- L2 topology (CDP/LLDP + MAC table)
- L3 topology (OSPF + BGP + VRF)
- Port Utilisation
- Bandwidth
- VLAN Port Finder
- Find Device (full BFS walk + port shut/no-shut)
- Inventory
- Monitor

## Detection

Aruba CX has clean detection — its `show version` output identifies the platform unambiguously. SSH banners often include `SSH-2.0-ARUBA` or `SSH-2.0-OpenSSH_for_Aruba`.

## VSF (Virtual Switching Framework) stacks

Aruba CX supports VSF stacking. Members are inventoried separately and tagged with their VSF member ID.

## VSX (Virtual Switching Extension)

VSX-paired CX switches appear as two separate devices in topology. The peer relationship is detected via LLDP and rendered as a dedicated VSX edge in L2 topology.

## Configuration model

Aruba CX uses a structured CLI with explicit `configure terminal` / `exit` boundaries. Node Control is read-only by design — won't enter config mode except for [Find Device port actions](../tasks/find-device.md#port-actions).

## REST API

Aruba CX exposes a comprehensive REST API. Node Control currently uses SSH only; REST API integration is on the roadmap if there's customer demand.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| Aruba CX detected as Cisco | Both share a similar prompt style | Updated detection in 0.9.x catches this via banner sniff |
| VLAN-based reports show different output between CX and OS-Switch | Different VLAN models | Expected — they ARE different OSes |
| Looking for an OS-Switch parser by `aruba_os` driver name | Wrong driver | Use `aruba_osswitch` (or `hp_procurve_cli`) for OS-Switch, not `aruba_os` |

## Wireless (Aruba IAP, Aruba Controller)

Wireless products (IAP, ArubaOS-controlled APs, Mobility Controllers) are partially supported:

- **Controllers (Mobility Master / Mobility Controller)**: SSH inventory works; topology / reports limited
- **Aruba IAP**: managed via cluster — inventory works through the master IAP's CLI
- **AP-205, AP-505, etc.** in a CAPWAP design: managed through the controller; individual APs are not directly SSH'd

For comprehensive Aruba wireless management, the Aruba Central / AirWave platforms are the right tools. Node Control's wireless support is best for Meraki and basic Aruba IAP — see [Meraki](meraki.md) for the deeper wireless story.

## Next steps

- [HP ProCurve](hp-procurve.md) — for OS-Switch specifically
- [Meraki](meraki.md) — for full wireless coverage in Node Control
