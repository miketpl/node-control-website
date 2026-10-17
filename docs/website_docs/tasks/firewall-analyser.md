# Firewall Rule Analyser

> Available on **Pro** and the **AI** edition. This is a PAN-OS tool.

The analyser reads a Palo Alto policy export, or a pull straight from Panorama, and checks it against your YAML standards. The checks are deterministic. An empty or unrecognised export fails clearly. It does not pass every check.

A destination of `any` that is governed by a URL filtering profile is not scored as wide open.

## Pull from Panorama

**Pull from Panorama** fetches the running config and the configuration log over the API (keygen, then the pull). Every pull is stored. The previous pull loads as the baseline. You pick any stored pull and any device group to work from.

## Compare

The **Compare** tab loads an earlier policy against the current one. Every rule that was added, modified, removed, or re-ordered is listed field by field.

**Changed By** names the admin from the Panorama configuration log. Three log formats are read. A rule that only moved is not attributed to anyone. Rules change position as a side effect of other edits.

## Proposed Rule Tester

The tester is where you try a rule before you commit it anywhere. Object names autocomplete on the fields. The assessment uses the screen, rather than a small pane.

## AI advisor

The AI advisor is optional and off unless you tick it. It uses the provider in [Settings → AI / LLM](../settings/ai.md). The deterministic findings do not need a provider.

## Next steps

- [Palo Alto](../vendors/palo-alto.md)
- [Safe Mode](../settings/safe-mode.md)
