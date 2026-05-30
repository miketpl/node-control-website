# SSH Terminal

Interactive SSH access to any device in your library, embedded directly in Node Control. No need to drop out to PuTTY, iTerm, or a separate terminal app — you can run topology and reports against a device, then jump into a shell on the same device without switching tools.

Available on **Free**, **Pro**, and **AI**.

## Open a session

Three ways:

1. Right-click a device in the library → **SSH**
2. From a topology / Find Device result → right-click a node → **Open SSH**
3. **Tools → SSH Terminal** → enter IP manually

A new tab opens in the terminal panel with the SSH session.

## Multiple concurrent sessions

Each SSH session lives in its own tab. Open as many as you need:

- One per device for comparing config
- One per role (your "core switch", "firewall", "wireless controller" workspace)

Tabs persist across app restarts (sessions reconnect automatically using the same credentials).

## Terminal features

- **Full xterm emulation** via pyte — Cisco / Aruba CLI menus render correctly
- **Mouse selection** for copy
- **Cmd+C / Ctrl+C** to copy selected text (does NOT send Ctrl+C to the device; that's mapped to the device's interrupt key)
- **Cmd+V / Ctrl+Shift+V** to paste
- **Search** within scrollback (Cmd+F / Ctrl+F)
- **Save scrollback** to a text file
- **Configurable colour theme** (Settings → Terminal)

## Sending Ctrl+C to the device

To send Ctrl+C as an interrupt to the device (e.g., to cancel a long `show tech-support`):

- macOS: **Ctrl+C** sends the interrupt (Cmd+C is copy)
- Windows / Linux: **Ctrl+Shift+C** = copy, **Ctrl+C** = interrupt

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

## Reconnection

If a session drops (network blip, idle timeout):

- The tab shows "Disconnected" in red
- Click **Reconnect** to re-establish using the same credentials
- Sessions auto-reconnect after sleep/wake on macOS if you have **Auto-reconnect** enabled in Settings

## Safe Mode and the terminal

[Safe Mode](../settings/safe-mode.md) gates commands routed through tasks (Find Device port actions, Discover Variables, Discovery walks). The SSH terminal is **not** Safe-Mode gated — what you type in an interactive terminal is sent verbatim. Safe Mode protects you from automated commands; it assumes you know what you're doing when you have a CLI prompt.

## Session sharing

You cannot currently share an SSH session between users — each session is local to your machine. For collaborative troubleshooting, screen-share works.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Terminal renders garbage characters | Vendor sending unsupported escape sequences | Try a different terminal type — Settings → Terminal → Terminal type: vt100 |
| Paste truncates long commands | Some devices have small input buffer | Settings → Terminal → enable **Paste with delay** (slows pastes to one line at a time) |
| Ctrl+C sends interrupt when you wanted to copy | macOS only — use Cmd+C for copy |
| Session locks up | Heavy command output exceeding terminal buffer | Settings → Terminal → increase scrollback size |

## Next steps

- [Find Device](find-device.md) — for jumping straight to a switch port from a MAC search
- [Safe Mode](../settings/safe-mode.md) — for terminal-vs-tasks command gating
