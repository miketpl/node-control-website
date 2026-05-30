# Reports overview

Reports run a specific data-collection workflow across one or more devices and render a structured result — typically a table, sometimes an interactive map.

## Open the Reports tab

- Top-level **Reports** tab (alongside Engineer, Discovery, Tasks, Monitor)

## Report types

| Report | Free | Pro | Purpose |
|---|:---:|:---:|---|
| [Inventory](inventory.md) | ✓ | ✓ | List devices with hardware model, OS version, serial number |
| [Port Utilisation](port-utilisation.md) | — | ✓ | For each port: status, VLAN, MAC count, in/out traffic |
| [Bandwidth](bandwidth.md) | — | ✓ | Aggregate in/out bandwidth per interface, top talkers |
| [VLAN Port Finder](vlan-port-finder.md) | — | ✓ | "Which ports are on VLAN X?" across the fleet |
| [Meraki Usage Summary](meraki-usage-summary.md) | — | ✓ | Per-org and per-network Meraki usage stats |

## Free tier — Inventory only

On Free, only **Inventory** is enabled. All other rows in the Reports list are greyed with an "Upgrade to Pro" tooltip. The site scope selector is locked to **INDIVIDUAL** (single device) — All Devices and per-site scopes are Pro features.

## Running a report

1. **Reports** tab → pick a report from the list on the left
2. Set **Scope**:
   - **Individual** — pick one device
   - **Site X** — every device in a site
   - **All Devices** — entire library
3. Set **Filters** if the report has them (e.g., interface name patterns for Port Utilisation)
4. Click **Run**

A progress dialog tracks SSH connections and command runs. When complete, results render in the main panel.

## Results format

Most reports produce a sortable, filterable table:

- **Click column headers** to sort
- **Filter bar** at the top for substring search
- **Export** button — CSV, XLSX, or HTML
- **Right-click row** for context actions (open SSH, view device details)

The HTML export is a self-contained file with embedded styles — easy to email or attach to tickets.

## Caching

Same 10-minute output cache as topology tasks. Re-running a report within the cache window reuses SSH output rather than re-walking devices. Force a fresh walk with **Skip cache**.

## Subnet scan as an inventory escape hatch (Free)

If you're on Free and want an Inventory across devices not yet in your 25-device library, run [Library Updater](../library/subnet-scan.md) on a subnet first — that ping-sweep + classify flow is unrestricted, and the subsequent Inventory report works on the discovered devices (subject to the cap on display).

## Run history

Each run's results are saved to:

```
~/Library/Application Support/netOps/reports/<report>_<scope>_<timestamp>.html
%APPDATA%\netOps\reports\<report>_<scope>_<timestamp>.html
```

Useful for before-and-after comparisons (e.g., "what was the port utilisation last month?").

## Performance

| Report | Typical timing |
|---|---|
| Inventory, individual | 5–10 sec |
| Inventory, 50-device site | 1–2 min |
| Port Utilisation, 50-device site | 2–4 min |
| Bandwidth, 50-device site | 2–4 min |
| VLAN Port Finder, 100-device site | 3–6 min |
| Meraki Usage Summary, 10 orgs | 2–5 min (depends on API quotas) |

Parallelism is configurable in Settings → Reports → Workers (default 8).

## Next steps

- [Inventory](inventory.md)
- [Port Utilisation](port-utilisation.md)
- [Bandwidth](bandwidth.md)
- [VLAN Port Finder](vlan-port-finder.md)
- [Meraki Usage Summary](meraki-usage-summary.md)
