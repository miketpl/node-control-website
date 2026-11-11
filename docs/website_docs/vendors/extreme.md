# Extreme — EXOS and VSP

Two Extreme switch OSes:

- **EXOS** — Extreme's primary OS (X-series, Summit-series)
- **VSP** — from the Avaya/Nortel acquisition (VSP 4000, 7000, 8000-series)

Both are supported.

## Drivers

| OS | Driver |
|---|---|
| Extreme EXOS | `extreme_exos` |
| Extreme VSP | `extreme_vsp` |

## What works

| Capability | EXOS | VSP |
|---|---|---|
| Detection | ✓ | ✓ |
| Inventory | ✓ | ✓ |
| L2 topology | ✓ | ✓ |
| L3 topology | ✓ | ✓ |
| Port Utilisation | ✓ | ✓ |
| Bandwidth | ✓ | ✓ |
| VLAN Port Finder | ✓ | ✓ |
| Find Device | ✓ | ✓ |
| Monitor | ✓ | partial |

## EXOS — command notes

EXOS has its own command vocabulary distinct from Cisco / Aruba:

- `show fdb` for MAC table (not `show mac-address-table`)
- `show ports` for interface status
- `show vlan` for VLAN list
- `show iproute` for routing table

The 0.9.x release added several missing EXOS capabilities:

- Running / startup config
- VRF list
- Default gateway lookup
- Fan / power / port stats
- Thermal sensors

## VSP — command notes

VSP (legacy Nortel/Avaya) uses different syntax again:

- `show running-config`
- `show interfaces vlan`
- `show fdb-entry`
- `show isis adjacencies` (VSP uses IS-IS for fabric, not OSPF)

The 0.9.x release added missing VSP capabilities for running config, startup config, VRFs, and switchport details.

## First contact and backups

An EXOS switch reached on first contact through the Cisco driver is recognised from `show version` and reconnected on the EXOS driver. Commands no longer wait about 30 seconds each, and backups no longer time out.

Host names are saved without the prompt's changing number. On Free that is the L2 map and backups. On Pro it is Discovery, the topology maps, and backups.

Config Backup reads the whole configuration and saves it only if it is complete. A read that stops early, is missing configuration sections that an earlier backup of the same switch had, or comes from an account without permission, is not saved. The row says why.

The first backup of a switch is read twice and saved only if both reads match. If they differ, for example because the configuration changed in between, nothing is saved. Run the backup again. Later backups are read once and checked against the last good one.

On Pro, the Config Compliance Audit checks EXOS against a complete configuration only, so a configuration that was cut off cannot give a wrong result.

## Detection

EXOS and VSP have distinct prompts. The classifier should pick them apart cleanly, but if you see one detected as the other (or as something generic), manually set + lock.

## SPB / SPBM (Shortest Path Bridging — VSP fabric)

VSP's SPBM fabric is partially visible via L3 topology — IS-IS adjacencies appear as topology edges. The L2 SPBM overlay (ISID-based) is not specifically rendered.

For deeper SPBM visualisation, the vendor's own management tools (XMC / Extreme Management Center) are better.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| MAC table empty | EXOS uses `show fdb`, not `show mac` | Should be in catalog — if not, update to 0.9.x+ |
| VRF list missing | Pre-0.9.x didn't have the EXOS VRF command | Update |
| VSP IS-IS adjacencies not on L3 map | L3 topology task didn't include IS-IS originally | Update to recent version |

## Next steps

- [L2 topology](../tasks/topology-l2.md)
- [Custom command catalogs](../settings/custom-commands.md) — to add variants for unusual EXOS / VSP firmware
