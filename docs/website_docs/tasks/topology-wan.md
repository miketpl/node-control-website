# WAN topology map

> Available on **Pro** and **AI** tiers only.

The WAN topology map renders the cross-site connectivity between your sites — the routers, firewalls, and SD-WAN edges that link locations together.

## Open the task

- **Tasks** tab → **Topology (WAN)** → **Run**

## Configure

| Setting | What it controls |
|---|---|
| **Scope** | All sites, or pick a subset |
| **Include redundant paths** | Show both primary and backup links between site pairs |
| **Protocols** | BGP, MPLS, IPSec — which transport overlays to detect |

## What's read

The WAN topology task walks one router-or-firewall per site (typically the WAN edge — pickable in Settings), and on each:

- `show ip bgp summary` — external BGP peers (cross-site, transit, ISP)
- `show ip route` — wan-facing routes, default route source
- `show crypto ipsec sa` (or equivalent) — IPSec tunnel endpoints
- SD-WAN-specific commands for Velocloud / Viptela / Silver Peak edges

## Reading the map

- **Nodes**: one per site (collapsed) OR one per WAN edge device (expanded)
- **Edges**: BGP peering, IPSec tunnels, MPLS pseudowires
- **Edge labels**: AS path for BGP, tunnel peer for IPSec, VRF name for MPLS
- Hover for full peer details

## Best practice

WAN topology works best when each site has a clearly-designated WAN edge device tagged in the library — typically:

- A WAN router (`rtr-wan-*`, `csr-*`)
- A firewall doing edge / VPN termination
- An SD-WAN appliance

If your library has every router tagged, the WAN task walks them all (slow, noisy). If you tag only the actual WAN edges, the map is cleaner and faster.

## When to use which topology

- **L2** — switch-to-switch view of a single site's fabric
- **L3** — routing protocol overlay (OSPF, BGP) for a site or full network
- **WAN** — cross-site connections only, your transport view

For "where does this packet go?" type questions, L3 + WAN together usually answers it.

## Vendor support

- Cisco IOS / IOS-XE — full BGP + IPSec
- Cisco ASA — IPSec only (no BGP unless licensed)
- Palo Alto PAN-OS — BGP via virtual routers, IPSec tunnels
- Velocloud, Viptela — SD-WAN overlay
- Juniper — BGP, IPSec, MPLS pseudowires
- Arista — BGP, EVPN

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Some sites missing | No WAN-tagged device in those sites | Tag one router/firewall per site as the WAN edge |
| IPSec tunnels not showing | Firewall's `show crypto` output couldn't be parsed | Check vendor + version; report to support with the raw output |
| BGP peers missing on PA | Older parser bug | Update to v0.9.27+ |
