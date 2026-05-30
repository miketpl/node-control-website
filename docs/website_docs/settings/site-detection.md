# Site detection rules

How Node Control extracts a site code from a device's hostname.

## What's a site code

A short identifier (typically 2–4 characters) that groups devices belonging to the same physical location or administrative domain. Examples: `LON`, `NYC`, `BR01`, `DC1`.

Site codes drive filters, scopes, and per-site behaviour throughout the app. See [Sites](../library/sites.md) for the broader context.

## How auto-detection works

When Node Control encounters a device with a hostname (either set manually or fetched from `show version`), it runs the hostname through a regex pattern. The first capture group becomes the site code.

The default pattern extracts an alphabetic prefix:

```
^([A-Za-z]+)
```

So `LON-CORE-SW-01` → `LON`, `nyc-fw-pri` → `nyc` (auto-uppercased to `NYC`), `BR01_ACCESS_03` → `BR` (alphabetic only — number stripped).

## When the default works

If your hostname convention is `<SITE>-<role>-<number>` or `<SITE>_<role>_<number>` and `<SITE>` is alphabetic, the default regex works. Confirm with a sample:

1. Settings → **Site Detection**
2. The **Test** field accepts a hostname; type one
3. The result shows the extracted site code
4. Adjust regex if needed

## When you need a custom regex

Common variations and matching regex:

| Hostname format | Example | Regex |
|---|---|---|
| `<SITE>-<role>-<n>` (alphabetic site) | `LON-CORE-1` | `^([A-Za-z]+)` (default) |
| `<SITE><role><n>` (no separator) | `LON-CORE1` → split by chars | `^([A-Z]{3})` |
| `<role>-<SITE>-<n>` (site in middle) | `CORE-LON-1` | `^[A-Z]+-([A-Z]+)` |
| `<SITE>_<role>_<n>` (underscore separator) | `LON_CORE_1` | `^([A-Za-z]+)_` |
| `<n>-<SITE>-<role>` (number prefix) | `01-LON-CORE` | `^\d+-([A-Z]+)-` |
| `<customer>-<SITE>-<role>` | `ACME-LON-CORE-1` | `^[A-Z]+-([A-Z]+)-` (extracts LON, skipping customer) |
| Numeric site code | `BR01-CORE-1` | `^([A-Z]+\d+)` (matches `BR01`) |
| Numeric site code only | `01-CORE-1` | `^(\d+)` |

## Configuring the regex

1. Settings → **Site Detection**
2. **Regex pattern** field — type the pattern
3. **Test hostname** field — paste a sample
4. **Test result** shows what the regex would extract
5. Adjust until samples produce the right site codes
6. Click **Save** — regex applied to all future hostname-to-site lookups

## Adaptive detection

Node Control's site detection is more than just a single regex — it's an adaptive system:

1. **Manual override always wins** — if you've set a site code manually on a device, the regex is ignored
2. **Last successful extraction is remembered** — if a device's hostname was already extracted to a site code, that's used unless the hostname changes
3. **Multi-pattern fallback** — if you've configured multiple regex patterns (advanced), they're tried in order

Most users only need one regex. The fallback is for complex environments where different hostname conventions exist in different parts of the library.

## Re-running detection on existing devices

After changing the regex, existing devices keep their old (potentially wrong) site codes — the change only applies to future hostname updates.

To re-detect for all devices:

1. Settings → Site Detection → **Re-detect all** button
2. Confirms — overwrites all site codes with what the current regex extracts
3. Doesn't touch devices with manually-set codes (they stay)

## Hostname formatting normalisation

Site codes are normalised:

- Auto-uppercased
- Whitespace trimmed
- Length capped at 8 characters

So `lon` and `LON  ` both produce site code `LON`.

## Reading the site code in tasks

Site codes are visible in:

- The Engineer tab's Site filter dropdown
- Every task's Scope = "Site X" picker
- The columns of most reports
- The hover tooltips on topology nodes

## Hostnames with no extractable site code

Devices where the regex doesn't match get site code = empty string. They appear under "Unassigned" in the Site filter.

To bulk-assign:

1. Filter Engineer tab to Unassigned
2. Select multiple devices
3. Right-click → Set Site Code → type the code
4. Save

## Best practice — hostname convention first

The most maintenance-free setup is one where every device's hostname encodes the site code consistently, so a single regex covers everything. If you're inheriting a library with inconsistent hostnames:

1. Standardise hostnames if you can
2. Use bulk site-code assignment in Node Control for the rest
3. As devices get renamed over time, the regex re-applies cleanly

## Next steps

- [Library — Sites](../library/sites.md)
- [Find Device — uses site codes for cores](../tasks/find-device.md)
