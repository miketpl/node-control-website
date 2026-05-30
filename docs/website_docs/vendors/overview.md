# Vendor support

Node Control connects to network devices over SSH using vendor-specific drivers (via the Netmiko library) and parsers (Node Control's own). This page summarises which vendors are supported and links to per-vendor notes for quirks worth knowing.

## Supported vendors

| Vendor / OS | Driver name | Status |
|---|---|---|
| [Cisco IOS / IOS-XE / IOS-XR](cisco.md) | `cisco_ios`, `cisco_xe`, `cisco_xr` | ✓ First-class |
| [Cisco NX-OS](cisco.md#nx-os) | `cisco_nxos` | ✓ First-class |
| [Cisco ASA](cisco.md#asa) | `cisco_asa` | ✓ |
| [Cisco Meraki](meraki.md) | (Dashboard API, not SSH) | ✓ |
| [Palo Alto PAN-OS](palo-alto.md) | `paloalto_panos` | ✓ First-class |
| [HP ProCurve](hp-procurve.md) | `hp_procurve_cli` (aliased to `aruba_osswitch`) | ✓ First-class |
| [Aruba CX](aruba.md) | `aruba_os` | ✓ |
| [Aruba OS-Switch](aruba.md) | `aruba_osswitch` | ✓ |
| [Juniper Junos](juniper.md) | `juniper_junos` | ✓ |
| [Arista EOS](arista.md) | `arista_eos` | ✓ |
| [Dell OS6](dell.md) | `dell_os6` | ✓ |
| [Dell OS10](dell.md) | `dell_os10` | ✓ |
| [Extreme EXOS](extreme.md) | `extreme_exos` | ✓ |
| [Extreme VSP](extreme.md) | `extreme_vsp` | ✓ |
| Linux (generic SSH) | `linux` | ✓ Limited |
| Generic Cisco-flavoured | Picks `cisco_ios` as fallback | ✓ |

"First-class" means we have dedicated parsers for that vendor's output, custom command catalogs, and per-vendor regression test coverage.

## What "support" actually means

For each supported vendor:

| Capability | Required for |
|---|---|
| Authentication & basic connectivity | Anything |
| `show version` parsing for type detection | Library Updater |
| Interface enumeration | L2 topology, Port Utilisation, Bandwidth |
| MAC address table parsing | L2 topology, Find Device |
| CDP/LLDP neighbour parsing | L2 topology, Discovery |
| VLAN list / port-VLAN mapping | VLAN Port Finder |
| Routing table parsing | L3 topology |
| OSPF / BGP / EIGRP neighbour parsing | L3 topology |
| ARP table parsing | Find Device IP→MAC |
| Environmental data | Monitor |
| PoE data | Monitor, Port Utilisation |
| Port shut/no-shut commands | Find Device port actions |

A vendor is "fully supported" when all the above work. Some vendors (Extreme VSP, Dell OS6) have partial coverage — the [per-vendor pages](#supported-vendors) document gaps.

## Adding a vendor we don't yet support

We add vendor support based on customer demand. If you have devices we don't list above:

1. Open a support ticket with:
   - Vendor name + OS / model
   - `show version` output from one device
   - List of commands the vendor uses (or a link to its CLI reference)
2. We assess feasibility — usually we can add support in 1–2 releases if the CLI is similar to a vendor we already cover

## Self-learning command catalog

Different firmware versions of the same vendor sometimes use slightly different commands. Node Control's catalog tracks multiple variants per capability:

- For each device, on each command run, the result is recorded as "succeeded" or "failed"
- Next time the same capability is needed on that device, the proven-working variant is tried first
- Known-failed variants are skipped

This auto-tuning means a switch running an older firmware that doesn't understand `show mac-address` (modern Cisco) but does understand `show mac address` (older Cisco) gets the right command without manual configuration.

See [Custom command catalogs](../settings/custom-commands.md) for how to add or override commands.

## Cross-vendor command translation

Where the same conceptual command differs across vendors, Node Control abstracts the difference. For example, "show me the MAC address table":

| Vendor | Command Node Control runs |
|---|---|
| Cisco IOS | `show mac address-table` |
| Cisco NX-OS | `show mac address-table` |
| Cisco IOS-XR | `show mac address-table` |
| HP ProCurve | `show mac-address` (older) / `show mac` (newer) |
| Aruba CX | `show mac-address-table` |
| Juniper | `show ethernet-switching table` |
| Arista | `show mac address-table` |
| Extreme EXOS | `show fdb` |

You don't have to know any of this — Node Control routes the right command based on detected device type.

## Per-vendor pages

For quirks, gotchas, and feature gaps:

- [Cisco IOS / IOS-XE / NX-OS / ASA](cisco.md)
- [Palo Alto PAN-OS](palo-alto.md)
- [HP ProCurve](hp-procurve.md)
- [Aruba (CX, OS-Switch)](aruba.md)
- [Juniper Junos](juniper.md)
- [Arista EOS](arista.md)
- [Dell OS6 / OS10](dell.md)
- [Extreme EXOS / VSP](extreme.md)
- [Cisco Meraki](meraki.md)

## Vendor-specific reporting issues

If a report has gaps for one vendor (empty columns, missing devices), check:

1. The per-vendor page above for known issues
2. [Verify Device Types](../tasks/verify-device-types.md) — might be a misdetection
3. Settings → Custom Commands — might be a missing catalog entry
4. Open a support ticket with the device's raw command output
