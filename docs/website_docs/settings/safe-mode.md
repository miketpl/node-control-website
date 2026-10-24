# Safe Mode

Safe Mode is session-wide. It is not a per-tab setting.

At startup the **Select Mode** dialog asks which mode to use. **Settings → General → Startup Mode** is what that dialog defaults to.

Mid-session, switch it from the **Edit** menu (**Switch to Safe Mode** / **Switch to Config Mode**) or from the mode badge.

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
- **Find Device** (read-only)
- **Config Compliance Audit**

**Find Device** runs read-only. **Config Compliance Audit** is in the list. Its remediation offer is suppressed in Safe Mode.

Safe Mode hides these from the dropdown:

- **Config Push**
- **Config Push Script**
- a [custom script](scripts.md) (`Script: <name>`)
- **Config from File**
- **Config Compliance Remediate**
- **Save Config**
- **File Transfer** (the task, not the File Transfer sidebar page)
- **Packet Capture**

**Config Compliance Remediate** stays out of Safe Mode. The audit task above does not offer remediation while Safe Mode is on.

When Safe Mode is off, the dropdown is the full list. On Free, the tasks outside None, L2 Topology Builder, Config Backup, Save Config, and Find Device stay greyed, with the tooltip **Upgrade to Pro to unlock this feature**.

While Safe Mode is on:

- **HTTPS** is hidden
- the task list is the reduced list above
- a command that is not read-only is blocked in an SSH session
- a [Meraki Configurator](../tasks/meraki-configurator.md) push is blocked

Safe Mode also restricts what automated commands Node Control sends. When it is on, only commands in the read-only allowlist are sent. Config-mode commands, port shut and no-shut, and custom commands that are not explicitly allowed are blocked.

## Why Safe Mode exists

Maps, reports, and discovery only send show commands. The write actions are separate, and each one asks you to confirm first:

- [Find Device](../tasks/find-device.md#port-actions-shut-no-shut) port shut and re-enable
- [Config Push](../tasks/config-push.md) and its revert
- [Config Compliance](../tasks/config-compliance.md) remediation (type `REMEDIATE`)
- [Meraki Configurator](../tasks/meraki-configurator.md) push (type `PUSH`). Safe Mode blocks that push

Safe Mode blocks compliance remediation. It also blocks a Meraki Configurator push. Leave it on until you mean to change something.

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

## SSH sessions

In Safe Mode, a command that is not read-only is blocked in the [SSH terminal](../tasks/ssh-terminal.md). **HTTPS** is hidden for the session. **Console** is hidden. The [local network terminal](../tasks/local-terminal.md) on the log header stays visible.

## Switching mode

Use the **Edit** menu or the mode badge. The next launch follows **Settings → General → Startup Mode**, which you confirm in the **Select Mode** dialog.

Once you are in Config Mode, write commands are allowed, subject to the confirmation the action already asks for (such as the type-to-confirm port shut).

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
2026-05-25T14:32:15Z [SAFE_MODE_OVERRIDE_OFF] user=admin
```

See [Audit log](../security/audit-log.md) for the full event taxonomy.

## When you would actually disable Safe Mode

- Doing a Find Device port action (shut/no-shut) to contain a compromised endpoint
- Running a custom write command you've explicitly added
- Performing a one-off remediation script

For everyday operations (topology, reports, troubleshooting), Safe Mode should stay on.

## Best practice

- Set **Startup Mode** to the mode you want the **Select Mode** dialog to offer
- Switch with the **Edit** menu or the mode badge for one session, then switch back
- The mode applies to the whole session, including SSH
- Review the audit log when you need to see that the mode changed

## Next steps

- [Find Device port actions](../tasks/find-device.md#port-actions-shut-no-shut) — the main use case for temporarily disabling Safe Mode
- [Audit log](../security/audit-log.md)
- [Credential storage](../security/credential-storage.md)
