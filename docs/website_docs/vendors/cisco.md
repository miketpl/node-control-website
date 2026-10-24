# Cisco — IOS, IOS-XE, IOS-XR, NX-OS, ASA

Node Control's most comprehensive vendor coverage. All Cisco platforms are first-class supported.

## Driver mapping

| Platform | Netmiko driver |
|---|---|
| Catalyst classic (3560, 3750, 2960) | `cisco_ios` |
| Catalyst 9k (9200, 9300, 9500) | `cisco_xe` (IOS-XE) |
| ISR / ASR / CSR | `cisco_xe` or `cisco_ios` |
| Nexus 5k / 7k / 9k | `cisco_nxos` |
| IOS-XR (ASR9k, NCS) | `cisco_xr` |
| ASA firewalls | `cisco_asa` |
| Cisco Meraki | (Dashboard API, not SSH) — see [Meraki page](meraki.md) |

## What works

Everything Node Control does works on Cisco:

- L2 topology with full CDP/LLDP + MAC table
- L3 topology with OSPF, BGP, EIGRP, multi-VRF. HSRP and VRRP gateways on IOS, IOS-XE, and NX-OS resolve to the active router on the L3 map instead of an Internet node. A routed campus keeps proper rows. Point-to-point OSPF neighbours are handled. When the VRF field is blank, the device's own VRFs from `show vrf` are walked
- WAN topology with BGP + IPSec tunnel detection
- Port Utilisation (including PoE)
- Bandwidth (5-min averages, peaks)
- VLAN Port Finder (access + trunk + voice)
- Find Device (wired walk + ARP probe + port shut/no-shut)
- Inventory (stack members, line cards, transceivers)
- Verify Device Types
- Monitor (CPU, memory, environmental, BGP/OSPF peers)
- [Config Push](../tasks/config-push.md), [packet capture](../tasks/packet-capture.md), and [config compliance](../tasks/config-compliance.md) (remediation is IOS, IOS-XE, and NX-OS)
- [Security Audit](../reports/security-audit.md) and [Lifecycle / EoX](../reports/lifecycle.md)
- Feature-level AI summaries, on Pro and the AI edition, with your own provider. The AI dashboard is the AI edition only. See [AI provider](../settings/ai.md)

## Auto-detection signature

For type detection, Node Control looks for in `show version`:

- "Cisco IOS Software" → cisco_ios
- "Cisco IOS XE Software" → cisco_xe
- "Cisco Nexus Operating System" → cisco_nxos
- "Cisco IOS XR" → cisco_xr
- "Cisco Adaptive Security Appliance" → cisco_asa

## NX-OS

NX-OS has subtle CLI differences from IOS-XE:

- `show interface` (no plural) instead of `show interfaces`
- `show ip route vrf <vrf>` includes VRF as a separate context
- VPC and FEX add their own commands (`show vpc`, `show fex`) — Node Control includes these in the catalog

NX-OS route tables are read correctly, including long via lines.

## ASA

Cisco ASA firewalls are supported with these caveats:

- `show interface` works but counters differ from IOS
- VPN / IPSec inspection via `show crypto ipsec sa`
- No L3 routing protocol parsing beyond BGP (ASA's OSPF is rarely used at scale)
- Failover pairs (active/standby) appear as two rows in Inventory, HA status flagged

## IOS-XR

For service-provider-grade ASR9k / NCS gear:

- Most "show" commands match IOS conventions
- Configuration commit model is different but Node Control is read-only in tasks (won't see this difference)
- BGP at SP scale — full peer enumeration

## Stack and VSS

Cisco stacks (3850 stack, 9300 stack) and VSS pairs (4500/6500/6800):

- Each member appears as a separate Inventory row tagged with the master
- L2/L3 topology shows the stack as one logical device
- Port names include the member number (e.g., `Gi1/0/1`, `Gi2/0/1`)

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| `terminal length 0` not running | Some IOS versions need `terminal length 0` AND `terminal pager 0` | Node Control handles both — but if you see paged output, raise a ticket |
| `show vlan brief` empty on routers | Routers without integrated switching don't have VLAN tables | Expected — VLAN Port Finder shows them as "no VLAN data" |
| ISR4451 / ASR9001 not detected after fresh import | Older classifier regex had a `\b` boundary issue with model strings ending in digits | Fixed in 0.9.x — bump version |

## Catalyst 9000 — IOS-XE differences

The Catalyst 9000 series runs IOS-XE which has minor CLI differences from IOS classic:

- `show running-config` works the same
- `show platform` exposes more detail on bootstrap state
- LISP, SD-Access overlays add commands that aren't in the standard catalog (Settings → Custom Commands if you need them)

## Known limitations

- SD-Access overlays (LISP-based) are not specially handled — they appear as standard IOS-XE devices in topology
- TrustSec / SGT data is not exposed in any report
- Embedded IPS sensors (IPS-4000 / IDS) — limited support, basic Inventory only

## Changes it will push

Maps, inventory, and the show-command reports are read-only. On Cisco the write paths are:

- [Find Device](../tasks/find-device.md#port-actions-shut-no-shut) port shut and re-enable
- [Config Push](../tasks/config-push.md) — commands to ports from a file, on Pro and the AI edition. Full support is Cisco IOS, IOS-XE, and NX-OS
- [Config Compliance](../tasks/config-compliance.md) remediation — IOS, IOS-XE, and NX-OS, on Pro and the AI edition

Each one asks you to confirm before it sends anything. Safe Mode blocks compliance remediation.

## Next steps

- [Topology L3](../tasks/topology-l3.md) — full BGP / OSPF detail for Cisco
- [Find Device](../tasks/find-device.md) — VRF-aware ARP probe works across Cisco VRFs
