# Safe Mode

Safe Mode is a global setting. Switch it from the **Edit** menu: **Switch to Safe Mode** or **Switch to Config Mode**.

## The task list in Safe Mode

In Safe Mode the Engineer dropdown is cut to:

- **None**
- **L2 Topology Builder**
- **L3 Topology Builder**
- **Watcher of The WAN**
- **Config Backup**
- **Library Updater**
- **VLAN Port Finder**
- **Refresh Hostnames**
- **Verify Device Types**
- **Discover Variables**
- **Find Device**

Safe Mode hides these from the dropdown:

- **Config Push**
- **Config Push Script**
- **Config from File**
- **Config Compliance Remediate**
- **Save Config**
- **File Transfer** (the task, not the File Transfer sidebar page)
- **Packet Capture**
- **Change ISE Password**

**Config Compliance Audit** is not in the reduced list, so it is not offered in Safe Mode either.

When Safe Mode is off, the dropdown is the full list. On Free, the tasks outside None, L2 Topology Builder, Config Backup, Save Config, and Find Device stay greyed, with the tooltip **Upgrade to Pro to unlock this feature**.

Safe Mode also restricts what commands Node Control sends. When it is on, only commands in the read-only allowlist are sent. Config-mode commands, port shut and no-shut, and custom commands that are not explicitly allowed are blocked.

Default state: **ON** for new installs.

## Why Safe Mode exists

Maps, reports, and discovery only send show commands. The write actions are separate, and each one asks you to confirm first:

- [Find Device](../tasks/find-device.md#port-actions-shut-no-shut) port shut and re-enable
- [Config Push](../tasks/config-push.md) and its revert
- [Config Compliance](../tasks/config-compliance.md) remediation (type `REMEDIATE`)
- [Meraki Configurator](../tasks/meraki-configurator.md) push and revert (type `PUSH`)

Safe Mode blocks compliance remediation. It also blocks a Meraki push and a Meraki revert. Leave it on until you mean to change something.

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

- [Find Device port actions](../tasks/find-device.md#port-actions-shut-no-shut) — the main use case for temporarily disabling Safe Mode
- [Audit log](../security/audit-log.md)
- [Credential storage](../security/credential-storage.md)
