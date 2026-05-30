# Layer 2 topology map

> Available on **Pro** and **AI** tiers only.

The L2 topology map walks every switch in a site, reads its MAC address table and CDP/LLDP neighbours, and renders an interactive HTML map of switch-to-switch connectivity.

## Open the task

- **Tasks** tab → **Topology (L2)** in the task picker → click **Run**

## Configure

| Setting | What it controls |
|---|---|
| **Scope** | **All devices**, **Site X**, or **Individual** (pick one device to map the local switching only) |
| **Include endpoints** | Show non-switch MAC addresses (phones, APs, PCs) — usually OFF for clarity |
| **Parallelism** | How many switches to SSH-walk concurrently. Default 8. |

## What happens during the run

1. Node Control filters the library to the chosen scope
2. For each switch, opens SSH and runs:
   - `show interfaces` (or vendor equivalent) — port list, link states
   - `show mac-address-table` (or `show mac address`) — what's on each port
   - `show cdp neighbours detail` and `show lldp neighbours detail` — directly-connected peers
3. Cross-references CDP/LLDP entries to known library devices by hostname/IP
4. Builds a graph: nodes = devices, edges = links
5. Classifies each device's role (access / distribution / wan / firewall)
6. Renders the result as an HTML file

Typical timing: 30–60 seconds per switch (parallelised). A 30-switch site map takes ~3–5 minutes.

## Reading the map

The map opens in your browser. Each node represents one device:

- **Colour** indicates role:
  - 🔵 Blue: access switch
  - 🟢 Green: distribution switch
  - 🟠 Orange: core / WAN
  - 🔴 Red: firewall
  - ⚪ Grey: device not in library / unidentified
- **Label** shows hostname + IP
- **Edge** between two nodes means CDP / LLDP detected a direct link

Interactions:

- **Hover** a node — shows interface details
- **Click** a node — opens the [Port Connections](#right-click-port-connections) dialog
- **Drag** a node — repositions it; the force-directed layout adjusts
- **Right-click** a node — context menu with options (Port Connections, Show Device Type, Open SSH)

## Right-click → Port Connections

Reveals the MAC-by-port table for the selected switch:

- **Port** column — interface name (e.g., `GigabitEthernet1/0/3`)
- **MAC** column — every MAC seen on that port
- **OUI Vendor** column — the manufacturer of each MAC, decoded from the OUI prefix
- **VLAN** column — VLAN that MAC was learned on
- **CDP/LLDP neighbour** column — if the port has a known direct-connected peer

Useful for "what's on port 24 of LON-ACCESS-03?" type questions without going back to SSH.

## Map per site

If your scope is **All devices**, you'll get one map per site (separate HTML tabs in your browser). Distinct sites are *not* shown on a single map — keeps each one readable.

## Caching

Topology runs cache device output for ~10 minutes. Re-running a topology within that window reuses cached MAC tables and neighbour data rather than re-walking. Force a fresh walk by ticking **Skip cache** in the run dialog.

## Endpoint filtering

By default, "endpoint" MACs (phones, APs, PCs, IoT) are filtered out so the map only shows switch infrastructure. Endpoints are detected by:

- OUI patterns for known endpoint vendors (Polycom, Cisco IP Phones, Apple AirPort, Aruba IAP, etc.)
- LLDP identity strings that look like end-user devices
- Single-MAC-per-port heuristic (multi-MAC ports are usually trunks to other switches)

To include endpoints in the map, tick **Include endpoints** before running.

## Vendor support

L2 topology works on every vendor Node Control supports:

- Cisco IOS, IOS-XE, NX-OS, IOS-XR
- HP ProCurve (with the recent classifier fixes — see [HP ProCurve notes](../vendors/hp-procurve.md))
- Aruba CX, Aruba OS-Switch
- Juniper Junos
- Arista EOS
- Dell OS6, OS10
- Extreme EXOS, VSP

Palo Alto and Meraki devices appear on L2 maps as endpoints of links (they're not switches themselves) — they're properly mapped in the [L3 topology](topology-l3.md) view instead.

## Saving and sharing

The HTML file is written to:

```
~/Library/Application Support/netOps/topology_l2_<site>_<timestamp>.html  (Mac)
%APPDATA%\netOps\topology_l2_<site>_<timestamp>.html                       (Windows)
```

You can copy it elsewhere or attach to support tickets — it's a self-contained HTML file with embedded CSS and JS.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Map missing some switches | Those switches failed SSH auth or weren't in the library | Check the **Run log** dialog after the run; add missing switches to the library |
| Loops shown where there aren't any | Stale MAC entries on the source switch | Clear MAC tables (`clear mac address-table dynamic`) and re-run |
| Stand-alone "ghost" nodes with no edges | Switch in library but its neighbours aren't | Add the neighbours to the library, re-run |
| HP ProCurve switch appears as cisco_ios | Detection error | Right-click in library → Change Device Type → `hp_procurve_cli`, Lock Device Type, re-run |

## Next steps

- [Layer 3 topology](topology-l3.md) — adds routing info, OSPF/BGP peers
- [WAN topology](topology-wan.md) — across-site view
- [Network Discovery](discovery.md) — live walk without needing the library pre-populated
