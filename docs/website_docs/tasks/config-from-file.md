# Config from File

> On **Pro** and the **AI** edition. On Free the task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode hides it.

**Config from File** sends the lines in a file to the devices you ticked. The lines go verbatim. There are no placeholders.

## Run it

1. Select **Config from File** and click **Run**. The **Config from File** dialog opens first.
   - **Browse...** The filter is `*.txt *.cfg *.conf *.ios *.set`
   - A count: `N lines total, M config lines (excluding blanks and '!' comments)`
   - A **Preview** box
   - **Push Config**, enabled once there is at least one config line
2. If no devices are ticked or selected, the warning **No target devices selected** appears and the run stops.
3. **Select Credentials**.
4. The push runs with the state **CONFIG PUSH**.
   - PAN-OS gets each line, then `commit`, unless a line gets an error. Then the commit is not sent and the device fails
   - Everything else gets enable plus a config set, falling back to `configure terminal` line by line, then `end`
5. The closing summary reads `N OK, W with warnings, F failed out of T`. A device with warnings is not counted as OK.

A reply that means a line was refused is not read as **config applied**. That covers Aruba AOS-CX `Invalid input: ...` and `% Command incomplete`, ProCurve incomplete and ambiguous input, FortiGate `command parse error` and `Command fail`, and Cisco IOS `Command authorization failed.` when AAA command authorization refuses a command. A line that only contains those words is not treated as a refusal. A refused config line does not stop the rest of that device's push.

When a device will not enter configuration mode (for example a read-only account, or NX-OS answering `Permission denied` to `configure terminal`), that device's push stops at once. Nothing is sent outside configuration mode. The row fails with `could not enter configuration mode (check account privileges)`, and the lines not sent are listed as skipped.

On Palo Alto, after a skipped or refused commit, or a commit that errored, only the changes made by the login Node Control used are reverted. The revert is checked against the firewall's change list. Other admins' pending changes are left alone. A commit output that just says `commit failed` counts as refused. Nothing is reverted in Safe Mode. The login name is masked where it appears in Node Control's own revert and change-list commands, and on the change list's owner and other-admins lines. The rest of the firewall's output is kept as written.

There are no output files. There is no save option. Use [Save Config](config-backup.md) for that.

**Dry run (log only)** on the main window logs `would push N config lines` per device. How many devices run at once comes from the **Conns** spinner on the Engineer page.

From 0.9.40, **Stop** reaches this task.

## Global config

Config Push has no global mode. Put global-only config here.

## Next steps

- [Config Backup](config-backup.md)
- [Config Push](config-push.md) — commands to a list of ports from a file, with placeholders. This task is a verbatim file, with none
- [Safe Mode](../settings/safe-mode.md)
