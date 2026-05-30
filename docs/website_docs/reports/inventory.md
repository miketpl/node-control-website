# Inventory report

Available on **Free**, **Pro**, **AI**.

The Inventory report walks each device in scope and collects hardware/software information — model, serial number, OS version, uptime, etc. The standard "what do we have?" report.

## Open the report

- **Reports** tab → **Inventory** → set Scope → **Run**

## What's collected per device

For each device, Inventory runs the vendor-equivalent of `show version` plus a few targeted commands, and extracts:

| Field | Source command |
|---|---|
| Hostname | `show version` / `show hostname` |
| Vendor | (from detected device type) |
| Model | `show version` / `show inventory` |
| Serial number | `show inventory` / `show chassis hardware` |
| OS version | `show version` |
| Uptime | `show version` |
| Last config save | `show running-config | include ^!` or vendor equivalent |
| MAC address (mgmt) | `show interfaces <mgmt>` |
| IP address | (from library) |
| Site code | (from library) |
| License state | Cisco/Aruba/PA — `show license` |

## Result table

Sortable, filterable. Columns are configurable via the column header menu (right-click a column → show/hide).

Default visible columns: Hostname, IP, Site, Vendor, Model, OS Version, Serial, Uptime.

Hidden by default but available: Last config save, Mgmt MAC, License state, Notes.

## Export

- **CSV** — for spreadsheet import
- **XLSX** — Excel-native with formatting preserved
- **HTML** — self-contained file with the report's styles

The HTML export includes a header with run timestamp, scope, and total device count — useful for compliance reporting.

## Free tier — scope behaviour

On Free, the Inventory scope selector is locked to **INDIVIDUAL** only (single device pick). All Devices and per-site scopes are Pro features.

Workaround for Free users who want a multi-device inventory: run [Library Updater](../library/subnet-scan.md) first (which is not capped on Free) — it produces device-list output as it scans, which serves as a quick inventory snapshot.

## Vendor-specific quirks

Different vendors expose different inventory data:

| Vendor | Special notes |
|---|---|
| Cisco IOS / IOS-XE | Full inventory via `show inventory` |
| Cisco NX-OS | `show inventory` plus per-line-card detail |
| HP ProCurve | `show system` for chassis, `show flash` for OS version |
| Aruba CX | `show system`, `show version`, `show software` |
| Juniper Junos | `show version`, `show chassis hardware` for stack/cluster detail |
| Arista EOS | `show version`, `show inventory` |
| Dell OS6/OS10 | `show system`, `show version` |
| Extreme EXOS | `show system`, `show version` |
| Palo Alto PAN-OS | `show system info` |
| Meraki | API-only (no SSH) — uses Dashboard inventory endpoint |

## Stack / chassis devices

For stacks (Cisco 3850 stack, Aruba CX VSF, Juniper VC) and chassis (Cisco 9500, Arista 7300, Juniper MX), each member appears as a separate row tagged with the master's hostname plus member number.

For modular chassis (e.g., 9500 supervisor + linecards), the report shows each line card model and serial.

## Cluster / HA pair handling

Active/standby firewall pairs (Palo Alto, ASA, Checkpoint, Fortigate) appear as two rows. The HA status column shows which is active, which is standby — useful during failover validation.

## Filtering

The filter bar above the result table accepts substring matches across all columns. Useful filters:

- `9300` — find all Catalyst 9300s
- `15.x` — find devices on IOS 15.x trains
- `2018-` — find devices reporting an uptime starting from 2018
- `LON` — find devices in the LON site (if Site column is shown)

Multi-column ranking (filtering by multiple criteria) is via the filter dialog: click the funnel icon next to each column header.

## Use cases

| Question | How |
|---|---|
| "What's our total switch count?" | Inventory → All Devices → sort by Vendor → count Cisco/HP/Aruba rows |
| "Which devices are EoL?" | Inventory → All → filter by Model → cross-reference against vendor EoL announcements |
| "Are all our serials matching the asset register?" | Export CSV → diff against your asset register |
| "Who's still running 12.x train Cisco IOS?" | Inventory → filter OS Version column for "12." |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Some devices show blank serial | Vendor's `show inventory` doesn't include serial for that device class | Check the raw output by SSH'ing into a sample device and looking at the inventory command |
| Reports show old data | Output cache (10 min) | Tick **Skip cache** in the run config |
| Some devices missing entirely | Failed SSH auth or unreachable | Check the run log for per-device errors |

## Next steps

- [Other reports](overview.md)
- [Verify Device Types](../tasks/verify-device-types.md) — for fixing device type misdetection that affects Inventory
