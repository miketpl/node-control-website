# Cisco Meraki

Meraki devices (MR wireless APs, MS switches, MX security appliances, MV cameras) are managed via the Meraki Dashboard API — Node Control doesn't SSH to them directly.

## How it works

Instead of SSH credentials, Meraki devices need a **Dashboard API key** with read access to your organisation(s).

## Configure the API key

1. In Meraki Dashboard → top-right account icon → **My profile**
2. Scroll to **API access** → **Generate API key**
3. Copy the long alphanumeric key — only shown once
4. In Node Control: **Settings → Credentials → Meraki API** → paste key → **Test**

The Test button confirms the key can fetch your org list. If it returns "Successfully fetched N organisations", you're set.

## What works

| Capability | Status |
|---|---|
| Find Device (wireless lookup) | ✓ |
| Meraki Usage Summary report | ✓ |
| Inventory (Meraki devices) | partial — basic info from Dashboard |
| Topology integration | partial — Meraki devices appear as "endpoint" nodes in L2 maps where seen via CDP/LLDP from non-Meraki switches |

## What doesn't work (yet)

- SSH-style direct device management (Meraki doesn't expose CLI for managed devices)
- Live config push (use Dashboard API directly for that)
- Topology maps purely between Meraki devices (would require Meraki's own topology API; on roadmap)

## Find Device — wireless lookup

The biggest Meraki integration. When you run Find Device with MAC addresses:

1. Wireless mode (or Unknown mode) queries the Meraki Dashboard for each MAC
2. Searches every network in every org your key can access
3. Returns: org, network, SSID, IP, status (online/offline), last seen, AP name + serial, VLAN

This makes "where is this wireless client?" answerable in seconds, even across multi-site Meraki estates.

See [Find Device](../tasks/find-device.md) for the full flow.

## Meraki Usage Summary

A dedicated report covering Meraki orgs at the network level. See [Meraki Usage Summary](../reports/meraki-usage-summary.md).

## Adding Meraki devices to the library

You can add Meraki devices to the library if you want them visible in the Engineer tab:

1. Use the static IP each Meraki device has on its local management interface
2. Set Device type to a custom "meraki" label (this is for your reference only — Node Control won't SSH to it)
3. Useful for tracking which Meraki devices belong to which site

But for actual Meraki operations (Find Device, Usage Summary), the API key is what matters — not the library entries.

## API rate limits

Meraki Dashboard API allows 5 requests per second per organisation. Node Control:

- Throttles to stay within the limit
- Backs off automatically on 429 Too Many Requests
- Uses cheap-overview endpoints first, expensive per-client endpoints only when needed

Most operations stay within the limit. If you have a very large estate (50+ orgs, 1000+ networks), the Meraki Usage Summary can take 5-10 minutes.

## Multi-org

A single API key can access multiple Meraki orgs (if your Dashboard user has access to them). Node Control automatically iterates all accessible orgs.

For MSPs managing many customers' Meraki environments, this means one Node Control session covers everything.

## Bulk provisioning

Meraki's `POST /networks/{id}/devices/claim` is capped around 50 serials per call. Node Control's bulk claim:

- Chunks claims into batches of 50
- Failed batches don't block successful ones
- The downstream PUT step (configure claimed devices) skips serials that didn't successfully claim, so the real claim failure surfaces rather than a misleading downstream 404

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| API key not authorised on some orgs | Dashboard user doesn't have access to those orgs | Get added to those orgs in Dashboard |
| Find Device shows no Meraki results | API key not configured | Settings → Credentials → Meraki API |
| Wireless client found in Meraki but no IP | Older Meraki firmware reports lastSeen as epoch int; Node Control coerces to string | Should work in 0.9.x+ |
| API throttled / slow | High request volume in large estates | Wait 1-2 minutes; the throttling backs off automatically |

## Next steps

- [Find Device — wireless lookup](../tasks/find-device.md#meraki-wireless-lookup)
- [Meraki Usage Summary report](../reports/meraki-usage-summary.md)
