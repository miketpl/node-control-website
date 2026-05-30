# How credentials are stored

Node Control treats device credentials (SSH usernames, passwords, key passphrases) as the most sensitive data it holds. They're stored in the operating system's secure credential vault, never in plain text on disk.

## Storage backend by OS

| OS | Backend | Where it's accessed from |
|---|---|---|
| **macOS** | Apple Keychain (Login keychain) | Keychain Access.app |
| **Windows** | Windows Credential Manager | Control Panel → User Accounts → Credential Manager |
| **Linux** | Secret Service (GNOME Keyring, KWallet, KeePassXC-Secret-Service) | OS-specific UI |

In every case, the OS vault encrypts the secrets at rest and gates access behind the user's login credentials.

## What's in `netOps.db` vs what's in the keychain

Node Control's local SQLite database (`netOps.db`) stores:

- Device IPs, hostnames, sites, tabs, types
- Credential profile **names** and **usernames**
- A reference to the keychain entry for each profile's password

The database does **NOT** contain:

- Passwords
- Key passphrases
- API keys
- License tokens

These all live in the OS keychain.

## What gets stored in the keychain

For each credential profile:

- **Service name**: `nodecontrol-credential-<profile-id>`
- **Username**: the profile's username
- **Password**: the profile's password

For the Meraki API key:

- **Service name**: `nodecontrol-meraki-api`
- **Password**: the API key

For SSH key passphrases (when using key-based auth):

- **Service name**: `nodecontrol-key-<profile-id>`
- **Password**: the key file's passphrase

## Read-on-demand pattern

The keychain is queried each time Node Control needs to authenticate:

1. Task starts → needs to SSH to a device
2. Reads the credential profile name from the DB
3. Queries the OS keychain for that profile's password
4. Uses the password to authenticate
5. Discards the password from memory once the SSH session is established (or shortly after)

This means passwords spend the absolute minimum time in process memory.

## When you'll be prompted by the OS

The OS keychain may prompt for your user login password the first time Node Control accesses it after a system reboot or screen lock:

- **macOS**: "Node Control wants to use your confidential information stored in 'login' in your keychain"
- **Windows**: Credential Manager doesn't typically prompt — uses your login session token directly
- **Linux**: Secret Service prompts via the desktop's credential dialog

Click **Always Allow** (Mac) / **Allow** for each prompt to avoid being asked every time.

## Backup and recovery

The OS keychain is backed up:

- **macOS**: included in Time Machine, iCloud Keychain (if enabled), and the `~/Library/Keychains/` folder
- **Windows**: included in System State backups and roaming user profile sync
- **Linux**: depends on backend; most users back up `~/.local/share/keyrings/` or the chosen vault's file

If you migrate Node Control to a new machine, copy the keychain content (or re-enter credentials manually on the new box). The `netOps.db` references credentials by name, so as long as the keychain entries with matching service names exist on the new machine, everything works.

## Rotating passwords

When a device's password changes:

1. Settings → Credentials → edit the relevant profile
2. Update the password field
3. Save — the keychain entry is updated immediately

The next SSH attempt uses the new password. Old entries are overwritten, not appended.

## Revoking access

To clear all of Node Control's stored credentials:

**Mac**:
```bash
# Find all NodeControl keychain entries
security find-generic-password -s "nodecontrol-credential-" -g
# Delete each one
security delete-generic-password -s "nodecontrol-credential-<id>"
```

Or use Keychain Access GUI → search "nodecontrol" → delete entries.

**Windows**:
- Control Panel → User Accounts → Credential Manager → Windows Credentials → Generic Credentials → find entries starting with `nodecontrol-` → Remove

**Linux**:
- Open Seahorse (GNOME) / KWalletManager (KDE) → search for `nodecontrol` → delete

After clearing, the next launch of Node Control will prompt for credentials (and write fresh entries when you save them).

## What about the GitHub PATs in updater.py?

The PATs baked into `core/updater.py` (for fetching update info) and `core/license_free.py` (for license check) are NOT in the keychain — they're base64-encoded in the binary itself. This is intentional: they have read-only scope to specific repos and are part of the app's published code.

Anyone with a Node Control binary can extract these PATs. That's why we don't put sensitive data behind them — they only allow reading public-shaped data:

- Update releases (the latest available version)
- License code list (a list of `NC-XXXX-XXXX` codes — not bound to user identities in the JSON)

The PATs that have write access (used by your backend to push new license codes to the licenses repo) are NOT in any client binary. Those are server-side only.

## Audit log

Credential changes are recorded (without password content) in:

```
~/Library/Application Support/netOps/audit.log
```

Format:

```
2026-05-25T14:32:01Z [CREDENTIAL_ADDED] profile=default user=admin
2026-05-25T14:35:12Z [CREDENTIAL_UPDATED] profile=default
2026-05-25T15:01:33Z [CREDENTIAL_DELETED] profile=customer-A
```

The audit log doesn't contain credentials — only the events.

## Best practices

- **Use a different credential profile per administrative domain**: prevents one breach cascading across customers/sites
- **Use SSH keys with passphrases over passwords** where vendors support it
- **Rotate device passwords periodically** and update profiles
- **Don't share Node Control's underlying DB across users** — each user should have their own keychain for separation
- **Lock your screen** when stepping away — keychain access is gated by your login session

## Next steps

- [Safe Mode](../settings/safe-mode.md) — defence in depth on top of credential isolation
- [Audit log](audit-log.md)
