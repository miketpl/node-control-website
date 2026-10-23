# AI on Professional

Bring your own AI provider. Professional uses your own API key. There is no AI subscription and no markup.

## Settings → AI / LLM

Supported. Pro uses your own API key:

- Auto-detect
- Backend (DGX / on-prem)
- Anthropic
- OpenAI
- Google Gemini
- xAI Grok
- OpenAI-compatible endpoint
- Ollama
- Disabled

## What can go to the AI

- **AI Summary** on the Reports tab, with **Preview before sending**
- End-of-task **AI Summary** on the Engineer page: topology, VLAN Port Finder, Library Updater, Find Device, Discover Variables, Verify Device Types, and Config Compliance Audit
- **AI headline on emailed assessment**, off by default, and only when the Lifecycle report is emailed
- **AI review** on the Firewall Analyser Assess row, ticked by default, and **AI advisory** on the same page. Both show on Pro and the AI edition. Free has no Firewall Analyser tab
- From 0.9.41, on Monitor: **Ask AI**, **Ask Network AI**, **Architect Review**, and the **Findings** tab

## How the prompt is framed

Answers are written as a senior network engineer at a large enterprise.

## Privacy

Three switches sit on Settings → AI / LLM. See [AI features overview](ai-features.md).

**Anonymise identifiable data before sending to AI** is on by default. Before anything leaves the machine it replaces:

- IPv4 and IPv6 addresses
- MAC addresses
- serial numbers
- hostnames and FQDNs

with tokens such as `[IP_1]` and `[HOST_1]`. The app swaps the real values back locally. You read real names. The provider sees the tokens.

**Show preview before sending data to AI** is off by default. When it is on, the preview shows those tokens.

**Enable AI analysis by default across all features** is off on a fresh install. It also sets the starting state of the **AI Summary** checkboxes on the Engineer page and the Reports tab, so those boxes start unticked. The Monitor alert narratives and the analyst review (the **Findings** tab) need the switch on. They do not run until you turn it on. There is no separate switch.

With a local Ollama model, nothing leaves your network at all.

## Monitor, from 0.9.41

From 0.9.41, on Pro and the AI edition, the Monitor tab has:

- **Ask AI**, per device
- **Ask Network AI**, which opens the dialog **Ask AI — Network**
- **Architect Review**, for the whole estate or one site. That covers single points of failure, the addressing plan, design risks, and an overall architecture view

On every poll, alerted devices are reviewed. The narrative appears in the alert row tooltip and fills the bottom **Findings** tab. The columns are When, Device, Category, Sev, Headline, and Narrative. **Enable AI analysis by default across all features** is off on a fresh install, so the alert narratives and the analyst review do not run until you turn it on. There is no separate switch. It never runs on Free.

## Background Learning

**Allow the backend and background jobs to log into devices with my credentials** is off by default. Background Learning is a Pro and AI feature. The setting is visible on Free. Nothing on Free uses it. Unattended logins are opt-in. Every unattended login appears as an **[AUTO]** line in the log.

## Free

On Free, AI is preview only. You can see the anonymised payload. Nothing is ever sent. Configuring a provider, and sending, is the upgrade to Professional.

## Node Control AI edition

The AI edition is a separate product. It runs nine specialist AI agents on infrastructure you host, on an on-prem GPU server, so the AI runs entirely inside your network. **AI Chat** and the **AI Dashboard** are the AI edition only. It is not yet available to buy. The site has no price and no download for it. Register interest from the [contact section](https://nodecontrol.io/#contact).

## Next steps

- [AI features overview](ai-features.md)
- [AI provider settings](ai.md)
- [Tier comparison](../tiers/overview.md)
