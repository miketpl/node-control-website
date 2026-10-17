# Packet Capture

> On **Pro** and the **AI** edition. On Free the task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode hides it.

**Packet Capture** runs an IOS-XE Embedded Packet Capture, exports it to flash, copies it locally, and opens it in Wireshark.

The dialog is **Packet Capture**:

- **Capture Interface**, with **Fetch from Device**
- **Direction**
- **Duration (seconds)**
- **Capture Filter**: **Match Any** / **Named ACL** / **Inline Match**
- **Capture Buffer Name**
- **Local Save Directory**
- **Start Capture**

The task is a sequence of commands: define, filter, start, stop, export. Each one logs what the switch answers.

A rejected define, filter, or start stops the run immediately, using the switch's own words. The run does not continue for minutes and then fail with a misleading "no file on flash" error.

## Before the file is downloaded

The file is checked on flash before any download:

- the export reply is read
- `dir flash:` is polled
- a missing file, a file that is not written yet, and an empty capture are each reported as that thing

A buffer with zero packets is called out before the export runs.

## If SCP is disabled

`SCPException: Administratively disabled` means the switch's SCP server is off. The task says so and names the missing line: `ip scp server enable`.

## Next steps

- [File Transfer](file-transfer.md) — the sidebar page, and the separate File Transfer task
- [Config Push](config-push.md)
