# AI provider

Feature-level AI runs on **Pro**, on a provider you configure. See [AI on Professional](ai-llm.md). Free opens the payload dialog and sends nothing.

The Node Control AI edition is a separate product: nine specialist agents on infrastructure you host. It is not yet available to buy. It is not the provider setting on this page.

On Free, an AI option opens the payload dialog so you can read what would have been sent. Nothing is ever sent. Free does not let you configure a provider for sending.

The maps, the Inventory report, and L2 Topology Builder all work with no provider. On Pro, with no provider configured, the deterministic output is what you get and the AI option reports that.

## Settings → AI / LLM

Bring your own AI provider. It uses your own API key. There is no AI subscription and no markup. Supported:

- Anthropic (Claude)
- OpenAI
- a local Ollama model

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

The firewall analyser AI advisor uses the same provider. Tick it for that run.

**Vuln Plan** is the AI edition only. It is a button on the Update tab, next to **Check PSIRT**, and it works from that tab's PSIRT results. Pro has neither the Update tab nor Vuln Plan.

That Monitor chat is the feature on Pro. It is not the AI-edition dashboard.

## Next steps

- [Tier comparison](../tiers/overview.md)
- [Security Audit](../reports/security-audit.md)
- [Lifecycle and EoX](../reports/lifecycle.md)
