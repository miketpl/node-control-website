# Find Device

The "where is this MAC / IP?" tool. Give Find Device one or more MAC addresses or IPs, and it'll tell you which switch port (or AP) each one is connected to.

## Tier differences

| Tier | What works |
|---|---|
| Free | Pick **one** library switch as the seed; Find Device walks only that switch's MAC table |
| Pro / AI | Pick a site (or All); Find Device walks every site's cores in parallel, recursively follows CDP/LLDP into the fabric, and includes Meraki wireless lookup |

## Open the task

- **Tasks** tab → **Find Device** → **Run**

## Input targets

Paste in one target per line:

```
aa:bb:cc:dd:ee:ff
00:11:22:33:44:55
10.1.5.42
192.168.20.18
```

Mix MAC addresses and IPs freely. Find Device normalises MAC formats (with or without colons, dots, hyphens) and accepts IPs in dotted-quad form.

## Search mode

Pick what to search:

| Mode | What it does |
|---|---|
| **Wired** | Walk the wired fabric only (switches + access points seen via CDP/LLDP). Skip Meraki API lookups. |
| **Wireless** | Query Meraki Dashboard API for wireless clients. Skip wired walks. MACs only. |
| **Unknown** (default) | Run BOTH wired and wireless searches in parallel. Best for "I don't know what this device is." |

In **Unknown** mode, the same target gets searched both ways. A wireless client's MAC also appears in the AP's switchport MAC table, so engineers see both the AP location AND the SSID/network the client is on.

## Wired walk — how it works (Pro / AI)

For each starting core / dist switch (configured per site in Settings):

1. Walk the local MAC address table
2. Match target MACs against the table → if found, also find which port
3. If the target's port is a trunk to another switch (CDP/LLDP confirms), follow that link
4. Recursively walk the downstream switches
5. Stop when:
   - Edge port found (target is on this port)
   - AP port found (target is on the wireless network behind this AP)
   - All cores exhausted with no match

## IP-to-MAC resolution

If you give Find Device an IP address (not a MAC):

1. It first does a VRF-aware ARP probe: SSH to the L3 owner of that IP's subnet, run `show ip arp <ip>` (with VRF if applicable), extract the MAC
2. Then continues the wired walk using the resolved MAC

The probe handles common VRF layouts automatically — no need to tell Find Device which VRF to look in.

## Meraki wireless lookup

If you've configured a Meraki Dashboard API key (Settings → Credentials → Meraki API), Find Device queries every Meraki org your key can access for the target MACs:

- Searches each network in each org
- Returns: org, network, SSID, IP, status (online/offline), last seen, AP name + serial, VLAN

Wireless results appear alongside wired results — one row per finding.

## Results dialog

One row per input target. Columns:

| Column | Meaning |
|---|---|
| **Target** | The MAC or IP you searched for |
| **Source** | Wired / Meraki / Wired+Meraki / — (not found) |
| **Edge Switch** | For wired: the access switch hosting the device. For wireless: the AP name |
| **Port** | For wired: the switchport. For wireless: the SSID |
| **VLAN** | For wired: VLAN ID. For wireless: VLAN from Meraki, if populated |
| **Neighbour** | For wired: CDP/LLDP info on the port. For wireless: AP details |
| **Vendor (OUI)** | MAC manufacturer decoded from OUI prefix |
| **IP Address** | The target IP (if you searched by IP), or the IP Meraki reported for the client |

Right-click a row for additional actions:

- **Shut Port** / **Re-enable Port** (Phase 4 port actions, gated by Safe Mode + type-to-confirm)
- **Copy MAC** / **Copy IP** / **Copy CSV row**
- **Open SSH to Edge Switch**

## Port actions (shut / no-shut)

If you need to disable a port on the edge switch (e.g., contain a compromised device):

1. Right-click the result row → **Shut Port**
2. A type-to-confirm dialog appears — type `SHUTDOWN` to proceed
3. Node Control SSHes to the edge switch, sets the port to admin down
4. The action is recorded in the audit log

The reverse (**Re-enable Port**) follows the same flow with `ENABLE` as the confirmation word.

Port actions are subject to:

- **Safe Mode** must be off (Safe Mode allows only read commands)
- Device type must support the action — currently Cisco IOS / IOS-XE / NX-OS, Aruba, ProCurve, Juniper

See the [audit log](../security/audit-log.md) for what's recorded.

## Performance — Pro / AI

Find Device is heavily optimised in 0.9.26+:

- **IP-prefix prioritisation**: cores sharing the most octets with the target IP are walked first
- **Cross-core pruning**: once a target is found on one core, it's removed from other not-yet-visited cores' pending lists
- **Bounded read timeout** (45s per command): no single slow switch blocks the BFS
- **Subnet-map preflight removed**: 40+ seconds shaved off per search

Typical timing:

- Single switch (Free): 3–10 seconds
- 8-core fabric, 100 access switches: 30–90 seconds depending on where targets are located

## Missing-sites picker

If you search "All sites" and one site has no starting switches configured, Find Device prompts you to pick a starting switch for that site mid-run. Pick one (or skip the site) — the search continues.

## Pre-flight gates

Find Device refuses to run if:

- **Wireless mode** + no MACs in input → "Meraki client search is MAC-keyed. Use Unknown mode for IP→MAC."
- **Wireless mode** + no Meraki API key configured → "Configure a Meraki Dashboard API key in Settings → Credentials → Meraki API."

## Honest "not found" reporting

When Find Device exhausts its search and locates nothing, the progress dialog ends with a red "NO TARGETS LOCATED" banner — not a misleading green tick. The Meraki query breadcrumbs in the run log show exactly how many MACs were sent to Meraki and how many came back as hits.

## Free tier behaviour

On Free, Find Device:

- Shows a single-switch dropdown (populated from your 25-device-capped library, sorted by IP) instead of the per-site cores picker
- Walks only that one switch's MAC table — no recursion
- No Meraki lookup
- A small hint underneath the picker spells out the limitation and links to the [Pro upgrade](../tiers/upgrading.md)

Free is enough for "I know roughly which switch the device is on, what port is it?" — most useful for spot-checks in a small environment.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Wired search returns nothing but you know the device is up | Starting switches not configured for the site | Settings → Find Device → Starting Switches → pick one or more per site |
| Meraki search returns nothing for a known wireless client | API key invalid or wrong org | Test the key in Settings → Credentials → Meraki API → Test |
| One slow switch hangs the search | Pre-0.9.26 you'd have to Ctrl-C — now the 45s bounded timeout prevents this | Update if you're on an older version |
| Right-click → Shut Port is greyed | Safe Mode is on, or device type doesn't support port actions | Disable Safe Mode (Settings → Safe Mode), or check device type |

## Next steps

- [Network Discovery](discovery.md) — for live walks without library setup
- [L2 topology](topology-l2.md) — for the bigger picture of where devices are connected
- [Safe Mode](../settings/safe-mode.md) — when to enable/disable it for port actions
