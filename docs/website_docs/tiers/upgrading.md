# Upgrading from Free to Pro

Once your network outgrows Free's 25-device cap, or you need the tasks and reports Free greys out, upgrading to Pro is straightforward.

## What you'll keep

- Your entire device library — all devices, sites, tabs, custom commands, and credential profiles
- All settings — site detection regex, command preferences, UI state
- The SSH host keys you've already accepted (no re-trust prompts)

## What changes

- **Activation flow**: instead of entering an `NC-XXXX-XXXX` code, Pro asks for the NCP licence key. Click **Activate**
- **App bundle name**: macOS shows "Node Control Pro.app" instead of "Node Control Free.app" in Applications
- **Feature gates**: all the Pro features become available immediately

## Upgrade steps

### 1. Buy a Pro license

Go to [nodecontrol.io](https://nodecontrol.io) and subscribe to Professional. Choose monthly (£25/month ex VAT) or annual (£255/year ex VAT, which is £21.25/mo billed annually, ex VAT, save 15%). Checkout asks for:

- Your name
- Email (this becomes the licensed identity)
- Billing address and payment details

When Stripe confirms the payment, the confirmation email contains the NCP licence key and the download for the first install. The checkout success page shows that key for 24 hours, with macOS and Windows links that last 30 minutes. Reload the page for a new pair. If the email cannot point at that page, it contains macOS and Windows links that last 24 hours, and they work only while the subscription is active. A key added by hand arrives with its own Mac and Windows links for the first install. Those last 7 days, and sending them again does not change the key. After that install, the app updates itself. The installer file is downloaded from GitHub.

### 2. Download Node Control Pro

From the email or the checkout success page, download:

- **Mac**: the Pro disk image from the download link in that email
- **Windows**: the Pro NSIS installer from the same link. It is signed, and the verified publisher is **The Promised Lan Limited**

### 3. Install Pro alongside Free (optional)

You can keep Node Control Free installed while you set up Pro — they coexist as separate applications.

**Mac**: drag Pro to Applications normally. You'll have both `Node Control Free.app` and `Node Control Pro.app`.

**Windows**: run the Pro Setup.exe. Installs to `C:\Program Files\Node Control Pro\` alongside Free's `C:\Program Files\Node Control Free\`.

### 4. Launch Pro and activate

On first launch of Pro:

1. Enter the NCP licence key
2. Click **Activate**
3. The app checks the key at api.nodecontrol.io

There is no email allow-list, and there is no GitHub licence check.

If this install is upgrading a 0.9.40 Pro install, the dialog emails a 6-digit code to the registration address. Enter that code.

If the key is lost, use **Email me a code**, then **Confirm code**. See [Your licence](../getting-started/licence.md).

### 5. Verify your library transferred

Open **Engineer** from the sidebar. You should see the devices that were in your Free library, without the 25-device cap. The library is stored in `~/Library/Application Support/netOps/netOps.db` (Mac) or `%APPDATA%\netOps\` (Windows), shared across all tiers on the same machine.

### 6. Uninstall Free (optional)

Once you're happy Pro is working, you can uninstall Free:

**Mac**: drag `Node Control Free.app` from Applications to Trash. Your data is unaffected.

**Windows**: **Settings → Apps → Node Control Free → Uninstall**. Data preserved.

The Free activation code you entered remains valid — if you ever want to install Free again on this or another machine, the same code works.

## If your key is not accepted

The launch screen is **Licence Not Accepted** or **Licence Check Failed**. Each has **Retry** and **Enter a licence key**.

1. Check the key against the confirmation email
2. Click **Retry**, or **Enter a licence key**
3. If it is still refused, email [support@nodecontrol.io](mailto:support@nodecontrol.io)

## One computer per licence

A licence runs on one computer. See [Your licence](../getting-started/licence.md).

On a new laptop:

1. Install Pro on the new machine
2. Activate with the same NCP key
3. If the key is already in use, **Licence in use** offers **Move licence here**. Confirm with the emailed code. Or, on the old computer, open **Settings → General → Deactivate this computer**
4. The library and settings do not auto-sync. Use [GitHub library sync](../library/github-sync.md) if you want a single source of truth

## Renewing or transferring a license

Professional is a subscription: £25/month ex VAT, or £255/year ex VAT. Cancelling stops the next renewal. The app keeps working until the end of the period you have already paid. When that period ends, or a renewal fails, the licence is no longer accepted. The app then blocks. If it cannot check in, it blocks after the 7-day offline grace.

Manage the card or cancel from the link on [nodecontrol.io](https://nodecontrol.io/#manage). That page emails a billing link. It does not show whether the address has a subscription.

To transfer a license to a different email (e.g., job change, company restructure), contact [support@nodecontrol.io](mailto:support@nodecontrol.io). We'll move the licensed email and disable the old one.

## Downgrading from Pro back to Free

If you want to switch back to Free (e.g., no longer working with large networks):

1. Install Node Control Free
2. Activate with an `NC-XXXX-XXXX` code from nodecontrol.io
3. Your library file is preserved. The Free table shows 25 devices even when the database holds more. A manual add refuses the 26th. A workbook import is cut to the first 25. A GitHub pull is cut to the first 25, sorted by IP. Library Updater does not run on Free. The extra rows are not deleted
4. You can uninstall Pro at any time

If you later re-upgrade, all devices become visible again.
