# Settings overview

Open **Settings** from the bottom of the left sidebar. It is also in the **Edit** menu.

Settings is organised by section. Pick the one you need.

## Settings tabs

| Tab | What it controls |
|---|---|
| **General** | Theme, font size, startup mode, default library, auto-update behaviour |
| **Credentials** | Username/password profiles, default profile, per-tab assignments, Meraki API key |
| **Library** | Library file path, [GitHub sync](../library/github-sync.md), import/export defaults |
| **Site Detection** | [Hostname-to-site-code regex](site-detection.md) |
| **Find Device** | [Per-site starting switches](../tasks/find-device.md), parallelism, timeout, infrastructure gate patterns |
| **Reports** | Workers (parallelism), output cache TTL, export defaults |
| **Discovery** | Infra patterns, max hops, ping method preference, force-direction tuning |
| **Topology (L2/L3/WAN)** | Endpoint filter patterns, layout preferences, render style |
| **Terminal** | Colour theme, scrollback size, paste-with-delay toggle, session logging |
| **Monitor** | SSH keepalive, sample persistence, default polling interval |
| **Safe Mode** | [Command allowlist / blocklist](safe-mode.md) |
| **Custom Commands** | [Per-vendor command catalog overrides](custom-commands.md) |
| **Scripts** | [Python scripts that run as tasks](scripts.md), Pro and AI |
| **AI / LLM** | Anthropic API key or an Ollama server, plus Workspace ID. [Feature-level AI](ai.md). Pro and AI |
| **Advanced** | Crash log location, telemetry opt-in, debug logging |

## Where settings are stored

```
~/Library/Application Support/netOps/settings.json   (Mac)
%APPDATA%\netOps\settings.json                        (Windows)
```

Settings are read on launch and saved on dismiss. Changes take effect immediately for most settings.

Four themes share the layout: **Dark Hacker**, **Dark Blue**, **Light**, and **High Contrast**. High Contrast keeps strong borders. Changing theme tells you a restart is required. It does not pretend to apply in place.

## Resetting to defaults

To reset all settings (without losing your library or credentials):

1. Quit Node Control
2. Rename `settings.json` to `settings.json.bak`
3. Launch — a fresh default `settings.json` is created
4. Reconfigure as needed; you can copy specific keys from `.bak` if helpful

## Exporting / importing settings

For sharing a baseline across team members:

- **Tools → Export Settings** → produces a JSON file you can email or commit to a repo
- **Tools → Import Settings** → loads from JSON, prompts before overwriting current values

Useful when standardising "everyone uses these site detection rules" across an org.

## Per-environment settings

If you switch between different customer networks, you can have multiple `settings.json` files and switch by:

1. Quit app
2. Backup current settings: `cp settings.json customer-A-settings.json`
3. Replace with the new env: `cp customer-B-settings.json settings.json`
4. Launch

A future release may add named settings profiles to skip the manual copy — let us know if this is important.

## Detailed pages

- [Site detection rules](site-detection.md)
- [Custom command catalogs](custom-commands.md)
- [Safe Mode](safe-mode.md)
- [Scripts](scripts.md)
- [AI provider](ai.md)

## Common configurations

| Goal | Settings to touch |
|---|---|
| Save typing of credentials | **Credentials** → set a default profile |
| Find Device knows my cores | **Find Device** → Starting Switches per site |
| Topology maps look right | **Topology** → Endpoint filter patterns |
| Custom hostname pattern for site detection | **Site Detection** → adjust regex |
| Don't want SSH session logging | **Terminal** → uncheck Log session output |
| Auto-update aggressively | **General** → Auto-check for updates daily |
| Disable telemetry | **Advanced** → uncheck Send anonymous usage data |

## Settings audit log

Every settings change is recorded in:

```
~/Library/Application Support/netOps/settings_audit.log
```

Useful when "what changed?" needs an answer after multiple users / multiple sessions.
