# Node Control Documentation

Node Control runs on your laptop and talks to switches, routers, and firewalls over SSH and vendor APIs. These pages are the how-to: install it, add devices, and draw an L2 map.

Free is 25 devices, with no time limit. It is not a trial.

## New to Node Control?

- [Installing on macOS](getting-started/installation-mac.md)
- [Installing on Windows](getting-started/installation-windows.md)
- [First launch and activation](getting-started/first-launch-activation.md)
- [Your licence and moving between computers](getting-started/licence.md)
- [Updating Node Control](getting-started/updating.md)
- [Where things are](getting-started/navigation.md) — sidebar, Home, the Engineer command bar
- [Adding your first device](getting-started/adding-first-device.md)
- [Setting up credentials](getting-started/credentials.md)

## Library

- [Library overview](library/overview.md)
- [Adding devices manually](library/adding-devices.md)
- [Discovering devices with subnet scan](library/subnet-scan.md)
- [Organising devices by site](library/sites.md)
- [Sharing libraries via GitHub](library/github-sync.md)

## Tasks

- [L2 Topology Builder](tasks/topology-l2.md) — on Free
- [L3 Topology Builder](tasks/topology-l3.md) — Pro and AI
- [Watcher of The WAN](tasks/topology-wan.md) — Pro and AI
- [Config Backup and Save Config](tasks/config-backup.md) — on Free
- [Config Compliance](tasks/config-compliance.md) — Pro and AI
- [Config from File](tasks/config-from-file.md) — Pro and AI; hidden in Safe Mode
- [Discover Variables](tasks/discover-variables.md) — Pro and AI; inventory enrichment
- [Discover](tasks/discovery.md) — sidebar page, Pro and AI; not on Free
- [Find Device](tasks/find-device.md) — on Free, one switch at a time
- [Verify Device Types](tasks/verify-device-types.md) — Pro and AI
- [SSH Terminal](tasks/ssh-terminal.md)
- [Serial console](tasks/serial-console.md) — on the Engineer tab. Free and Pro; hidden in Safe Mode
- [Local network terminal](tasks/local-terminal.md) — on the Engineer tab. Free and Pro; visible in Safe Mode
- [Monitor](tasks/monitor.md) — Pro and AI; not on Free
- [Config Push](tasks/config-push.md) — Pro and AI. Commands to ports from a file. Full support is Cisco IOS, IOS-XE, and NX-OS. On Juniper Junos, revert restores the snapshot taken before the push; if that snapshot could not be taken, the revert is marked as manual. Every other vendor, Palo Alto included, gets a template only, with no reliable revert. On Palo Alto, [Config from File](tasks/config-from-file.md) discards its own uncommitted changes when its commit is skipped or refused. Safe Mode removes Config Push
- [Packet Capture](tasks/packet-capture.md) — Pro and AI; hidden in Safe Mode
- [Firewall Rule Analyser](tasks/firewall-analyser.md) — Pro and AI; not on Free
- [File Transfer](tasks/file-transfer.md) — the page is on Free. The task is Pro
- [IPAM](tasks/ipam.md) — Pro and AI; not on Free
- [Meraki Configurator](tasks/meraki-configurator.md) — Pro and AI; not on Free

## Reports

- [Reports overview](reports/overview.md)
- [Port Utilisation](reports/port-utilisation.md)
- [Bandwidth](reports/bandwidth.md)
- [VLAN Port Finder](reports/vlan-port-finder.md)
- [Inventory](reports/inventory.md) — the report that runs on Free
- [Meraki Usage Summary](reports/meraki-usage-summary.md)
- [Security Audit](reports/security-audit.md)
- [Lifecycle and EoX](reports/lifecycle.md)
- [Change Summary](reports/change-summary.md)

## Vendors

- [Vendor overview](vendors/overview.md)
- [Cisco IOS / IOS-XE / NX-OS](vendors/cisco.md)
- [Palo Alto PAN-OS](vendors/palo-alto.md)
- [HP ProCurve](vendors/hp-procurve.md)
- [Aruba (CX, OS-Switch)](vendors/aruba.md)
- [Aruba AOS-CX](vendors/aruba-aos-cx.md)
- [Juniper Junos](vendors/juniper.md)
- [Arista EOS](vendors/arista.md)
- [Dell OS6 / OS10](vendors/dell.md)
- [Extreme EXOS / VSP](vendors/extreme.md)
- [Cisco Meraki](vendors/meraki.md)

## Settings

- [Settings overview](settings/overview.md)
- [Site detection rules](settings/site-detection.md)
- [Custom command catalogs](settings/custom-commands.md)
- [Custom scripts](settings/scripts.md) — Pro and the AI edition. On Free the task is greyed
- [Safe Mode](settings/safe-mode.md)
- [AI provider](settings/ai.md)
- [AI on Professional](settings/ai-llm.md)
- [AI features overview](settings/ai-features.md)

## Security

- [How credentials are stored](security/credential-storage.md)
- [What leaves your laptop](security/data-and-privacy.md)
- [Safe Mode and the command allowlist](security/safe-mode.md)
- [Audit log](security/audit-log.md)

## Troubleshooting

- [Common issues](troubleshooting/overview.md)
- [SSH connection problems](troubleshooting/ssh-connection-issues.md)
- [Device type misdetection](troubleshooting/device-type-detection.md)
- [Reading the crash log](troubleshooting/crash-logs.md)
- [Update problems](troubleshooting/update-issues.md)

## Tiers

- [Free, Pro, and AI](tiers/overview.md) — Free is 25 devices, no time limit
- [Upgrading from Free to Pro](tiers/upgrading.md)

## Getting help

- Email: support@nodecontrol.io
- Website: [nodecontrol.io](https://nodecontrol.io)
- Release notes: **Help → Check for Updates...** inside the app
