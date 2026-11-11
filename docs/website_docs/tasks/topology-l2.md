# Layer 2 topology map

**L2 Topology Builder** runs on **Free**, **Pro**, and the **AI** edition. On Free it is one of the five tasks that are not greyed out. Safe Mode leaves it in the list.

The map walks the switches in scope, reads each MAC address table and the LLDP neighbours, and CDP on Cisco, and renders an HTML map of switch-to-switch connectivity. The Free Edition is free for up to 25 devices, so that is the largest map Free will draw.

On Arista EOS the L2 Topology Builder uses EOS parsers, not Cisco IOS parsers, for LLDP neighbours, port-channel members, the default gateway, and spanning tree (MST and rapid-PVST). It does not use the MAC table. CDP is Cisco only.

## Open the task

- Engineer command bar → **Task** → **L2 Topology Builder** → **Run**

An optional AI summary of the map (structure, single points of failure, failed devices) is on Pro and the AI edition. Tick it for that run. See [AI provider](../settings/ai.md).

## Configure

| Setting | What it controls |
|---|---|
| **Scope** | **All devices**, **Site X**, or **Individual** (pick one device to map the local switching only) |
| **Include endpoints** | Show non-switch MAC addresses (phones, APs, PCs) — usually OFF for clarity |
| **Parallelism** | How many switches to SSH-walk concurrently. Six at a time by default. |

## What happens during the run

1. Node Control filters the library to the chosen scope
2. For each switch, opens SSH and runs:
   - the MAC address table
   - CDP neighbours on Cisco, and LLDP neighbours
   - VLANs, spanning tree, and port-channels
3. Cross-references CDP/LLDP entries to known library devices by hostname/IP
4. Builds a graph: nodes = devices, edges = links
5. Classifies each device's role (access / distribution / wan / firewall)
6. Renders the result as an HTML file

On Arista EOS the neighbour read uses the EOS parsers for LLDP. CDP is Cisco only. The builder does not run the MAC-table command.

Typical timing: 30–60 seconds per switch (parallelised). A 30-switch site map takes ~3–5 minutes.

## One cable, one link

A cable reported from both ends, with different port names, is drawn once. The link count in the header matches the number of cables.

A link that would pass straight through another switch curves around it.

## Reading the map

The map opens in your browser. Each node represents one device:

- **Colour**: switches you queried and neighbours it found are coloured differently
- **Label** shows hostname + IP
- **Edge** between two nodes means CDP / LLDP detected a direct link

Interactions:

- **Hover** a node — shows interface details
- **Drag** a node — repositions it; the force-directed layout adjusts
- **Right-click** a node — its MAC table, grouped by VLAN with the port for each MAC, plus its VLANs, spanning tree and trunk ports

Port Connections is the Pro Discover tab. It is not this map.

## Right-click → MAC table

Right-click a switch for its MAC table, grouped by VLAN with the port for each MAC, plus its VLANs, spanning tree and trunk ports. The MAC flyout does not show an OUI vendor or a neighbour.

## Map per run

The task draws one HTML map per run, named after the site.

## Caching

Topology runs cache device output for ~10 minutes. Re-running a topology within that window reuses cached MAC tables and neighbour data rather than re-walking. Force a fresh walk by ticking **Skip cache** in the run dialog.

## Endpoint filtering

Endpoints are left off so you see the switches. You can tick APs and IP phones back in as small dots. Host-only endpoints such as PCs stay off. Endpoints that are filtered are detected by:

- OUI patterns for known endpoint vendors (Polycom, Cisco IP Phones, Apple AirPort, Aruba IAP, etc.)
- LLDP identity strings that look like end-user devices
- Single-MAC-per-port heuristic (multi-MAC ports are usually trunks to other switches)

To include endpoints in the map, tick **Include endpoints** before running.

## Vendor support

L2 topology works on every vendor Node Control supports:

- Cisco IOS, IOS-XE, NX-OS
- HP ProCurve (with the recent classifier fixes — see [HP ProCurve notes](../vendors/hp-procurve.md))
- Aruba AOS-CX. The builder reads the LLDP neighbour table, then one per-port query per neighbour for its management address. MC-LAG legs to a VSX pair, the ISL, and LAG members are drawn and labelled like Cisco port-channel members. See [Aruba AOS-CX](../vendors/aruba-aos-cx.md). Aruba OS-Switch is supported as well
- Juniper Junos
- Arista EOS. The builder uses EOS parsers, not Cisco IOS parsers, for LLDP neighbours, port-channel members, the default gateway, and spanning tree (MST and rapid-PVST). It does not use the MAC table. CDP is Cisco only
- Dell OS6, OS10
- Extreme EXOS, VSP

Palo Alto and Meraki devices appear on L2 maps as endpoints of links (they're not switches themselves) — they're properly mapped in the [L3 topology](topology-l3.md) view instead.

## Link status

On Pro, Monitor can colour the cables on this map. **Link status** is on by default. Green is up, red dashed is down, and grey is unknown. Hover a cable to see both ports. That covers Cisco IOS, IOS-XE, and NX-OS ports. See [Monitor](monitor.md).

After each Monitor poll, the latest status is written into the map's own page, with the time. A map opened outside Node Control shows how the network looked at the last poll. It is marked stale after 24 hours.

On Pro, after an L2 topology run, the map page says **Open in Monitor for live status**.

Device names and other text read from devices are shown as plain text on this map. A device name containing page code cannot change or run anything in the page. On Pro the same is true of the other topology maps and the Discovery map.

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

On Cisco NX-OS, MAC-table entries are read on their real port. The age column is not taken as the port, and `vPC Peer-Link` is not cut short. IOS, IOS-XE, and Arista read as before.

## Next steps

- [Layer 3 topology](topology-l3.md) — adds routing info, OSPF/BGP peers
- [WAN topology](topology-wan.md) — across-site view
- [Discover](discovery.md) — live walk without needing the library pre-populated. Pro and AI; not on Free
