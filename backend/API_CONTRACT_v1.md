# Admin stats contract

`GET /api/admin/stats/v1` returns counts for a UTC window. `since` is inclusive and `until` is exclusive. Both are `YYYY-MM-DD`. The response has no emails, IP addresses, licence keys, licence ids, or names.

## Tokens

Send `Authorization: Bearer <token>`.

| Token | Where it works |
|---|---|
| `ADMIN_TOKEN` | Admin routes, including this one |
| `ADMIN_READ_TOKEN` | `GET /api/admin/stats`, `GET /api/admin/stats/v1`, `GET /api/admin/flags` |
| `STATS_READ_TOKEN` | `GET /api/admin/stats/v1` only |

An empty value, or `change-me-in-production`, is not a token. The comparison is constant-time. `STATS_READ_TOKEN` is rejected on every other admin route.

## `marketing`

`marketing` is counts for the same window. UTM values are lower case, at most 64 characters, and only `[a-z0-9_-]`. Anything else is `other`. An empty value is `none`.

Rows whose UTM or tag is `nc-selftest`, or starts with `v0`, are left out. Free licence ids 23, 24 and 32 are left out. Each section has `total` for the rows that remain and `excluded` for the rows that were left out.

`funnel.rows` is one count per UTC day, event, `utm_source`, `utm_campaign` and `utm_content`. The events include `free_section_view`, `free_form_start` and `free_form_submit`, and any other event stored in `funnel_daily`. This is the same split as `admin_cli.py funnel --by-campaign`, limited to the stats window.

`signups.rows` is Free sign-ups per day and those three UTM fields. `requested`, `verified`, `unverified` and `redeemed` are counts. `verified` is status `active`. `unverified` is status `unverified`. `redeemed` is a download count above zero. When all three UTM fields are empty and the stored referrer is a host, `referrer` is `ref:` plus that host. Otherwise `referrer` is `none`.

`downloads.rows` is Free download events per day, platform and kind. The kinds are `app_download`, `auto` and `redirect`. UTM is copied from the linked licence. A download with no linked licence uses `none`.

`pro_purchases` is a count by plan for Professional keys created in the window. `attribution` is `none`. Pro UTM is not included.
