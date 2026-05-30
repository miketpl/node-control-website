# SSH connection problems

When Node Control can't SSH to a device, the cause is one of:

- Network (can't reach the IP at all)
- SSH service (TCP/22 not open or wrong port)
- Authentication (username, password, or key wrong)
- Vendor-specific (algorithm mismatch, host key change, banner timeout)

Work through these in order — most issues are network or auth.

## Step 1 — Confirm reachability

From a separate terminal (not Node Control):

```bash
ping <device-ip>
```

If ping fails: it's a routing / firewall / device-down issue. Not a Node Control problem. Fix the network first.

If ping works but the next step fails: continue.

## Step 2 — Confirm SSH service is listening

```bash
# Mac/Linux
nc -zv <device-ip> 22

# Windows PowerShell
Test-NetConnection -ComputerName <device-ip> -Port 22
```

Expected: "Connection succeeded" or similar.

If TCP/22 is closed: SSH isn't enabled on the device, or it's running on a non-standard port. Check the device's SSH config.

For non-standard ports:

- In Node Control → Engineer tab → right-click device → **Edit Device** → set SSH port
- Or update the credential profile's port setting

## Step 3 — Confirm authentication

Try SSH from a separate terminal with the exact same credentials Node Control would use:

```bash
ssh <username>@<device-ip>
```

Type the password when prompted. Three outcomes:

| Outcome | Meaning | Fix |
|---|---|---|
| Login succeeds, you get a CLI prompt | Credentials are correct; Node Control should also work | Re-test in Node Control; if it still fails, it's a Node Control config issue |
| "Permission denied" | Wrong username, password, or key | Check the credential profile in Settings → Credentials |
| Host key verification prompts | First connect to this device | Type `yes` to accept; future connects skip the prompt |
| "Algorithm mismatch" | Old device, modern SSH client | Add older algorithms — see below |
| Connection hangs after banner | Device's SSH service is slow / overloaded | Wait or restart the device |

## Step 4 — Common Node Control fixes

### Credential profile wrong

The number-one cause. Open Settings → Credentials → confirm:

- Profile **username** field
- Profile **password** field (re-enter, save)
- Profile is set as **Default** OR is selected for this device

### Per-device credential override

If you previously set a different profile for this device:

- Engineer tab → right-click → **Credentials** → check which profile is selected
- Reset to default if the per-device override is wrong

### Device type wrong → wrong commands → "auth failed"

If the detected device type is wrong, Node Control sends commands the device doesn't understand → may report "auth failed" misleadingly. Verify the device type:

- Right-click → **Test Connection** → result message includes the detected type
- If wrong → manually set + lock the correct type

## Step 5 — Algorithm and version mismatches

Old devices may not support modern SSH crypto. Node Control supports legacy algorithms by default but you can extend further:

### Allow legacy algorithms

Settings → Credentials → **Advanced** → check:

- **Enable legacy SSH algorithms** (CBC ciphers, SHA1 KEX, DSS keys)
- Specific algorithms can be listed if you need particular ones

### Vendor-specific symptoms

| Vendor | Common SSH issue | Fix |
|---|---|---|
| Cisco IOS classic (12.x) | Only supports older ciphers | Enable legacy algorithms |
| HP ProCurve (older firmware) | Slow banner exchange | Increase SSH connect timeout in Settings → SSH |
| Palo Alto | Detects as cisco_ios if prompt looks similar | Manually set device type, lock |
| Juniper SRX | May reject if you connect too fast | Increase SSH connect delay |

## Step 6 — Connection timeouts

Default timeouts:

- SSH connect: 10 seconds
- Per-command read: 45 seconds (bounded — prevents one slow switch from hanging the BFS)
- Session keepalive: 30 seconds

For devices on slow links (WAN, satellite):

- Settings → SSH → increase connect timeout to 30 or 60 seconds
- Per-command timeout can be increased per task in advanced settings

## Step 7 — Host key changed

If a device's SSH host key changes (firmware upgrade, replacement, MITM):

- Node Control will refuse to connect with "Host key verification failed"
- Confirm the change is legitimate (replaced hardware, expected firmware update)
- Delete the cached host key:
  - Mac/Linux: `ssh-keygen -R <device-ip>`
  - Or delete the line in `~/.ssh/known_hosts` containing that IP
- Re-test — Node Control accepts the new key on next connect

## Step 8 — Two-credential fallback

If you're migrating credentials (old password being rotated to new):

- Settings → Credentials → set up TWO profiles (old and new)
- Per-device: assign both — Node Control tries old first, falls back to new on auth fail

When the rotation is done, remove the old profile.

## Step 9 — Enable debug logging

Last resort: capture exactly what's happening:

- Settings → Advanced → enable **Debug logging**
- Restart Node Control
- Reproduce the failed connection
- The log captures the full SSH dialogue:

```bash
~/Library/Application Support/netOps/debug.log
%APPDATA%\netOps\debug.log
```

Attach this log to a support ticket — we can usually pinpoint the issue within hours.

## Step 10 — Per-credential SSH keys

If using SSH key auth:

- Confirm the key file exists and is readable: `cat ~/.ssh/id_rsa`
- Confirm the credential profile **SSH key path** points to the right file (absolute path, not `~`)
- Confirm the passphrase (if any) is set in the profile's Password field
- Test the key works outside Node Control: `ssh -i ~/.ssh/id_rsa <user>@<device-ip>`

## Common error messages

| Error | Cause |
|---|---|
| "Authentication failed" | Bad credentials |
| "Connection refused" | SSH not running on device |
| "Connection timed out" | Network unreachable |
| "Host key verification failed" | Cached host key doesn't match current device |
| "No matching key exchange method" | Algorithm mismatch — enable legacy |
| "Bad packet length" | Usually network corruption / MTU mismatch |
| "Permission denied (publickey)" | Key auth attempted but key wrong or device doesn't trust it |
| "Operation timed out (no data on socket)" | Device SSH service hung |

## Next steps

- [Device type misdetection](device-type-detection.md) — sometimes manifests as auth failures
- [Credential storage](../security/credential-storage.md)
- [Settings → Credentials](../getting-started/credentials.md)
