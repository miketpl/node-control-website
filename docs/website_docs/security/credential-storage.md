# How credentials are stored

Passwords and API keys are encrypted on your machine, and the key that unlocks them is held in the macOS Keychain or Windows Credential Manager. The passwords themselves are not each stored in the keychain.

## Storage backend by OS

| OS | Where the master key is held | Where you can see that key |
|---|---|---|
| **macOS** | Apple Keychain (Login keychain) | Keychain Access.app |
| **Windows** | Windows Credential Manager | Control Panel → User Accounts → Credential Manager |

The master key is what the OS credential store holds. Passwords stay in the encrypted blob.

## What's in `netOps.db` vs what's in the keychain

Node Control's local SQLite database (`netOps.db`) stores:

- Device IPs, hostnames, sites, tabs, types
- Credential profile **names** and **usernames**
- The encrypted password blob

The keychain holds the master key that unlocks that blob. It is read once per session, with a single prompt. The database does not hold each password as its own keychain item.

## What gets stored in the keychain

The master key. Not a separate item for every profile password, API key, or passphrase. Those are in the encrypted blob.

## How a task uses a password

The master key is read from the keychain once per session and kept in memory. A task reads the encrypted blob from the database and unlocks the password it needs. It does not look up each password as its own keychain item.

## Rotating passwords

When a device's password changes:

1. Settings → Credentials → edit the relevant profile
2. Update the password field
3. Save — the encrypted blob is updated

## Revoking access

The encrypted passwords are in the local database. The master key is in the OS credential store. Clearing the master key from Keychain Access or Credential Manager, and deleting the database, removes both. Credential changes are not written to an audit log.

## Best practices

- **Use a different credential profile per administrative domain**: prevents one breach cascading across customers/sites
- **Use SSH keys with passphrases over passwords** where vendors support it
- **Rotate device passwords periodically** and update profiles
- **Don't share Node Control's underlying DB across users** — each user should have their own keychain for separation
- **Lock your screen** when stepping away — keychain access is gated by your login session

## Background Learning

**Allow the backend and background jobs to log into devices with my credentials** is under Settings → AI / LLM. It is off by default. Background Learning is a Pro and AI feature. On Free, the Settings → AI / LLM tab is not shown. Nothing on Free uses it. Unattended logins are opt-in. Every unattended login appears as an **[AUTO]** line in the log. See [What leaves your laptop](data-and-privacy.md).

## Next steps

- [What leaves your laptop](data-and-privacy.md)
- [Safe Mode](../settings/safe-mode.md) — defence in depth on top of credential isolation
