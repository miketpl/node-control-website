# VLAN Port Finder

> Available on **Pro** and **AI** tiers only.

Find every port on every switch in scope that's a member of a given VLAN (or matches a VLAN filter).

The classic "where is VLAN 100 carried?" question, answered fleet-wide in one report.

## Open the report

- **Reports** tab → **VLAN Port Finder** → set Scope → set VLAN filter → **Run**

## Configure

| Field | What it controls |
|---|---|
| **Scope** | All devices, single site, or individual |
| **VLAN(s)** | A single VLAN ID, comma-separated list (`100, 200, 300`), or range (`100-200`) |
| **Include trunks** | Whether to include trunks where the VLAN is allowed (ON) or only access ports (OFF) |
| **Include voice VLANs** | Whether to count voice VLANs as separate entries |

## Result table

| Column | Source |
|---|---|
| **Device** | Hostname |
| **Site** | Site code |
| **Port** | Interface name |
| **Description** | Port description |
| **VLAN** | The VLAN ID found |
| **Type** | Access / Trunk / Voice |
| **Status** | up / down / err-disabled |
| **MAC count** | MACs on this port in this VLAN |
| **Neighbour** | CDP/LLDP if present |

## Per-vendor capability

Reports knows which command to run on each vendor:

| Vendor | Command |
|---|---|
| Cisco IOS / IOS-XE | `show vlan brief`, `show interfaces trunk`, `show interface switchport` |
| Cisco NX-OS | `show vlan`, `show interface switchport`, `show vlan extended` |
| HP ProCurve | `show vlan <id>`, `show vlans port` |
| Aruba CX | `show vlan`, `show interface vlan` |
| Juniper | `show vlans extensive` |
| Arista | Cisco-compatible |

For vendors without native "show VLAN X interfaces" support, Node Control walks every interface and filters client-side. Slower but works.

## Use cases

| Question | How |
|---|---|
| "Where is VLAN 100?" | VLAN Port Finder → VLAN = 100 → All Devices |
| "Which switches have an unused VLAN range I can reclaim?" | Run for VLAN range 4000-4094 → find switches with no ports in any of them |
| "Is the voice VLAN consistent across access switches?" | Run for voice VLAN ID, scope = single site → check all access switches show it as Voice type |
| "How many ports are on the user VLAN?" | Run for the user VLAN → count rows where Type = Access |

## Capability-aware lookup

If a vendor doesn't support the report (e.g., a basic L2 switch with limited CLI), the result table simply omits those devices and notes them in the run log. The other devices in scope still report normally.

## Saving / exporting

CSV / XLSX / HTML — same as other reports.

## Use with Port Utilisation

For "find VLAN X" + "show its utilisation" combined:

1. Run VLAN Port Finder for the VLAN → get a list of ports
2. Run Port Utilisation for the same scope
3. Cross-reference manually, or export both CSVs and merge in a spreadsheet

A future release may combine these into a single "VLAN bandwidth" report — let us know if this matters.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| VLAN not found anywhere but you know it exists | Sources of truth disagree — e.g., VTP propagation issue | Open SSH to a switch where it should be and run `show vlan brief` manually |
| Trunk ports not appearing | "Include trunks" toggle is OFF | Toggle ON and re-run |
| Voice VLANs counted twice | "Include voice VLANs" interacts with vendor-specific behaviour | Try toggling and compare |

## Next steps

- [Port Utilisation](port-utilisation.md)
- [Find Device](../tasks/find-device.md) — for the inverse question ("which port is this MAC on?")
