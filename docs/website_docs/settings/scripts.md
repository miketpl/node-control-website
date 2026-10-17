# Scripts

> Available on **Pro** and the **AI** edition.

A script registered under **Settings → Scripts** runs like a built-in task. It shows in the Engineer task dropdown as `Script: <name>`. It receives the devices you ticked in the library, and it prompts for a credential profile the same way the built-in tasks do.

**Config Push Script** is separate. It appears in the task dropdown only when **Settings → Paths → Config Push Script** points at an existing file. Safe Mode hides Config Push Script.

This is not the [command catalog](custom-commands.md). The catalog picks which show command a built-in capability runs. A script is your own Python program.

## Credentials

Credentials are handed to the script through its environment. They are not placed on the command line, and they are not written to disk.

Any Python script gets those credentials, including one that already has a username and password written into it. Before the script runs, netmiko and paramiko logins are redirected to try your chosen credential sets in order. The script's own login is kept only as a last resort. The log shows which account connected.

## Output

The script is told the app's reports folder. Its output appears there. Lines reach the log as they are printed, not in one block at the end.

## Example: upstream_portchannel.py

The example script finds each ticked switch's Layer 2 uplink from the STP root port. It reports whether that uplink is a port-channel, and it lists the members, the channel-group mode, and the allowed VLANs. It writes one workbook per run, in the layout Config Push reads.

It is read-only. Only show commands are sent. It does not log in to the upstream switch.

## Next steps

- [Custom command catalogs](custom-commands.md)
- [Config Push](../tasks/config-push.md)
- [Setting up credentials](../getting-started/credentials.md)
