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
   - PAN-OS gets each line, then `commit`
   - Everything else gets enable plus a config set, falling back to `configure terminal` line by line, then `end`
5. A row shows OK **config applied**, WARN with the device's error text (the lines were sent, and the device complained), or FAIL. The summary is `Config push complete: X OK, Y failed out of Z`.

There are no output files. There is no save option. Use [Save Config](config-backup.md) for that.

**Dry run (log only)** on the main window logs `would push N config lines` per device. How many devices run at once comes from the **Conns** spinner on the Engineer page.

From 0.9.40, **Stop** reaches this task.

## Global config

Config Push has no global mode. Put global-only config here.

## Next steps

- [Config Backup](config-backup.md)
- [Config Push](config-push.md) — commands to a list of ports from a file, with placeholders. This task is a verbatim file, with none
- [Safe Mode](../settings/safe-mode.md)
