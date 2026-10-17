# Meraki Configurator

> The **Meraki Configurator** is a sidebar page on **Pro** and the **AI** edition. Free does not show it.

The Meraki Configurator changes SSIDs and RF profiles across many Meraki networks in one pass. It uses the Dashboard API. It does not SSH to the access points.

## Load the grid

1. Open the Meraki Configurator from the left sidebar
2. Pick an organisation
3. Load its networks
4. Tick the networks you want
5. Read the chosen SSID slot, or the RF profile, side by side

Drift is visible before anything is sent.

## What gets sent

The editor is a whitelist. Every field has its own tick. Only ticked fields are sent. A network that already matches is skipped, and the page says so.

## Review and push

**Review & push** re-reads the ticked networks first. The plan you sign is the plan against the networks at that moment, not against the grid from when you loaded it.

Type `PUSH` to arm the button. An empty plan cannot be armed. Safe Mode blocks push and revert.

## Revert

Every push is recorded. **Push history** restores a push through the same sign-off. Only the fields that push touched are restored.

A revert will not delete a profile the push created, and it will not re-send a masked secret. Set those by hand.

## Next steps

- [Cisco Meraki](../vendors/meraki.md)
- [Safe Mode](../settings/safe-mode.md)
