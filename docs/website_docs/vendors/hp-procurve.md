# HP ProCurve

HP ProCurve switches (now Aruba OS-Switch since the HPE acquisition) are first-class supported. ProCurve has historically been the most painful vendor for Node Control to detect correctly — the 0.9.x releases include dedicated parsers and detection probes specifically for ProCurve.

## Driver

- Netmiko: `hp_procurve_cli` — aliased internally to `aruba_osswitch` so the same parser handles both labels

## What works

- Detection (with the 0.9.x classifier improvements)
- L2 topology with full CDP / LLDP + MAC table
- L3 topology (OSPF + BGP if configured and licensed)
- Port Utilisation
- Bandwidth (dedicated ProCurve parser branch)
- VLAN Port Finder
- Find Device (full BFS walk + port shut/no-shut)
- Inventory (chassis info, OS version, license state)
- Monitor (CPU, memory, environmental, PoE)

## The detection gotcha

**ProCurve switches accept the `cisco_ios` Netmiko driver silently.** This means:

- An initial connection with `cisco_ios` succeeds
- Commands run but return ProCurve syntax errors / odd output
- The device ends up wrongly classified as cisco_ios in your library

This used to be a chronic problem. The 0.9.x fixes:

1. **SSH banner sniffing**: `SSH-2.0-HP` banners (covering ProCurve, ProVision, and several firmware variants) reorder the try-list so the correct driver is tried first
2. **Post-connect probe**: even if `cisco_ios` succeeds at login, an opportunistic ProCurve detection probe runs — checks for ProCurve prompts, model strings, and specific command behaviour. If it hits, the device is reconnected with `hp_procurve_cli` and re-classified
3. **Persistence lock**: once correctly classified, the device type can be locked (right-click → Lock Device Type) so future scans don't accidentally regress

## Self-learning command catalog

ProCurve firmware varies more than most vendors in command syntax. The catalog has multiple variants per capability:

| Capability | Variants |
|---|---|
| MAC table | `show mac-address`, `show mac address`, `show mac` |
| Interfaces | `show interfaces`, `show interface` |
| LLDP neighbours | `show lldp info remote-device`, `show lldp neighbours-info` |
| CDP neighbours | `show cdp neighbors` (capital N), `show cdp neighbours` |

On first use against a device, all variants are tried until one succeeds. The winning variant is recorded in `device_command_prefs` and used first on future runs.

This means a fresh subnet scan against a mixed-firmware ProCurve fleet self-tunes — older switches running older firmware quietly get the older command syntax.

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| Device shows as cisco_ios after Library Updater | ProCurve detection failed (rare with 0.9.x fixes) | Right-click → Change Device Type → `hp_procurve_cli` → Lock Device Type. Re-run any topology / reports. |
| L2 topology shows all ports filtered as endpoints | ProCurve LLDP often reports phones / PCs by MAC only, no description | The 0.9.x improvements added MAC-only LLDP filter as endpoint detection — should not show as topology nodes. If it still does, check Settings → L2 → Endpoint filter patterns |
| Bandwidth report empty for ProCurve | Pre-0.9.x didn't have a dedicated ProCurve parser branch | Update to 0.9.x+ |
| L3 classification shows ProCurve as core | Multi-VLAN access switches with 30+ SVIs used to default to distribution/core | Fixed in 0.9.x — known access switches with only connected/static routes are always classified access |

## L3 topology classification

For 0.9.x and later, the L3 classifier specifically handles ProCurve:

- L3 capability detected from `show ip route` output
- Multi-VLAN switches (e.g., a ProCurve with 30+ VLAN interfaces) are NOT auto-classified as distribution/core unless they also run BGP / OSPF with external peers
- A ProCurve with only connected + static routes is classified as **access** regardless of VLAN count

## Inventory

`show system` plus `show flash` for OS version. ProCurve's `show inventory`-equivalent is `show modules` for chassis switches.

For stacks (5400zl, 8200zl): each stacked switch appears as a separate Inventory row tagged with stack member ID.

## Aruba OS-Switch (post-HPE-acquisition rebrand)

What was sold as "ProCurve" is now branded "Aruba OS-Switch" (no relation to Aruba CX, which is a different OS). Node Control treats them as the same vendor — the same driver, parsers, and command catalogs work for both.

If you see a switch labeled "Aruba 2530" or "Aruba 2930" in your library, that's an OS-Switch — same detection path as ProCurve.

For the genuinely-different Aruba CX (CX 6000-series, CX 8000-series, etc.) see the [Aruba CX page](aruba.md).

## Next steps

- [Aruba (CX, OS-Switch)](aruba.md) — for the modern Aruba CX OS
- [Custom command catalogs](../settings/custom-commands.md) — to add variants if your firmware uses syntax outside our defaults
