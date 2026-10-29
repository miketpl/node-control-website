# Juniper Junos

Juniper switches, routers, and SRX firewalls are supported via the standard Junos CLI.

## Driver

- Netmiko: `juniper_junos`

## What works

- L2 topology with LLDP (Juniper doesn't do CDP)
- L3 topology with OSPF + BGP
- Port Utilisation
- Bandwidth and Path Bandwidth. Interfaces and routes are read with Junos parsing
- VLAN Port Finder
- Find Device (full BFS walk + port disable)
- Inventory (chassis, modules, virtual chassis members)
- Monitor (CPU, memory, alarms)

## Detection

`show version` output identifies Junos cleanly. SSH banner often `SSH-2.0-OpenSSH_for_Junos`.

## Virtual Chassis (VC)

Juniper EX-series VC stacks appear as one logical device with multiple members. Each member is inventoried with its serial.

## VRFs and routing-instances

Junos supports multiple routing-instances. Node Control walks all instances for L3 topology and unions the results, similar to the Palo Alto LR handling.

## SRX firewalls

Junos-based SRX firewalls:

- Detected as `juniper_junos`
- Inventory works
- L3 topology covers OSPF + BGP within the chosen routing-instances
- IPSec tunnels (used heavily on SRX) are covered in the WAN topology task

## Common gotchas

| Issue | Why | Fix |
|---|---|---|
| `show interfaces` is verbose | Junos `extensive` mode is default | The catalog uses `show interfaces brief` for most reports, `extensive` only when full data needed |
| LLDP-only neighbours | Junos doesn't support CDP | Expected — neighbours appear via LLDP |
| Stack members not enumerated | VC didn't detect as a stack | `show virtual-chassis status` should appear in Inventory — check raw output |

## Configuration mode

Junos has a commit-based config model with `commit` / `commit and-quit`. The write path I can confirm here is Find Device port shut, which uses a single operational-mode line (`set interfaces <port> disable`). Config compliance remediation is Cisco IOS, IOS-XE, and NX-OS only.

## Limitations

- **Mist** (Juniper's cloud wireless): not currently supported — like Meraki, would require API integration. On the roadmap.
- **EVPN-VXLAN underlay**: visible in L3 topology as BGP peers, but the VXLAN overlay isn't separately rendered
- **Junos PyEZ**: Node Control uses SSH directly; PyEZ-based integration isn't planned

A device reached on another driver and identified as Juniper Junos is reconnected on the Junos driver. If that reconnect fails, the connection stops.

**Config Push** loads the lines in `configure private` and runs `commit check` and `commit and-quit`, rolling back on any error. Each interface is snapshotted before the push. Revert restores that snapshot. If the snapshot could not be taken, the revert is marked as manual. An `aeN` LAG member is blocked like a Cisco port-channel member, with the same **UPLINK** override.

Discovery saves the host name without the `user@` prefix. Find Device skips Junos with a clear reason until the output format is confirmed. Asset Lifecycle reports the model and serial.

## Next steps

- [Topology L3](../tasks/topology-l3.md) — for OSPF/BGP detail
- [Find Device](../tasks/find-device.md) — works with Junos VRF probes
