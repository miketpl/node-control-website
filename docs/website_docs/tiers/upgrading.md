# Upgrading from Free to Pro

Once your network outgrows Free's 25-device cap or you need topology maps and reports, upgrading to Pro is straightforward.

## What you'll keep

- Your entire device library — all devices, sites, tabs, custom commands, and credential profiles
- All settings — site detection regex, command preferences, UI state
- The SSH host keys you've already accepted (no re-trust prompts)

## What changes

- **Activation flow**: instead of entering an `NC-XXXX-XXXX` code, Pro asks for the email address you used when purchasing
- **App bundle name**: macOS shows "Node Control Pro.app" instead of "Node Control Free.app" in Applications
- **Feature gates**: all the Pro features become available immediately

## Upgrade steps

### 1. Buy a Pro license

Go to [nodecontrol.io](https://nodecontrol.io) and click **Buy Pro**. The purchase flow asks for:

- Your name
- Email (this becomes the licensed identity)
- Payment details

Once paid, your email is added to the Pro allowed-users list within ~5 minutes. You'll receive a confirmation email with download links.

### 2. Download Node Control Pro

From the email or your customer portal, download:

- **Mac**: `Node Control Pro-X.Y.Z.dmg`
- **Windows**: `Node Control Pro-X.Y.Z-Setup.exe`

### 3. Install Pro alongside Free (optional)

You can keep Node Control Free installed while you set up Pro — they coexist as separate applications.

**Mac**: drag Pro to Applications normally. You'll have both `Node Control Free.app` and `Node Control Pro.app`.

**Windows**: run the Pro Setup.exe. Installs to `C:\Program Files\Node Control Pro\` alongside Free's `C:\Program Files\Node Control Free\`.

### 4. Launch Pro and register

On first launch of Pro:

1. The **Welcome to Node Control** registration dialog appears
2. Enter your name, email (must match your purchase email), organisation
3. Click **Submit**
4. The app checks your email against the Pro allowed-users list
5. If your email is on the list — you're in. If not — confirm the email matches, or contact support

### 5. Verify your library transferred

Open the **Engineer** tab. You should see all the devices that were in your Free library — and now without the 25-device cap. The library is stored in `~/Library/Application Support/netOps/netOps.db` (Mac) or `%APPDATA%\netOps\` (Windows), shared across all tiers on the same machine.

### 6. Uninstall Free (optional)

Once you're happy Pro is working, you can uninstall Free:

**Mac**: drag `Node Control Free.app` from Applications to Trash. Your data is unaffected.

**Windows**: **Settings → Apps → Node Control Free → Uninstall**. Data preserved.

The Free activation code you entered remains valid — if you ever want to install Free again on this or another machine, the same code works.

## What if my Pro email isn't on the allowed list yet?

If you've just purchased and your registration is rejected:

1. Wait ~5 minutes for the allowed list to update
2. Click **Re-register** in the rejection dialog and try again
3. If still rejected after 15 minutes, email [info@nodecontrol.io](mailto:info@nodecontrol.io) with your order number — we'll add you manually within a few hours

## Sharing one Pro license across machines

A Pro license is per-user, not per-machine. You can install Pro on as many machines as you personally use — laptop, desktop, lab box. Each registration adds an entry to the Pro user list, but only your email needs to match.

If you change machines (e.g., new laptop):

1. Install Pro on the new machine
2. Register with the same email
3. The Pro library and settings don't auto-sync — use [GitHub library sync](../library/github-sync.md) if you want a single source of truth

## Renewing or transferring a license

Pro is sold as a perpetual licence with a one-year support and updates window. After year one, the app continues to work but you stop receiving updates until you renew.

To transfer a license to a different email (e.g., job change, company restructure), contact [info@nodecontrol.io](mailto:info@nodecontrol.io). We'll move the licensed email and disable the old one.

## Downgrading from Pro back to Free

If you want to switch back to Free (e.g., no longer working with large networks):

1. Install Node Control Free
2. Activate with an `NC-XXXX-XXXX` code from nodecontrol.io
3. Your library is preserved. Tools that respect Free's 25-device cap will only see the first 25 devices (sorted by IP) — but the rest aren't deleted; they're just hidden
4. You can uninstall Pro at any time

If you later re-upgrade, all devices become visible again.
