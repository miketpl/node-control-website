# SSH Terminal

Interactive SSH access to any device in your library, embedded directly in Node Control. No need to drop out to PuTTY, iTerm, or a separate terminal app — you can run topology and reports against a device, then jump into a shell on the same device without switching tools.

The SSH session is on **Free**, **Pro**, and the **AI** edition. It is not an Engineer task. SSH opens only from a library row.

## Open a session

- The toolbar **SSH** button
- A double-click on the row
- Right-click **Connect SSH**, in Connection Manager mode

There is no box for a raw IP, and there is no Tools menu.

A new tab opens in the terminal panel with the SSH session.

## Multiple concurrent sessions

Each SSH session lives in its own tab. Open as many as you need:

- One per device for comparing config
- One per role (your "core switch", "firewall", "wireless controller" workspace)

## Session controls

The session controls are **SSH**, **HTTPS**, **Exit**, **Exit All**, **Broadcast**, **Paginate**, **Record**, **Fullscreen**, and **Hostnames**. Each tab has **Stay in config** and **Terminal Mode**.

**Console** sits beside **SSH** and **HTTPS** on the Engineer tab. See [Serial console](serial-console.md). **Terminal** is a button on the log header. See [Local network terminal](local-terminal.md).

**Esc** leaves the fullscreen terminal.

The only other shortcut in the app is **Ctrl+C**, which copies a table selection as tab-separated text. There is no Ctrl+, or Cmd+, shortcut.

## Terminal features

- **Full xterm emulation** via pyte — Cisco / Aruba CLI menus render correctly
- **Mouse selection** for copy
- Output is a fixed-width font, including on Windows, so a table such as `show ip interface brief` lines up
- The session tells the device the terminal width, per vendor, including PAN-OS, so a wrapped command edits on the column you expect
- A pasted line that wraps can be edited and deleted normally
- **Save scrollback** to a text file
- **Configurable colour theme** (Settings → Terminal)

## Login notices

If ISE or another TACACS+ server says at login that the password is about to expire, or that it must be changed, the terminal shows that message before the prompt. Each notice is repeated in bold yellow. The Connection Manager log keeps a `LOGIN NOTICE` line per notice. Tasks log the same notice.

## Send command to multiple sessions

For ad-hoc multi-device commands:

1. Open SSH sessions to each target device
2. Right-click any tab → **Send to all open sessions**
3. Type a command in the dialog
4. Click Send — the same command runs in every open SSH tab

Useful for "show clock" across the fleet, or pushing a single config line to multiple switches.

## Pagination

Long output (e.g., `show running-config`) on Cisco gear is auto-paged with `--More--` prompts. Node Control's terminal disables paging on connect by sending `terminal length 0` (or vendor equivalent), so commands return their full output without manual paging.

To re-enable paging for a specific session: in the device CLI, type `terminal length 24` (Cisco) or `screen-length 0 disable` (Aruba CX) etc.

The auto-pagination-off behaviour can be toggled per-tier in Settings → Terminal — useful if you have a workflow that depends on `--More--` prompts.

## Logging session output

Every SSH session is logged to:

```
~/Library/Application Support/netOps/sessions/<device>-<timestamp>.log  (Mac)
%APPDATA%\netOps\sessions\<device>-<timestamp>.log                       (Windows)
```

Includes both your input and the device's output. Useful for change documentation or troubleshooting.

To disable session logging: Settings → Terminal → uncheck **Log session output**.

## When a session times out

There is no Auto-reconnect checkbox. When a session times out, a red banner reads **Session timed out -** and the reason, with a **Reconnect** button. Reconnect uses the same tab and the current credential profile.

## Send Config File and Paste

**Send Config File** and **Paste** (**Send to Devices**) report a refused line as an error. That covers Aruba AOS-CX and ProCurve `Invalid input`, incomplete and ambiguous input, FortiGate `command parse error` and `Command fail`, Cisco IOS `Command authorization failed.`, and Juniper Junos load and commit errors. A line that only contains those words is not treated as a refusal.

## Safe Mode and the terminal

Safe Mode is session-wide. In Safe Mode, **HTTPS** is hidden, **Console** is hidden, and a command that is not read-only is blocked in the SSH session. The **Terminal** button on the log header stays visible. See [Safe Mode](../settings/safe-mode.md).

## Session sharing

You cannot currently share an SSH session between users — each session is local to your machine. For collaborative troubleshooting, screen-share works.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Terminal renders garbage characters | Vendor sending unsupported escape sequences | Try a different terminal type — Settings → Terminal → Terminal type: vt100 |
| Paste truncates long commands | Some devices have small input buffer | Settings → Terminal → enable **Paste with delay** (slows pastes to one line at a time) |
| Ctrl+C does not interrupt the device | Ctrl+C copies a table selection. It is not a terminal-break shortcut |
| Session locks up | Heavy command output exceeding terminal buffer | Settings → Terminal → increase scrollback size |

## Next steps

- [Find Device](find-device.md) — for jumping straight to a switch port from a MAC search
- [Safe Mode](../settings/safe-mode.md) — session-wide. Non-read-only commands are blocked in SSH
