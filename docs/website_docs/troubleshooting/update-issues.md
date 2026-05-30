# Update problems

When **Help → Check for Updates** doesn't work, or downloads fail, or installs hang.

## Symptom 1 — "No update available" when you know there's a newer version

Possible causes:

### You're on a different tier's update channel

Pro builds check the Pro releases repo; Free builds check the Free releases repo. If you're running Free and there's a Pro v0.9.30 release, your Free install won't see it (and shouldn't — they're different products).

Confirm: Help → About → check the tier. Confirm the latest version available for THAT tier on:

- Free: https://github.com/miketpl/node-control-releases-free/releases
- Pro: (Pro release channel — your customer portal has the URL)

### The releases page hasn't been published yet

Sometimes a build is internally tested before the release is published to the GitHub releases page. Check the public release page — if no v0.9.30 there, your client correctly reports no update.

### Cached lookup

The updater caches the latest-known version for ~1 hour. To force re-check:

- Quit and re-launch
- Try Check for Updates again

## Symptom 2 — "Could not reach any release repo"

The updater can't fetch the latest release info. Causes:

### Network connectivity

```bash
ping api.github.com
curl https://api.github.com/repos/miketpl/node-control-releases-free/releases/latest
```

If either fails: your network blocks GitHub API access. Common in corporate networks behind strict proxies.

### Proxy / firewall

Settings → Advanced → check if HTTP/HTTPS proxy needs to be configured. Node Control uses the system proxy by default.

For corporate firewalls that proxy-intercept SSL:

- The proxy CA needs to be trusted by Node Control's bundled `certifi` cert store
- Workaround: Settings → Advanced → check **Use system cert store** (uses macOS / Windows root CAs instead of bundled certifi)

### Token expired / revoked

The PATs baked into Node Control to read the releases repos are long-lived (1+ years) but can be rotated/revoked. If we rotate a token, you may need to update to a newer Node Control to pick up the new token.

Symptom: every update check fails with 401 Unauthorized. Solution: download the latest version manually from the releases page.

## Symptom 3 — Download fails partway through

Cause: connection dropped mid-download.

The downloader supports resume — re-trigger the download and it'll pick up where it stopped:

1. Help → Check for Updates → Download

For chronic download failures:

- Manually download the DMG / Setup.exe from the releases page in a browser
- Install manually — same end-state as the in-app downloader

## Symptom 4 — "Install & Restart" fails on Windows

When the in-app installer runs (Windows):

1. Node Control downloads the new Setup.exe
2. Triggers an elevated PowerShell script that:
   - Sleeps 2 seconds (lets Node Control fully exit)
   - `Start-Process -Verb RunAs` invokes the installer with UAC
3. The installer runs silently and re-launches Node Control on the new version

Failure modes:

### "Error opening file for writing" (Windows-specific)

Old Node Control held a lock on a file in its install dir while the installer tried to overwrite it. Fixed in 0.9.x — the 2-second sleep before launch closes Node Control fully before UAC.

If you see this on an older version, manually run the downloaded Setup.exe after closing Node Control.

### UAC declined

User clicked No on the UAC prompt. The installer doesn't run. Re-trigger from Help → Check for Updates → Install & Restart.

### Antivirus quarantining the installer

Some AVs flag installers as suspicious. Whitelist `Node Control Free-X.Y.Z-Setup.exe` (or Pro equivalent) in your AV.

## Symptom 5 — Mac install hangs

Cause: Gatekeeper checking the downloaded DMG online for notarization status.

Wait 30-60 seconds. If still hung after that:

- The Mac is likely trying to fetch the notarization ticket from Apple's CDN and failing
- Quit Node Control (Cmd+Q)
- Open the DMG manually from your Downloads folder
- Drag the app to Applications

The stapled notarization ticket makes Gatekeeper checks instant (no online lookup), but if the staple is somehow missing (rare), Gatekeeper falls back to online.

## Symptom 6 — New version installs but app doesn't restart

Cause: macOS LaunchServices cache out of date.

Fix:

- Quit Node Control fully
- Open Applications → double-click the app

Or use the LaunchServices register command (Mac power-user):

```bash
/System/Library/Frameworks/CoreServices.framework/Versions/A/Frameworks/LaunchServices.framework/Versions/A/Support/lsregister -kill -r -domain local -domain system -domain user
```

## Symptom 7 — License re-check fails after update

After updating, the license check fails with "Unable to verify your license."

Cause: the new version may have a different license check endpoint (rare, but possible during major changes). Free's license check now points at `licenses-free` repo, for example — a very old Free build won't have known to check there.

Fix:

- Re-launch the app (often a one-time issue)
- If persistent, do a clean re-activation: enter your code again at the dialog
- For Pro: re-register with your email

## Symptom 8 — App crashes after update

Hopefully rare. If it happens:

- Check the [crash log](crash-logs.md) — what does the latest crash say?
- Send to support with the version you upgraded FROM and TO
- Workaround: downgrade by running the previous installer (Setup.exe / DMG) — your data is preserved

## Manual update flow

If the in-app updater is unreliable, you can always:

1. Download from https://nodecontrol.io or the release repo directly
2. Install over the top (Mac: drag to Applications; Windows: run Setup.exe)
3. Library, settings, credentials all preserved

## Checking what version you're on

- Help → About
- Or: `Node Control` menu (Mac) → About Node Control
- Or: command line on Mac: `defaults read /Applications/Node\ Control\ Free.app/Contents/Info CFBundleShortVersionString`

## Auto-update channel

Settings → General → **Auto-check for updates**:

- **Daily** (default): silent background check at app launch + every 24h while running
- **Weekly**: same but every 7 days
- **Never**: only checks when you explicitly use Help → Check for Updates

Notifications appear in the status bar; clicking opens the download dialog.

## Next steps

- [Installation Mac](../getting-started/installation-mac.md)
- [Installation Windows](../getting-started/installation-windows.md)
- [Reading the crash log](crash-logs.md)
