# Updating Node Control

0.9.41 is a required release. It is the minimum version the licence server accepts. Anything below 0.9.41 is refused.

## Updating from 0.9.41

From 0.9.41 the app updates itself. The licence server never offers a downgrade. The installer file is still downloaded from GitHub, so a network that blocks GitHub can fail the download even when the check itself succeeds.

## Help > Check for Updates...

**Help → Check for Updates...** asks the licence server now. The app also checks for updates itself. There is no Daily, Weekly, or Never setting for that check.

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

## Update Required

**Update Required** cannot be dismissed. The buttons are **Download Update**, **Open nodecontrol.io**, and **Quit**.

## When Free downloads are paused

Free in-app downloads may be paused briefly after a release. The check then reports that Free downloads are paused. Pro downloads are not paused by that switch. Install the current Free build from [nodecontrol.io](https://nodecontrol.io) if you cannot wait.

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
