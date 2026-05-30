# Adding your first device

Once Node Control is launched and activated, the first thing you'll want to do is add a device to your library. The library is the list of switches, firewalls, routers, and APs that Node Control can connect to.

## Two ways to add devices

1. **Manually** — enter one device's IP and metadata
2. **Subnet scan** — let Node Control ping-sweep a range, attempt SSH, and auto-add what it finds

Manual is simplest for a first device; subnet scan is how you'd populate a real network of dozens or hundreds.

## Manual: add one device

1. In the **Engineer** tab (the main library view), click **+ Add Device** (or right-click in the device table → **Add Device**)
2. Fill in:
   - **IP address** — required (e.g., `10.1.1.1`)
   - **Hostname** — optional; the app will fill this from `show version` once it connects
   - **Site code** — optional; Node Control can auto-detect this from hostname patterns ([see Sites](../library/sites.md))
   - **Tab** — which library tab to put it in: Switches, Routers, Firewalls, SD-WAN, Wireless, etc.
   - **Device type** — leave blank for auto-detect, or pick a specific Netmiko driver (cisco_ios, hp_procurve_cli, paloalto_panos, etc.)
3. Click **Save**

The device appears in your library. It hasn't been *connected to* yet — only listed.

## Test the connection

To make sure SSH credentials work:

1. Right-click the device → **Test Connection**
2. Node Control opens an SSH session, runs a basic command (`show version` or equivalent), and reports the result
3. If successful, the **Hostname** column populates from the device's actual hostname
4. If failed, see [Troubleshooting SSH connection issues](../troubleshooting/ssh-connection-issues.md)

## Set up credentials before connecting

Node Control needs SSH credentials to connect to your devices. You can:

- Use a global default username/password ([see Credentials](credentials.md))
- Use per-device credentials
- Use multiple credential profiles for different sites

Without credentials configured, **Test Connection** will fail with an auth error. Set those up first — see [Setting up credentials](credentials.md).

## Subnet scan (faster for many devices)

If you have a known management subnet (e.g., `10.1.1.0/24` or `192.168.10.0/24`):

1. Click **Library Updater** in the toolbar (or the **Tools** menu)
2. Enter the subnet — `10.1.1.0/24`
3. Pick the **Tab** for discovered devices to land in
4. Click **Start Scan**

Node Control will:

- Ping every host in the range (using `fping` if installed, otherwise Python ping)
- For each ping-alive host, attempt SSH using your configured credentials
- Run `show version` (or vendor-equivalent) to identify the device type and hostname
- Add it to the library with all fields auto-filled
- Detect the site code from the hostname pattern (if Site Detection is configured)

Typical timing: a /24 with ~30 devices takes 2–5 minutes.

See [Library Updater details](../library/subnet-scan.md) for advanced options (which Netmiko driver to try first, parallelism, retry behaviour).

## Free tier device limit

If you're on the Free tier, your library is capped at **25 devices**. The library will still accept additions beyond 25, but tools that read from the library — Find Device, Inventory report, Reports tab — only operate on the first 25 (sorted by numeric IP).

To remove this cap, [upgrade to Pro](../tiers/overview.md).

## Library tabs

Devices are organised into tabs based on their role:

| Tab | Typical contents |
|---|---|
| **Switches** | Access switches, distribution switches, core switches |
| **Routers** | WAN edge routers, branch routers, ISR / ASR / CSR |
| **Firewalls** | Palo Alto, Cisco ASA, Fortigate, Checkpoint |
| **SD-WAN** | Velocloud, Viptela, Silver Peak edges |
| **Wireless** | Access points (Meraki MR, Cisco APs, Aruba IAP) and controllers |
| **Other** | Anything that doesn't fit above |

Devices can be moved between tabs by right-click → **Move to tab**.

## Next steps

- [Setting up credentials](credentials.md)
- [Library overview](../library/overview.md)
- Run your first task: [Layer 2 topology](../tasks/topology-l2.md)
