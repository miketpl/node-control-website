# SSH Terminal

Interactive SSH access to any device in your library, embedded directly in Node Control. No need to drop out to PuTTY, iTerm, or a separate terminal app — you can run topology and reports against a device, then jump into a shell on the same device without switching tools.

The SSH session is on **Free**, **Pro**, and the **AI** edition. You open it by right-clicking a device. It is not an Engineer task. On Free the tasks that run are **None**, **L2 Topology Builder**, **Config Backup**, **Save Config**, and **Find Device**.

## Open a session

Three ways:

1. Right-click a device in the library → **SSH**
2. From a topology or Find Device result → right-click a node → **Open SSH**

A new tab opens in the terminal panel with the SSH session.

## Multiple concurrent sessions

Each SSH session lives in its own tab. Open as many as you need:

- One per device for comparing config
- One per role (your "core switch", "firewall", "wireless controller" workspace)

Tabs persist across app restarts (sessions reconnect automatically using the same credentials).

## Terminal features

- **Full xterm emulation** via pyte — Cisco / Aruba CLI menus render correctly
- **Mouse selection** for copy
- **Ctrl+C** copies the selection. With nothing selected, Ctrl+C still interrupts the device
- On a Mac, **Cmd+C** copies as well
- **Cmd+V / Ctrl+Shift+V** to paste
- Output is a fixed-width font, including on Windows, so a table such as `show ip interface brief` lines up
- The session tells the device the terminal width, per vendor, including PAN-OS, so a wrapped command edits on the column you expect
- A pasted line that wraps can be edited and deleted normally
- You can switch between command mode and terminal mode while a command is still running
- **Search** within scrollback (Cmd+F / Ctrl+F)
- **Save scrollback** to a text file
- **Configurable colour theme** (Settings → Terminal)

## Sending Ctrl+C to the device

Ctrl+C copies when text is selected. Click somewhere with no selection, then Ctrl+C, to interrupt the device (for example to cancel a long `show tech-support`).

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

## Reconnection

If an SSH session times out or drops:

- The tab shows a **Session Timed Out** banner. It does not sit there frozen
- **Reconnect** opens the session again in the same tab, with the same credential profile
- If you were in terminal mode, you land back in terminal mode, ready for input
- Reconnect works on Palo Alto firewalls as well as on Cisco switches

## Safe Mode and the terminal

[Safe Mode](../settings/safe-mode.md) gates commands routed through tasks (Find Device port actions, Discover Variables, Discovery walks). The SSH terminal is **not** Safe-Mode gated — what you type in an interactive terminal is sent verbatim. Safe Mode protects you from automated commands; it assumes you know what you're doing when you have a CLI prompt.

## Session sharing

You cannot currently share an SSH session between users — each session is local to your machine. For collaborative troubleshooting, screen-share works.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Terminal renders garbage characters | Vendor sending unsupported escape sequences | Try a different terminal type — Settings → Terminal → Terminal type: vt100 |
| Paste truncates long commands | Some devices have small input buffer | Settings → Terminal → enable **Paste with delay** (slows pastes to one line at a time) |
| Ctrl+C interrupts when you wanted to copy | A selection has to be active. Select the text, then Ctrl+C. On a Mac, Cmd+C copies as well |
| Session locks up | Heavy command output exceeding terminal buffer | Settings → Terminal → increase scrollback size |

## Next steps

- [Find Device](find-device.md) — for jumping straight to a switch port from a MAC search
- [Safe Mode](../settings/safe-mode.md) — for terminal-vs-tasks command gating
