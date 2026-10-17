# IPAM

> **IPAM** is a sidebar page on **Pro** and the **AI** edition. Free does not show it.

IPAM is its own page. It tracks your subnets and how much of each was seen in use.

Columns:

- site
- VRF
- subnet
- description
- size
- live addresses
- free addresses
- percentage used

## Where the subnet list comes from

The list is the **Site Subnets** report. Run that report once and IPAM fills from it. The two cannot disagree, because IPAM does not keep a second copy of the list.

## Scan usage

**Scan usage** reads the ARP tables of the devices you select. An optional ping sweep catches hosts that are up but quiet.

Each scan is saved. Every row shows the change since the previous scan. Double-click a subnet for its history.

## How addresses are counted

- A `/31` counts as two usable addresses. A `/32` counts as one
- The same subnet in two VRFs is two rows
- A host seen by several routers is counted once
- Free addresses are addresses nothing was seen on. They are not proof the address is unallocated. A powered-off host still owns its address

## Next steps

- [Reports overview](../reports/overview.md)
- [Library overview](../library/overview.md)
