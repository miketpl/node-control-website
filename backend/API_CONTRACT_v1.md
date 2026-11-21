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

`signups.rows` includes `source` (`web_instant`, `first_run`, or `none` for an older form row). `downloads.rows` includes kind `direct` for the public installer redirect. UTM on a direct download comes from the query string. A linked licence still supplies the UTM. `optins` is submitted, confirmed and unsubscribed update opt-ins per UTC day.

## Email-less Free

`POST /api/free/instant-key` with `{"platform": "mac|win"}` returns `{"licence_key": "NC-..."}`. No email. Status is `active`, `source` is `web_instant`.

`POST /api/free/instant-key` and `POST /api/v1/app/free/claim` return `licence_key` as an `NC-XXXX-XXXX` code and `tier` `free`. They do not return an `NCP-` key. The lease written on activate has edition `free`. While a trial is active the lease carries that trial. It never has edition `pro` or entitlement `all`.

The trial starts on its own only when the machine hash is present and has not been used for a trial. A missing hash, `unavailable`, or a hash that already had a trial still gets Free, with no trial. Confirming the update opt-in can start it later, if that email has not had one and the computer's hash has not had one. Pass `licence_key` on the opt-in body to tie the address to that Free licence. The key is not returned. An address that is already confirmed can be tied the same way on a later opt-in, and that also unlocks the trial under the same rule. A licence that already had an email still starts its trial on first activation. `/api/confirm-email` does not start the clock early.

`POST /api/v1/app/free/claim` issues a new `NC-` key on every claim. `FREE_CLAIM_REPEAT` is `new` or `same`. Empty, or any other value, means `new`. `same` returns the existing Free key for that computer. A new code does not start a second trial on a hash that already had one. The 300-a-day cap and the per-IP and per-machine-hash rate limits still apply to every new code.

`GET /api/v1/download/free/latest` is public JSON: version, published time, and mac/win name, size and sha256. `GET /api/v1/download/free/latest/<mac|win>` 302s to the short-lived installer URL and counts kind `direct` with the `utm_*` query fields.

A GET that is served sends one admin mail to `ADMIN_ALERT_EMAIL`, including a crawler and a repeat from the same client within 24 hours. The subject is `Node Control Free download (mac)` or `(win)`. The body is the platform, the version, the UTC time, a prefix of the client hash, whether the caller looks like a crawler, whether this client already downloaded that platform within 24 hours, the user agent, the UTM source, medium, campaign and content when those are present, the referrer host when it is present, and the counted downloads for today. It has no raw IP address, full client hash, machine hash, or email address. Crawlers are mailed and stay out of the download counts. HEAD requests are not mailed. The redirect is returned even when the mail fails.

`FREE_DOWNLOAD_ALERTS` turns that mail on or off. Empty means on. `false`, `0`, `off`, or `no` turns it off. `FREE_DOWNLOAD_ALERT_DAILY_CAP` is the number of those messages per UTC day. Empty uses 1000. After the cap, downloads are still counted and no further message is sent that day.

`POST /api/free/updates/subscribe` needs `email`, `consent: true` and `consent_text_version`. The response is always 202. Confirmation and unsubscribe are one-click links and do not show the address.

`FREE_CLAIM_DAILY_CAP` is the number of new email-less licences per UTC day. Empty uses 300. Over the cap the response is 503 `claim_capacity`.

`FREE_CLAIM_REPEAT` is `new` or `same`, described above. Empty means `new`.

The redeem box on the website stays until 2027-02-17.
