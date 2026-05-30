# Setting up credentials

Node Control connects to your devices over SSH and needs login credentials to do so. Credentials are stored securely in your OS keychain — never in plain text — and can be configured globally, per site, or per device.

## Where credentials are stored

| OS | Storage backend |
|---|---|
| macOS | Apple Keychain (Login keychain) |
| Windows | Windows Credential Manager |
| Linux | Secret Service (GNOME Keyring / KWallet) |

Node Control's database (`netOps.db`) only stores a *reference* to the credential profile — never the actual password. The secret is fetched from the keychain on demand each time the app connects.

See [How credentials are stored](../security/credential-storage.md) for the full security model.

## Credential profiles

A **credential profile** is a named set of:

- **Username**
- **Password** (and optional secondary password for enable mode)
- Optional **SSH key** (for key-based auth instead of password)

You typically have one profile per administrative domain — e.g., "Acme Networks Production", "Customer Site A Read-Only".

## Adding a credential profile

1. **Settings → Credentials** tab (or **Tools → Credentials**)
2. Click **+ Add Profile**
3. Fill in:
   - **Profile name** — friendly name (e.g., "Default Read-Write")
   - **Username** — the SSH login name
   - **Password** — the SSH password
   - **Secondary password** (optional) — for Cisco enable mode or PaloAlto super-user
   - **SSH key path** (optional) — full path to a private key file (PEM format)
4. Click **Save**

The password is written to your OS keychain at this point.

## Default profile

The profile marked **Default** is used for any device that doesn't have its own per-device credential override.

Mark a profile as default by clicking the star icon next to it in the Credentials table.

## Per-device credentials

To override the default profile for one specific device:

1. In the library, right-click a device → **Credentials**
2. Pick a different profile from the dropdown
3. Click **Save**

Useful when a single switch in your library has a different password from everything else.

## Per-tab credentials

For environments where Firewalls have different creds from Switches, you can assign a profile per library tab in the Credentials settings.

## Two-credential fallback

Node Control supports trying *two* credential profiles on each connection — useful if you're migrating from old passwords to new ones. Set up both as profiles and pick them in the per-device dropdown; the app tries the first, falls back to the second if the first fails authentication.

## SSH key authentication

If your devices use SSH keys instead of passwords:

1. Add a credential profile with **Username** filled in and **Password** blank
2. Set **SSH key path** to the full path of your private key (e.g., `/Users/you/.ssh/id_rsa` or `C:\Users\you\.ssh\id_rsa`)
3. If the key has a passphrase, put it in **Password** — Node Control will use it to unlock the key

The key file itself isn't moved into the keychain — only the key path and passphrase are remembered.

## Multiple credentials per network

For real-world networks with mixed credentials (Cisco TACACS + Aruba local + Palo Alto admin), set up one profile per credential, then assign them per-device or per-tab.

## Troubleshooting authentication

Common failures:

| Error | Cause | Fix |
|---|---|---|
| "Authentication failed" | Wrong username/password | Test the creds via PuTTY / native SSH first |
| "Connection refused" | SSH not running on device, or wrong port | Confirm device has SSH enabled and reachable on TCP/22 |
| "Connection timed out" | Network unreachable, firewall blocking | Confirm `ping` reaches the IP and TCP/22 is open |
| "Host key verification failed" | New device with unfamiliar SSH key | Node Control auto-accepts on first connect — if you see this, the device's host key changed (possible MITM, or device was replaced) |

See [Troubleshooting SSH connection issues](../troubleshooting/ssh-connection-issues.md) for a deeper guide.

## Removing or rotating credentials

To delete a profile:

1. **Settings → Credentials**
2. Click the row → **Delete**
3. Confirm — the password is removed from the keychain immediately

To rotate a password (e.g., the device's password changed), just edit the profile and save the new value. The keychain entry is updated atomically.

## Next steps

- [Adding your first device](adding-first-device.md)
- [Run your first task](../tasks/topology-l2.md)
- [Library overview](../library/overview.md)
