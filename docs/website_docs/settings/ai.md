# AI provider

Feature-level AI runs on **Pro** and the **AI** edition, on a provider you configure. The AI dashboard, the chat tabs, and the backend assistant are the **AI** edition only. That backend runs on infrastructure you host. Free does not show an AI page.

The Firewall Analyser **AI advisory** checkbox is the AI edition only.

On Free, an AI option opens the payload dialog so you can read what would have been sent. Nothing is ever sent. Free does not let you configure a provider for sending.

The maps, the Inventory report, and L2 Topology Builder all work with no provider. On Pro, with no provider configured, the deterministic output is what you get and the AI option reports that.

## Settings → AI / LLM

Set one of:

- an Anthropic API key
- an Ollama server

Identity-linked keys use the **Workspace ID** field. The connection test names the real failure: a rejected key, a retired model, a rate limit, a proxy problem, or a timeout. It does not blame the key for all of them.

If you tick an AI option and nothing is configured, the app prompts immediately and offers **Open Settings**. It does not wait until the end of the run and then skip quietly.

## What is sent

Nothing is sent unless you tick the option for that run. With **Preview AI** on, you approve the anonymised payload before it leaves the machine. Responses are de-anonymised before you see them. Raw tokens are not written to the log you read.

On Free the same dialog opens and then stops. Nothing is sent, and there is no provider to send it.

The checkbox is greyed out for tasks that have nothing to summarise, such as a backup, a save, a file transfer, or a push.

## Where it shows up

End-of-task summaries, when you tick them, cover:

- L2, L3, and WAN topology (structure, single points of failure, failed devices)
- Config Compliance Audit (posture and the common gaps)
- Find Device
- Library Updater
- Verify Device Types
- Discover Variables
- VLAN Port Finder

Where the task writes HTML, the summary is a panel at the top of that page, and it is also in the log. The page opens after the summary lands.

The same provider is used for:

- the report executive summary
- the lifecycle assessment narrative, and the emailed AI briefing (off by default)
- Monitor, on Pro: alert narratives, an analyst review of alerted devices, Ask AI for a device, whole-network chat, and the architect review

The Firewall Analyser **AI advisory** checkbox is the AI edition.

**Vuln Plan** is the AI edition only. It is a button on the Update tab, next to **Check PSIRT**, and it works from that tab's PSIRT results. Pro has neither the Update tab nor Vuln Plan.

That Monitor chat is the feature on Pro. It is not the AI-edition dashboard.

## Next steps

- [Tier comparison](../tiers/overview.md)
- [Security Audit](../reports/security-audit.md)
- [Lifecycle and EoX](../reports/lifecycle.md)
