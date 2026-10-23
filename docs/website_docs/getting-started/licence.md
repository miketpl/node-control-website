# Your licence and moving between computers

Pro activates with the NCP licence key alone. Free activates with its activation code. Both are checked at api.nodecontrol.io. There is no GitHub licence check, and there is no email allow-list.

## One computer per licence

One licence runs on one computer. A second computer needs **Move licence here**, or **Deactivate this computer** on the computer that already has it.

The server allows two moves in 30 days. The move code expires after 15 minutes.

## Activating Pro with your NCP key

The confirmation email after purchase contains the NCP key.

1. Install Pro. The download links are in that email, and on the checkout success page. See [Installing on macOS](installation-mac.md) or [Installing on Windows](installation-windows.md)
2. Enter the NCP key
3. Click **Activate**
4. The app checks the key at api.nodecontrol.io

## Activating Free with your code

1. Request Free at [nodecontrol.io](https://nodecontrol.io) and verify the 6-digit email code
2. Copy the `NC-XXXX-XXXX` activation code
3. On first launch, paste it into **Activation code**
4. Click **Activate**

The code is checked at api.nodecontrol.io.

## Upgrading a 0.9.40 Pro install

0.9.41 is a required release. When the dialog opens on a 0.9.40 Pro install, a 6-digit code is emailed to the registration address. Enter that code. After 0.9.41 is installed, the app updates itself. See [Updating Node Control](updating.md).

## Lost your key: Email me a code

**Email me a code** sends a 6-digit code to the registration address. **Confirm code** returns the NCP key. The same key is sent.

## Licence in use: Move licence here

If the key is already active on another computer, the **Licence in use** dialog offers **Move licence here**.

1. Click **Move licence here**
2. Enter the code from the email
3. This computer becomes the one active computer for that licence

## Deactivate this computer

**Settings → General → Deactivate this computer** frees the licence on this computer. The key can then be activated on another computer, still within the two moves in 30 days.

## Working offline: the 7-day grace

A successful check is good for 7 days offline. While those days remain, **Offline Mode** offers **Continue**. When the 7 days run out, the app stays on **Grace Period Expired** until it can check again.

## What the launch screens mean

Each of these has **Retry** and **Enter a licence key**.

| Screen | What it means |
|---|---|
| **Verifying Licence** | The app is checking the licence at api.nodecontrol.io |
| **Offline Mode** | The check could not run, and grace remains. **Continue** opens the app |
| **Licence Not Accepted** | The key or the Free code was refused |
| **Grace Period Expired** | The 7-day offline grace has run out. The app stays here until a check succeeds |
| **Licence Check Failed** | The check failed. **Retry** runs it again |

## Next steps

- [First launch and activation](first-launch-activation.md)
- [Updating Node Control](updating.md)
- [Upgrading from Free to Pro](../tiers/upgrading.md)
