# Library overview

The **library** is Node Control's list of the devices it can connect to. Everything else — topology maps, reports, Find Device, the SSH terminal — operates on devices in the library.

## What's in the library

Each entry holds:

| Field | Description |
|---|---|
| **IP address** | The management IP. Used to SSH to the device. |
| **Hostname** | What `show version` says the device is called. Auto-filled. |
| **Site code** | Two-letter or short identifier for grouping (e.g., `LON`, `NYC`, `BR1`). [Auto-detected from hostname](sites.md). |
| **Device type** | Netmiko driver name (`cisco_ios`, `hp_procurve_cli`, `paloalto_panos`, ...). Auto-detected on first connect, can be manually overridden. |
| **Tab** | Which library tab (Switches, Routers, Firewalls, SD-WAN, Wireless, Other) the device lives in. |
| **Credential profile** | Which set of SSH credentials to use. Defaults to your global default. |
| **Notes** | Free-text field for engineer comments. |

The library lives in `~/Library/Application Support/netOps/netOps.db` (Mac) or `%APPDATA%\netOps\netOps.db` (Windows) — a single SQLite database.

## The Engineer tab — main library view

The **Engineer** tab is your default library view. It's a sortable, filterable table:

- **Filter by site** — top-left dropdown narrows the table to one site
- **Search** — top-right box does live substring matching across all columns
- **Sort** — click any column header
- **Right-click a row** for:
  - Test Connection
  - SSH (opens the terminal)
  - Change Device Type
  - Edit Credentials
  - Move to tab
  - Delete

## Tabs

| Tab | Typical contents |
|---|---|
| **Switches** | Access, distribution, core switches |
| **Routers** | WAN routers, branch ISRs, ASRs, CSRs |
| **Firewalls** | Palo Alto, ASA, Fortigate, Checkpoint |
| **SD-WAN** | Velocloud, Viptela, Silver Peak edges |
| **Wireless** | Meraki MR, Cisco APs, Aruba IAP, controllers |
| **Other** | Anything that doesn't fit above |

Move devices between tabs by right-click → **Move to tab**.

## Adding devices

Three ways, in increasing automation:

1. **Manual** — right-click in the table → **Add Device** ([details](adding-devices.md))
2. **Subnet scan** — Library Updater walks an IP range and adds what it finds ([details](subnet-scan.md))
3. **GitHub library sync** — pull a shared library from a GitHub repo ([details](github-sync.md), Pro/AI only)

## Free tier device cap

Free tier limits the library to **25 devices**. Additional devices can be added but won't appear in the device picker, won't be scanned by Inventory, and won't be visible to the (single-switch) Find Device picker.

The cap is enforced at the database-read boundary — even if your library has 251 devices left over from a Pro install, the Free build only operates on 25.

To remove the cap, [upgrade to Pro](../tiers/upgrading.md).

## Sites

A **site** groups devices that share physical location, ownership, or credentials. Site codes drive a lot of Node Control's behaviour:

- The **Site filter** dropdown filters the library view
- Reports and tasks can be run "for this site only" instead of all devices
- Find Device walks each site's cores in parallel
- Topology maps draw a separate map per site

Site codes are usually 2–4 characters derived from hostname patterns. See [Site detection](sites.md) for how Node Control extracts them.

## Backing up your library

The library is a single SQLite file. To back up:

**Mac**:
```
cp ~/Library/Application\ Support/netOps/netOps.db ~/Desktop/netOps-backup.db
```

**Windows**:
```
copy "%APPDATA%\netOps\netOps.db" %USERPROFILE%\Desktop\netOps-backup.db
```

To restore, just copy it back. Node Control reads the file on launch.

Pro/AI users have a better option: [GitHub library sync](github-sync.md) keeps a remote copy and tracks every change in commit history.

## Editing devices

Double-click any field in the device table to edit it inline. Press Enter to save, Escape to cancel.

For multi-field edits, right-click → **Edit Device** opens a dialog with all fields visible.

## Deleting devices

Right-click → **Delete**. Confirms before deletion. Doesn't remove the SSH host key from your known-hosts file or the credentials from your keychain — both are reusable if you re-add the same IP.

## Library size limits

| Tier | Library size |
|---|---|
| Free | 25 devices (enforced) |
| Pro / AI | Practical limit ~10,000 devices (no enforced cap, but the Engineer tab gets slow above that) |

Beyond ~10,000, the Library Updater subnet-scan flow is slow and Find Device starts struggling — use multiple libraries (one per region/customer) instead of one giant one.

## Next steps

- [Add devices manually](adding-devices.md)
- [Subnet scan](subnet-scan.md)
- [Organise by site](sites.md)
- [GitHub library sync](github-sync.md)
