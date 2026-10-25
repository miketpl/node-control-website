# Reports overview

A report collects from one or more devices and renders a result, usually a table.

A read-only report cannot send a config-altering command by mistake. Every command it sends has to pass a safe list of commands first.

Open **Reports** in the left sidebar. It is its own page, not a task in the Engineer command bar.

## Report types

| Report | Free | Pro | Purpose |
|---|:---:|:---:|---|
| [Inventory](inventory.md) | ✓ | ✓ | Hardware model, OS version, serial number |
| [Port Utilisation](port-utilisation.md) | — | ✓ | Per port: status, VLAN, MAC count, in/out traffic |
| [Bandwidth](bandwidth.md) | — | ✓ | Aggregate in/out bandwidth per interface |
| [VLAN Port Finder](vlan-port-finder.md) | — | ✓ | Which ports are on a VLAN, across the devices in scope |
| [Meraki Usage Summary](meraki-usage-summary.md) | — | ✓ | Per-org and per-network Meraki usage |
| [Security Audit](security-audit.md) | — | ✓ | Cisco advisories by severity, plus an optional baseline check |
| [Lifecycle and EoX](lifecycle.md) | — | ✓ | End-of-sale and end-of-life dates, and a replacement plan |
| [Change Summary](change-summary.md) | — | ✓ | Commands that were entered, and who entered them |
| Site Subnets | — | ✓ | The subnet list [IPAM](../tasks/ipam.md) is filled from |

The Reports page is on Free. The only report that runs there is Inventory, and it covers the whole library, up to 25 devices. Every other report is Pro and the AI edition.

Site Subnets is Pro and the AI edition. On AOS-CX it reads the per-VRF interface listing. On Arista EOS it has its own L3 command.

## Running a report

1. **Reports** → pick a report from the list
2. Set the scope: one device, a site, or all devices
3. Set any filters the report has
4. Click **Run**

When the run finishes, the result is in the main panel.

## Tables, CSV, and email

Most reports give you a sortable, filterable table. Click a column header to sort. The filter bar is a substring search.

Every HTML report has an **Export CSV** button above each table. You can also export HTML. The HTML file is self-contained.

Report email sends in the background, with a timeout long enough for a slow relay. The app does not freeze while it waits. If the email is skipped, the log says why: the option was unticked, or there were no recipients.

The Reports tab has **AI Summary** and **Preview before sending**. **AI Summary** starts from **Enable AI analysis by default across all features**, which is off on a fresh install, so the box starts unticked. **Preview before sending** starts unticked. Each time the tab loads it takes its starting state from **Show preview before sending data to AI** (off by default). It is enabled only while **AI Summary** is ticked, and you can change it for that run. **AI headline on emailed assessment** is off by default and applies only when the Lifecycle report is emailed. See [AI provider](../settings/ai.md).

## Caching

Report runs cache device output for about 10 minutes, same as the topology tasks. Inside that window a re-run reuses the output. **Skip cache** forces a fresh walk.

## Where results are saved

```
~/Library/Application Support/netOps/reports/<report>_<scope>_<timestamp>.html
%APPDATA%\netOps\reports\<report>_<scope>_<timestamp>.html
```

## Workers

Parallelism is set under Settings → Reports → Workers.

## Next steps

- [Inventory](inventory.md)
- [Security Audit](security-audit.md)
- [Lifecycle and EoX](lifecycle.md)
- [VLAN Port Finder](vlan-port-finder.md)
