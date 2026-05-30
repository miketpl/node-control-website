# Tier overview — Free, Pro, AI

Node Control comes in three tiers. Same codebase, different feature gates. Pick the tier that matches what you're trying to do.

## Quick comparison

| Feature | Free | Pro | AI |
|---|:---:|:---:|:---:|
| Device library | 25 max | Unlimited | Unlimited |
| Activation | Free code from nodecontrol.io | Paid licence | Paid licence + Azure backend |
| Multi-vendor SSH (Cisco, PA, HP, Aruba, Juniper, Arista, Dell, Extreme) | ✓ | ✓ | ✓ |
| **Library** | | | |
| Add devices manually | ✓ | ✓ | ✓ |
| Subnet scan (Library Updater) | ✓ | ✓ | ✓ |
| GitHub library sync | — | ✓ | ✓ |
| **Tasks** | | | |
| Find Device (single switch) | ✓ | ✓ | ✓ |
| Find Device (whole fabric, BFS across cores) | — | ✓ | ✓ |
| Network Discovery (live topology walk) | — | ✓ | ✓ |
| Layer 2 topology map | — | ✓ | ✓ |
| Layer 3 topology map | — | ✓ | ✓ |
| WAN topology map | — | ✓ | ✓ |
| Verify Device Types | — | ✓ | ✓ |
| SSH Terminal (interactive) | ✓ | ✓ | ✓ |
| Monitor tab (passive watch) | — | ✓ | ✓ |
| **Reports** | | | |
| Inventory | ✓ | ✓ | ✓ |
| Port Utilisation | — | ✓ | ✓ |
| Bandwidth | — | ✓ | ✓ |
| VLAN Port Finder | — | ✓ | ✓ |
| Meraki Usage Summary | — | ✓ | ✓ |
| **AI** | | | |
| AI Dashboard chat | — | — | ✓ |
| Natural-language network queries | — | — | ✓ |
| Automated config analysis | — | — | ✓ |
| **Other** | | | |
| Custom command catalogs | ✓ | ✓ | ✓ |
| Safe Mode (read-only command allowlist) | ✓ | ✓ | ✓ |
| Auto-updates | ✓ | ✓ | ✓ |

## Free

Designed for small-shop engineers managing a handful of devices. Free is fully functional for inventory and ad-hoc lookups, with deliberate limits to differentiate from Pro.

### What you get

- Up to 25 devices in your library
- Find Device against one switch at a time (you pick the seed switch when running)
- Full Inventory report
- Interactive SSH terminal to any device in the library
- Custom command catalogs
- All the same vendor support as Pro

### What's locked

- More than 25 devices in the library (additions are accepted but tools only see the first 25, sorted by IP)
- Topology maps (L2, L3, WAN, Discovery)
- Reports other than Inventory
- Find Device across multiple switches simultaneously
- Monitor tab
- GitHub library sync

### How to get it

1. Visit [nodecontrol.io](https://nodecontrol.io)
2. Enter your email
3. Verify with the 6-digit code emailed to you
4. Receive your `NC-XXXX-XXXX` activation code
5. Download and install the Free DMG or Setup.exe
6. Enter your code on first launch

Free is forever — no time limit, no payment required.

## Pro

The standard tier for professional network engineers and managed-service providers.

### What you get beyond Free

- Unlimited devices in the library
- Full topology maps — L2, L3, WAN, and live Discovery
- All reports — Port Utilisation, Bandwidth, VLAN Port Finder, Meraki Usage Summary
- Find Device across an entire site or fabric, with cross-core pruning and Meraki wireless lookup
- Verify Device Types worker for keeping the library accurate
- Monitor tab for passive watch of one or more devices
- GitHub library sync — share device library across team members with separate read-only and push tokens
- Priority email support

### How to get it

Contact us at [info@nodecontrol.io](mailto:info@nodecontrol.io) or buy directly from [nodecontrol.io/pro](https://nodecontrol.io).

Pro is licensed per-user. Each licensed email can be used on as many machines as the user owns (laptop, desktop, lab).

## AI

For teams who want LLM-assisted network operations. Includes everything in Pro plus an AI dashboard.

### What you get beyond Pro

- **AI chat** — ask natural-language questions about your network ("which switches have STP issues?", "show me ports with high error counts")
- **Automated config analysis** — AI flags risky configs, suggests cleanups, identifies compliance gaps
- **Live SSH proxy** — AI agent can drive SSH sessions on your behalf to answer multi-step questions
- Backend service running on a customer-deployed Azure / NVIDIA DGX appliance (you control where your data goes)

### How to get it

AI is sold as an annual subscription including the backend infrastructure. Contact [info@nodecontrol.io](mailto:info@nodecontrol.io) for a demo and pricing.

## Upgrading

- **Free → Pro**: see [Upgrading to Pro](upgrading.md)
- **Pro → AI**: contact sales

Your library and credentials carry forward through any upgrade — no re-entry needed.

## Cross-tier coexistence on the same machine

Pro and Free can both be installed on the same Mac or Windows machine simultaneously. They appear as separate apps in Applications / Start Menu and have separate Gatekeeper / SmartScreen registrations. Their data directories are shared, so you'll see the same library in both — useful if you want to confirm "this device is visible to Free" before recommending it to a Free user.

## Choosing the right tier

| You are | Pick |
|---|---|
| A network engineer with a handful of devices, want a free SSH multi-tool | Free |
| Managing 25+ devices, want topology maps and reports | Pro |
| Running a managed-service practice, want AI-assisted analysis | AI |
| A student / learner who wants to explore | Free |
| Evaluating Node Control before buying Pro | Free (then upgrade) |
