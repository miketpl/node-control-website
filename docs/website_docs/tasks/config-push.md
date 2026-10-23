# Config Push

> On **Pro** and the **AI** edition. On Free the task is listed but greyed, with an upgrade prompt. Safe Mode removes it.

**Config Push** sends commands to a list of switch ports from a file. You get a preview, safety exclusions, and a revert. It was called Interface Config Push until 0.9.39.

## What it does

- **Config template** is the default. Config mode (`conf t`) applies the template to every matched interface. There is no global mode.
- The **Exec mode** checkbox runs show, clear, and cable-test commands per port, without entering config mode.
- **Admin shutdown**.
- **Default interface**, on Cisco IOS, IOS-XE, and NX-OS only.

## Input file

The file is `.xlsx` or `.json`. CSV is not accepted.

Columns are matched by name. Only Port is mandatory.

| Column | Required |
|---|---|
| Port/Interface | Yes |
| Switch/Hostname | No |
| IP | No |
| Mode | No |
| VLAN | No |
| Voice VLAN | No |
| MAC | No |
| Status | No |
| Last Active | No |
| Switch Uptime | No |

A [VLAN Port Finder](../reports/vlan-port-finder.md) export is the native source. Any file with the same columns works.

Rows are grouped per switch, with the ports sorted. Each switch is one block.

## Filters

- Target VLANs, as lists or ranges.
- Port mode: access, access+voice, trunk, or voice.
- Activity: any, never active, or inactive for at least N hours. N is from 1 to 8760. The default is 720. Unknown activity is always excluded.
- **Include admin-down / disabled ports**.

Config Push targets live ports by default. Ports that are down, notconnect, disabled, err-disabled, or admin down are excluded unless **Include admin-down / disabled ports** is ticked, or an activity filter is on. There is no separate up-only option.

If the switch uptime is less than the threshold, you get a warning.

## Placeholders

| Placeholder |
|---|
| `{{interface}}` |
| `{{vlan}}` |
| `{{voice_vlan}}` |
| `{{hostname}}` |
| `{{ip}}` |
| `{{n}}` |
| `{{date}}` |
| `{{time}}` |

Filters are `short`, `safe`, `num`, `lower`, and `upper`. Chain them with `|`. `{{interface|short|safe}}` is an example. A misspelt placeholder is flagged red.

Templates can be loaded from a file.

## Safety

A hard blacklist blocks Loopback, Vlan SVIs, Management, Tunnel, NVE, Port-channel, Null, and BDI.

Uplink detection skips a port with more than 2 VLANs. Trunk mode has a checkbox override for that skip.

Port-channel members are detected live and block that switch. The only override is a trunk-mode option armed by typing `UPLINK`. It never unblocks SVIs, loopbacks, management, or tunnels.

## Preview and run

The preview is on by default. There is no separate dry run. The preview is the dry run.

It shows the switches and interfaces, with ticks, editable config per switch, last-active times, and exclusions by reason. A final Yes/No then shows the counts.

How many switches run at once follows the **Conns** spinner on the main Engineer page. That spinner is 1 to 50, and the default is 6. Config Push caps it at 4, so the run is `min(4, Conns)` switches at once, on separate SSH sessions. Settings **Default Thread Count** does not drive it.

A result is OK, WARN, BLOCKED, SKIP, or FAIL. Output is scanned for vendor errors and flagged WARN.

Saving is opt-in and off by default. It uses the vendor save command.

## Revert

The running config of each target interface is snapshotted before the push. The last 20 pushes are kept.

**Revert a previous push** lets you pick a run, tick devices and interfaces, see and edit the restore commands, and confirm by typing `REVERT`. A revert saves by default.

Only interface config can be reverted.

- Exec pushes cannot be reverted.
- A change outside the interface block cannot be reverted.
- A push from before 0.9.37 has no snapshot.

Revert warns about drift. It does not detect drift.

## Vendors and edition

Sending is vendor-generic, through Netmiko. Save is mapped for Cisco, Arista, Aruba, Juniper, Palo Alto, Dell, and Extreme.

Full support is Cisco IOS, IOS-XE, and NX-OS only. On any other vendor the task can send a template, and nothing else: no activity targeting, and no reliable revert.

The task is on Pro and the AI edition. On Free it is listed but greyed, with an upgrade prompt.

## Safe Mode

Safe Mode removes Config Push.

## Config from File

[Config from File](config-from-file.md) is a separate task. It sends the lines in a file verbatim. There are no placeholders. Global-only config belongs there.

## What changed

- 0.9.36: activity targeting, Admin shutdown, and Default interface.
- 0.9.37: revert.
- 0.9.38: Exec mode.
- 0.9.39: the task was renamed.
- 0.9.40: the UPLINK override.

## Next steps

- [Config from File](config-from-file.md)
- [VLAN Port Finder](../reports/vlan-port-finder.md)
- [Safe Mode](../settings/safe-mode.md)
