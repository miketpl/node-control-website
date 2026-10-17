# Change ISE Password

> On **Pro** and the **AI** edition. On Free the task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode hides it.

**Change ISE Password** changes an internal Cisco ISE network-access user. It uses ISE ERS on port 9060 (`PUT /ers/config/internaluser/<id>`).

No ISE API changes an admin account's password. A locked-out account still needs an ISE administrator.

## Settings → API Platforms

The group is **Cisco ISE (Identity Services Engine)**:

- **Enable**
- **Base URL:** placeholder `https://ise.example.com`
- **Username:**
- **Password:** with **Set Credentials**, and a status that reads **Configured** or **Not set**
- **Test Connection**
- **Password min length:** 4 to 64, default 12
- **Password requires:** checkboxes A-Z, a-z, 0-9, Special
- **Allowed specials:** default `!@#$%^&*-_=+`

This is a local mirror of the ISE policy. ISE publishes no API for that policy, and ISE has the final say.

There is no verify-SSL control. Certificate verification is off for all API clients.

## The task dialog

- **ISE username:**
- **Current password:**
- **New password:** with **Generate** and **Show** / **Hide**
- **Confirm new password:**
- **Also update saved credential:** The first item is **(do not update a saved credential)**
- A policy line
- **Change Password** / Cancel

Then a Yes/No confirmation: `Change the password for <user> now?` There is no typed word.

The task generates a random password against the policy above, and it checks the entries before it sends them.

The last profile chosen for this task is pre-selected the next time it runs.

## Login notices

When ISE (TACACS+) says at login that a password is about to expire, the terminal shows it. See [SSH Terminal](ssh-terminal.md).

## Next steps

- [Setting up credentials](../getting-started/credentials.md)
- [SSH Terminal](ssh-terminal.md)
