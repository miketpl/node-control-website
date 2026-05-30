# Port Utilisation report

> Available on **Pro** and **AI** tiers only.

For each switch in scope, lists every port with its status, VLAN, MAC count, and traffic counters. Useful for capacity planning, finding unused ports, and spotting interface errors.

## Open the report

- **Reports** tab → **Port Utilisation** → set Scope → **Run**

## What's collected per port

| Column | Source |
|---|---|
| **Port** | Interface name (Gi1/0/1, swp1, ge-0/0/0, etc.) |
| **Status** | up / down / admin-down / err-disabled |
| **Description** | Port description if configured |
| **VLAN** | Access VLAN, or "trunk" for trunk ports |
| **MAC count** | Number of MAC addresses learned on the port |
| **Speed / Duplex** | Negotiated speed and duplex |
| **In octets** | Cumulative inbound bytes since counter reset |
| **Out octets** | Cumulative outbound bytes |
| **In errors** | Inbound error count |
| **Out errors** | Outbound error count |
| **PoE draw** | Power consumed by attached device (watts) |
| **CDP / LLDP neighbour** | If a neighbour is detected on the port |

## Filtering

The filter bar narrows the table by substring across all columns. Common filters:

- `down` — find unused / disconnected ports
- `err-disabled` — find ports that auto-shut due to errors
- `trunk` — find trunks
- `VLAN 100` — find access ports on VLAN 100
- `0 errors` and sort by In errors — find error-free ports

## Per-vendor command set

| Vendor | Commands |
|---|---|
| Cisco IOS / IOS-XE | `show interfaces`, `show interfaces status`, `show interfaces counters errors`, `show mac address-table` |
| Cisco NX-OS | `show interface brief`, `show interface counters`, `show interface counters errors` |
| HP ProCurve | `show interfaces` with the older syntax; counters parsed from the brief output |
| Aruba CX | `show interface`, `show interface brief`, `show mac-address-table` |
| Juniper | `show interfaces extensive`, `show ethernet-switching table` |
| Arista | Cisco-compatible commands |
| Extreme | `show ports`, `show ports configuration` |

The 0.9.x improvements added a dedicated ProCurve parser path so HP devices produce the same column layout as Cisco — this used to fail silently with empty columns.

## Use cases

| Question | How |
|---|---|
| "Which ports are unused on this switch?" | Run for that switch, filter Status = "down" + MAC count = 0 |
| "Which ports have errors?" | Run, sort In errors descending |
| "Where is high PoE draw?" | Sort PoE draw descending → top 5 ports |
| "Which trunks exist?" | Filter VLAN = "trunk" |
| "Is VLAN 100 spread correctly across access switches?" | Filter VLAN = "100", check distribution |

## Export

Same CSV / XLSX / HTML options as other reports.

## Performance

Roughly 30 seconds per switch (parallelised). A 50-switch site takes ~3–5 minutes.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| In/Out octets show 0 on some switches | Vendor's counter command doesn't produce parseable output | Open a ticket with the device's `show interfaces` raw output |
| PoE column empty for everything | Switch doesn't support PoE, or PoE command isn't in the catalog for this vendor | Check Settings → Custom Commands |
| Status column blank for some ports | Port type not recognised (e.g., management interface on some platforms) | Usually safe to ignore — main data is still correct |

## Next steps

- [Bandwidth](bandwidth.md) — for time-windowed traffic vs port-level snapshot
- [VLAN Port Finder](vlan-port-finder.md) — for VLAN-centric questions
