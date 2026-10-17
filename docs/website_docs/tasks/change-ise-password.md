# Change ISE Password

> On **Pro** and the **AI** edition. On Free the task is greyed out and reads **Upgrade to Pro**.

**Change ISE Password** is an Engineer task. It changes your own Cisco ISE network-access password. It does not need a separate browser session to ISE.

Your current password is required. The task cannot change an account you do not already have credentials for. A locked-out account still needs an ISE administrator.

## What else moves with the password

ISE will tell you, in plain language, whether your admin login is covered:

- An admin account created from your network-access user shares the password. It changes with it
- A standalone admin account does not share it. No API can change that password from here

Where ISE also authenticates device logins, you can nominate a saved credential. That profile is updated to the new password, so the copy in the app does not go stale the moment the change lands.

## Password policy

The task generates a random password against the policy you record in Settings, and it checks the entries before it sends them.

The credential prompt remembers the profile you accepted for this task, separate from [Config Push](config-push.md).

## Login notices

When ISE (TACACS+) says at login that a password is about to expire, the terminal shows it. See [SSH Terminal](ssh-terminal.md).

## Next steps

- [Setting up credentials](../getting-started/credentials.md)
- [SSH Terminal](ssh-terminal.md)
