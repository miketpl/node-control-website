# Firewall Rule Analyser

> On **Pro** and the **AI** edition. Free does not show this page. This is a PAN-OS tool.

There is no standards picker and no list of named standards.

The tab has **Load Config File...**, **Edit Standards...**, and **Analyse**. **AI review** is on the Assess row, and it is ticked by default. **AI advisory** is on the same page. Both show on Pro and the AI edition. Free has no Firewall Analyser tab. They use the provider in Settings → AI / LLM. See [AI on Professional](../settings/ai-llm.md).

Inner tabs: **Rulebase Analyser**, **Compare**, **Proposed Rule Tester**.

**Edit Standards...** opens **Firewall Rulebase Standards**: one YAML editor, **Reset to Default**, Save / Cancel. The fields are:

- `naming_regex`
- `ticket_regex`
- `require_logging`
- `max_src_hosts`
- `max_dst_hosts`
- `max_port_breadth`
- `flag_any_any`
- `url_filtering_offsets_any_destination`
- `forbidden_services`
- `forbidden_zone_pairs`

The default forbids tcp/23, udp/69, and tcp/512-514.

The checks are deterministic. An empty or unrecognised export fails clearly. It does not pass every check.

A destination of `any` that is governed by a URL filtering profile is not scored as wide open.

## Pull from Panorama

**Pull from Panorama** fetches the running config and the configuration log over the API (keygen, then the pull). Every pull is stored. The previous pull loads as the baseline. You pick any stored pull and any device group to work from.

## Compare

The **Compare** tab loads an earlier policy against the current one. Every rule that was added, modified, removed, or re-ordered is listed field by field.

**Changed By** names the admin from the Panorama configuration log. Three log formats are read. A rule that only moved is not attributed to anyone. Rules change position as a side effect of other edits.

## Proposed Rule Tester

The tester is where you try a rule before you commit it anywhere. Object names autocomplete on the fields. The assessment uses the screen, rather than a small pane.

## AI review

**AI review** is on the Assess row, and it is ticked by default. **AI advisory** is shown as well. Both show on Pro and the AI edition. Free has no Firewall Analyser tab. They use the provider you configure: your own API key, with no AI subscription and no markup. The providers are Auto-detect, Backend (DGX / on-prem), Anthropic, OpenAI, Google Gemini, xAI Grok, OpenAI-compatible endpoint, Ollama, and Disabled. The deterministic findings do not need them.

## Next steps

- [Palo Alto](../vendors/palo-alto.md)
- [Safe Mode](../settings/safe-mode.md)
