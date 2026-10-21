# Settings overview

Open **Settings** from the navigation footer, or **Edit → Settings...**. On macOS, **Settings...** is in the application menu. There is no Tools menu and no Ctrl+, or Cmd+, shortcut.

The **Edit** menu holds only **Switch to Config Mode** / **Switch to Safe Mode**, and **Settings...**.

Settings is organised by section. Pick the one you need.

## API Platforms

**Settings → API Platforms** holds **Catalyst Center** and **Cisco ISE (Identity Services Engine)**. The fields are on the [Lifecycle](../reports/lifecycle.md) and [Change ISE Password](../tasks/change-ise-password.md) pages. There is no verify-SSL control. Certificate verification is off for all API clients.

## Settings tabs

| Tab | What it controls |
|---|---|
| **General** | Theme, font size, **Startup Mode** (what the Select Mode dialog defaults to), default library, auto-update behaviour |
| **Credentials** | Profiles, try order, and the device-type map. No star, and no per-tab memory. See [Credentials](../getting-started/credentials.md) |
| **Library** | Library file path, [GitHub sync](../library/github-sync.md), import/export defaults |
| **Site Detection** | [Hostname-to-site-code regex](site-detection.md) |
| **Find Device** | [Per-site starting switches](../tasks/find-device.md), parallelism, timeout, infrastructure gate patterns |
| **Reports** | Workers (parallelism), output cache TTL, export defaults |
| **Discovery** | Infra patterns, max hops, ping method preference, force-direction tuning |
| **Topology (L2/L3/WAN)** | Endpoint filter patterns, layout preferences, render style |
| **Terminal** | Colour theme, scrollback size, paste-with-delay toggle, session logging |
| **Monitor** | SSH keepalive, sample persistence, default polling interval |
| **Safe Mode** | Not a per-tab setting. The mode is session-wide. See [Safe Mode](safe-mode.md) |
| **Custom Commands** | [Per-vendor command catalog overrides](custom-commands.md) |
| **Scripts** | [Custom scripts](scripts.md) that run as tasks. Pro and the AI edition. On Free the page is there, and the task is greyed |
| **AI / LLM** | Bring your own AI provider, with your own API key. Anthropic (Claude), OpenAI, and local Ollama, plus Workspace ID. [Feature-level AI](ai.md). Pro and AI |
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

## Sharing a settings file

There is no Tools menu, and no Export Settings command under one. `settings.json` is the file. Copy it if you want the same settings on another machine.

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
- [Custom scripts](scripts.md)
- [AI provider](ai.md)

## Common configurations

| Goal | Settings to touch |
|---|---|
| Save typing of credentials | **Credentials** dropdown → **All**, with the profiles in try order |
| Find Device knows my cores | **Find Device** → Starting Switches per site |
| Topology maps look right | **Topology** → Endpoint filter patterns |
| Custom hostname pattern for site detection | **Site Detection** → adjust regex |
| Don't want SSH session logging | **Terminal** → uncheck Log session output |
| Auto-update aggressively | **General** → Auto-check for updates daily |
| Disable telemetry | **Advanced** → uncheck Send anonymous usage data. Those counts are stored against the licence. They are not anonymous. The privacy notice describes them. |

## Settings audit log

Every settings change is recorded in:

```
~/Library/Application Support/netOps/settings_audit.log
```

Useful when "what changed?" needs an answer after multiple users / multiple sessions.
