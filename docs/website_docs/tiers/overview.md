# Tier overview — Free, Pro, AI

Node Control is one codebase with three gates. Free is the one to start with: 25 devices, no time limit, not a trial. Pro is the working set for a real estate. The AI edition adds the dashboard and the backend assistant on top of Pro.

Feature-level AI (summaries and the lifecycle briefing) is on Pro as well, using a provider you configure. The Firewall Analyser **AI advisory** checkbox is the AI edition. See [AI provider](../settings/ai.md).

## Quick comparison

| Feature | Free | Pro | AI |
|---|:---:|:---:|:---:|
| Device library | 25 shown. Manual add refuses the 26th. Imports keep the first 25 | Unlimited | Unlimited |
| Licence check | Online, then a 7-day offline grace, then the app is blocked until it can check again | Paid licence | Paid licence |
| FREE VERSION badge in the status bar | ✓ | — | — |
| Multi-vendor SSH (Cisco, PA, HP, Aruba, Juniper, Arista, Dell, Extreme) | ✓ | ✓ | ✓ |
| **Sidebar** | | | |
| Home, Engineer, Reports, File Transfer | ✓ | ✓ | ✓ |
| Monitor, Discover, IPAM, Meraki Configurator, Firewall Analyser | — | ✓ | ✓ |
| Update tab | — | — | ✓ |
| AI page | — | — | ✓ |
| **Library** | | | |
| Add devices manually | ✓, until 25 | ✓ | ✓ |
| Library Updater (subnet scan, not Discover) | greyed | ✓ | ✓ |
| Workbook import | ✓, first 25 | ✓ | ✓ |
| GitHub push and pull | pull keeps the first 25, sorted by IP | ✓ | ✓, and a fallback repository |
| **Engineer tasks** | | | |
| None | ✓ | ✓ | ✓ |
| L2 Topology Builder | ✓ | ✓ | ✓ |
| Config Backup | ✓ | ✓ | ✓ |
| Save Config | ✓ | ✓ | ✓ |
| Find Device | one switch, single thread, no site or cores model | site and cores, plus Meraki wireless | site and cores, plus Meraki wireless |
| File Transfer task, Packet Capture | greyed | ✓, hidden in Safe Mode | ✓, hidden in Safe Mode |
| Every other task | greyed, tooltip Upgrade to Pro to unlock this feature | ✓ | ✓ |
| **Reports** | | | |
| Inventory | ✓ | ✓ | ✓ |
| Security Audit (PSIRT), Lifecycle and EoX, and the other reports | — | ✓ | ✓ |
| Update tab and Vuln Plan | — | — | ✓. Vuln Plan is a button on the Update tab |
| **AI** | | | |
| Payload dialog | opens, nothing is sent | opt-in, your provider | opt-in, your provider |
| A provider you can configure for sending | — | ✓ | ✓ |
| AI dashboard, chat, and backend assistant | — | — | ✓ |

## Free

Free is a working copy for a small estate, not a timed demo.

### What you get

- 25 devices in the library table. No time limit. The status bar shows **FREE VERSION**
- Sidebar: Home, Engineer, Reports, File Transfer
- Tasks that run: None, L2 Topology Builder, Config Backup, Save Config, Find Device. Find Device is one switch at a time, single thread, with no site or cores model
- The Inventory report
- Workbook import, cut to the first 25. GitHub push and pull, with your own repository and token. A pull keeps the first 25, sorted by IP. Library Updater is greyed out
- An AI payload dialog that opens and sends nothing. You cannot configure a provider for sending
- The Free code is checked online. Offline, you have 7 days. After that the app is blocked until the check succeeds

### What is on Pro instead

- A library past 25 devices, and a table that shows all of them
- Every task that Free greys out, with the tooltip **Upgrade to Pro to unlock this feature**. That includes L3 Topology Builder, Watcher of The WAN, Verify Device Types, Config Push, Config from File, Discover Variables, and config compliance
- Discover, Monitor, IPAM, the Meraki Configurator, and the Firewall Analyser. The Update tab is the AI edition, not Pro
- Reports other than Inventory
- Find Device across a site or a fabric, including Meraki wireless
- Feature-level AI on a provider you configure

A larger library left by Pro is not deleted when you install Free. The Free table shows 25 of those devices.

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

- Unlimited devices, shown in full
- L3 Topology Builder, Watcher of The WAN, Discover, and Verify Device Types. L2 Topology Builder is already on Free
- The full report list, including Security Audit (the PSIRT checks), Lifecycle and EoX, and Change Summary. Pro has no Update tab and no Vuln Plan
- Find Device across a site or a fabric, with Meraki wireless lookup
- Monitor, IPAM, the Meraki Configurator, and the Firewall Analyser
- Config Push (Cisco IOS, IOS-XE, and NX-OS; other vendors untested), the File Transfer task, Packet Capture, Config from File, and config compliance
- [Custom scripts](../settings/scripts.md) under Settings → Scripts, and Change ISE Password
- Feature-level AI on your own Anthropic key or Ollama server. No Node Control backend is required for that. The Firewall Analyser AI advisory checkbox is the AI edition
- GitHub push and pull without the 25-device cut. You still set your own repository and token

### How to get it

Buy from [nodecontrol.io](https://nodecontrol.io), or email [support@nodecontrol.io](mailto:support@nodecontrol.io).

Pro is licensed per user. Each licensed email can be used on as many machines as that user owns.

## AI edition

The AI edition is Pro, plus the parts that stay on this tier only:

- the AI dashboard and chat
- the backend assistant
- the Update tab
- **Vuln Plan**, a button on the Update tab, next to **Check PSIRT**. It works from that tab's PSIRT results

The backend runs on infrastructure you host. The desktop talks to it over HTTP. Feature-level summaries on Pro do not use it. They use the provider in Settings → AI / LLM. Pro has no Update tab and no Vuln Plan.

### How to get it

Contact [support@nodecontrol.io](mailto:support@nodecontrol.io).

## Upgrading

- **Free → Pro**: see [Upgrading to Pro](upgrading.md)
- **Pro → AI**: contact [support@nodecontrol.io](mailto:support@nodecontrol.io)

The library and the credentials carry forward. You do not re-enter devices.

## Both editions on one machine

Pro and Free install side by side. They are separate apps, with separate Gatekeeper and signature records. They share the data directory, so the library is the same file. That is useful when you want to see what Free will show before you hand a laptop to someone on Free.

## Which one

| You are | Pick |
|---|---|
| An engineer with up to 25 devices who wants an L2 map, Find Device, config backup, and an inventory | Free |
| Managing more than 25 devices, or you need L3/WAN maps, Discover, compliance, or pushes | Pro |
| You want the dashboard and the backend assistant as well as Pro | AI edition |
| Trying the tool before you buy | Free, then upgrade |
