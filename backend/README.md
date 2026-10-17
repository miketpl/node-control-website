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
cd backend && python3 -m unittest test_app -v
```
