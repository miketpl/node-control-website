# Network Discovery

> Available on **Pro** and **AI** tiers only.

Network Discovery is the live, "I don't know what's out there" topology walk. Give it a seed switch and credentials, and it builds a topology map by walking CDP/LLDP neighbours hop by hop — discovering devices that aren't yet in your library.

Contrast with [L2 topology](topology-l2.md), which only maps devices already in your library.

## When to use Discovery vs L2 topology

| Situation | Use |
|---|---|
| Walking a network you've never seen before | Discovery |
| Mapping a known site whose library is up to date | L2 topology (faster) |
| Auditing whether your library is complete | Discovery (reveals devices missing from library) |
| One-off site visit, customer doesn't have an inventory | Discovery |
| Daily ops on a documented network | L2 topology |

## Open the task

- **Discovery** tab (separate top-level tab)

## Configure

| Field | What it controls |
|---|---|
| **Subnet** | Optional — narrow ping sweep to this range. Leave blank to start solely from the seed switch |
| **Seed switch IP** | The starting point for the BFS walk |
| **Seed credentials** | SSH credentials for the seed switch |
| **Walk neighbours** | Whether to recursively SSH into discovered neighbours (default ON) |
| **Max hops** | Limit on BFS depth (default 5) |
| **Infrastructure only** | Skip CDP/LLDP entries identified as phones, APs, end-user devices (default ON) |

## Click Start

Discovery runs in phases:

### Phase 1 — Seed login

SSH to the seed switch, run `show cdp neighbours detail` and `show lldp neighbours detail`, list its directly-connected peers.

### Phase 2 — Ping sweep (optional)

If you set a subnet, ping-sweep that range. Hosts that respond appear on the map as "grey nodes" (alive but not yet walked).

### Phase 3 — BFS walk

For each discovered neighbour that looks like infrastructure (not a phone / AP / endpoint):

1. Attempt SSH using your seed credentials
2. On successful login: read its neighbours
3. Add new neighbours to the BFS queue
4. Repeat until queue is empty or max hops reached

The map updates live as devices are walked.

### Phase 4 — L3 blending (optional)

If your scope includes routers/firewalls, Discovery also blends in L3 hop information — so you see both L2 (CDP/LLDP) and L3 (routing) relationships in one map.

### Phase 5 — Dedup and tier hierarchy

Devices that appear via multiple paths (dual-homed switches) get merged into a single node. The classifier assigns L2/L3 roles and lays them out in a tier hierarchy: access on the bottom, distribution in the middle, core/WAN on top.

## The live map

The Discovery map updates as devices are walked. You'll see:

- 🟢 Green pulse — node currently being walked
- ✅ Solid green — successfully walked
- ⚠ Yellow — auth failed, infrastructure but couldn't log in
- 🔘 Grey — pinged alive but never walked (no seed credentials worked)
- ❌ Red — explicitly excluded (phone, AP, endpoint)

## Right-click a node for Port Connections

Same Port Connections dialog as L2 topology — shows the per-port MAC + CDP/LLDP table for the selected switch.

Useful workflow: discover a site, spot a switch you don't recognise, right-click it, see what's plugged into each port → answer "what device is on this port?" type questions immediately.

## What gets added to your library

Discovery **does NOT auto-add devices to your library** — discovery is read-only. To add discovered devices:

1. Right-click a discovered node → **Add to Library**
2. The device is added with its detected type, hostname, and any site code matched by your detection rules

## Best practices

- **Pick a well-connected seed**: a distribution or core switch with CDP/LLDP to most of the fabric. An access switch at the edge will only walk a few hops before stopping.
- **Use the same credentials across the fabric**: if every switch has different creds, Discovery stops at the first auth failure.
- **Limit max hops** on large networks: 5 hops covers most enterprise topologies; bumping to 10+ wanders into the unknown.

## Performance

- 50-device discovery, 5 hops, parallel SSH: ~5–10 minutes
- 200-device discovery, 5 hops: ~20–30 minutes
- Larger walks scale roughly linearly

The map updates live, so you can stop the walk early if you've already learned what you needed.

## Saving the map

Same as L2/L3 topology — HTML file in your app support directory. Reload it any time without re-running the discovery.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Discovery stops after one hop | Seed credentials don't work on neighbours | Add per-device credentials or use a global credential that works everywhere |
| Tons of red/yellow nodes | CDP/LLDP entries are mostly endpoints | Tighten the infrastructure filter (Settings → Discovery → Infra gate patterns) |
| Map overlapping labels | Too many nodes in one tier | Discovery has force-direction tuning to spread same-tier nodes — usually self-corrects after a few seconds of layout |
| Walk seems hung | One slow switch holding up parallel workers | Bounded read timeout (45s) per command prevents hangs — wait or restart |

## Next steps

- [L2 topology](topology-l2.md) — for known libraries
- [Find Device](find-device.md) — uses similar BFS to locate one MAC across the fabric
- [Add discovered devices to your library](../library/adding-devices.md)
