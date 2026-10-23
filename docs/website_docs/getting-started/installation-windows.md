# Installing on Windows

Node Control ships as a standard Windows installer (`.exe`) built with NSIS.

## System requirements

- **Windows**: 10 or 11 (64-bit)
- **Disk space**: ~500 MB
- **Network**: SSH access from your PC to the devices you intend to manage

## Download

From [nodecontrol.io](https://nodecontrol.io):

- **Free** — sign up with your email to receive a download link and an `NC-XXXX-XXXX` activation code
- **Pro** — the confirmation email after purchase contains the NCP licence key and the download for the first install. The checkout success page shows that key for 24 hours, with macOS and Windows links that last 30 minutes. Reload the page for a new pair. If the email cannot point at that page, it contains links that last 24 hours, and they work only while the subscription is active. A key added by hand arrives with its own links for the first install. Those last 7 days, and sending them again does not change the key. After that install, the app updates itself
- **AI** — there is no download on the site. The edition is not yet available to buy

The file is the NSIS installer for the edition you downloaded. The installer file is downloaded from GitHub. Do not bookmark an old filename.

## Install

1. Double-click the downloaded `Setup.exe`
2. Windows User Account Control (UAC) prompts for permission — click **Yes**
3. The installer opens. Click **Next** through:
   - Welcome screen
   - Install location (default: `C:\Program Files\Node Control Free\` or `Node Control Pro\`)
4. Click **Install** — files copy in ~30 seconds
5. **Finish**. Tick "Launch Node Control" to start it immediately

You'll find shortcuts on your Desktop and in the Start Menu under the app name (e.g., "Node Control Free"). On first run you [activate](first-launch-activation.md). Free uses its activation code. Pro uses the NCP key.

## The installer is signed

The installer and the app are signed. They show **The Promised Lan Limited** as the verified publisher, in the UAC prompt and in the installer's properties. The **Unknown publisher** block is gone.

SmartScreen reputation builds with downloads, so an early download may still show a **More info** prompt.

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

From 0.9.41 the app checks once at launch, right after the licence check. There is no timer after that. **Help → Check for Updates...** checks again. If the server says it is busy or paused, the app backs off for 24 hours by default. The licence server never offers a downgrade. Before **Install & Restart**, the app checks the checksum and the Authenticode publisher, **The Promised Lan Limited**. Downloads resume.

1. Click **Download**
2. The new installer downloads to your `%TEMP%` folder. A dropped connection can resume
3. Click **Install & Restart**. Node Control closes, a UAC prompt appears, the installer runs silently, and the app opens on the new version

**Update required.** The text is `This version (v…) is no longer supported. Version v… must be installed to continue.` It cannot be dismissed. The buttons are **Download Update**, **Open nodecontrol.io**, and **Quit**.

0.9.40 and earlier cannot self-update. Install the current build by hand from [nodecontrol.io](https://nodecontrol.io). Anything below 0.9.41 is refused. Your library, settings, and credentials carry over.

See [Updating Node Control](updating.md).

## Crash logs

If Node Control crashes, a log file is written to:

```
%USERPROFILE%\NodeControl_crash.log
```

Typically `C:\Users\<you>\NodeControl_crash.log`. Attach this file when reporting a crash to support.

## Next steps

- [First launch and activation](first-launch-activation.md)
- [Adding your first device](adding-first-device.md)
