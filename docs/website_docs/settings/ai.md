# AI provider

Feature-level AI runs on **Pro**, on a provider you configure. See [AI on Professional](ai-llm.md). Free opens the payload dialog and sends nothing.

The Node Control AI edition is a separate product: nine specialist agents on infrastructure you host. It is not yet available to buy. It is not the provider setting on this page. **AI Chat** and the **AI Dashboard** are the AI edition only.

On Free, an AI option opens the payload dialog so you can read what would have been sent. Nothing is ever sent. Free does not let you configure a provider for sending.

The maps, the Inventory report, and L2 Topology Builder all work with no provider. On Pro, with no provider configured, the deterministic output is what you get and the AI option reports that.

## Settings → AI / LLM

Bring your own AI provider. It uses your own API key. There is no AI subscription and no markup. The providers are Auto-detect, Backend (DGX / on-prem), Anthropic, OpenAI, Google Gemini, xAI Grok, OpenAI-compatible endpoint, Ollama, and Disabled. See [AI on Professional](ai-llm.md).

Identity-linked keys use the **Workspace ID** field. The connection test names the real failure: a rejected key, a retired model, a rate limit, a proxy problem, or a timeout. It does not blame the key for all of them.

If you tick an AI option and nothing is configured, the app prompts immediately and offers **Open Settings**. It does not wait until the end of the run and then skip quietly.

## What is sent

Three switches sit on Settings → AI / LLM:

- **Enable AI analysis by default across all features**
- **Anonymise identifiable data before sending to AI** (on by default)
- **Show preview before sending data to AI** (off by default)

The preview shows tokens such as `[IP_1]` and `[HOST_1]`. Responses are de-anonymised before you see them. Raw tokens are not written to the log you read.

End-of-task **AI Summary** is a checkbox on the Engineer page. You tick it for that run. The checkbox is greyed out for tasks that have nothing to summarise, such as a backup, a save, a file transfer, or a push.

On Free the same dialog opens and then stops. Nothing is sent, and there is no provider to send it.

The Findings review on Monitor is separate from that checkbox. It runs on every poll when **Enable AI analysis by default across all features** is on. It has no separate switch, and it never runs on Free.

## Where it shows up

End-of-task summaries, when you tick them on the Engineer page, cover:

- Topology (L2, L3, and WAN: structure, single points of failure, failed devices)
- VLAN Port Finder
- Library Updater
- Find Device
- Discover Variables
- Verify Device Types
- Config Compliance Audit (posture and the common gaps)

Where the task writes HTML, the summary is a panel at the top of that page, and it is also in the log. The page opens after the summary lands.

The same provider is used for:

- **AI Summary** and **Preview before sending** on the Reports tab
- **AI headline on emailed assessment** (off by default; only when the Lifecycle report is emailed)
- Monitor, from 0.9.41, on Pro and the AI edition: **Ask AI** (per device), **Ask Network AI** (opens the dialog **Ask AI — Network**), **Architect Review** (whole estate or one site), and the **Findings** tab

**AI review** is an option on the Firewall Analyser Assess row, and it is on by default. The AI advisor stays a Pro feature.

**Vuln Plan** is the AI edition only. It is a button on the Update tab, next to **Check PSIRT**, and it works from that tab's PSIRT results. Pro has neither the Update tab nor Vuln Plan.

**AI Chat** and the **AI Dashboard** stay on the AI edition.

## Background Learning

**Allow the backend and background jobs to log into devices with my credentials** is on Settings → AI / LLM. It is off by default. Unattended logins are opt-in. Every unattended login appears as an **[AUTO]** line in the log. See [What leaves your laptop](../security/data-and-privacy.md).

## Next steps

- [AI features overview](ai-features.md)
- [Tier comparison](../tiers/overview.md)
- [Security Audit](../reports/security-audit.md)
- [Lifecycle and EoX](../reports/lifecycle.md)
