# AI features overview

Feature-level AI on Pro uses a provider you configure. Pro uses your own key. Free gets an AI preview only. **AI Chat** and the **AI Dashboard** are the AI edition only.

## Before you start: pick a provider

Open **Settings → AI / LLM** and pick a provider before you expect an answer. With nothing configured, the app prompts and offers **Open Settings**. The maps, the Inventory report, and L2 Topology Builder still run. They do not need a provider.

See [AI on Professional](ai-llm.md) and [AI provider](ai.md).

## Providers

- Auto-detect
- Backend (DGX / on-prem)
- Anthropic
- OpenAI
- Google Gemini
- xAI Grok
- OpenAI-compatible endpoint
- Ollama
- Disabled

Pro uses your own API key. There is no AI subscription and no markup. With Ollama, the request stays on your network.

## The three global switches

These three switches are on Settings → AI / LLM:

- **Enable AI analysis by default across all features** (off on a fresh install)
- **Anonymise identifiable data before sending to AI** (on by default)
- **Show preview before sending data to AI** (off by default)

The preview shows tokens such as `[IP_1]` and `[HOST_1]`. You read real names. The provider sees the tokens when the anonymiser is on.

**Enable AI analysis by default across all features** also sets the starting state of the **AI Summary** checkboxes on the Engineer page and the Reports tab. On a fresh install those boxes start unticked.

The Monitor alert narratives and the analyst review (the **Findings** tab) need that switch on. They do not run until you turn it on. There is no separate switch. They never run on Free.

## Where AI shows up

| Feature | Where | Default | Edition |
|---|---|---|---|
| End-of-task AI Summary | Engineer page checkbox | Starts from **Enable AI analysis by default across all features**. Off on a fresh install | Pro and AI. Free opens a preview and sends nothing |
| Ask AI | Monitor, per device | You open it | Pro and AI |
| Ask Network AI | Monitor. The dialog is **Ask AI — Network** | You open it | Pro and AI |
| Architect Review | Monitor, whole estate or one site | You open it | Pro and AI |
| Findings | Every Monitor poll. Alert row tooltip and the Findings tab | Off until you turn **Enable AI analysis by default across all features** on. No separate switch | Pro and AI. It never runs on Free |
| AI Summary | Reports tab | Starts from the same switch. Off on a fresh install | Pro and AI |
| Preview before sending | Reports tab | Starts unticked. Each time the tab loads it takes its starting state from **Show preview before sending data to AI** (off by default). Enabled only while **AI Summary** is ticked. You can change it for that run | Pro and AI |
| AI headline on emailed assessment | Only when the Lifecycle report is emailed | Off | Pro and AI |
| AI review | Firewall Analyser, Assess row | Ticked | Pro and AI. Free has no Firewall Analyser tab |
| AI advisory | Firewall Analyser | Shown with **AI review** | Pro and AI. Free has no Firewall Analyser tab |
| Background Learning | Settings → AI / LLM | Off | Pro and AI. On Free, the Settings → AI / LLM tab is not shown. Nothing on Free uses it |

## Monitor: Ask AI, Ask Network AI, Architect Review, Findings

From 0.9.41, on Pro and the AI edition:

- **Ask AI** is per device
- **Ask Network AI** opens the dialog **Ask AI — Network**
- **Architect Review** covers the whole estate, or one site

On every poll, alerted devices are reviewed. The narrative appears in the alert row tooltip and fills the bottom **Findings** tab. The columns are When, Device, Category, Sev, Headline, and Narrative. **Enable AI analysis by default across all features** is off on a fresh install, so the alert narratives and the analyst review do not run until you turn it on. There is no separate switch. It never runs on Free.

See [Monitor](../tasks/monitor.md).

## Background Learning

**Allow the backend and background jobs to log into devices with my credentials** is off by default. Background Learning is a Pro and AI feature. On Free, the Settings → AI / LLM tab is not shown. Nothing on Free uses it. Unattended logins are opt-in. Every unattended login appears as an **[AUTO]** line in the log.

## How answers are written

Answers are written as a senior network engineer at a large enterprise.

## Free: preview only

On Free, AI is a preview. The payload dialog opens so you can read what would have been sent. Nothing is sent. Findings never runs on Free. The Settings → AI / LLM tab is not shown. Configuring a provider, and sending, is the upgrade to Professional.

## What stays on the AI edition

**AI Chat** and the **AI Dashboard** are the AI edition only. The nine specialist agents, the Update tab, and **Vuln Plan** stay on that edition too. The AI edition is not yet available to buy. The site has no price and no download for it.

## Next steps

- [AI on Professional](ai-llm.md)
- [What leaves your laptop](../security/data-and-privacy.md)
- [Tier comparison](../tiers/overview.md)
