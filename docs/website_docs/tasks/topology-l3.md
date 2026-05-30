# Layer 3 topology map

> Available on **Pro** and **AI** tiers only.

The L3 topology map walks every routing device in scope, reads its routing table, OSPF and BGP neighbours, and renders an interactive map of the L3 overlay — which routers and firewalls peer with which, across what protocols.

## Open the task

- **Tasks** tab → **Topology (L3)** → click **Run**

## Configure

| Setting | What it controls |
|---|---|
| **Scope** | All devices, a single site, or individual |
| **Protocols** | Which routing protocols to include (OSPF, BGP, EIGRP, static). Default is OSPF + BGP |
| **Parallelism** | Concurrent SSH workers |

## What's read from each device

For each L3-capable device:

- `show ip route` — connected, static, dynamic routes
- `show ip ospf neighbour` — OSPF adjacencies, including area
- `show ip bgp summary` — BGP peers, AS numbers, prefix counts
- VRF-aware: `show ip route vrf <name>`, `show ip ospf vrf <name> neighbour`, etc.
- Palo Alto: walks every logical router and the "default" router, unions the results

## Reading the map

- Nodes: routers, firewalls, L3 switches
- Edges: routing adjacencies, colour-coded by protocol:
  - 🔵 Blue: OSPF
  - 🟢 Green: BGP
  - 🟠 Orange: EIGRP
  - ⚪ Grey: static / connected
- Hover an edge: shows the OSPF area, BGP AS, or static route details
- Click a node: opens routing table summary

## Per-LR / per-VRF unioning

Devices with multiple routing instances (Palo Alto LRs, Cisco VRFs, Juniper routing-instances) have their adjacencies discovered per-instance and unioned together. The resulting map shows all peer relationships, with each edge annotated by which VRF / LR it came from.

Hover a multi-VRF edge to see the per-VRF breakdown.

## Vendor notes

| Vendor | Notes |
|---|---|
| Cisco IOS / IOS-XE / NX-OS | Full OSPF + BGP + EIGRP, multi-VRF |
| Palo Alto PAN-OS | Walks every Logical Router via `show routing protocol` commands, unions across them. Several recent fixes in 0.9.x to capture all peers correctly |
| Juniper | OSPF + BGP via `show ospf neighbour` and `show bgp summary` |
| Arista EOS | Cisco-compatible commands |
| HP ProCurve / Aruba CX | OSPF + BGP if licensed and configured |

Devices without L3 capability (pure L2 access switches) don't appear on the L3 map even if they're in the library — only L3 hops show up.

## Device role classification

Each L3 device gets a role inferred from its routing table:

| Role | Indicator |
|---|---|
| **Access switch (L3 SVI)** | Has L3 interfaces but mostly connected/static routes |
| **Distribution / aggregation** | Multiple OSPF areas, several VLAN SVIs |
| **WAN router** | BGP peers to external AS, default route from BGP |
| **Firewall** | Identified by device type, special icon |
| **L3 core** | Most-connected node, large routing table |

The classifier improvements in 0.9.x correctly identify non-Cisco L3 hardware (HP ProCurve, Aruba CX, Arista, Dell, Extreme, Juniper) as access switches when appropriate — previously they were defaulting to "distribution/core".

## Cross-site WAN edges

If two sites are connected via OSPF area 0 or BGP, the L3 map will show those cross-site edges. For a comprehensive WAN-only view, use [WAN topology](topology-wan.md) instead.

## Caching and timing

Same 10-minute cache as [L2 topology](topology-l2.md). Re-runs within the window reuse cached output.

Typical timing: 30–60 seconds per L3 device (parallelised). A 20-router site takes 2–4 minutes.

## Saving the map

Same as L2 — the HTML is written to your app support directory with a timestamped filename.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| BGP peers missing on Palo Alto | Older parser only captured first LR's peers | Update to v0.9.27+ — multi-LR union is fixed |
| OSPF area shown as `unknown` | Vendor's neighbour output doesn't include area | Hover edge to see the partial data; check the source device manually |
| L3 switches misclassified as core | Classifier got it wrong | The 0.9.x improvements should catch most cases. Open a support ticket with the device's `show ip route` output if it still misclassifies |

## Next steps

- [Layer 2 topology](topology-l2.md)
- [WAN topology](topology-wan.md)
- [Find Device](find-device.md) — uses the L3 routing tables to locate IPs across VRFs
