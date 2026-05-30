# Device type misdetection

When Node Control identifies a device as the wrong vendor / OS, downstream tasks (topology, reports, Find Device) send the wrong commands → empty results, parsing errors, or outright failures.

This page covers diagnosis and fix.

## Why misdetection happens

Multiple causes:

1. **Vendors share CLI conventions** — HP ProCurve accepts the `cisco_ios` Netmiko driver silently. Aruba CX shares prompt style with Cisco. The classifier has to disambiguate from `show version` output, which isn't always definitive
2. **Firmware variations** — older firmware may return different `show version` text than current firmware, missing the signature strings
3. **Custom hostnames** — a Cisco switch named "JUNIPER-SW-01" trips no auto-detection logic, but it might confuse a human looking at the library
4. **Library imports** — devices added via CSV or copied from another library may have stale or wrong device types

## How to confirm misdetection

Symptoms vary by what's failing:

| Symptom | Likely | Confirm via |
|---|---|---|
| Topology missing a device | Wrong device type → wrong commands → no neighbour data | Right-click → Test Connection — check the reported type |
| Inventory has blank columns for a device | Wrong type → parser doesn't match output | Same as above |
| Find Device returns nothing for a known-good IP | Wrong type → ARP probe / MAC table command fails | Same as above |
| Reports skip a device | SSH error or empty output → wrong commands | Check the run log for per-device errors |

## Step 1 — Test Connection to see detected type

1. Engineer tab → right-click device → **Test Connection**
2. The popup message includes the detected type:
   - "Connected as cisco_ios. Hostname: SW-01" ← detected as cisco_ios
3. If this is wrong, proceed to Step 2

## Step 2 — Manually set the correct type

1. Right-click device → **Change Device Type**
2. Pick the correct Netmiko driver from the dropdown:
   - HP ProCurve / Aruba OS-Switch → `hp_procurve_cli` (alias `aruba_osswitch`)
   - Aruba CX → `aruba_os`
   - Palo Alto → `paloalto_panos`
   - Juniper → `juniper_junos`
   - (full list in [Vendor overview](../vendors/overview.md))
3. Save

## Step 3 — Lock the device type

To prevent future detection runs from overwriting your manual setting:

- Right-click device → **Lock Device Type**

A small lock icon appears next to the type in the table. Auto-detection now skips this device.

## Step 4 — Re-run failed tasks

After fixing the type, the previous results are stale (they were collected with wrong commands). Re-run:

- Topology / reports / Find Device / Inventory

Output cache is per-(device, capability, timestamp), so it'll re-fetch with the correct commands.

## Bulk fix — Verify Device Types task

For multiple wrong devices, the [Verify Device Types task](../tasks/verify-device-types.md) sweeps the library and re-detects every device, prompting you for each mismatch.

Particularly useful after inheriting a library from another engineer or upgrading from a Node Control version with weaker detection.

## When auto-detection keeps getting it wrong

If you set type → lock → it still gets reset:

- The lock is a database flag — should never be overridden by auto-detect
- If it IS being overridden, that's a bug — please report

## Specific vendor known issues

### HP ProCurve detected as cisco_ios

The classic. 0.9.x added:

- SSH banner sniffing (`SSH-2.0-HP` patterns)
- Post-connect probe for ProCurve-specific commands
- The probe usually catches mis-classification automatically

If still happening on 0.9.x+, please open a support ticket with the device's `show version` output.

### Aruba CX detected as cisco_ios

Less common but possible. Same fix path: manual set + lock.

### Palo Alto detected as cisco_ios

PA's `>` prompt looks like Cisco's user mode. The opportunistic `show system info` probe should catch this. If not, manual override + lock.

### Cisco IOS detected as cisco_xe (or vice versa)

Less impactful — both drivers run mostly the same commands. Manual override only needed if specific tasks fail.

### Generic Linux box detected as cisco_ios

The generic Linux driver is the fallback when nothing else matches. If a Cisco box ends up labeled `linux`, the classifier missed it — manual override.

## When the wrong type was inherited from import

If you imported a library via CSV or pull-from-GitHub and a bunch of devices have wrong types:

1. Run **Verify Device Types** with scope = All Devices
2. Apply the corrections in bulk
3. Optionally tick "Apply and lock" for each

This is the fastest cleanup path.

## "Inconclusive" detection

If `show version` output doesn't match any known vendor signature:

- The classifier returns "inconclusive"
- The device keeps whatever type was previously set (or nothing if never set)
- Manual override is required

This is rare on modern firmware. Most often happens with:

- Customised vendor builds with non-standard `show version` headers
- Very old firmware (pre-2010) with unusual output format
- Network OS forks (e.g., a Cumulus-flavoured Mellanox box)

If you have a class of devices that consistently come up inconclusive, send us a sample `show version` output and we'll add the signature.

## Confidence and recovery

The detection system is designed to be:

- **Conservative**: when in doubt, leaves the existing type alone rather than guessing
- **Reversible**: every detection decision is logged in the audit log; you can see what happened and when
- **Override-respectful**: manual + locked types are never overwritten

This makes detection issues recoverable — they don't cascade silently.

## Next steps

- [Vendor overview](../vendors/overview.md)
- [Verify Device Types task](../tasks/verify-device-types.md) — for bulk re-detection
- [HP ProCurve specifics](../vendors/hp-procurve.md) — the most-common misdetection vendor
