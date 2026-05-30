# Dell — OS6 and OS10

Dell switches come in two CLIs:

- **OS6** — older PowerConnect-style CLI (N-series, X-series)
- **OS10** — modern Linux-based, Cumulus-like (S-series, Z-series)

Both are supported.

## Drivers

| OS | Driver |
|---|---|
| Dell OS6 | `dell_os6` |
| Dell OS10 | `dell_os10` |

## What works

| Capability | OS6 | OS10 |
|---|---|---|
| Detection | ✓ | ✓ |
| Inventory | ✓ | ✓ |
| L2 topology | ✓ | ✓ |
| L3 topology | partial | ✓ |
| Port Utilisation | ✓ | ✓ |
| Bandwidth | ✓ | ✓ |
| VLAN Port Finder | ✓ | ✓ |
| Find Device | ✓ | ✓ |
| Monitor — CPU/Mem | ✓ | ✓ |
| Monitor — environmental | ✓ | ✓ |
| Monitor — PoE | ✓ | ✓ |

## Dell OS6 — command catalog notes

OS6 has some Dell-specific syntax differences. The catalog covers:

- `show interfaces` (port stats)
- `show inventory` (chassis)
- `show vlan` (VLAN list)
- `show mac address-table` (MAC table)
- `show lldp remote-device all` (neighbours)

The 0.9.x release fixed several OS6 command syntax errors:

- CPU / memory commands corrected
- Environment commands fixed
- Port-channel commands aligned to actual Dell syntax

## Dell OS10 — Linux-flavoured

OS10 sits on Debian. Most network commands look familiar (Cisco-like), but:

- Some `show` commands have JSON output options (Node Control uses CLI text)
- `show route` instead of `show ip route` for default gateway
- `show running-configuration` for full config

The 0.9.x release switched OS10 default gateway from a config-grep approach to a proper `show route` lookup.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| OS6 detected, but reports show empty CPU | Pre-0.9.x had wrong CPU command for OS6 | Update to 0.9.x+ |
| OS10 default gateway blank | Older versions used config grep | Update to 0.9.x+ |
| Stack members not enumerated | Dell stacks vary in CLI exposure | Most modern stacks (N4000, S3000, etc.) work; older PowerConnects may not |
| Detection picks generic `cisco_ios` | Banner not sniffed | Manual override + lock |

## Stacking

Dell N-series and S-series stacks appear as one logical device with multiple members in Inventory.

## VLT (Virtual Link Trunking)

VLT pairs on OS10 (Dell's equivalent of Cisco vPC / Arista MLAG) — both members appear separately. The peer link is visible via LLDP.

## Cumulus → OS10 transition

Older Dell switches that ran Cumulus Linux are now mostly converted to OS10. If you have legacy Cumulus boxes, use the generic `linux` driver:

- Connectivity works
- Inventory is limited
- Topology / reports are mostly empty (Cumulus has different commands)

Migrating those boxes to OS10 (or replacing them) restores full Node Control coverage.

## Next steps

- [Custom command catalogs](../settings/custom-commands.md) — add variants for unusual firmware
