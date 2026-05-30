# Adding devices manually

The simplest way to add a single device.

## Open the Add Device dialog

In the **Engineer** tab:

- Right-click anywhere in the device table → **Add Device**
- OR click the **+ Add Device** toolbar button

## Fill in the form

| Field | Required? | Notes |
|---|---|---|
| **IP address** | Yes | The management IP. IPv4 only. |
| **Hostname** | No | Auto-filled from `show version` on first connect. |
| **Site code** | No | 2–4 character identifier. [Auto-detected from hostname](sites.md) if your hostname matches a known pattern. |
| **Tab** | Yes | Switches / Routers / Firewalls / SD-WAN / Wireless / Other |
| **Device type** | No | Leave blank for auto-detect. Manually set if you want to skip the detection step (faster first connect). |
| **Credential profile** | No | Defaults to your global default. Override per-device here. |
| **Notes** | No | Free-text — anything useful for context (e.g., "Replacement scheduled Q3"). |

Click **Save** — the device appears in the table immediately. No SSH connection happens at this point.

## Test the connection

To confirm credentials work and detect the device type:

1. Right-click the new device → **Test Connection**
2. Node Control opens an SSH session, attempts authentication, runs `show version`
3. Result appears in a popup:
   - ✅ "Connected as cisco_ios. Hostname: ACME-CORE-01"
   - ❌ Auth failure / connection error with diagnostic text

Successful tests update the **Hostname** and **Device type** columns automatically.

## Device type — auto-detect vs manual

If you leave **Device type** blank, Node Control will:

1. Look up any previously-known device type for this IP (stored locally)
2. Sniff the SSH banner for vendor hints (`SSH-2.0-HP`, `SSH-2.0-Cisco`, `OpenSSH_for_Junos` etc.)
3. Try the most likely Netmiko driver
4. If that connects, run `show version` and look at the output for vendor signatures
5. Run opportunistic probes to catch ambiguous cases — e.g., HP ProCurve accepts the `cisco_ios` driver silently, so a probe for HP-specific commands is run

Pick a specific driver from the dropdown only if:

- You know the device type and want to skip the detection
- A previous detection got it wrong and you want to override permanently
- Detection is failing and you want to force a specific driver

When you manually set a device type, the **Device type locked** flag is set in the database — auto-detect can never overwrite it. Right-click → **Unlock Device Type** to re-enable auto-detect.

## Common driver names

| Vendor / OS | Driver |
|---|---|
| Cisco IOS / IOS-XE | `cisco_ios` |
| Cisco NX-OS | `cisco_nxos` |
| Cisco ASA | `cisco_asa` |
| HP ProCurve | `hp_procurve_cli` (alias of `aruba_osswitch`) |
| Aruba AOS-CX | `aruba_os` |
| Palo Alto PAN-OS | `paloalto_panos` |
| Juniper Junos | `juniper_junos` |
| Arista EOS | `arista_eos` |
| Dell OS6 | `dell_os6` |
| Dell OS10 | `dell_os10` |
| Extreme EXOS | `extreme_exos` |
| Extreme VSP | `extreme_vsp` |
| Cisco Meraki (via Dashboard API, not SSH) | n/a |

A full list of supported drivers is available in **Settings → Device Types → View driver list**.

## Bulk-adding from a list

If you have a list of IPs in a spreadsheet:

1. Save the IPs as a CSV with columns: `ip, hostname, tab, site_code`
2. **Tools → Import Library → From CSV**
3. Pick the file → preview → **Import**

The CSV columns are mapped to device fields. Missing columns are left blank.

## Bulk-adding from a subnet

If you don't have a list — just a known subnet range — use [Subnet scan](subnet-scan.md) instead. It pings every IP in the range and auto-adds responding devices.

## Editing a device after adding

Double-click any cell in the table to edit inline. Or right-click → **Edit Device** for a full-field dialog.

## Right-click menu — full options

| Option | What it does |
|---|---|
| Test Connection | SSH in, run a basic command, report result |
| SSH | Open the interactive terminal to this device |
| Edit Device | Full-field edit dialog |
| Change Device Type | Open a dropdown to manually set the Netmiko driver |
| Lock / Unlock Device Type | Toggle whether auto-detect can change the type |
| Credentials | Override the credential profile for this one device |
| Move to tab | Reassign which library tab it appears in |
| Refresh hostname | Re-run `show version` and update the hostname field |
| Notes | Quick edit of the notes field |
| Delete | Remove from library (with confirmation) |

## Next steps

- [Subnet scan for bulk add](subnet-scan.md)
- [Organise devices by site](sites.md)
- [Test the connection by running a topology](../tasks/topology-l2.md)
