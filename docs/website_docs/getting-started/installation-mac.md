# Installing on macOS

Node Control is distributed as a notarized macOS application bundle. Installation is the standard Mac drag-to-Applications flow.

## System requirements

- **macOS**: 11 Big Sur or later (Intel and Apple Silicon both supported via universal binary)
- **Disk space**: ~500 MB
- **Network**: SSH access from your Mac to the devices you intend to manage

## Download

Go to [nodecontrol.io](https://nodecontrol.io) and choose your tier:

- **Free** — sign up with your email to receive a download link and activation code
- **Pro** / **AI** — log in to your customer portal to download

The download is a `.dmg` file named like:

- `Node Control Free-0.9.29.dmg`
- `Node Control Pro-0.9.29.dmg`

## Install

1. Double-click the downloaded `.dmg`
2. A Finder window opens showing **Node Control Free.app** (or Pro / AI) and a shortcut to your **Applications** folder
3. Drag the app icon onto the Applications shortcut
4. Eject the DMG (right-click → Eject, or drag to Trash)
5. Open **Applications** in Finder → double-click **Node Control Free** (or Pro)

That's it — the app launches. On first run you'll be asked to [activate](first-launch-activation.md) (Free) or [register](first-launch-activation.md) (Pro / AI).

## "Apple cannot check it for malicious software" warning

You should *not* see this dialog — Node Control is signed with a Developer ID certificate and notarized by Apple. If you do see it:

- Check that you downloaded the file from `nodecontrol.io` (not a mirror)
- Right-click the app in Applications → **Open** → click **Open** in the dialog
- If problems persist, contact [info@nodecontrol.io](mailto:info@nodecontrol.io) with the macOS version you're running

## Where your data is stored

Node Control stores its database, settings, and credentials at:

```
~/Library/Application Support/netOps/
```

This includes:

- `netOps.db` — the device library, settings, and credential references
- `settings.json` — per-tab UI state
- Credential **secrets** are stored separately in the macOS **Keychain**, not in this folder

**Uninstalling**: drag the app from Applications to Trash. To fully remove your data, also delete `~/Library/Application Support/netOps/` and clear any Node Control entries from Keychain Access.

## Updating

Use **Help → Check for Updates** inside the app. Node Control will tell you when a newer version is available and offer to download the updated DMG.

You can also manually re-download from [nodecontrol.io](https://nodecontrol.io) — the new version installs over the old one with no data loss.

## Crash logs

If Node Control crashes, a log file is written to:

```
~/NodeControl_crash.log
```

Attach this file when reporting a crash to support. See [Reading the crash log](../troubleshooting/crash-logs.md) for what to look for.

## Next steps

- [First launch and activation](first-launch-activation.md)
- [Adding your first device](adding-first-device.md)
