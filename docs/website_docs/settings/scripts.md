# Custom Scripts

> On **Pro** and the **AI** edition. On Free, **Settings → Scripts** is there and a script can be registered, but every `Script: <name>` task is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**, and **Run** refuses. Safe Mode hides these tasks on every tier.

A custom script is a Python file I run as an Engineer task. It is not the [command catalog](custom-commands.md). The catalog chooses which show command a built-in task sends. A script is the program itself.

**Config Push Script** is a different entry. It appears in the task dropdown only when **Settings → Paths → Config Push Script** points at an existing file. Safe Mode hides that one too.

## Register a script

Open **Settings → Scripts** and click **Add Script**. Give it a name and the path to a `.py` file. **Remove** drops one.

**Settings → Paths** holds the Python interpreter the scripts run under. The app's own interpreter is the default.

## Run it

Each script appears in the Engineer task dropdown as `Script: <name>`. Tick the devices, pick that task, click **Run**, and choose a credential profile in **Select Credentials**. It then runs like any built-in task.

## What the script receives

The script gets its inputs through the environment only. I do not put them on the command line, and I do not write them to disk.

| Variable | What it holds |
|---|---|
| `NC_TASK` | The script's registered name |
| `NC_TARGETS` | The ticked devices, comma-separated IPs |
| `NC_TARGETS_JSON` | The same devices as a list of `{ip, hostname, device_type}` |
| `NC_SWITCH` | The first target's IP, for a script that talks to one device |
| `NC_DEVICE_TYPE` | The first target's device type |
| `NC_USER`, `NC_PASS`, `NC_SECRET` | The first credential set chosen |
| `NC_CREDS_JSON` | Every chosen set, in the order the app would try them |
| `NC_OUTPUT_DIR` | The app's reports folder. Files written there show under Home's recent reports |

The script then runs as `__main__`, the same as if it had been started by hand: same arguments, same working directory, under the interpreter from **Settings → Paths**. Output streams to the app log line by line.

## A script that already logs in itself

A script written for something else, with its own username and password hard-coded and its own device list, still runs with the credentials chosen in **Select Credentials**. Before the script starts, the launcher patches netmiko's `ConnectHandler` and paramiko's `SSHClient.connect`. Every login tries the chosen credential sets in order. The script's own login is kept only as a last resort. The log shows which account connected.

## Do not print the credentials

The credentials live only in the environment. Do not print `NC_PASS`, `NC_SECRET`, or `NC_CREDS_JSON` in the script's output. The log would then hold them.

## The example that ships: upstream_portchannel.py

I ship an example script, `upstream_portchannel.py`. It finds each ticked switch's Layer 2 uplink from the STP root port and reports whether that uplink is a port-channel, plus its members, the channel-group mode, and the allowed VLANs. It writes one workbook per run, in the layout [Config Push](../tasks/config-push.md) reads.

It is read-only. It sends only show commands. It never logs in to the upstream switch.

## An illustrative example

This is an illustration, not the script that ships. It reads `NC_TARGETS_JSON`, `NC_USER`, and `NC_PASS`, runs one show command with netmiko, and writes the text under `NC_OUTPUT_DIR`. The launcher still tries the credential sets from **Select Credentials** first, and keeps whatever this script passes only as a last resort.

```python
import json
import os
from pathlib import Path

from netmiko import ConnectHandler

targets = json.loads(os.environ["NC_TARGETS_JSON"])
device = targets[0]

conn = ConnectHandler(
    device_type=device["device_type"],
    host=device["ip"],
    username=os.environ["NC_USER"],
    password=os.environ["NC_PASS"],
)
text = conn.send_command("show version")
conn.disconnect()

out = Path(os.environ["NC_OUTPUT_DIR"]) / "show-version.txt"
out.write_text(text)
print(f"Wrote {out}")
```

## Next steps

- [Custom command catalogs](custom-commands.md)
- [Config Push](../tasks/config-push.md)
- [Safe Mode](safe-mode.md)
- [Setting up credentials](../getting-started/credentials.md)
