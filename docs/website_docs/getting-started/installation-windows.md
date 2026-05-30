# Installing on Windows

Node Control ships as a standard Windows installer (`.exe`) built with NSIS.

## System requirements

- **Windows**: 10 or 11 (64-bit)
- **Disk space**: ~500 MB
- **Network**: SSH access from your PC to the devices you intend to manage

## Download

From [nodecontrol.io](https://nodecontrol.io):

- **Free** — sign up with your email to receive a download link and activation code
- **Pro** / **AI** — log in to your customer portal

The download is named like:

- `Node Control Free-0.9.29-Setup.exe`
- `Node Control Pro-0.9.29-Setup.exe`

## Install

1. Double-click the downloaded `Setup.exe`
2. Windows User Account Control (UAC) prompts for permission — click **Yes**
3. The installer opens. Click **Next** through:
   - Welcome screen
   - Install location (default: `C:\Program Files\Node Control Free\` or `Node Control Pro\`)
4. Click **Install** — files copy in ~30 seconds
5. **Finish**. Tick "Launch Node Control" to start it immediately

You'll find shortcuts on your Desktop and in the Start Menu under the app name (e.g., "Node Control Free").

## "Windows protected your PC" SmartScreen warning (Free / Pro builds before late 2026)

This appears because our Windows code-signing certificate is in the SmartScreen reputation-building phase. To proceed:

1. Click **More info** on the SmartScreen dialog
2. Click **Run anyway**

The warning disappears entirely once enough downloads have built up the SmartScreen reputation for our publisher. We're also actively working through Microsoft's Trusted Signing programme to eliminate it sooner.

You can verify the installer is genuinely from us by right-clicking the `Setup.exe` → **Properties** → **Digital Signatures** tab → confirm "The Promised LAN" appears as the signer.

## Pro and Free side-by-side

Pro and Free install as fully separate Windows apps. You can have both on the same machine without conflict:

- **Pro**: `C:\Program Files\Node Control Pro\`, registry under `HKLM\Software\Node Control Pro`
- **Free**: `C:\Program Files\Node Control Free\`, registry under `HKLM\Software\Node Control Free`

They appear as separate entries in **Settings → Apps** and have separate Start Menu folders. Their data directories are shared (see below) so the device library is visible to both — useful if you're testing the upgrade path.

## Where your data is stored

```
%APPDATA%\netOps\
```

Typically expands to `C:\Users\<you>\AppData\Roaming\netOps\`. Contains:

- `netOps.db` — device library, settings, credential references
- `settings.json` — UI state
- Credential **secrets** live in **Windows Credential Manager**, not in this folder

**Uninstalling**: use **Settings → Apps → Node Control Free** (or Pro) → **Uninstall**. Your data in `%APPDATA%\netOps\` is preserved unless you delete it manually. Credentials in Credential Manager can be cleared from **Control Panel → User Accounts → Credential Manager → Windows Credentials → Generic Credentials**.

## Updating

Use **Help → Check for Updates** inside the app. When an update is available:

1. Click **Download**
2. The new installer downloads to your `%TEMP%` folder
3. Click **Install & Restart** — Node Control closes, a UAC prompt appears, the installer runs silently and re-launches the app on the new version

Your library, settings, and credentials carry over.

## Crash logs

If Node Control crashes, a log file is written to:

```
%USERPROFILE%\NodeControl_crash.log
```

Typically `C:\Users\<you>\NodeControl_crash.log`. Attach this file when reporting a crash to support.

## Next steps

- [First launch and activation](first-launch-activation.md)
- [Adding your first device](adding-first-device.md)
