# Arista EOS

Arista switches (7050, 7150, 7280, 7320, 7500-series and cloud-grade boxes) are supported via the standard EOS CLI.

## Driver

- Netmiko: `arista_eos`

## What works

Most things, because Arista EOS is largely Cisco-compatible at the CLI level:

- L2 topology (CDP + LLDP + MAC table)
- L3 topology (OSPF, BGP, EIGRP)
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

MLAG-paired Arista switches appear as two separate devices in topology. The MLAG peer relationship is visible through the inter-switch link in CDP/LLDP.

## VARP / Anycast gateway

Arista VARP is detected at the L3 level — the anycast IP appears as a routing endpoint on each member switch.

## EVPN-VXLAN

EVPN-VXLAN overlay is increasingly common on Arista. Node Control covers:

- BGP-EVPN peering visible in L3 topology
- The VXLAN underlay routing is mapped
- The VXLAN-encapsulated overlay (VTEP-to-VTEP) is not specifically rendered — it appears as BGP peers between VTEP loopbacks

For deep EVPN-VXLAN visualisation, dedicated tools (Arista CloudVision, third-party SDN viewers) are better.

## CloudVision

Arista CloudVision is the vendor's centralised management. Node Control doesn't integrate with CloudVision — they're separate products. CloudVision provides the rich change-management, config push, and analytics; Node Control provides the multi-vendor read-only operational view.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| `show interfaces` output paginated | Arista's `terminal length 0` is `terminal length 0` (matches Cisco) | Should auto-disable; if not, raise a ticket |
| MLAG peer detected as separate device | Yes — that's correct (MLAG members ARE separate boxes) | No fix needed, just be aware |
| Detection picks `cisco_ios` | Arista's CLI is Cisco-compatible enough to fool initial driver | Banner sniff usually catches; if not, manually set + lock |

## Next steps

- [L3 topology](../tasks/topology-l3.md) — BGP-EVPN is well-covered
