# Verify Device Types

> Available on **Pro** and **AI** tiers only.

A bulk sweep that re-runs device type detection across every device (or a subset) in your library. Useful when:

- You suspect device type misdetection is affecting reports / topology
- Library Updater added devices with the wrong type
- A site upgraded its switches and the library is out of sync
- You're inheriting a library from another engineer and want to validate

## Open the task

- **Tasks** tab → **Verify Device Types** → **Run**

## Configure

| Setting | What it controls |
|---|---|
| **Scope** | All devices, single site, or individual |
| **Skip locked** | Whether to skip devices with **Device type locked** flag (default ON — locks were set deliberately) |
| **Parallelism** | Concurrent SSH connections (default 10) |

## What happens

For each device in scope:

1. SSH using configured credentials
2. Run `show version` (or vendor equivalent)
3. Match output against the known vendor signature regex set
4. Compare detected type against the type stored in the library
5. Log: matched / mismatched / unreachable / not enough info

## Results

A summary dialog appears when the sweep completes:

```
Verify Device Types — completed
  Total scanned: 234
  Matched (no change): 198
  Mismatched (updated): 28
  Auth failures: 5
  Inconclusive: 3
```

A details table lists each mismatched device:

- Old type
- New (correct) type
- Confidence level

For each mismatch, you decide:

- **Apply** — update the library entry
- **Skip** — leave the library as-is, ignore this run
- **Apply and lock** — update + flag the device so future detection runs don't change it again

## Why mismatches happen

- A switch was reflashed to a different OS (IOS → NX-OS, ProCurve → ArubaOS-Switch)
- A previous detection picked the wrong driver (HP ProCurve accepting `cisco_ios` is the classic case)
- A device was replaced with a different model that shares the management IP
- Hostname / `show version` output changed in a way that confused the detector

The 0.9.x classifier improvements catch most known misdetection cases automatically — but legacy libraries built before those fixes often have stale wrong types that Verify Device Types can clean up in one run.

## When to use

| Frequency | When |
|---|---|
| One-off | After importing a library from another engineer or system |
| Monthly | Standard hygiene for production libraries |
| After a network change | Whenever switches are replaced or reflashed |
| After Library Updater | Optional sanity check on bulk-added devices |

## Locked devices

If you've manually set a device type and locked it (right-click → **Lock Device Type**), Verify Device Types will skip it by default — your manual setting wins. To force-revalidate locked devices, uncheck **Skip locked** in the run config.

## Timing

Roughly 10–20 seconds per device with parallelism 10. A 200-device library takes ~5 minutes.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Auth failures on devices that previously worked | Credential rotation | Update credentials in Settings |
| "Inconclusive" results | Device's `show version` output doesn't match known patterns | Open a support ticket with the raw output — we'll add a signature |
| Same mismatch keeps recurring | Mismatch is real but detection keeps flipping | Apply and lock the device type once you're confident in the correct value |

## Next steps

- [Library Updater](../library/subnet-scan.md) — the subnet-scan flow that often populates types in the first place
- [Adding devices manually](../library/adding-devices.md) — for fine-grained control over device types
