# Arista EOS

Arista switches (7050, 7150, 7280, 7320, 7500-series and cloud-grade boxes) are supported via the standard EOS CLI.

## Driver

- Netmiko: `arista_eos`

## What works

Most things work through the EOS CLI. EOS reads LLDP and the MAC table. It does not read CDP.

- L2 topology maps are LLDP-only. The L2 Topology Builder does not use the MAC table. The native L2 and L3 reads also include STP, routes, interfaces, IPv4 BGP, OSPF neighbours, and VRRP gateways
- The MAC table is read for VLAN Port Finder, Find Device (the wired trace), the Discover walk, and the Bandwidth report
- Find Device's per-port probe tries CDP first and falls back to LLDP, so Arista answers from LLDP
- Port Utilisation
- Bandwidth
- VLAN Port Finder
- Find Device
- Inventory
- Monitor

## Detection

`show version` cleanly identifies EOS:

- Header line: "Arista DCS-..." or "vEOS"
- Banner: `SSH-2.0-OpenSSH_for_Arista`

## MLAG (Multi-Chassis Link Aggregation)

MLAG-paired Arista switches appear as two separate devices in topology. The MLAG peer relationship is visible through the inter-switch link in LLDP.

## VARP

A VARP gateway resolves by subnet ownership.

## CloudVision

Arista CloudVision is the vendor's centralised management. Node Control doesn't integrate with CloudVision — they're separate products. CloudVision provides the rich change-management, config push, and analytics; Node Control provides the multi-vendor read-only operational view.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| `show interfaces` output paginated | Arista's `terminal length 0` is `terminal length 0` (matches Cisco) | Should auto-disable; if not, raise a ticket |
| MLAG peer detected as separate device | Yes — that's correct (MLAG members ARE separate boxes) | No fix needed, just be aware |
| Detection picks `cisco_ios` | Arista's CLI is Cisco-compatible enough to fool initial driver | Banner sniff usually catches; if not, manually set + lock |

## Next steps

- [L3 topology](../tasks/topology-l3.md)
