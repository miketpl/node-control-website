# Arista EOS

Arista switches (7050, 7150, 7280, 7320, 7500-series and cloud-grade boxes) are supported via the standard EOS CLI.

## Driver

- Netmiko: `arista_eos`

## What works

Most things work through the EOS CLI. EOS reads LLDP and the MAC table. From 0.9.42 the L2 Topology Builder uses EOS parsers, not Cisco IOS parsers.

- L2 topology uses those EOS parsers for LLDP and CDP neighbours, port-channel members, the default gateway, and spanning tree (MST and rapid-PVST). The builder does not use the MAC table
- The MAC table is read for VLAN Port Finder, Find Device (the wired trace), the Discover walk, and the Bandwidth report
- Find Device's per-port probe tries CDP first and falls back to LLDP, so Arista answers from LLDP
- Port Utilisation
- Bandwidth and Path Bandwidth read the EOS route table. The per-VRF pass runs on EOS as well as the Cisco family
- VLAN Port Finder
- Find Device, traced with EOS MAC-table, LLDP, and LAG commands
- Inventory reads the model, the serials, and the EOS version from EOS output
- On Pro and the AI edition, L3 Topology Builder reads routes, interfaces, and BGP peers as JSON first, with a text fallback. On an EOS campus a dynamically learned default is a routed adjacency, not a configured gateway. The VRRP virtual address resolves to the router that holds it. OSPF neighbours are parsed
- On Pro and the AI edition, Asset Lifecycle reads the EOS inventory and the EOS version. Health Monitor reads memory from `show version`. Site Subnets has its L3 command
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

A device reached on another driver and identified as Arista EOS is reconnected on the EOS driver. If that reconnect fails, the connection stops. IOS, IOS-XE, and Arista MAC-table reads on the L2 map, in Find Device, and in the Bandwidth report are unchanged.

## Next steps

- [L3 topology](../tasks/topology-l3.md)
