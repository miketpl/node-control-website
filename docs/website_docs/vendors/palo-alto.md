# Palo Alto PAN-OS

Palo Alto firewalls (PA-200 through PA-7000, plus VM-series) are first-class supported.

## Driver

- Netmiko: `paloalto_panos`

## What works

- Connectivity via SSH (the CLI mode, not the API)
- Auto-detection from `show system info`
- Inventory (model, serial, software version, HA peer)
- L3 topology — full BGP + OSPF support across all logical routers
- WAN topology — BGP peers + IPSec tunnel endpoints
- Find Device — ARP probe across virtual routers
- VLAN-equivalent data: Zone-to-Interface mapping (not VLAN, but similar conceptually)
- Monitor — CPU, memory, env, BGP/OSPF state, session count

## Auto-detection

For `show system info`:
- "device-name: PA-..." → paloalto_panos
- SSH banner pattern `SSH-2.0-OpenSSH_for_PANOS_*` is a primary signal
- Post-connect probe: if the prompt is `user@host>` (PA shell prompt with `>`), confirmed PA
- Opportunistic probe runs even if the initial driver is `cisco_ios` — PA accepts the Cisco driver silently otherwise

## Logical routers and multi-routing

PA firewalls have a per-virtual-router routing model. Each VR can run BGP, OSPF, EIGRP independently.

Node Control's L3 topology task walks **every logical router** plus the special "default" router and unions the results:

- Each LR's BGP peers
- Each LR's OSPF neighbours
- Each LR's static + connected routes

Edges in the L3 map are tagged with the LR they came from. Hover an edge to see the per-LR breakdown.

**Important fix in 0.9.x**: previous versions only walked the first LR — multi-LR PA deployments showed only partial peer detail. The 0.9.x parsers accumulate across all command outputs and the L3 task iterates every LR explicitly. Update if you're on an older version.

## VRF stamping

In the unioned L3 map, each edge is stamped with the LR (acting as VRF) it came from. If two LRs share a BGP peer (multi-tenant edge), you'll see two edges between the same nodes, one per LR.

## Inventory specifics

For `show system info`:

- Model
- Serial
- PAN-OS version
- Boot software version
- Maintenance support state
- HA peer (if configured) — appears as separate Inventory row with HA state (active / passive / synced / not synced)

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| BGP peers missing | Older Node Control parser bug (only first LR's peers captured) | Update to 0.9.27+ |
| `show config running` truncated | Some PA versions paginate even with `set cli scripting-mode on` | The catalog uses `set cli pager off` first; if still seeing pagination, raise a ticket |
| Detection initially flags as `cisco_ios` | PA's prompt looks like Cisco's at first glance | The opportunistic probe (`show system info`) catches this; if detection persists wrongly, manually set + lock the device type |
| OSPF area shown as `unknown` | PA's `show routing protocol ospf neighbor` output is concise | Hover the edge to see partial data; the LR-level config has the area detail |

## CLI mode

Node Control uses PAN-OS CLI mode (NOT the web GUI, NOT the XML API):

- Commands run via SSH
- Read-only — no `commit` operations
- Disables paging on connect with `set cli pager off`

For users who prefer the XML API (which has wider parsing support upstream), we may add a hybrid mode in a future release — let us know if this matters.

## HA pairs

Active/passive PA pairs are common. Node Control:

- Inventories both members separately
- Marks each with its HA role (Active / Passive)
- L3 topology shows both members but folds them into a single logical node if both peer with the same neighbours (typical for routing protocols in active/passive setups where only the active speaks)

## Limitations

- **Panorama**: not supported as a "device" type. Manage individual firewalls instead.
- **GlobalProtect**: not specifically exposed
- **App-ID / User-ID**: not surfaced in reports
- **Policy review**: no built-in policy inspector

For Panorama-driven workflows or policy review, dedicated PA tools (Strata Cloud Manager, Panorama itself, third-party policy auditors) are better.

## Next steps

- [L3 topology](../tasks/topology-l3.md) — for full LR + multi-VR coverage
- [Find Device](../tasks/find-device.md) — VRF-aware ARP probes work with PA LRs
