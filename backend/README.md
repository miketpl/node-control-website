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
```

The CLI calls the API. It does not open `licenses.db`. Revoke removes the code from `licenses.json` first and only then marks the row revoked. If GitHub cannot be updated, the row is left as it was.

## Deploy

On the VPS, the process is `nodecontrol-api` (gunicorn on `127.0.0.1:5000`), with env from `/opt/nodecontrol-api/.env`.

1. Copy `app.py`, `admin_cli.py`, and `README.md` into `/opt/nodecontrol-api/`. Do not replace the live `.env` with `.env.example`.
2. In the live `.env`, confirm `LICENSE_REPO`, `ADMIN_TOKEN`, `GITHUB_PAT_WRITE`, and `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `SMTP_FROM`.
3. Restart: `sudo systemctl restart nodecontrol-api`
4. Check: `curl -s http://127.0.0.1:5000/api/health`

`database` should be `ok`. A `503` from an admin call that says `admin disabled` means the token is still empty or still the placeholder.

## Tests

No secrets required. SMTP and GitHub are mocked.

```bash
cd backend && python3 -m unittest test_app test_pro -v
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

Access is `allowlist.json` on `main` in `miketpl/node-control-registrations`. The file is already live and includes beta addresses added by hand. The API preserves every other key (including `grace_period_days`). It lowercases and dedupes `allowed_emails` only when it adds or removes a Stripe subscriber. It writes with the file sha and retries a 409.

It removes an email only when a `pro_subscriptions` row has `added_to_allowlist` set, that subscription is the one that ended, and no other subscription for the address is `active` or `trialing`. A hand-added address is not removed, including when that person later subscribes and then cancels. `cancel_at_period_end` leaves the address in place until the subscription actually ends. A failed invoice removes it only once Stripe marks the subscription `past_due`, `unpaid`, or `canceled`.

The allow-list token is `GITHUB_PAT_REGISTRATIONS` if set, otherwise `GITHUB_PAT_WRITE`. It needs contents:write on `miketpl/node-control-registrations`. Reuse the existing write token when that token already has this scope. A missing file is an error. The API does not create a new allow-list.

`PRO_RELEASES_PAT` reads the private installer repo `miketpl/node-control-releases-pro`. `GET /api/pro/download?token=` checks a short-lived signed token and an active subscription, then redirects to GitHub's asset URL. The PAT is not put in the redirect.

`POST /api/portal` emails a Customer Portal link when the address has a subscription. The JSON response is the same when it does not. Turn on the Customer Portal in Stripe, allow cancel and payment-method updates, and set the return URL to `https://nodecontrol.io/#manage`.

| Key | What it is |
|---|---|
| `STRIPE_SECRET_KEY` | Secret key. Test mode until checkout is switched on. |
| `STRIPE_WEBHOOK_SECRET` | Signing secret for `/api/stripe/webhook`. |
| `STRIPE_PRICE_PRO_MONTHLY` | Price id for £25/month ex VAT. |
| `STRIPE_PRICE_PRO_ANNUAL` | Price id for £255/year ex VAT. |
| `GITHUB_PAT_REGISTRATIONS` | Optional. Falls back to `GITHUB_PAT_WRITE`. |
| `PRO_ALLOWLIST_REPO` | Default `miketpl/node-control-registrations`. |
| `PRO_ALLOWLIST_PATH` | Default `allowlist.json`. |
| `PRO_RELEASES_REPO` | Default `miketpl/node-control-releases-pro`. |
| `PRO_RELEASES_PAT` | Read access to that private repo's release assets. |
| `PRO_DOWNLOAD_SECRET` | Signs download tokens. Falls back to `SECRET_KEY`. |
| `SITE_URL` | `https://nodecontrol.io`. Used for Checkout return URLs. |

Deploy step, after the free-tier copy: install `stripe` from `requirements.txt`, add the keys above to the live `.env`, restart `nodecontrol-api`, then `curl -s http://127.0.0.1:5000/api/health`. Do not set `PRO_CHECKOUT_LIVE` until a test-mode subscription has been checked end to end.
