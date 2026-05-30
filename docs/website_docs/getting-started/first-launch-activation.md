# First launch and activation

On first launch, Node Control needs to verify your tier — different flows for Free vs Pro/AI users.

## Free tier — activation code

When you launch Node Control Free for the first time, an **Activate Node Control Free** dialog appears.

### Where the code comes from

1. Visit [nodecontrol.io](https://nodecontrol.io) and click **Get Free**
2. Enter your email
3. Check your inbox for a 6-digit verification code; enter it on the website
4. The website then generates your activation code in the format `NC-XXXX-XXXX` (e.g., `NC-TH7G-6VNI`)
5. Save the code somewhere safe — your password manager is ideal

### Entering the code in the app

1. Type or paste the code into the **Activation code** field
2. Click **Activate**
3. The app contacts the license server (~1–2 seconds), confirms the code is valid, and stores it locally
4. The dialog closes and the main app window appears

After this, you won't be asked for the code again unless:

- The code is later revoked (e.g., you violate terms of use), OR
- You haven't been online for more than 7 days *and* your offline grace period has expired

### Code format rules

- Always starts with `NC-`
- Eight characters after the prefix, split as `NC-XXXX-XXXX`
- Uppercase letters and digits only (the app auto-uppercases lowercase input)
- The dashes are required

### If activation fails

| Error | What it means | What to do |
|---|---|---|
| "Code must be in the format NC-XXXX-XXXX" | The code is malformed or wrong length | Re-paste from the website / email |
| "This license code is not active" | The code wasn't found in our active licenses list | Confirm you copied it correctly; if so, request a fresh code at nodecontrol.io |
| "Unable to verify your license" with no prior check | Network failure on first activation — your machine can't reach `api.github.com` | Check your internet connection, firewall, proxy settings |
| "Offline grace period: N days remaining" | Network failure but you've successfully activated before — you can continue offline for the remaining days | Just close the message; the app will retry next launch |

## Pro / AI tier — email registration

When you launch Node Control Pro (or AI) for the first time, a **Welcome to Node Control** registration dialog appears.

### Registration form

Fill in:

- **Name** — your full name
- **Email** — the email address associated with your Pro purchase or beta access
- **Organisation** (optional) — your company name
- **Role** (optional) — e.g., Network Engineer, IT Manager

Click **Submit**. The app:

1. Records your registration locally
2. Submits the details to our private registrations system on GitHub (used for support, not for marketing)
3. Checks your email against the allowed Pro user list
4. If your email is on the list — you're in
5. If not — a "not approved" message appears with contact info for support

### When you'll see this again

- After installing on a new machine
- After a clean uninstall + reinstall
- If you cancel the registration and re-open the app

### License re-check

On every launch, Pro / AI rechecks your email against the allowed user list. Same 7-day offline grace period applies — useful if you're on a customer site without internet for a few days.

## Why we check at all

The license check exists to:

- Track active users for support and update notifications
- Allow rapid response if a code or account is misused
- Give us a feedback channel ("we noticed v0.9.29 is crashing for 3 customers — let's investigate")

We do *not* use your email or activation data for marketing. Our [privacy policy](https://nodecontrol.io/privacy) covers full details.

## Next steps

- [Adding your first device](adding-first-device.md)
- [Setting up credentials](credentials.md)
- [Tier comparison](../tiers/overview.md)
