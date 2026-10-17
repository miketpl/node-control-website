# Setting up credentials

Node Control connects to your devices over SSH and needs login credentials to do so. Credentials are stored in your OS keychain. The database stores a reference to the profile, not the password.

## Where credentials are stored

| OS | Storage backend |
|---|---|
| macOS | Apple Keychain (Login keychain) |
| Windows | Windows Credential Manager |
| Linux | Secret Service (GNOME Keyring / KWallet) |

See [How credentials are stored](../security/credential-storage.md) for the full security model.

## The Credentials dropdown

The toolbar **Credentials** dropdown has the tooltip **Credential set for NEW SSH connections**. It lists:

- **All**
- each profile
- **Manual**
- **Device Type Creds...**
- **Add Credentials...**

With **All**, profiles are tried in list order.

## Settings → Credentials

**Edit → Settings...** → **Credentials**, or **Settings** in the sidebar footer. There is no Tools menu.

The page has **Add**, **Remove**, and up/down buttons. **Move up** says: with **All** selected, profiles are tried in this order.

Profile fields:

- **Profile Name**
- **Keychain Service (Login)**
- **Keychain Service (Enable)**
- **Username**
- **Credential Provider**
- **Login Password**
- **Enable Password**
- **Save Profile**

There is no star icon and no default-profile flag.

**Device Type Creds...** opens **Credential Settings**. That dialog has the try order and a Device Type to Credential Profile map.

## Select Credentials

When a task starts, **Select Credentials** shows **Default Credentials** → **Profile:**. The combo is All, the profiles, or Manual.

When the targets span two or more device types, a **Per Device Type** table is shown. Each row defaults to **(Use Default)**.

## What is remembered

Tabs do not remember a credential profile. Sites do not either.

What is remembered is the last profile chosen for that task, pre-selected the next time the task runs, and the global device-type map.

## Login notices

When ISE (TACACS+) says at login that your password is about to expire, or that you must change it, Node Control shows that message. The terminal replays it before the prompt and repeats each notice in bold yellow. Tasks log it as well. See [SSH Terminal](../tasks/ssh-terminal.md).

Changing an ISE network-access password is a Pro task: [Change ISE Password](../tasks/change-ise-password.md).

## Troubleshooting authentication

| Error | Cause | Fix |
|---|---|---|
| "Authentication failed" | Wrong username or password | Test the creds with your usual SSH client first |
| "Connection refused" | SSH not running on the device, or the wrong port | Confirm SSH is enabled and reachable on TCP/22 |
| "Connection timed out" | Network unreachable, or a firewall is blocking | Confirm the IP answers and TCP/22 is open |
| "Host key verification failed" | The device's host key changed | Treat that as a replaced device, or as something to check, before you accept the new key |

See [Troubleshooting SSH connection issues](../troubleshooting/ssh-connection-issues.md).

## Removing or rotating a profile

1. **Settings → Credentials**
2. Select the row → **Remove**
3. Confirm. The password is removed from the keychain

To rotate a password, edit the profile and click **Save Profile**.

## Next steps

- [Adding your first device](adding-first-device.md)
- [L2 Topology Builder](../tasks/topology-l2.md)
- [Library overview](../library/overview.md)
