# Config Push

> Available on **Pro** and the **AI** edition.

**Config Push** pushes a per-port template: interface configuration, captures, ACLs, or clears. It used to be called **Interface Config Push**. The old name still runs.

This is not the [Meraki Configurator](meraki-configurator.md), and it is not [Config Compliance](config-compliance.md). Compliance checks a hardening baseline. Config Push targets ports.

## Choose the ports

The usual source is a [VLAN Port Finder](../reports/vlan-port-finder.md) export. You can target:

- ports that have never been active
- ports inactive for at least N hours, which includes never-active ports

Ports whose activity is unknown are always excluded. Nothing is pushed without evidence.

VLAN Port Finder records each switch's uptime. The preview shows that uptime beside **Last Active**. If your inactivity threshold is longer than the switch's uptime, you get a warning first. "Never active" only means never since the last reboot.

If no ports match, the message counts how many were excluded, and why.

The safety layers stay in place: uplink detection, the interface blacklist, a tick per interface, and a confirmation before anything is sent. In Prepare Config, excluded interfaces are a count plus a button that lists them in full, grouped by reason, so a large selection does not push the button off the screen.

## What you can send

- A config template
- **Admin shutdown**
- **Default interface**, which wipes the port back to defaults
- Exec-mode commands, for per-interface `show` and `clear`. Configuration mode rejects those

### Placeholders

A placeholder can carry filters. The short and safe filters turn `GigabitEthernet1/0/1` into `Gi1_0_1`, which fits a capture name, a filename, or an ACL name where the raw interface name would be rejected.

Other placeholders supply the port's sequence number on that device, and the date and time, for filenames. A misspelt or unknown placeholder is shown under the template editor. It is not sent to the device as literal text.

### Uplinks

A typed `UPLINK` override, and only in trunk mode, is the one deliberate way past the uplink safety layers. It lets a push reach port-channels and their members. Vlan, Loopback, Management, Tunnel, and other virtual interfaces stay blocked no matter what you tick.

## Run

Pick **Config Push** in the Engineer **Task** group and click **Run**. The credential prompt remembers the profile you accepted for this task, separate from other tasks.

## Revert

Every push stores a pre-change snapshot of each interface. **Revert a previous push** lets you pick the push, tick the interfaces to restore, review and edit the commands, and confirm by typing `REVERT`. Each selected interface is wiped back to defaults and its original config is replayed.

Pushes made before this snapshot behaviour have nothing to restore. They cannot be auto-reverted.

## Next steps

- [Packet Capture](packet-capture.md)
- [VLAN Port Finder](../reports/vlan-port-finder.md)
- [Change ISE Password](change-ise-password.md) — the credential prompt remembers a different profile for that task
