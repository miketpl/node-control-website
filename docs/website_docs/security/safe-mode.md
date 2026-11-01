# Safe Mode (security view)

See [Safe Mode](../settings/safe-mode.md) for how the mode is chosen and what it blocks. This page covers Safe Mode from a security and compliance perspective.

Config-changing tasks check Safe Mode again inside the task, before credentials are asked for or a connection is opened. Anything refused is marked **Blocked: Safe Mode is on**. Read-only tasks, reports, and downloads run as before.

## What Safe Mode protects against

| Threat | How Safe Mode helps |
|---|---|
| Accidental config change by clicking the wrong menu item | All write commands blocked by default |
| Malicious automation (e.g., compromised script) attempting to disable ports | Blocked unless Safe Mode explicitly off |
| Tool misuse by junior engineers | You choose Safe Mode or Config Mode at each launch. There is no default |

## What Safe Mode does NOT protect against

- **Read-only SSH** — a command that is not read-only is blocked in an SSH session while Safe Mode is on. Read-only commands still run. See [SSH Terminal](../tasks/ssh-terminal.md)
- **Read-only data exfiltration** — `show running-config` is allowed under Safe Mode; if a config has secrets in it, they're visible
- **Privileged credentials being used elsewhere** — passwords are encrypted on your machine, and the key that unlocks them is held in the macOS Keychain or Windows Credential Manager. Other tools that use the same device account are not constrained
- **Network-level threats** (MITM, etc.) — SSH host key checking is the relevant control there

## Default state

Every time it opens, you choose Safe Mode or Config Mode. There is no default. Cancelling that choice quits the app. **Remember my choice** is off until you tick it. Settings → General → Startup Mode can be Ask every time, Always Safe Mode, or Always Config Mode. With nothing saved, it asks every time.

In Safe Mode only read-only commands are sent, the write tasks leave the list, and the terminal is off. **HTTPS** is hidden and **Console** is hidden. A built-in blocklist stops commands like reload, write, erase and configure from going out of a read-only task. The allowlist is checked first: a command on the allowlist passes even if it also matches the blocklist. There is no list in Settings where you add your own never-run commands, and Safe Mode changes are not written to an audit log.

## Compliance use cases

For organisations that need to demonstrate a control against accidental change: start in Safe Mode. You can set Startup Mode to Always Safe Mode.

For deployment to multiple machines, copy `settings.json`. See [Sharing a settings file](../settings/overview.md#sharing-a-settings-file).

The Engineer dropdown in Safe Mode, and the tasks it hides, are listed on [Safe Mode](../settings/safe-mode.md).

## Integration with SSH credential separation

Safe Mode pairs well with credential design:

- Configure a **read-only** SSH credential profile (using an account on the device with `privilege 1` / read-only ACL)
- Use that profile for "view-only" devices
- Use a write-capable profile only on devices you're actively managing
- Even with Safe Mode off, an unprivileged account can't run write commands at the device level

Defence in depth: Safe Mode (app-level) + read-only accounts (device-level) gives two independent guarantees.

## Related

- [Safe Mode](../settings/safe-mode.md) — Select Mode, Startup Mode, and what the session blocks
- [Credential storage](credential-storage.md) — the master key, and the encrypted passwords
