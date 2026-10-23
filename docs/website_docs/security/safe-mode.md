# Safe Mode (security view)

See [Safe Mode](../settings/safe-mode.md) for how the mode is chosen and what it blocks. This page covers Safe Mode from a security and compliance perspective.

## What Safe Mode protects against

| Threat | How Safe Mode helps |
|---|---|
| Accidental config change by clicking the wrong menu item | All write commands blocked by default |
| Malicious automation (e.g., compromised script) attempting to disable ports | Blocked unless Safe Mode explicitly off |
| Tool misuse by junior engineers | Default-ON setting means new users start in safe state |
| Audit gap ("did anyone disable ports last week?") | All Safe Mode bypasses and blocked commands logged |

## What Safe Mode does NOT protect against

- **Read-only SSH** — a command that is not read-only is blocked in an SSH session while Safe Mode is on. Read-only commands still run. See [SSH Terminal](../tasks/ssh-terminal.md)
- **Read-only data exfiltration** — `show running-config` is allowed under Safe Mode; if a config has secrets in it, they're visible
- **Privileged credentials being used elsewhere** — Node Control reads from your keychain; if those creds are also used by other tools, those tools aren't constrained
- **Network-level threats** (MITM, etc.) — SSH host key checking is the relevant control there

## Default state

Safe Mode is session-wide. It is not a per-tab setting.

The **Select Mode** dialog at startup uses the default in **Settings → General → Startup Mode**. Mid-session, the **Edit** menu or the mode badge switches it. In Safe Mode, **HTTPS** is hidden, **Console** is hidden, the [local network terminal](../tasks/local-terminal.md) on the log header stays visible, the task list is trimmed, non-read-only SSH commands are blocked, and a Meraki Configurator push is blocked. See [Serial console](../tasks/serial-console.md).

## Compliance use cases

For organisations that need to demonstrate "we have technical controls preventing accidental change":

- The mode is logged when it changes
- Custom blocklist patterns provide explicit "we always block X command" evidence

The audit log can be shared with auditors as evidence — see [Audit log](audit-log.md) for format and contents.

## Bypass logging

When a user disables Safe Mode:

```
2026-05-25T14:32:01Z [SAFE_MODE_OVERRIDE_OFF] user=admin
2026-05-25T14:32:15Z [PORT_ACTION_SHUT] device=10.1.1.5 port=Gi1/0/3 confirmed=yes
2026-05-25T14:32:18Z [SAFE_MODE_OVERRIDE_ON] user=admin
```

A best-practice flow: turn off → do the one action → turn back on immediately. The audit trail then clearly shows scope-limited intent rather than "Safe Mode was off all afternoon, who knows what happened".

## Customising for sensitive environments

For high-compliance environments:

- Set **Startup Mode** to Safe Mode
- Add specific commands to the **blocklist** that should NEVER run (e.g., `reload`, `format`)
- Periodically review the audit log for unexpected toggles

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
- [Audit log](audit-log.md) — what gets logged
- [Credential storage](credential-storage.md) — for the credential side of the security model
