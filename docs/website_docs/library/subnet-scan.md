# Subnet scan (Library Updater)

The Library Updater walks an IP range, attempts SSH on each responding host, and adds discovered devices to your library — auto-filling the device type, hostname, and site code along the way.

This is the fastest way to populate a new library, or to keep an existing one accurate as devices change.

## Open the Library Updater

- **Tools → Library Updater** (or the toolbar button)

## Configure the scan

| Field | What it controls |
|---|---|
| **Subnet** | IP range to scan, in CIDR notation (e.g., `10.1.1.0/24`, `192.168.10.0/24`). Multiple subnets can be added — they'll be scanned in sequence. |
| **Default tab** | Where discovered devices land (Switches / Routers / Firewalls / etc.). The classifier may reassign based on hostname patterns. |
| **Credentials** | Which credential profile(s) to try. If you have two profiles configured, both are tried per device. |
| **Parallelism** | How many SSH connections to attempt at once. Default 10 — bump to 20-30 if you have a fast machine and good network. |

## Click Start Scan

The Library Updater runs through four phases:

### Phase 1 — Ping sweep

Pings every IP in the range. Uses `fping` if installed (fast, ~5 seconds for a /24), otherwise falls back to Python ping (slower, ~30 seconds for a /24).

**Install `fping`** if you don't have it:

- **Mac**: `brew install fping`
- **Linux**: `sudo apt-get install fping`
- **Windows**: not directly available; the Python fallback is used

### Phase 2 — SSH classification

For each ping-alive IP, attempts SSH using your configured credential profiles. On successful login:

1. Runs `show version` (or vendor equivalent)
2. Looks at the output for vendor-identifying strings (e.g., "Cisco IOS", "ProCurve", "PAN-OS")
3. Picks the right Netmiko driver
4. Extracts the hostname

### Phase 3 — Library write

For each successfully-classified device:

1. **New device**: added to the library with all fields filled
2. **Existing device** (IP already in library): updates hostname and device type if changed, leaves other fields alone

The **Default tab** chosen at config time is overridden by the classifier when the hostname matches certain patterns:

| Hostname pattern | Goes to tab |
|---|---|
| `ap-*`, `wap-*`, `*-ap-*`, `aironet-*`, `mr*` | Wireless |
| `fw-*`, `*-fw-*`, `palo-*`, `sonicwall-*`, `fortigate-*` | Firewalls |
| `rtr-*`, `r-*`, `*-rtr-*`, `csr-*`, `isr-*`, `asr-*` | Routers |
| `sw-*`, `csw-*`, `dsw-*`, `asw-*`, `stk-*` | Switches |
| `sdwan-*`, `velocloud-*`, `viptela-*` | SD-WAN |

Hostnames that don't match any pattern land in the Default tab.

### Phase 4 — Summary

When the scan completes, you'll see a summary:

```
Scan complete: 47 hosts pinged, 32 SSH-classified, 28 new, 4 updated, 0 errors
```

The library updates immediately.

## What gets logged

Every scan writes a session log to:

```
~/Library/Application Support/netOps/library_updater.log  (Mac)
%APPDATA%\netOps\library_updater.log                       (Windows)
```

Useful for tracking why a specific IP wasn't classified (auth failure, unsupported vendor, etc.).

## Scanning multiple subnets

The Library Updater accepts multiple subnets per scan. Click **+ Add Subnet** to chain them:

```
10.1.1.0/24
10.1.2.0/24
192.168.50.0/24
```

All run in sequence. Total time scales linearly with subnet count.

## Free tier behaviour

The subnet scan itself works on Free, but:

- Devices added beyond the 25-device cap are accepted into the library but won't be visible to other tools
- This is **intentional** — subnet scan is the escape hatch for free users who want to inventory devices that aren't yet in their library, without being blocked by the cap
- After scanning, you can review the full result list and decide which 25 are most important to keep — the rest can be ignored or deleted

## Re-scanning

Running the Library Updater on the same subnet later:

- Doesn't duplicate devices (existing IPs are updated, not re-added)
- Refreshes hostnames if devices have been renamed
- Catches device type changes (e.g., a switch that got reflashed from IOS to NX-OS)
- Leaves your manually-set device types alone if they're locked

## Scheduling regular scans

There's no built-in scheduler. For weekly/monthly automated scans:

- **Mac**: `launchd` with a script that opens the app and triggers `Tools → Library Updater` via AppleScript
- **Windows**: Task Scheduler running the app with command-line args

We're considering native scheduling in a future release — let us know if this matters to you.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| All hosts ping but none SSH | Credentials wrong | Test one device manually first via right-click → Test Connection |
| Some devices show up as `cisco_ios` but they're actually HP ProCurve | ProCurve accepts the Cisco driver silently — Node Control runs an opportunistic probe to catch this, but it can occasionally miss | Right-click → Change Device Type → set to `hp_procurve_cli` manually; check Lock Device Type |
| Scan very slow | Default Python ping fallback | Install `fping` |
| `fping not found` warning | `fping` binary not in PATH | Install or symlink it; otherwise scan continues with Python ping |
| Many "Connection timed out" | Devices unreachable, firewall blocking, or ARP cache stale | Check `ping` works from a separate terminal first |

## Next steps

- [Organising devices by site](sites.md)
- [Sharing libraries via GitHub](github-sync.md)
- [Verify Device Types task](../tasks/verify-device-types.md) — periodic sweep to catch detection errors
