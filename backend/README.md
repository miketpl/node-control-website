# NodeControl licence API

Flask service for the free-download form: email a 6-digit code, then publish an `NC-` code to the private GitHub list the desktop app reads (`miketpl/node-control-license-free`, file `licenses.json`).

This repository does not deploy the VPS. Copy the files onto the box and restart the service yourself.

## Configure

Copy `.env.example` to `.env` on the server and replace every placeholder. The admin routes stay disabled until `ADMIN_TOKEN` is set to something other than `change-me-in-production`.

| Key | What it is |
|---|---|
| `LICENSE_REPO` | `miketpl/node-control-license-free` |
| `ADMIN_TOKEN` | Long random secret. Not the placeholder. |
| `GITHUB_PAT_WRITE` | GitHub PAT with Contents write on that repo |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASS`, `SMTP_FROM` | Mail account that sends the 6-digit code |

`GITHUB_PAT` is optional and read-only. Writes use `GITHUB_PAT_WRITE`, then fall back to `GITHUB_PAT`.

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
python3 admin_cli.py maintenance --local
```

List, revoke, flags, and Pro key commands call the API. `maintenance --local` opens the database and does not issue a key. Revoke removes the code from `licenses.json` first and only then marks the row revoked. If GitHub cannot be updated, the row is left as it was.

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

`database` should be `ok`. A `503` from an admin call that says `admin disabled` means the token is still empty or still the placeholder. A flag change is visible to both workers within 10 seconds. No restart is required for the pause switch:

```bash
python3 admin_cli.py flags set free_downloads_paused false
```

`database` should be `ok`. A `503` from an admin call that says `admin disabled` means the token is still empty or still the placeholder.

## Tests

No secrets required. SMTP and GitHub are mocked.

```bash
cd backend && python3 -m unittest test_app test_pro test_v1 -q
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

Checkout issues one `NCP-` key per Stripe subscription and stores it encrypted with `KEY_ENCRYPTION_KEY`. Resend returns that same key. The success page shows it for 24 hours. `allowlist.json` is not updated. Set `LEGACY_ALLOWLIST_SYNC=true` only if an old client still needs that file. Hand-added beta keys are `python3 admin_cli.py pro-key issue --email …`. That command does not run on startup.

Free codes are still published to `licenses.json` with `GITHUB_PAT_WRITE` so 0.9.40 clients can check a licence. `miketpl/node-control-releases-free` and `miketpl/node-control-releases-pro` are private. `RELEASES_READ_PAT` reads both. `PRO_RELEASES_PAT` is the fallback. The website redeem response is still `{downloads: {mac, win}}`. Those URLs are server-signed links on this API, and each one redirects to GitHub's short-lived asset URL. The PAT is not put in the redirect.

`GET /api/pro/download?token=` checks a short-lived signed token and an active subscription, then redirects the same way.

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
| `MIN_SUPPORTED_VERSION_FREE` | Default `0.9.41`. |
| `MIN_SUPPORTED_VERSION_PRO` | Default `0.9.41`. |
| `API_PUBLIC_URL` | Default `https://api.nodecontrol.io`. Used in signed Free links. |
| `REGISTRATION_ALERT_EMAIL` | Default `support@nodecontrol.io`. Empty disables the alert. |
| `PRO_DOWNLOAD_SECRET` | Signs download tokens. Falls back to `SECRET_KEY`. |
| `SITE_URL` | `https://nodecontrol.io`. Used for Checkout return URLs. |

Do not set `PRO_CHECKOUT_LIVE` until a test-mode subscription has been checked end to end. The prices stay £25/month ex VAT and £255/year ex VAT.
