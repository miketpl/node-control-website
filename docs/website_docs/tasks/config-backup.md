# Config Backup and Save Config

**Config Backup** runs on **Free**, **Pro**, and the **AI** edition. It is allowed in Safe Mode.

**Save Config** also runs on Free, Pro, and the AI edition. Safe Mode hides it.

On Free the tasks that run are **None**, **L2 Topology Builder**, **Config Backup**, **Save Config**, and **Find Device**. Every other task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**.

## Config Backup

1. Tick or select the devices. Select **Config Backup**. Click **Run**.
2. **Select Credentials**.
3. The **Config Backup** dialog:
   - **Config Type:** radio **Running Config (show running-config)** (the default) or **Startup Config (show startup-config)**
   - **Output Directory:** with **Browse...**. The default is `<Output Directory from Settings>/connection_manager/backups`
   - **Start Backup**
4. The task is read-only. It runs the vendor's running or startup command from the catalogue, through the safe-send allowlist:
   - Cisco and Arista: `show running-config`
   - Junos: `show configuration | no-more`. There is no startup variant
   - PAN-OS: `show config running` / `show config saved`
   - Aruba, Extreme, and Dell have their own variants

On AOS-CX, an operators-level login cannot read the config. Config Backup tells you an admin or manager user is needed. It does not save an empty file. Save Config needs the same login.

5. One file per device:

```
<hostname>_<ip with underscores>_<running|startup>_<YYYYmmdd_HHMMSS>.txt
```

One timestamp covers the whole run. A row shows **Backed up** or FAIL. The summary is `Complete - X saved, Y failed. Output: <dir>`.

**Dry run** logs the commands and the file it would write. **Stop** cancels the run.

## Save Config

**Save Config** writes the running configuration into the saved config on the devices that are ticked or highlighted in the library. Config Backup does not do that, and [Config from File](config-from-file.md) does not either.

1. Tick or highlight the devices. Select **Save Config**. Click **Run**.
2. **Select Credentials**.

There is no further dialog. The task saves the config on each device. The log window reports success or failure.

## Next steps

- [Config from File](config-from-file.md)
- [L2 Topology Builder](topology-l2.md)
- [Safe Mode](../settings/safe-mode.md)
