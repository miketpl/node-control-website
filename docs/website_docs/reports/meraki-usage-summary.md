# Meraki Usage Summary report

> Available on **Pro** and **AI** tiers only.

For each Meraki organisation your API key can access, generates a per-network usage summary — total clients, total bandwidth, top consumers, and per-network breakdown.

A lightweight Meraki dashboard inside Node Control, without needing to log into dashboard.meraki.com.

## Prerequisites

- A Meraki Dashboard API key with read access to one or more orgs
- Configure the key in **Settings → Credentials → Meraki API** → paste key → **Test**

The Test button confirms the key can fetch the org list.

## Open the report

- **Reports** tab → **Meraki Usage Summary** → **Run**

The scope selector applies at the org level — pick all orgs, or specific orgs your key has access to.

## What's collected

**Per organisation**:

- Total networks
- Total clients (last 24h)
- Total bandwidth used (last 24h, last 7 days)
- Network count by product type (wireless / switch / appliance / camera)

**Per network**:

- Network name
- Product type
- Client count
- Bandwidth used
- Top 5 clients by usage

## API quota awareness

Meraki's Dashboard API has rate limits — 5 requests per second per organisation. Node Control's collector:

- Throttles to stay within the per-org limit
- Uses the cheap-overview endpoints first
- Only hits expensive per-client endpoints on networks that pass a preflight client-count check (skip empty networks)
- Backs off automatically if Meraki returns 429 Too Many Requests

A 10-org, 50-network summary typically completes in 2–5 minutes.

## Result format

Two tabs in the result panel:

- **Per-org summary** — one row per org with totals
- **Per-network breakdown** — one row per network with detail

Both tabs are filterable / sortable / exportable.

## Use cases

| Question | How |
|---|---|
| "Which Meraki network is busiest?" | Per-network → sort by Bandwidth descending |
| "Which org has the most clients?" | Per-org → sort by Total clients |
| "Are any networks unused?" | Per-network → filter Client count = 0 |
| "Where should I focus my next site visit?" | Per-network → top bandwidth = where activity is |

## Drilldown

Click any network row to expand:

- Per-SSID breakdown (for wireless networks)
- Per-device breakdown (for switch networks)
- Top 5 clients with hostname, OS, IP, bandwidth

For deeper Meraki Dashboard investigation, right-click → **Open in Dashboard** (opens dashboard.meraki.com in your browser at the relevant network).

## Combining with Find Device

Find Device's wireless lookup uses the same Meraki API key. After running Meraki Usage Summary to find a busy network, you can run Find Device against a specific MAC to locate one client's connection details (AP, SSID, etc.).

## Export

CSV / XLSX / HTML — same as other reports.

The XLSX export has multiple sheets — one per tab — useful for ongoing reporting.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| "API key invalid" | Wrong key or key revoked | Re-test in Settings → Credentials → Meraki API |
| Some orgs missing | API key doesn't have access to those orgs | Check Meraki Dashboard → permission to the missing orgs |
| Bandwidth shows 0 for active networks | Meraki API quota hit, rate-limit backoff in progress | Wait a few minutes and re-run; it'll resume from cached partial data |
| Report takes a long time | Many networks per org, deep per-client queries | Run on fewer orgs at a time, or rely on the cheap-overview-only mode |

## Next steps

- [Find Device](../tasks/find-device.md) — for per-MAC wireless lookup using the same API key
- [Meraki vendor notes](../vendors/meraki.md)
