# Upgrading from Free to Pro

Once your network outgrows Free's 25-device cap, or you need the tasks and reports Free greys out, upgrading to Pro is straightforward.

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

Go to [nodecontrol.io](https://nodecontrol.io) and subscribe to Professional. Choose monthly (£25/month ex VAT) or annual (£255/year ex VAT, which is £21.25/mo billed annually, ex VAT, save 15%). Checkout asks for:

- Your name
- Email (this becomes the licensed identity)
- Billing address and payment details

When Stripe confirms the payment, that email is added to the Pro allowed-users list. You'll receive a confirmation email with the download page.

### 2. Download Node Control Pro

From the email or the checkout success page, download:

- **Mac**: the Pro disk image from the download link in that email
- **Windows**: the Pro NSIS installer from the same link. It is signed, and the verified publisher is **The Promised Lan Limited**

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

Open **Engineer** from the sidebar. You should see the devices that were in your Free library, without the 25-device cap. The library is stored in `~/Library/Application Support/netOps/netOps.db` (Mac) or `%APPDATA%\netOps\` (Windows), shared across all tiers on the same machine.

### 6. Uninstall Free (optional)

Once you're happy Pro is working, you can uninstall Free:

**Mac**: drag `Node Control Free.app` from Applications to Trash. Your data is unaffected.

**Windows**: **Settings → Apps → Node Control Free → Uninstall**. Data preserved.

The Free activation code you entered remains valid — if you ever want to install Free again on this or another machine, the same code works.

## What if my Pro email isn't on the allowed list yet?

If you've just paid and your registration is rejected:

1. Wait a few minutes for the allowed list to update
2. Click **Re-register** in the rejection dialog and try again
3. If still rejected after 15 minutes, email [support@nodecontrol.io](mailto:support@nodecontrol.io) with the email you paid with — we'll check the subscription and add you manually if the payment is there

## Sharing one Pro license across machines

A Pro license is per-user, not per-machine. You can install Pro on as many machines as you personally use — laptop, desktop, lab box. Each registration adds an entry to the Pro user list, but only your email needs to match.

If you change machines (e.g., new laptop):

1. Install Pro on the new machine
2. Register with the same email
3. The Pro library and settings don't auto-sync — use [GitHub library sync](../library/github-sync.md) if you want a single source of truth

## Renewing or transferring a license

Professional is a subscription: £25/month ex VAT, or £255/year ex VAT. Cancelling stops the next renewal. The app keeps working until the end of the period you have already paid. When that period ends, or a renewal fails, the email comes off the allowed-users list. The app then blocks. If it cannot check in, it blocks after the 7-day offline grace.

Manage the card or cancel from the link on [nodecontrol.io](https://nodecontrol.io/#manage). That page emails a billing link. It does not show whether the address has a subscription.

To transfer a license to a different email (e.g., job change, company restructure), contact [support@nodecontrol.io](mailto:support@nodecontrol.io). We'll move the licensed email and disable the old one.

## Downgrading from Pro back to Free

If you want to switch back to Free (e.g., no longer working with large networks):

1. Install Node Control Free
2. Activate with an `NC-XXXX-XXXX` code from nodecontrol.io
3. Your library file is preserved. The Free table shows 25 devices even when the database holds more. A manual add refuses the 26th. A workbook import is cut to the first 25. A GitHub pull is cut to the first 25, sorted by IP. Library Updater does not run on Free. The extra rows are not deleted
4. You can uninstall Pro at any time

If you later re-upgrade, all devices become visible again.
