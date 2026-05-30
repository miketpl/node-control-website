# Safe Mode

Safe Mode is a global setting that restricts what commands Node Control sends to your devices. When ON, only commands in the read-only allowlist are sent — config-mode commands, port shut/no-shut, and any custom commands not explicitly allowed are blocked.

Default state: **ON** for new installs. Most users keep it on.

## Why Safe Mode exists

Node Control was built primarily as a read-only operations tool. The few write actions it supports (port shut/no-shut via [Find Device](../tasks/find-device.md#port-actions)) are dangerous if triggered accidentally — a misclick could disable a port carrying critical traffic.

Safe Mode provides a global "I'm just looking, no changes" guarantee. Toggle it off only when you intentionally need to use a write action.

## What's allowed under Safe Mode

The allowlist covers every `show` command Node Control runs as part of its built-in tasks:

- Interface status, MAC tables, CDP/LLDP neighbours, routing tables, BGP/OSPF peers
- Inventory commands (`show version`, `show inventory`, `show chassis hardware`)
- Configuration display (`show running-config`, `show startup-config`)
- Environmental (`show environment`, `show power`)
- ARP probes (VRF-aware) for Find Device
- Custom commands you've added via Settings → Custom Commands, if you tag them as read-only

## What's blocked under Safe Mode

Anything that could modify device state:

- `configure terminal` / `config t` / `edit` / `configure exclusive`
- `interface ... shutdown` / `interface ... no shutdown` (Cisco)
- `disable interface ...` / `enable interface ...` (Aruba CX)
- `set interfaces ... disable` (Junos)
- `commit` (Junos, IOS-XR)
- `write memory` / `copy running-config startup-config`
- `reload` / `reboot`
- Any custom command you've tagged as write-required

When a blocked command is attempted, Node Control:

- Refuses to send it
- Logs the attempt in the audit log
- Shows a UI warning

## The SSH terminal exception

Safe Mode does **not** apply to the interactive [SSH terminal](../tasks/ssh-terminal.md). What you type in a terminal is sent verbatim. The reasoning:

- The terminal is a CLI prompt — you're a human typing commands and you know what they do
- Safe Mode protects against automated / programmatic commands, not against intentional human input
- Blocking config commands in the terminal would make the terminal useless

If you want a fully read-only terminal, log into the device with a read-only user account.

## Disabling Safe Mode

1. **Settings → Safe Mode** → toggle **OFF**
2. A confirmation dialog: "Disable Safe Mode? Write commands will be allowed."
3. Confirm

Once off, write commands are allowed (subject to per-action confirmation dialogs like the type-to-confirm port shut).

## Per-tab Safe Mode

You can selectively enable Safe Mode for specific library tabs (e.g., Firewalls always Safe Mode, Switches can have it off). Configure in:

- Settings → Safe Mode → **Per-tab overrides**

Useful for: "I'm comfortable shutting switch ports, but never touching firewalls."

## Customising the allowlist

For advanced users who need to allow specific custom commands:

1. Settings → Safe Mode → **Allowlist patterns**
2. Add a regex matching the commands you want to allow
3. Save

Be careful — allowing a regex that accidentally matches a config command opens the safety net.

## Customising the blocklist

The blocklist takes precedence over the allowlist. To explicitly forbid commands that might otherwise slip through:

1. Settings → Safe Mode → **Blocklist patterns**
2. Add regex
3. Save

Useful for: "always block `reload`, even when Safe Mode is off."

## Audit log

Every Safe Mode decision (allow, block, override) is recorded in:

```
~/Library/Application Support/netOps/audit.log
```

Format:

```
2026-05-25T14:32:01Z [SAFE_MODE_BLOCK] device=10.1.1.5 cmd="interface gi1/0/3" reason="Config mode entry"
2026-05-25T14:32:15Z [SAFE_MODE_OVERRIDE_OFF] user=mike
```

See [Audit log](../security/audit-log.md) for the full event taxonomy.

## When you would actually disable Safe Mode

- Doing a Find Device port action (shut/no-shut) to contain a compromised endpoint
- Running a custom write command you've explicitly added
- Performing a one-off remediation script

For everyday operations (topology, reports, troubleshooting), Safe Mode should stay on.

## Best practice

- **Leave Safe Mode ON by default**
- **Turn it off only for the specific action you need**, then turn it back on
- **Per-tab overrides** are a good compromise — keep it on for the high-risk tabs (Firewalls, WAN routers) always
- **Audit log is your friend** — periodically review it to see if anyone disabled Safe Mode unexpectedly

## Next steps

- [Find Device port actions](../tasks/find-device.md#port-actions) — the main use case for temporarily disabling Safe Mode
- [Audit log](../security/audit-log.md)
- [Credential storage](../security/credential-storage.md)
