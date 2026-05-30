# Safe Mode (security view)

See [Settings → Safe Mode](../settings/safe-mode.md) for configuration and behaviour details. This page covers Safe Mode from a security and compliance perspective.

## What Safe Mode protects against

| Threat | How Safe Mode helps |
|---|---|
| Accidental config change by clicking the wrong menu item | All write commands blocked by default |
| Malicious automation (e.g., compromised script) attempting to disable ports | Blocked unless Safe Mode explicitly off |
| Tool misuse by junior engineers | Default-ON setting means new users start in safe state |
| Audit gap ("did anyone disable ports last week?") | All Safe Mode bypasses and blocked commands logged |

## What Safe Mode does NOT protect against

- **Anything done in the [SSH terminal](../tasks/ssh-terminal.md)** — Safe Mode is for automated commands, not human typing
- **Read-only data exfiltration** — `show running-config` is allowed under Safe Mode; if a config has secrets in it, they're visible
- **Privileged credentials being used elsewhere** — Node Control reads from your keychain; if those creds are also used by other tools, those tools aren't constrained
- **Network-level threats** (MITM, etc.) — SSH host key checking is the relevant control there

## Default state

New installations: Safe Mode **ON**.

This is enforced as a sensible default — the cost of being too safe is occasionally needing to toggle it off for a port action, vs. the cost of being too permissive (silent config changes).

## Compliance use cases

For organisations that need to demonstrate "we have technical controls preventing accidental change":

- Safe Mode ON state is logged at every app launch
- Toggle events (ON → OFF and OFF → ON) are recorded with timestamp
- Per-tab override settings are exportable for audit review
- Custom blocklist patterns provide explicit "we always block X command" evidence

The audit log can be shared with auditors as evidence — see [Audit log](audit-log.md) for format and contents.

## Bypass logging

When a user disables Safe Mode:

```
2026-05-25T14:32:01Z [SAFE_MODE_OVERRIDE_OFF] user=mike
2026-05-25T14:32:15Z [PORT_ACTION_SHUT] device=10.1.1.5 port=Gi1/0/3 confirmed=yes
2026-05-25T14:32:18Z [SAFE_MODE_OVERRIDE_ON] user=mike
```

A best-practice flow: turn off → do the one action → turn back on immediately. The audit trail then clearly shows scope-limited intent rather than "Safe Mode was off all afternoon, who knows what happened".

## Customising for sensitive environments

For high-compliance environments:

- Set Safe Mode ON globally
- Use **per-tab overrides** to keep it ON for Firewalls, WAN, and Core tabs even when off elsewhere
- Add specific commands to the **blocklist** that should NEVER run (e.g., `reload`, `format`)
- Periodically review the audit log for unexpected toggles

For deployment to multiple machines, [export Settings](../settings/overview.md#exporting--importing-settings) so the same Safe Mode configuration applies fleet-wide.

## Integration with SSH credential separation

Safe Mode pairs well with credential design:

- Configure a **read-only** SSH credential profile (using an account on the device with `privilege 1` / read-only ACL)
- Use that profile for "view-only" devices
- Use a write-capable profile only on devices you're actively managing
- Even with Safe Mode off, an unprivileged account can't run write commands at the device level

Defence in depth: Safe Mode (app-level) + read-only accounts (device-level) gives two independent guarantees.

## Related

- [Settings → Safe Mode](../settings/safe-mode.md) — configuration UI
- [Audit log](audit-log.md) — what gets logged
- [Credential storage](credential-storage.md) — for the credential side of the security model
