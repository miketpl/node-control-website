# NodeControl licence API

Flask service for the free-download form: email a 6-digit code, then store an `NC-` code in SQLite. Publishing that code to `licenses.json` happens only when `LEGACY_ALLOWLIST_SYNC=true`.

This repository does not deploy the VPS. Copy the files onto the box and restart the service yourself.

## Configure

Copy `.env.example` to `.env` on the server and replace every placeholder. The admin routes stay disabled until `ADMIN_TOKEN` is set to something other than `change-me-in-production`.

`ADMIN_READ_TOKEN` is a second secret for the read-only dashboard. Empty or `change-me-in-production` is ignored. It is accepted only on `GET /api/admin/stats`, `GET /api/admin/stats/v1`, and `GET /api/admin/flags`. Those three return counts and flags, not emails, licence keys, install ids, or IP addresses. `GET /api/admin/pro-keys` includes customer emails, so it stays on `ADMIN_TOKEN`, as do every other admin route: listing licences, changing flags, issuing or revoking keys, resending a key's download links, resetting a device, resyncing a subscription, deleting a licence, and sending notices.

| Key | What it is |
|---|---|
| `LICENSE_REPO` | `miketpl/node-control-license-free` |
| `ADMIN_TOKEN` | Long random secret. Not the placeholder. |
| `ADMIN_READ_TOKEN` | Long random secret for the read-only routes above. Not the placeholder. |
| `GITHUB_PAT_WRITE` | GitHub PAT with Contents write on that repo |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Mail account that sends the 6-digit code |

`GITHUB_PAT` is optional and read-only. Writes use `GITHUB_PAT_WRITE`, then fall back to `GITHUB_PAT`. Neither token is sent unless `LEGACY_ALLOWLIST_SYNC=true`.

## Admin CLI

From the directory that holds `admin_cli.py`, with the service already running:

```bash
export ADMIN_TOKEN='the-real-token'
export API_BASE='http://127.0.0.1:5000'   # default; use https://api.nodecontrol.io from elsewhere
python3 admin_cli.py list
python3 admin_cli.py list --status active
python3 admin_cli.py revoke --code NC-ABCD-2345
python3 admin_cli.py revoke --email person@example.com
python3 admin_cli.py flags get
python3 admin_cli.py flags set free_downloads_paused false
python3 admin_cli.py pro-key issue --email person@example.com
python3 admin_cli.py pro-key send-links --id 12
python3 admin_cli.py maintenance --local
python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --below-version 0.9.41 --include-unknown-version --dry-run
python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --below-version 0.9.41 --include-unknown-version --confirm
python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --licence-id 22 --dry-run
python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_downloaded --licence-id 22,25 --dry-run
python3 admin_cli.py notify --template upgrade-0.9.41 --audience free_all --exclude-licence-id 22,25 --confirm
python3 admin_cli.py funnel --days 14
```

`funnel --days N` opens the licence database read-only and prints one row for each of the last N days in Europe/London, including today. It does not need `ADMIN_TOKEN`. The columns are `free_section_view`, `free_form_start`, `free_form_submit`, then `form_start/section_view` and `submit/form_start`. A zero denominator is `-`. The stored day is the UTC date. The table lists the UK date of the same name. `POST /api/funnel-event` is what fills it: a text/plain body that is either the event name or JSON `{"event": "..."}`. The only stored fields are that UTC day, the event, and a count. No IP address, user agent, cookie, id, or referrer is stored. Each address is limited to 30 events a minute in memory on that worker, and a request over the limit is still a 204 with no increment.

List, revoke, flags, and Pro key commands call the API. `maintenance --local` opens the database and does not issue a key or call GitHub. When `LEGACY_ALLOWLIST_SYNC=true`, revoke removes the code from `licenses.json` first and only then marks the row revoked. If GitHub cannot be updated, the row is left as it was. When the flag is false, revoke only updates the database.

`notify` sends one template from `email_templates/` through the same mail sender as the 6-digit codes. It needs `ADMIN_TOKEN`. `ADMIN_READ_TOKEN` is rejected. `--dry-run` counts and sends nothing. A real send needs `--confirm` and `NOTICE_UNSUBSCRIBE_SECRET` set to something other than the placeholder. Audiences are `free_downloaded` (verified Free licences with a download), `free_all` (verified Free licences), `pro_active` (active Professional keys, and an active subscription that has no key), and `all`. `--below-version 0.9.41` keeps licences whose newest known version, from a registration or a telemetry session, is below that. Licences with no known version are left out unless `--include-unknown-version` is set. The same template is not sent to the same licence twice. Each mail has a signed unsubscribe link. The command prints `matched`, `already_sent`, `opted_out`, `sent`, and `failed` only. `NOTICE_THROTTLE_SECONDS` is the pause between messages. Empty uses 0.25.

`--licence-id` narrows that audience to those ids. The value is a comma-separated list, and the flag can be repeated (`--licence-id 22` or `--licence-id 22,25`). `--exclude-licence-id` uses the same form and leaves those ids out. On `POST /api/admin/notify` the same filters are `licence_ids` and `exclude_licence_ids`, each a list of positive integers. Audience, version, opt-out, and already-sent checks still apply. For a Free audience the id is the number `list` prints. For `pro_active` it is the Professional key id, or the subscription row id when that subscription has no key yet. An id that does not exist, or is not in the audience, adds to `not_matched` and is not printed. With either flag the command also prints `not_matched`. It still prints counts only.

## Admin alerts

`ADMIN_ALERT_EMAIL` receives a short mail when a Free installer redirect is served, when a Free sign-up is verified, when a Professional checkout is paid, and when a hand-added Professional key's first-install link is used. That last one is the event Pro beta download. Empty means the alerts are off, so they can be switched off later without a code change. The mail goes out on a background thread. If sending fails, the log line has no address, and the download, the verification response, and the webhook status stay as they were.

The body has the event, tier, platform, architecture when the file name has one, version, time in Europe/London, licence id, utm source, medium and campaign, the referrer host, the landing path, and the totals for today and all time. It has no email address, no name, no company, and no IP address.

A click or an auto beacon is the same download as the installer redirect that follows it. The alert is sent for that redirect. A second redirect for the same licence and platform within 5 minutes is the same download and does not send another mail. A Pro beta download uses the same 5-minute rule. At most 30 of these alerts go out in an hour. The next event sends one summary, with no licence ids, and then nothing further until the hour has moved on.

`ADMIN_ALERT_SKIP_LICENCE_IDS` is an optional comma-separated list of licence ids to ignore. A Free id is the number `list` prints. A Professional id is the Professional key id.

`GET /api/admin/stats/v1` takes the same `since` and `until` dates as `GET /api/admin/stats` (`until` is exclusive). The body is counts: `licences` by tier, status and source, `pro_keys` by status and plan, `device_moves` for rows in `device_moves`, `devices` for current active seats, `registrations` as a number, `telemetry` for sessions, distinct installs and monthly rollups, `downloads` for free installer redirects, and `update_checks` per UTC day, tier, platform and version. `flags`, `db_bytes` and `generated_at` are included. List items carry only a label (`platform`, `tier`, `version`, `os`, `status`, `plan`, `month`, `day` or `source`) and a `count`. Emails, keys, install ids and IP addresses are not included. Device resets, move requests, telemetry opt-outs and rate-limit 429s are not stored, so they are left out. `update_checks[].day` is the UTC day.

`GET /api/v1/status` and update-check report no minimum when `MIN_SUPPORTED_VERSION_FREE` or `MIN_SUPPORTED_VERSION_PRO` is empty and no flag is set. If the configured minimum is higher than the latest published release for that tier, the response uses the published version and the process logs a warning.

## Deploy

The live service is on the Spark. `app.py` loads `~/node-control-website/.env` (the repo root, beside `backend/`). It does not read `/opt/nodecontrol-api/.env`. `api.nodecontrol.io` reaches the box through a Cloudflare tunnel, so gunicorn sees the peer as localhost. Trust `CF-Connecting-IP` only in that case. Do not add an origin firewall of Cloudflare IP ranges.

`backend/deploy/setup.sh`, `nodecontrol-api.service`, and `nginx-api.conf` are the old direct-nginx recipe. They are not how the Spark is run.

Before a restart, copy the database:

```bash
mkdir -p ~/nc-backups
cp ~/node-control-website/backend/licenses.db ~/nc-backups/licenses-$(date -u +%Y%m%dT%H%M%SZ).db
```

Use the real `DB_PATH` from the live `.env` if it is not `backend/licenses.db`.

1. Pull the merged commit into `~/node-control-website`. Do not replace the live `.env` with `.env.example`.
2. Add the 0.9.41 names from `.env.example` to `~/node-control-website/.env`. `KEY_ENCRYPTION_KEY` and `RELEASES_READ_PAT` have to be set or checkout and downloads fail. Leave `FREE_DOWNLOADS_PAUSED=true` until Free should open.
3. `cd ~/node-control-website/backend && ./venv/bin/pip install -r requirements.txt` so `cryptography` is installed.
4. `sudo systemctl restart nodecontrol-api`
5. `curl -s http://127.0.0.1:5000/api/health` and `curl -s http://127.0.0.1:5000/api/v1/status`
6. Optional nightly roll-up: `backend/deploy/nodecontrol-maintenance.service` and `.timer`. Set the account that owns the checkout before enabling them. The timer runs `admin_cli.py maintenance --local`. That command does not issue keys.

`database` should be `ok`. `git_sha` is the deployed commit: `GIT_SHA` if that is set, otherwise `git rev-parse --short HEAD` read once at startup, otherwise `unknown`. A `503` from an admin call that says `admin disabled` means the token is still empty or still the placeholder. A flag change is visible to both workers within 10 seconds. No restart is required for the pause switch:

```bash
python3 admin_cli.py flags set free_downloads_paused false
```

`database` should be `ok`. A `503` from an admin call that says `admin disabled` means the token is still empty or still the placeholder.

## Tests

No secrets required. SMTP and GitHub are mocked.

```bash
cd backend && python3 -m unittest test_app test_pro test_v1 test_notify test_alerts test_pro_beta -q
```

## Professional subscriptions

Pro is a Stripe subscription: £25/month ex VAT (`STRIPE_PRICE_PRO_MONTHLY`) or £255/year ex VAT (`STRIPE_PRICE_PRO_ANNUAL`). UK VAT (20%) is added at checkout where applicable. Checkout is created by `POST /api/checkout`. The site button stays hidden until `PRO_CHECKOUT_LIVE` in `js/main.js` is set to `true`.

The webhook is `https://api.nodecontrol.io/api/stripe/webhook`. In the Stripe Dashboard, send these events:

- `checkout.session.completed`
- `invoice.paid`
- `invoice.payment_failed`
- `customer.subscription.updated`
- `customer.subscription.deleted`

`STRIPE_WEBHOOK_SECRET` is the signing secret for that endpoint. A bad signature is rejected. A handler failure returns a non-2xx status so Stripe retries. Event ids are stored after a successful handler, so a retry does not add the email twice or send a second welcome email.

Stripe Tax is on (`automatic_tax`, billing address required, tax ID collection). The Promised Lan Limited is VAT registered. Set the Stripe Tax origin address in the Dashboard before taking live payments.

Checkout issues one `NCP-` key per Stripe subscription and stores it encrypted with `KEY_ENCRYPTION_KEY`. Resend returns one key for the address: a key with no active computer if one exists, otherwise the most recently issued key. The recovery email lists every active key. The success page shows the checkout key for 24 hours. `allowlist.json` is not updated. Set `LEGACY_ALLOWLIST_SYNC=true` only if an old client still needs that file. Hand-added beta keys are `python3 admin_cli.py pro-key issue --email …`. That command emails the key and 7-day Mac and Windows links for the first install, and does not run on startup. A second key for the same address is a second computer. `python3 admin_cli.py pro-key send-links --id N` sends those links again for one active manual key and does not change the key. `GET /api/v1/download/pro/<platform>?t=` checks that signed link and redirects to the Professional installer while the key is active. A revoked key is refused.

Free codes stay in SQLite. They are published to `licenses.json` with `GITHUB_PAT_WRITE` only when `LEGACY_ALLOWLIST_SYNC=true`, for a 0.9.40 client that still reads that file. The same flag is required before the API reads `licenses.json` or calls GitHub with `GITHUB_PAT` or `GITHUB_PAT_WRITE` (including the allow-list, which falls back to `GITHUB_PAT_WRITE`). `miketpl/node-control-releases-free` and `miketpl/node-control-releases-pro` are private. `RELEASES_READ_PAT` reads both whether or not the flag is set. `PRO_RELEASES_PAT` is the fallback. The website redeem response is still `{downloads: {mac, win}}`. Those URLs are server-signed links on this API, and each one redirects to GitHub's short-lived asset URL. The PAT is not put in the redirect.

`GET /api/pro/download?token=` checks a short-lived signed token and an active subscription, then redirects the same way. The hand-added first-install links are a different token, on `GET /api/v1/download/pro/<platform>?t=`.

`POST /api/portal` emails a Customer Portal link when the address has a subscription. The JSON response is the same when it does not. Turn on the Customer Portal in Stripe, allow cancel and payment-method updates, and set the return URL to `https://nodecontrol.io/#manage`.

| Key | What it is |
|---|---|
| `STRIPE_SECRET_KEY` | Secret key. Test mode until checkout is switched on. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `/api/stripe/webhook`. |
| `STRIPE_PRICE_PRO_MONTHLY` | Price id for £25/month ex VAT. |
| `STRIPE_PRICE_PRO_ANNUAL` | Price id for £255/year ex VAT. |
| `GITHUB_PAT_REGISTRATIONS` | Unused while `LEGACY_ALLOWLIST_SYNC` is false. |
| `PRO_ALLOWLIST_REPO` | Default `miketpl/node-control-registrations`. |
| `PRO_ALLOWLIST_PATH` | Default `allowlist.json`. |
| `PRO_RELEASES_REPO` | Default `miketpl/node-control-releases-pro`. |
| `RELEASES_READ_PAT` | Contents read on the private Free and Pro release repos. |
| `PRO_RELEASES_PAT` | Fallback if `RELEASES_READ_PAT` is empty. |
| `KEY_ENCRYPTION_KEY` | Encrypts the stored Professional key. |
| `FREE_DOWNLOADS_PAUSED` | Empty or unset means paused. A database flag overrides it. |
| `MIN_SUPPORTED_VERSION_FREE` | Leave unset, or `0.9.40`, until 0.9.41 is published. Empty means no minimum. A higher value is capped to the latest published release. |
| `MIN_SUPPORTED_VERSION_PRO` | Leave unset, or `0.9.40`, until 0.9.41 is published. Empty means no minimum. A higher value is capped to the latest published release. |
| `API_PUBLIC_URL` | Default `https://api.nodecontrol.io`. Used in signed Free links. |
| `REGISTRATION_ALERT_EMAIL` | Default `support@nodecontrol.io`. Empty disables the alert. |
| `ADMIN_ALERT_EMAIL` | Empty disables instant admin alerts. Set the mailbox to turn them on. |
| `ADMIN_ALERT_SKIP_LICENCE_IDS` | Optional comma-separated licence ids to leave out of those alerts. |
| `PRO_DOWNLOAD_SECRET` | Signs download tokens. Falls back to `SECRET_KEY`. |
| `SITE_URL` | `https://nodecontrol.io`. Used for Checkout return URLs. |

Do not set `PRO_CHECKOUT_LIVE` until a test-mode subscription has been checked end to end. The prices stay £25/month ex VAT and £255/year ex VAT.
