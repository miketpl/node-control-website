# Update problems

When **Help → Check for Updates...** does not work, or a download fails, or an install hangs. The check asks the licence server at api.nodecontrol.io. The installer file is then downloaded from GitHub. The server never offers a downgrade. See [Updating Node Control](../getting-started/updating.md).

## Symptom 1 — you expected a newer version

**Help → Check for Updates...** says **You're running the latest version (v0.9.42).** when nothing newer is offered. The version in parentheses is the one you are running.

### You're on a different edition

Free and Pro are different products. A Pro update is not offered to a Free install.

Confirm the edition in Help → About. The current installer for that edition is on [nodecontrol.io](https://nodecontrol.io).

### You are below 0.9.41

0.9.40 and earlier cannot self-update. Install the current build by hand from nodecontrol.io. Anything below 0.9.41 is refused.

## Symptom 2 — the check cannot reach the licence server

The update check goes to api.nodecontrol.io. The installer file is downloaded from GitHub, so a network that blocks GitHub can still fail the download after the check succeeds.

```bash
ping api.nodecontrol.io
ping api.github.com
```

### Proxy / firewall

Settings → Advanced → check if an HTTP/HTTPS proxy needs to be configured. Node Control uses the system proxy by default.

For a corporate firewall that intercepts SSL:

- The proxy CA needs to be trusted by Node Control's bundled `certifi` store
- Workaround: Settings → Advanced → **Use system cert store** (macOS or Windows root CAs instead of bundled certifi)

## Symptom 3 — Download fails partway through

The dialog is **Download failed.** The downloader resumes. Run **Help → Check for Updates...** again and it picks up where it stopped.

If that keeps failing, download the current installer from nodecontrol.io and install it by hand. That is the same end state. Do not install an older build.

**Downloads are paused.** On Free the text is `Downloads for Node Control Free are paused at the moment. Get the latest installer from nodecontrol.io, or try again later.` If the server says it is busy or paused, the app backs off for 24 hours by default.

## Symptom 4 — "Install & Restart" fails on Windows

1. Node Control downloads the new Setup.exe
2. An elevated PowerShell script waits 2 seconds so Node Control has exited, then `Start-Process -Verb RunAs` starts the installer
3. The installer runs and opens Node Control on the new version

Before that, the app checks the checksum and the Authenticode publisher, **The Promised Lan Limited**. If a check fails, the log names it: checksum, publisher, or version.

### "Error opening file for writing"

An old build could still hold a file in its install directory. Close Node Control, then run the downloaded Setup.exe yourself.

### UAC declined

**No** on the UAC prompt means the installer does not run. Use **Help → Check for Updates...** → **Install & Restart** again.

### Antivirus quarantining the installer

Whitelist the Setup.exe for the edition you installed.

## Symptom 5 — Mac install hangs

Gatekeeper may be checking the downloaded disk image.

Wait 30–60 seconds. If it is still hung:

- Quit Node Control
- Open the disk image from Downloads
- Drag the app to Applications

Before **Install & Restart**, the app checks the checksum and the code signature (`codesign`, `spctl`, and the Team ID). If a check fails, the log names it: checksum, codesign, spctl, Team ID, or version.

macOS keeps `Node Control Pro.previous.app` until the new version starts.

## Symptom 6 — New version installs but the app does not restart

Quit Node Control, then open the app from Applications.

Or, on a Mac:

```bash
/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -kill -r -domain local -domain system -domain user
```

## Symptom 7 — Licence check fails after the update

The launch screen is **Licence Check Failed**, **Licence Not Accepted**, or **Grace Period Expired**. Each has **Retry** and **Enter a licence key**.

- **Retry** runs the check again
- **Enter a licence key** if this computer should use a different key
- Anything below 0.9.41 is refused. Install 0.9.41 or later from nodecontrol.io

## Symptom 8 — App crashes after the update

- Read the [crash log](crash-logs.md)
- Send it to support with the version you came from and the version you installed
- Install the current build again from nodecontrol.io. The library is kept. There is no downgrade

## Update required

The dialog is **Update required.** The text is `This version (v…) is no longer supported. Version v… must be installed to continue.` It cannot be dismissed. **Download Update** starts the install. **Open nodecontrol.io** opens the site. **Quit** closes the app.

## Install by hand

1. Download the current installer from https://nodecontrol.io
2. Install over the top (Mac: drag to Applications; Windows: run Setup.exe)
3. The library, settings, and credentials are kept

## Checking what version you're on

- Help → About
- Or, on a Mac: the **Node Control** menu → About Node Control

## When the check runs

0.9.42 checks once at launch, right after the licence check. There is no timer after that. **Help → Check for Updates...** checks again.

If the server says it is busy or paused, the app backs off for 24 hours by default.

The start-up check stays silent if it fails. The failure dialog is only from **Help → Check for Updates...**: **Could not check for updates.** The line underneath is the server's message, `Update check failed (<status> <code>)`, or the network error.

When the start-up check finds an update, it asks **Update Available**. **Help → Check for Updates...** says **Update available!**

## Next steps

- [Updating Node Control](../getting-started/updating.md)
- [Installation Mac](../getting-started/installation-mac.md)
- [Installation Windows](../getting-started/installation-windows.md)
- [Reading the crash log](crash-logs.md)
