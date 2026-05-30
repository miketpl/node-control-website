# Troubleshooting

Common Node Control issues and how to resolve them. Click through to the specific topic for detailed guidance.

## Common issues

| Issue | Page |
|---|---|
| Can't SSH to a device | [SSH connection problems](ssh-connection-issues.md) |
| Device detected as wrong type | [Device type misdetection](device-type-detection.md) |
| App crashed or won't launch | [Reading the crash log](crash-logs.md) |
| Check for Updates doesn't work | [Update problems](update-issues.md) |

## Quick checks first

Before deep-diving into a specific issue, run through these basics:

### Confirm the app is on the latest version

- Help → About → check version number
- Help → Check for Updates → install if there's a newer version
- Many issues are fixed in newer releases (especially detection / vendor parsing)

### Confirm device is reachable from your machine

```bash
ping <device-ip>
ssh <username>@<device-ip>     # without Node Control, baseline test
```

If neither works, it's a network issue — not a Node Control issue.

### Confirm credentials are correct

- Open Node Control → Engineer tab → right-click device → **Test Connection**
- The result message tells you specifically what failed (auth, network, parsing)

### Check the audit log

```bash
~/Library/Application Support/netOps/audit.log
%APPDATA%\netOps\audit.log
```

Look for `SESSION_FAILED` events with details on why the connection failed.

### Check the crash log

If the app is crashing:

```bash
~/NodeControl_crash.log
%USERPROFILE%\NodeControl_crash.log
```

The latest crash is at the bottom — Python tracebacks plus Qt/C++ stack traces when applicable.

## Where else to look

| What | Where |
|---|---|
| Per-task run logs | Open the task → Run log button |
| SSH session logs | `~/Library/Application Support/netOps/sessions/` |
| Library Updater scan log | `~/Library/Application Support/netOps/library_updater.log` |
| Library sync log | `~/Library/Application Support/netOps/library_sync.log` |
| Monitor alert history | `~/Library/Application Support/netOps/monitor_alerts.log` |

## Restart vs reset

If something's behaving oddly:

1. **Restart the app first** — clears caches, re-opens DB connections
2. **Quit + relaunch** — same effect, more explicit
3. **Restart with debug logging** — Settings → Advanced → enable Debug logging, restart, reproduce the issue, attach the resulting log to support ticket
4. **Reset settings** (last resort) — rename `settings.json` to `settings.json.bak` and launch fresh

A reset preserves your library and credentials. To also reset those, delete `netOps.db` (you'll lose your library) and the OS keychain entries (you'll lose stored passwords).

## Getting support

When opening a support ticket, include:

- Node Control version (Help → About)
- OS and version (macOS 14 / Windows 11 / Ubuntu 24.04)
- Device vendor / model / OS version involved
- What you did, what happened, what you expected
- Relevant log file (crash log, audit log, task run log)
- Screenshot if a UI issue

Email: [info@nodecontrol.io](mailto:info@nodecontrol.io)

## Common patterns

| Symptom | Likely cause | First thing to try |
|---|---|---|
| App freezes during a task | One slow SSH connection blocking | Wait for the bounded read timeout (45s), then retry with reduced parallelism |
| Topology has missing nodes | Devices not in library, or auth failed | Check the run log; add missing devices |
| Find Device says "not found" but you know it's there | Starting switches not configured for that site | Settings → Find Device → set Starting Switches |
| Reports missing some devices | SSH failures during the run | Check run log for per-device errors |
| Custom command override not working | Wrong capability name | Check Settings → Custom Commands; capability must match exactly |
| Wireless device search empty | Meraki API key not configured or invalid | Settings → Credentials → Meraki API → Test |

## Performance issues

If Node Control feels slow:

- Reduce parallelism (Settings → Reports / Find Device → Workers)
- Increase Output cache TTL (Settings → Reports → Cache duration)
- Use site-scoped tasks rather than All Devices
- Close other resource-heavy applications

For very large libraries (>1000 devices), consider splitting into multiple libraries per customer / region — switch using [GitHub library sync](../library/github-sync.md) instead of one mega-library.

## Reporting bugs

Bugs reproduce best with:

- A specific sequence of clicks
- The version number
- An error message or screenshot
- A minimum example device or task that triggers it

We respond to all bug reports within 1 business day. Critical bugs (data loss, security issues) within 4 hours.

## Next steps

- [SSH connection problems](ssh-connection-issues.md)
- [Device type misdetection](device-type-detection.md)
- [Reading the crash log](crash-logs.md)
- [Update problems](update-issues.md)
