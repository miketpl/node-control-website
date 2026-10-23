# Discover Variables

> On **Pro** and the **AI** edition. On Free the task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode allows it.

**Discover Variables** reads a few facts off each device and stores them on the library row. It is an inventory enrichment step. Nothing else in the app reads these values yet. [Config Push](config-push.md) does not use them.

## Run it

1. Tick or select the devices. Select **Discover Variables**. Click **Run**.
2. **Select Credentials**. There is no further dialog.
3. The task is read-only. It collects:
   - VRF names, excluding default and management
   - chassis PID or model
   - default gateway
   - on PAN-OS, the virtual-router and logical-router lists
4. Those values are stored in the device library as per-device metadata, with a timestamp.

The log line per device is `<ip>: vrfs=N lrs=N pid=... gw=...`. At the end: `Done. Variables captured on X/Y device(s); stored in device library.`

No files are written. The table's Status column is not updated. Dry run is ignored. Stop reaches it from 0.9.40.

Tick **AI Summary** before you run if you want an end-of-task summary. See [AI provider](../settings/ai.md).

## Next steps

- [Inventory report](../reports/inventory.md)
- [Config Push](config-push.md)
- [Verify Device Types](verify-device-types.md)
