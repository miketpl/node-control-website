# Installing on macOS

Node Control is distributed as a notarized macOS application bundle. Installation is the standard Mac drag-to-Applications flow.

## System requirements

- **macOS**: 11 Big Sur or later (Intel and Apple Silicon both supported via universal binary)
- **Disk space**: ~500 MB
- **Network**: SSH access from your Mac to the devices you intend to manage

## Download

Go to [nodecontrol.io](https://nodecontrol.io) and choose your tier:

- **Free** — sign up with your email to receive a download link and an `NC-XXXX-XXXX` activation code
- **Pro** — the confirmation email after purchase contains the NCP licence key and the download for the first install. The checkout success page shows that key for 24 hours, with macOS and Windows links that last 30 minutes. Reload the page for a new pair. If the email cannot point at that page, it contains links that last 24 hours, and they work only while the subscription is active. A key added by hand arrives with its own links for the first install. Those last 7 days, and sending them again does not change the key. After that install, the app updates itself
- **AI** — there is no download on the site. The edition is not yet available to buy

The file is a `.dmg`. The installer file is downloaded from GitHub.

## Install

1. Double-click the downloaded `.dmg`
2. A Finder window opens showing **Node Control Free.app** (or Pro / AI) and a shortcut to your **Applications** folder
3. Drag the app icon onto the Applications shortcut
4. Eject the DMG (right-click → Eject, or drag to Trash)
5. Open **Applications** in Finder → double-click **Node Control Free** (or Pro)

That's it — the app launches. On first run you [activate](first-launch-activation.md). Free uses its activation code. Pro uses the NCP key.

## "Apple cannot check it for malicious software" warning

You should *not* see this dialog — Node Control is signed with a Developer ID certificate and notarized by Apple. If you do see it:

- Check that you downloaded the file from `nodecontrol.io` (not a mirror)
- Right-click the app in Applications → **Open** → click **Open** in the dialog
- If problems persist, contact [support@nodecontrol.io](mailto:support@nodecontrol.io) with the macOS version you're running

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

From 0.9.41 the app updates itself. **Help → Check for Updates...** asks the licence server, which never offers a downgrade. The app checks the checksum and the code signature (`codesign`, `spctl`, and the Team ID) before **Install & Restart**. Downloads resume. macOS keeps `Node Control Pro.previous.app` until the new version starts.

**Update Required** cannot be dismissed. The buttons are **Download Update**, **Open nodecontrol.io**, and **Quit**.

0.9.40 and earlier cannot self-update. Install the current build by hand from [nodecontrol.io](https://nodecontrol.io). Anything below 0.9.41 is refused. The library is kept.

See [Updating Node Control](updating.md).

## Crash logs

If Node Control crashes, a log file is written to:

```
~/NodeControl_crash.log
```

Attach this file when reporting a crash to support. See [Reading the crash log](../troubleshooting/crash-logs.md) for what to look for.

## Next steps

- [First launch and activation](first-launch-activation.md)
- [Adding your first device](adding-first-device.md)
