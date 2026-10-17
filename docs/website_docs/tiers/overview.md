# Tier overview — Free, Pro, AI

Node Control is one codebase with three gates. Free is the one to start with: 25 devices, no time limit, not a trial. Pro is the working set for a real estate. The AI edition adds the dashboard and the backend assistant on top of Pro.

Feature-level AI (summaries, the lifecycle briefing, the firewall advisor) is on Pro as well, using a provider you configure. It is not reserved for the AI edition. See [AI provider](../settings/ai.md).

## Quick comparison

| Feature | Free | Pro | AI |
|---|:---:|:---:|:---:|
| Device library | 25 max | Unlimited | Unlimited |
| Activation | Free code from nodecontrol.io | Paid licence | Paid licence |
| Multi-vendor SSH (Cisco, PA, HP, Aruba, Juniper, Arista, Dell, Extreme) | ✓ | ✓ | ✓ |
| **Library** | | | |
| Add devices manually | ✓ | ✓ | ✓ |
| Subnet scan (Library Updater) | ✓ | ✓ | ✓ |
| GitHub library sync | ✓ | ✓ | ✓ |
| **Tasks and pages** | | | |
| Find Device (single switch) | ✓ | ✓ | ✓ |
| Find Device (whole fabric, plus Meraki wireless) | — | ✓ | ✓ |
| Network Discovery | — | ✓ | ✓ |
| Layer 2 / Layer 3 / WAN topology | — | ✓ | ✓ |
| Verify Device Types | — | ✓ | ✓ |
| SSH Terminal | ✓ | ✓ | ✓ |
| File Transfer server (SFTP and SCP) | ✓ | ✓ | ✓ |
| File Transfer remote client | — | ✓ | ✓ |
| Monitor | — | ✓ | ✓ |
| Config Push | — | ✓ | ✓ |
| Packet Capture | — | ✓ | ✓ |
| Config Compliance audit and remediate | — | ✓ | ✓ |
| Firewall Rule Analyser (PAN-OS) | — | ✓ | ✓ |
| Change ISE Password | — | ✓ | ✓ |
| IPAM | — | ✓ | ✓ |
| Meraki Configurator | — | ✓ | ✓ |
| Custom scripts (Settings → Scripts) | — | ✓ | ✓ |
| **Reports** | | | |
| Inventory | ✓ | ✓ | ✓ |
| Port Utilisation, Bandwidth, VLAN Port Finder, Meraki Usage Summary | — | ✓ | ✓ |
| Security Audit, Lifecycle / EoX, Change Summary, Site Subnets | — | ✓ | ✓ |
| CSV export and report email | ✓ | ✓ | ✓ |
| **AI** | | | |
| Feature-level AI on your own provider | preview only, nothing sent | ✓ | ✓ |
| AI dashboard, chat, and backend assistant | — | — | ✓ |
| **Other** | | | |
| Custom command catalogs | ✓ | ✓ | ✓ |
| Safe Mode | ✓ | ✓ | ✓ |
| Four themes (Dark Hacker, Dark Blue, Light, High Contrast) | ✓ | ✓ | ✓ |

## Free

Free is a working copy for a small estate, not a timed demo.

### What you get

- Up to 25 devices in the library. No time limit
- Find Device against one switch at a time
- The Inventory report, with CSV export and email
- The SSH terminal
- The File Transfer server
- GitHub library sync
- Custom command catalogs, Safe Mode, and the same vendor drivers as Pro
- The Home page, the sidebar, and the Engineer command bar

### What is on Pro instead

- A library past 25 devices
- Topology maps, Discovery, and Monitor
- Reports other than Inventory
- Find Device across a site or a fabric, including Meraki wireless
- Config Push, packet capture, compliance remediation, the firewall analyser
- IPAM, the Meraki Configurator, custom scripts, Change ISE Password
- Lifecycle, Security Audit, and the rest of the report set
- Feature-level AI, once you add your own provider

The library database enforces the 25-device cap. Devices already stored are not deleted if you install Free on a machine that already has a larger library.

### How to get it

1. Visit [nodecontrol.io](https://nodecontrol.io)
2. Enter your email
3. Verify with the 6-digit code emailed to you
4. Receive your `NC-XXXX-XXXX` activation code
5. Download and install the Free build for your platform
6. Enter your code on first launch

## Pro

Pro is the tier for an engineer who needs the whole estate: maps, reports, compliance, and pushes.

### What you get beyond Free

- Unlimited devices
- L2, L3, WAN, and live Discovery
- The full report list, including Security Audit, Lifecycle, and Change Summary
- Find Device across a site or a fabric, with Meraki wireless lookup
- Verify Device Types
- Monitor
- GitHub library sync was already on Free; on Pro it is the same mechanism, with room for the larger library
- Config Push with revert, packet capture, the remote file-transfer client
- Config compliance with guided remediation
- The firewall rule analyser
- IPAM, the Meraki Configurator, and scripts under Settings → Scripts
- Change ISE Password
- Feature-level AI on your own Anthropic key or Ollama server. No Node Control backend is required for that

### How to get it

Buy from [nodecontrol.io](https://nodecontrol.io), or email [info@nodecontrol.io](mailto:info@nodecontrol.io).

Pro is licensed per user. Each licensed email can be used on as many machines as that user owns.

## AI edition

The AI edition is Pro, plus the parts that stay on this tier only:

- the AI dashboard and chat
- the backend assistant

The desktop talks to that backend over HTTP. Feature-level summaries on Pro do not use it. They use the provider in Settings → AI / LLM.

### How to get it

Contact [info@nodecontrol.io](mailto:info@nodecontrol.io).

## Upgrading

- **Free → Pro**: see [Upgrading to Pro](upgrading.md)
- **Pro → AI**: contact [info@nodecontrol.io](mailto:info@nodecontrol.io)

The library and the credentials carry forward. You do not re-enter devices.

## Both editions on one machine

Pro and Free install side by side. They are separate apps, with separate Gatekeeper and signature records. They share the data directory, so the library is the same file. That is useful when you want to see what Free will show before you hand a laptop to someone on Free.

## Which one

| You are | Pick |
|---|---|
| An engineer with a handful of devices who wants a free SSH tool and an inventory | Free |
| Managing more than 25 devices, or you need maps, compliance, or pushes | Pro |
| You want the dashboard and the backend assistant as well as Pro | AI edition |
| Trying the tool before you buy | Free, then upgrade |
