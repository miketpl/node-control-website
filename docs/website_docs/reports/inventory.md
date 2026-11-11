# Inventory report

Available on **Free**, **Pro**, **AI**.

The Inventory report walks each device in scope and collects hostname, IP, device type, model, OS version and serial. It is an HTML report you can filter and export to CSV. There is no uptime column and no Excel export.

## Open the report

- **Reports** in the left sidebar → **Inventory** → set Scope → **Run**

## What's collected per device

For each device, Inventory runs the vendor-equivalent of `show version` plus a few targeted commands, and extracts:

The columns are hostname, IP, device type, model, OS version and serial. Stack members get their own rows.

## Result table

The report is a self-contained HTML page. A text filter and device-type buttons are in that page. Filtering by a model such as 9300, or by an IOS version, works there. There is no show/hide column menu.

## Export

The HTML report has **Export Inventory (CSV)** and **Export Inventory (JSON)**. There is no Excel export.

Device names and other text read from devices are shown as plain text on this report. A device name containing page code cannot change or run anything in the page.

## Free

Inventory is the report that runs on Free, on the devices you tick. Every other report is on Pro and the AI edition. See [Reports overview](overview.md).

## Vendor-specific quirks

Different vendors expose different inventory data:

| Vendor | Special notes |
|---|---|
| Cisco IOS / IOS-XE | Full inventory via `show inventory` |
| Cisco NX-OS | `show inventory` plus per-line-card detail |
| HP ProCurve | `show system` for chassis, `show flash` for OS version |
| Aruba AOS-CX | Model, serial, and version |
| Juniper Junos | `show version`, `show chassis hardware` for stack/cluster detail |
| Arista EOS | Model, serials, and the EOS version, from EOS output |
| Dell OS6/OS10 | `show system`, `show version` |
| Extreme EXOS | `show system`, `show version` |
| Palo Alto PAN-OS | `show system info` |
| Meraki | API-only (no SSH) — uses Dashboard inventory endpoint |

## Stack / chassis devices

For stacks (Cisco 3850 stack, Aruba CX VSF, Juniper VC) and chassis (Cisco 9500, Arista 7300, Juniper MX), each member appears as a separate row tagged with the master's hostname plus member number.

For modular chassis (e.g., 9500 supervisor + linecards), the report shows each line card model and serial.

## Cluster / HA pair handling

Active/standby firewall pairs appear as two rows.

## Filtering

You can filter the HTML report with a text box and device-type buttons. Filtering by 9300, or by an IOS version, works there. There is no uptime column.

## Use cases

| Question | How |
|---|---|
| "What's our total switch count?" | Inventory → filter by device type |
| "Which devices are EoL?" | Filter the HTML report by model |
| "Are all our serials matching the asset register?" | Export CSV → diff against your asset register |
| "Who's still running 12.x train Cisco IOS?" | Inventory → filter OS Version column for "12." |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Some devices show blank serial | Vendor's `show inventory` doesn't include serial for that device class | Check the raw output by SSH'ing into a sample device and looking at the inventory command |
| Reports show old data | Output cache (10 min) | Tick **Skip cache** in the run config |
| Some devices missing entirely | Failed SSH auth or unreachable | Check the run log for per-device errors |

On Cisco NX-OS, the host name comes from `Device name:` and is not `Kernel`. Inventory reads the Nexus model (for example N9K-C93180YC-EX) and the NX-OS version instead of the BIOS version.

On Cisco IOS / IOS-XE, Inventory reads the model from the `cisco <model>` line of `show version` when there is no Model Number line, the same way Asset Lifecycle does.

On HP ProCurve / Aruba OS-Switch firmware with a two-column `show system`, the serial number in the right-hand column is read.

## Next steps

- [Other reports](overview.md)
- [Verify Device Types](../tasks/verify-device-types.md) — for fixing device type misdetection that affects Inventory
