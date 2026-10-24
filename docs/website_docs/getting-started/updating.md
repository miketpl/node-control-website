# Updating Node Control

The current release is 0.9.42. 0.9.41 is still the minimum version the licence server accepts. Anything below 0.9.41 is refused.

## Updating from 0.9.41

From 0.9.41 the app checks once at launch, right after the licence check. There is no timer after that. The licence server never offers a downgrade. The installer file is still downloaded from GitHub, so a network that blocks GitHub can fail the download even when the check itself succeeds.

## Help > Check for Updates...

0.9.42 checks once at launch, right after the licence check. There is no timer after that. **Help → Check for Updates...** checks again.

If the server says it is busy or paused, the app backs off for 24 hours by default.

The start-up check stays silent if it fails. When it finds an update, it asks **Update Available**.

**Help → Check for Updates...** shows one of these:

- **Could not check for updates.** The line underneath is the server's message, `Update check failed (<status> <code>)`, or the network error.
- **Downloads are paused.** On Free the text is `Downloads for Node Control Free are paused at the moment. Get the latest installer from nodecontrol.io, or try again later.`
- **Download failed.**
- **You're running the latest version (v0.9.42).**
- **Update available!**

## What is checked before installing

Before **Install & Restart**, the app checks:

- the checksum
- on macOS, the code signature: `codesign`, `spctl`, and the Team ID
- on Windows, the Authenticode publisher, **The Promised Lan Limited**
- the version

If a check fails, the log names the check that failed: checksum, codesign, spctl, Team ID, publisher, or version.

## Install & Restart on Mac and Windows

Downloads resume if the connection drops.

On a Mac, **Install & Restart** replaces the app after those checks pass.

On Windows:

1. The new installer downloads to `%TEMP%`
2. **Install & Restart** closes Node Control
3. A UAC prompt appears, the installer runs, and the app opens on the new version

The library, settings, and credentials carry over.

## The .previous.app copy on macOS

macOS keeps `Node Control Pro.previous.app` until the new version starts.

## Update required

The dialog is **Update required.** The text is `This version (v…) is no longer supported. Version v… must be installed to continue.` It cannot be dismissed. The buttons are **Download Update**, **Open nodecontrol.io**, and **Quit**.

## When Free downloads are paused

The dialog is **Downloads are paused.** On Free the text is `Downloads for Node Control Free are paused at the moment. Get the latest installer from nodecontrol.io, or try again later.` If the server says it is busy or paused, the app backs off for 24 hours by default.

## On 0.9.40 or earlier: install by hand

0.9.40 and earlier cannot self-update. Download the current installer from [nodecontrol.io](https://nodecontrol.io) and install it over the old one. The library is kept. Do not install an older build. The licence server refuses anything below 0.9.41.

A 0.9.40 Pro install emails a 6-digit code to the registration address when the activation dialog opens. See [Your licence](licence.md).

## Oldest supported version

0.9.41 is the oldest version the licence server accepts. There is no downgrade path.

## Next steps

- [Update problems](../troubleshooting/update-issues.md)
- [Your licence](licence.md)
- [Installing on macOS](installation-mac.md)
- [Installing on Windows](installation-windows.md)
