# First launch and activation

On first launch, Node Control checks the licence at api.nodecontrol.io. Pro activates with the NCP licence key alone. Free activates with its activation code. There is no GitHub licence check, and there is no email allow-list.

## Free tier — activation code

When you launch Node Control Free for the first time, an **Activate Node Control Free** dialog appears.

### Where the code comes from

1. Visit [nodecontrol.io](https://nodecontrol.io) and click **Get Free**
2. Enter your email
3. Check your inbox for a 6-digit verification code; enter it on the website
4. The website then generates your activation code in the format `NC-XXXX-XXXX`
5. Save the code somewhere safe — your password manager is ideal

### Entering the code in the app

1. Type or paste the code into the **Activation code** field
2. Click **Activate**
3. The app contacts api.nodecontrol.io, confirms the code is valid, and stores it locally
4. The dialog closes and the main app window appears

The Free code is checked online. If that check cannot run, you get a **7-day offline grace period**. While the grace period still has days left, the app opens. When the grace period runs out, the app is blocked until it can check the code again.

You will also be stopped if the code is later revoked.

### Code format rules

- Always starts with `NC-`
- Eight characters after the prefix, split as `NC-XXXX-XXXX`
- Uppercase letters and digits only (the app auto-uppercases lowercase input)
- The dashes are required

## Pro — NCP key

Pro activates with the NCP licence key. The confirmation email after purchase contains it.

1. Enter the key
2. Click **Activate**
3. The app checks the key at api.nodecontrol.io

One computer per licence. The full move and deactivate steps are on [Your licence](licence.md).

### Upgrading a 0.9.40 Pro install

When the dialog opens on a 0.9.40 Pro install, a 6-digit code is emailed to the registration address. Enter that code.

### Lost your key

**Email me a code**, then **Confirm code**, recovers a lost key. The same key is sent.

### Licence in use

If the key is already on another computer, **Licence in use** offers **Move licence here**. Confirm with the emailed code. The server allows two moves in 30 days.

**Settings → General → Deactivate this computer** frees the licence on the computer you are leaving.

### When you'll see this again

- After installing on a new machine
- After a clean uninstall and reinstall
- If you cancel activation and re-open the app

## If activation fails

| Dialog or message | What it means | What to do |
|---|---|---|
| **Verifying Licence** | The app is checking the licence at api.nodecontrol.io | Wait. **Retry** if it sits there. **Enter a licence key** to use a different one |
| **Offline Mode** | The check could not run, and the 7-day grace still has time | **Continue**. **Retry** when the laptop can reach api.nodecontrol.io. **Enter a licence key** to change it |
| **Licence Not Accepted** | The key or the Free code was refused | **Retry**, or **Enter a licence key** |
| **Grace Period Expired** | The 7-day offline grace has run out | Connect, then **Retry**. **Enter a licence key** if this computer should use a different one |
| **Licence Check Failed** | The check failed | **Retry**. **Enter a licence key** if the stored one is wrong |
| "Code must be in the format NC-XXXX-XXXX" | The Free code is malformed or the wrong length | Re-paste it from the website or the email |
| "This license code is not active" | The Free code is not an active licence | Confirm you copied it. If you did, request a fresh code at nodecontrol.io |

## Why we check at all

The licence check exists to:

- See which licences are in use, so support and product notices can reach them
- Revoke a code or a subscription that is misused
- See which build is in use if you email a crash log to support. The crash log stays on the laptop until you send it

Service email, including a notice that a version will stop working, is described in the [privacy notice](https://nodecontrol.io/privacy.html). That notice also says what is not a promotional mailing list.

## Next steps

- [Your licence and moving between computers](licence.md)
- [Updating Node Control](updating.md)
- [Adding your first device](adding-first-device.md)
- [Tier comparison](../tiers/overview.md)
