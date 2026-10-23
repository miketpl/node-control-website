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
- an OpenAI-compatible endpoint
- Ollama
- Disabled

## What can go to the AI

- Reports: inventory, end-of-life and lifecycle, and the Security Audit (PSIRT) checks
- End-of-task summaries, including topologies, the compliance audit, and Find Device
- The lifecycle replace or upgrade plan narrative
- The firewall analyser AI advisor
- Per-device **Ask AI** on the Monitor tab

## How the prompt is framed

Prompts cast the AI as a senior network operations analyst, a security analyst, or a principal network architect. The answer is written to read like an experienced engineer's.

## Privacy

The anonymiser is on by default. Before anything leaves the machine it replaces:

- IPv4 and IPv6 addresses
- MAC addresses
- serial numbers
- hostnames and FQDNs

with opaque tokens such as `[IP_1]` and `[HOST_1]`. The app swaps the real values back locally. You read real names. The provider never sees them.

An optional preview shows exactly what will be sent before you approve it. AI is opt-in per run. Nothing is sent without that. With a local Ollama model, nothing leaves your network at all.

## Architect review and network-wide chat

From 0.9.41, **Architect Review** looks at the whole estate, or one site, on Pro and the AI edition. That covers single points of failure, the addressing plan, design risks, and an overall architecture view. **Ask Network AI** is on the Monitor tab. Both arrived in 0.9.41.

## Free

On Free, AI is preview only. You can see the anonymised payload. Nothing is ever sent. Configuring a provider, and sending, is the upgrade to Professional.

## Node Control AI edition

The AI edition is a separate product. It runs nine specialist AI agents on infrastructure you host, on an on-prem GPU server, so the AI runs entirely inside your network. It is not yet available to buy. The site has no price and no download for it. Register interest from the [contact section](https://nodecontrol.io/#contact).

## Next steps

- [Tier comparison](../tiers/overview.md)
- [AI provider settings](ai.md)
