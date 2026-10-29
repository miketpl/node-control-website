# Aruba AOS-CX

AOS-CX is its own platform in 0.9.42. It is not ProCurve, and it is not Cisco. OS-Switch stays on the [Aruba](aruba.md) page, with the HP ProCurve notes.

The driver is `aruba_os`. Node Control uses SSH. It does not use the AOS-CX REST API.

## Detection

Detection reads `show version` and `show system`, including when the SSH banner has no vendor name. The device is recorded as AOS-CX.

Only AOS-CX 10.x command forms are sent. ProCurve forms are not tried. Cisco forms are not tried.

## L2 topology

On Free, Pro, and the AI edition.

The L2 Topology Builder reads the LLDP neighbour table, then runs one per-port query per neighbour for its management address.

MC-LAG legs to a VSX pair, the ISL, and LAG members are drawn and labelled the same way as Cisco port-channel members.

See [L2 topology](../tasks/topology-l2.md).

## Config Backup and Save Config

On Free, Pro, and the AI edition.

An operators-level login cannot read the config. The task tells you an admin or manager user is needed. It does not save an empty file.

The same login is required for Save Config.

## Find Device

The wired search reads the AOS-CX MAC address table and the LLDP table, with AOS-CX LAG commands. A LAG member is blocked on **Config Push** like a Cisco port-channel member. The typed **UPLINK** override still lets it through. The row says `LAG/trunk members`.

A device reached on another driver and identified as Aruba AOS-CX is reconnected on the AOS-CX driver. If that reconnect fails, the connection stops.

**Config from File** treats `Invalid input: ...` and `% Command incomplete` as a refused line, not as config applied. A line that only contains those words is not treated as a refusal.

On Free, Find Device is one switch at a time. On Pro and the AI edition it walks the site.

## Inventory

On Free, Pro, and the AI edition. Inventory reads the model, serial, version, and uptime.

## L3 topology

On Pro and the AI edition. On Free the task is greyed out.

An access switch whose only default route is in the management VRF does not use that route as its gateway. Its VLANs resolve over LLDP to the nearest switch that has an SVI for them.

A VSX pair answers with its active-gateway virtual address. The map draws one link to each member. OSPF neighbours show their area.

## Config compliance

On Pro and the AI edition.

The compliance pull needs an admin or manager login, the same as Config Backup. An operators-level login cannot read the config.

## Port Utilisation

On Pro and the AI edition.

A port with no description does not take the next line as its description. Activity comes from the rate and packet counters, so a busy uplink shows In Use. LAG, VLAN, and loopback rows are left out of the physical counts.

## VLAN Port Finder

On Pro and the AI edition.

The report fills description, port status, Last Active, and switch uptime. A LAG the switch calls a trunk is listed as a trunk.

## Bandwidth

On Pro and the AI edition.

An all-AOS-CX site reports interfaces, rates, utilisation, and key links. LAG rates are summed from the members. The default route resolves to the egress port and the LAG, as it does on Cisco.

## Lifecycle and Health Monitor

On Pro and the AI edition.

Asset Lifecycle and Health Monitor read model, serial, version, uptime, CPU, and memory.

## Site Subnets

On Pro and the AI edition.

Site Subnets reads the per-VRF interface listing. [IPAM](../tasks/ipam.md) fills from that report.

## VSF stacks

VSF members are inventoried separately and tagged with their VSF member ID.

## Next steps

- [Aruba OS-Switch and wireless](aruba.md)
- [L2 topology](../tasks/topology-l2.md)
- [L3 topology](../tasks/topology-l3.md)
