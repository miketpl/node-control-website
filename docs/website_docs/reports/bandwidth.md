# Bandwidth report

> Available on **Pro** and **AI** tiers only.

Per-interface bandwidth statistics across one or more devices. Like Port Utilisation, but focused on traffic volumes and top-talkers rather than per-port capacity.

## Open the report

- **Reports** tab → **Bandwidth** → set Scope → **Run**

## What's collected

For each interface on each device in scope:

| Column | Source |
|---|---|
| **Port** | Interface name |
| **Description** | Port description if configured |
| **5-min avg in** | Average inbound traffic over the last 5 minutes (Mbps) |
| **5-min avg out** | Average outbound traffic over the last 5 minutes (Mbps) |
| **Peak in** | Peak inbound observed (Mbps) |
| **Peak out** | Peak outbound observed (Mbps) |
| **In utilisation %** | 5-min avg in / link speed |
| **Out utilisation %** | 5-min avg out / link speed |
| **Link speed** | Negotiated speed (Mbps or Gbps) |

## Top talkers view

Toggle to **Top talkers** view to see the N busiest interfaces across the entire scope, ranked by combined in+out average.

Useful for "where's most of our traffic going through?" — the answer is usually a handful of uplinks, and Bandwidth surfaces them immediately.

## Per-vendor command set

| Vendor | Commands |
|---|---|
| Cisco IOS / IOS-XE | `show interfaces` — average / peak rates parsed from output |
| Cisco NX-OS | `show interface counters detailed` |
| HP ProCurve | `show interfaces detail` — new ProCurve branch added in 0.9.x for proper parsing |
| Aruba CX | `show interface` extended |
| Juniper | `show interfaces extensive` |
| Arista | Cisco-compatible |

## Time window

Vendors typically report:

- 5-minute moving average (most common)
- 30-second moving average (Cisco)
- 1-minute / 5-minute / 15-minute load averages (Juniper)

Node Control uses the most-stable common metric across vendors, which is the 5-minute moving average. For shorter-window observation, use [Monitor](../tasks/monitor.md) instead.

## Saturation alerts

In the result table, utilisation cells are colour-coded:

- 🟢 Green: < 50%
- 🟡 Yellow: 50% – 80%
- 🔴 Red: > 80%

Sort by In or Out utilisation to find saturated links instantly.

## Use cases

| Question | How |
|---|---|
| "Where are my busiest uplinks?" | Bandwidth → Top talkers view → sort by Combined avg |
| "Is the WAN circuit saturated?" | Bandwidth → filter to WAN router → check uplink utilisation |
| "Which switches are pushing the most traffic to the core?" | Bandwidth → All switches → sort by Out utilisation |
| "Trend over time" | Not from Bandwidth — use [Monitor](../tasks/monitor.md) with sample persistence |

## Export

CSV / XLSX / HTML, same as other reports.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| All counters show 0 | Counter reset recently or device just rebooted | Wait 5 min and re-run |
| Some interfaces missing | Sub-interfaces or VLAN interfaces aren't counted by default | Settings → Reports → Include sub-interfaces |
| Wildly inflated peak values | Single short burst skews the peak | Use 5-min avg as the more reliable indicator |

## Next steps

- [Port Utilisation](port-utilisation.md) — for per-port detail
- [Monitor](../tasks/monitor.md) — for continuous polling with time-series graphs
