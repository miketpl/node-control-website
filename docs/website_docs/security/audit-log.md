# Audit log

Every security-relevant action Node Control takes is recorded in an append-only audit log.

## Location

```
~/Library/Application Support/netOps/audit.log   (Mac)
%APPDATA%\netOps\audit.log                        (Windows)
~/.local/share/netOps/audit.log                   (Linux)
```

The file is plain text, UTF-8 encoded, one event per line. Rotates when it reaches 100 MB (old logs gzipped with timestamp).

## Event format

```
<ISO-8601 timestamp> [<EVENT_TYPE>] <key>=<value> [<key>=<value> ...]
```

Example:

```
2026-05-25T14:32:01.123Z [PORT_ACTION_SHUT] device=10.1.1.5 port=GigabitEthernet1/0/3 confirmed=yes user=mike
2026-05-25T14:32:15.456Z [SAFE_MODE_OVERRIDE_OFF] user=mike
2026-05-25T14:35:12.789Z [CREDENTIAL_UPDATED] profile=default
```

Values containing spaces or special characters are quoted.

## Event types

### Authentication & credentials

- `CREDENTIAL_ADDED` — new credential profile saved
- `CREDENTIAL_UPDATED` — existing profile modified
- `CREDENTIAL_DELETED` — profile removed
- `KEYCHAIN_PROMPT_DENIED` — OS keychain access was denied by user

### Device write actions

- `PORT_ACTION_SHUT` — port shut/down command sent (Find Device → right-click → Shut Port)
- `PORT_ACTION_NOSHUT` — port enable command sent
- `CUSTOM_WRITE_COMMAND` — a user-added write command was executed

### Safe Mode

- `SAFE_MODE_BLOCK` — a command was blocked by Safe Mode
- `SAFE_MODE_OVERRIDE_OFF` — Safe Mode globally disabled
- `SAFE_MODE_OVERRIDE_ON` — Safe Mode globally re-enabled
- `SAFE_MODE_PER_TAB_CHANGED` — per-tab override modified

### Sessions

- `SESSION_OPEN` — SSH session opened
- `SESSION_CLOSE` — SSH session closed
- `SESSION_FAILED` — SSH connection failed (with reason)

### License & registration

- `LICENSE_CHECK_OK` — successful re-validation
- `LICENSE_CHECK_DENIED` — code/email rejected
- `LICENSE_CHECK_GRACE` — offline grace period invoked
- `REGISTRATION_SUBMITTED` — user registered

### Library

- `DEVICE_ADDED` — new device added to library
- `DEVICE_DELETED` — device removed
- `DEVICE_TYPE_CHANGED` — device type changed (manual or auto)
- `DEVICE_TYPE_LOCKED` — type lock enabled
- `LIBRARY_IMPORTED` — bulk import via CSV
- `LIBRARY_GITHUB_PUSH` — library pushed to GitHub
- `LIBRARY_GITHUB_PULL` — library pulled from GitHub (with diff summary)

### Updates

- `UPDATE_CHECK_OK` — update check ran successfully
- `UPDATE_DOWNLOADED` — new version downloaded
- `UPDATE_INSTALLED` — install initiated

## Filtering and analysis

The audit log is plain text — `grep`, `awk`, and standard log analysis tools work directly:

```bash
# All port shut/no-shut actions in May
grep "PORT_ACTION" audit.log | grep "^2026-05"

# Safe Mode bypasses
grep "SAFE_MODE_OVERRIDE_OFF" audit.log

# Failed SSH sessions to a specific device
grep "SESSION_FAILED" audit.log | grep "device=10.1.1.5"
```

For Splunk / ELK ingestion, the format is parseable as key=value pairs.

## What's deliberately NOT logged

- **Credential content** (passwords, API keys) — only the event of a credential change, not the secret itself
- **Full command output** — only the fact that a command was run
- **SSH session contents** — those go to per-session logs (`sessions/` directory), with their own opt-out
- **User keystrokes in the SSH terminal** — only that a session was opened/closed

## Rotation

When the audit log exceeds 100 MB:

1. Renamed to `audit-<timestamp>.log.gz` and gzipped
2. New empty `audit.log` is created
3. Old logs retained for 1 year by default (configurable in Settings → Advanced → Audit log retention)

To keep audit logs longer for compliance, set retention to 0 (never delete) or 7 years.

## Tampering detection

The audit log is append-only by design — Node Control's code only opens it in append mode. The OS file system permissions are standard (your user can edit it if they want to), so we don't claim tamper-proofness at the file level.

For tamper-evident audit:

- Ship the log to a remote syslog / SIEM
- Use OS-level forensic tools (e.g., FSEvents on macOS, USN journal on Windows)
- Sign the log file periodically with a separate key

Roadmap: a built-in option to ship audit events to remote syslog over TCP/UDP. Let us know if this matters for your compliance posture.

## GDPR / data residency

The audit log contains:

- IP addresses of devices in your library (potentially location-identifying)
- Hostnames (potentially location-identifying)
- Your local user account name

It does NOT contain:

- Personal data of network end-users
- Customer PII
- Credentials

For organisations with GDPR concerns: the log is stored locally on your machine, never sent to Node Control servers. Treat it like any other operational log under your data residency policy.

## Disabling the audit log

Possible but strongly discouraged:

- Settings → Advanced → uncheck **Enable audit log**
- The file stops being written
- Existing log entries remain on disk

If you do this for development / testing, remember to re-enable for production use.

## Related

- [Safe Mode](safe-mode.md) — the primary control whose events get audited
- [Credential storage](credential-storage.md) — credential events go in the audit log
