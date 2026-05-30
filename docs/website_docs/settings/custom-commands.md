# Custom command catalogs

Node Control's command catalog maps vendor-and-capability to a specific command (or list of variants to try). For most users, the default catalog covers everything. For unusual firmware or non-standard vendor builds, you can override or add commands per device.

## What's in the catalog

For each (vendor, capability) pair, the catalog stores:

- **Primary command** — what to run first
- **Alternative variants** — fallbacks if the primary fails
- **Output parser** — how to interpret the result

Example for `(cisco_ios, MAC_TABLE)`:

- Primary: `show mac address-table`
- Alternative: `show mac-address-table`
- Alternative: `show mac address`

The first one that returns parseable output wins. The successful variant is recorded per-device so next time, it's tried first.

## Where the catalog lives

The catalog is bundled with Node Control (`core/vendors/command_catalog.py` in the source). Updates ship with each release.

Per-device learned preferences are in:

```
~/Library/Application Support/netOps/netOps.db
```

In the `device_command_prefs` table — one row per (device IP, capability, command, last result).

## When to add a custom command

| Reason | Example |
|---|---|
| Vendor firmware uses different syntax | An old Cisco IOS that uses `show mac-address-table` (hyphenated) when the default catalog tries `show mac address-table` (no hyphen) |
| Custom command produces better output | You wrote a TCL script that returns nicer-formatted MAC tables |
| Vendor not directly supported | You want to use a generic `cisco_ios` driver but customise commands for a special device class |
| Diagnostic / additional data | You want to add a capability that doesn't exist in default catalog |

## Adding a custom command

1. **Settings → Custom Commands**
2. Click **+ Add Override**
3. Fill in:
   - **Vendor / Driver** — pick from dropdown
   - **Capability** — pick (INTERFACES, MAC_TABLE, BGP_PEERS, etc.) or **Custom**
   - **Command** — the actual CLI string
   - **Priority** — Primary / Alternative
   - **Per-device scope** — Apply to all devices of this vendor, or only to specific IPs
4. Save — takes effect on the next task run

## Per-device overrides

If only one device needs a special command (not the whole vendor):

1. Right-click device in library → **Commands** → **Override**
2. Pick a capability → enter the custom command
3. Future runs against this device use the override

## Self-learning behaviour

Even without custom commands, Node Control tunes itself:

- Runs the catalog's primary command first
- If that fails (syntax error, empty output, error keywords), tries the next variant
- Records the winning variant in `device_command_prefs`
- Next time the same capability is needed on that device, tries the recorded winner first
- Variants that have failed are skipped

This means a fresh subnet scan against firmware variations self-tunes — older switches get older syntax, newer ones get newer syntax, no manual intervention.

To inspect what's been learned:

1. Settings → Custom Commands → **View per-device preferences** button
2. Filter to a specific IP
3. See which command variant won for each capability

## Resetting learned preferences

If a device upgrades firmware and the previously-learned command no longer works:

1. Settings → Custom Commands → **Reset per-device preferences**
2. Confirms — clears `device_command_prefs` for the selected device(s)
3. Next task run re-tries the catalog's primary command, re-learns

## Adding a brand-new capability

If you want to add a custom capability not in the default catalog:

1. Settings → Custom Commands → **+ Add Capability** (advanced)
2. Name it — e.g., `MY_CUSTOM_REPORT`
3. Add commands for each vendor
4. The capability appears in the Reports tab as a custom report

This is power-user territory and rarely needed. Most useful for organisations with custom firmware variants or proprietary network OSes built on top of vendor stacks.

## Sharing custom catalogs

Custom command overrides are stored in `settings.json` and `device_command_prefs` in the local DB. To share with a colleague:

1. Export your custom commands via **Settings → Custom Commands → Export**
2. Email the resulting JSON file
3. Colleague imports via **Settings → Custom Commands → Import**

Per-device preferences are tied to specific IPs in your library — they don't transfer cleanly across networks. The catalog-level overrides do.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Custom command doesn't run | Capability name typo | Check the capability constant in the dropdown — must match exactly |
| Output parsed wrong | Custom command produces different format than the standard parser expects | Either match the format, or write a custom parser (advanced — contact support) |
| Per-device preference stuck on old command | Learned preference cached after a firmware change | Reset per-device preferences |

## Next steps

- [Vendor support overview](../vendors/overview.md)
- [Settings overview](overview.md)
