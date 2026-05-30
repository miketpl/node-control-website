# Organising devices by site

A **site** in Node Control is a label that groups devices belonging to the same physical location, customer, or administrative domain. Site codes drive how tools narrow their scope, which devices appear in which topology map, and how reports aggregate.

## What a site code looks like

A site code is typically a short identifier:

| Site code | Meaning |
|---|---|
| `LON` | London office |
| `NYC` | New York office |
| `BR01` | Branch 01 |
| `DC1` | Data centre 1 |
| `ACME` | Customer Acme Networks |

Two to four characters is the sweet spot — long enough to be unambiguous, short enough to fit in hostname schemes.

## How site codes get assigned

Three ways:

1. **Auto-detected from hostname** (most common) — Node Control extracts the site code from the hostname using a regex
2. **Manually set** — right-click a device → **Edit Device** → set Site code
3. **Bulk-assigned by site detection rule** — configured in Settings

## Auto-detection from hostname

Most network operators name devices with a hostname convention that embeds the site code. Examples:

| Hostname | Extracted site code |
|---|---|
| `LON-CORE-SW-01` | `LON` |
| `nyc-dist-fw-pri` | `NYC` |
| `BR01_ACCESS_03` | `BR01` |
| `ACME-LON-CORE-1` | depends on regex — could be `ACME` or `LON` |

Node Control's default site detection regex looks for an alphabetic prefix at the start of the hostname. If your hostnames are different, you can customise the regex in **Settings → Site Detection**.

See [Site detection rules](../settings/site-detection.md) for the configuration details.

## Filtering the library by site

In the Engineer tab, the top-left **Site** dropdown shows every unique site code in your library plus an "All" option. Pick one to filter the table.

## Running tasks for a single site

Most tasks have a **Scope** option:

| Scope | What it means |
|---|---|
| **All devices** | Run across the entire library (slow on large libraries) |
| **Site X** | Run only against devices tagged with site X |
| **Individual** | Pick one device to run against |

For Reports, Discovery, Find Device, and Topology, you'll typically pick a specific site to keep runtime manageable.

## Sites and Find Device

Find Device has a per-site concept of **starting switches** (cores). For each site, you configure one or more switches that serve as the BFS entry points:

1. **Settings → Find Device → Starting Switches**
2. For each site, pick 1–3 switches that are CDP/LLDP-connected to most of the access layer
3. Find Device will walk those switches first, then traverse out from there via CDP/LLDP

If you don't configure starting switches for a site and try to run Find Device for that site, you'll get a "missing starting switches" prompt asking you to pick now.

## Sites and topology maps

When you run L2 / L3 / WAN topology with **Scope = Site X**, only devices in that site are walked. The resulting map shows only that site's switches, routers, firewalls, and the links between them.

This keeps the maps readable — a 200-device customer network broken into 8 site maps is much more useful than one massive 200-device map.

## Renaming a site

To change a site code (e.g., from `LON` to `LDN`):

1. Right-click any device with the old code → **Edit Device**
2. Change the Site code field
3. Save
4. Repeat for every device, OR use a SQL bulk update against the local DB:

```sql
UPDATE devices SET site_code = 'LDN' WHERE site_code = 'LON';
```

(Be careful with direct DB edits — close the app first, then run via `sqlite3 ~/Library/Application\ Support/netOps/netOps.db`.)

## Devices with no site code

Devices added without a site code (and where auto-detection didn't match) appear under the "Unassigned" site in the filter dropdown. To bulk-assign:

1. Filter to Unassigned
2. Select multiple devices (Cmd/Ctrl + click)
3. Right-click → **Set Site Code** → pick from existing codes or type a new one

## Best practice — pick a convention and stick with it

The most maintenance-free setup is one where every device's hostname encodes the site code, so auto-detection just works. If you're starting from scratch:

- Decide on 2–4 character site codes
- Use them consistently in hostnames (e.g., `<SITE>-<ROLE>-<NUMBER>` like `LON-CORE-01`)
- Configure site detection regex to match your format
- Run Library Updater on each site's management subnet — devices auto-land in the right site

For environments with inconsistent hostname conventions, you'll end up manually assigning site codes after import. Still useful, but more work.

## Next steps

- [Site detection rules](../settings/site-detection.md) — customise the regex
- [Find Device](../tasks/find-device.md) — uses site codes for cores
- [Topology maps](../tasks/topology-l2.md) — render one map per site
