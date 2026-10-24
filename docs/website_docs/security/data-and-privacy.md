# What leaves your laptop

Node Control runs on the laptop. This page is what the app sends off the machine. The full notice is the [privacy notice](../../privacy.html).

## Licence checks

Licence checks go to api.nodecontrol.io. A check sends the licence key, a random install id, the app version, the OS family, and the CPU architecture. The server stores the install id, platform, architecture, the time the computer was activated, and the time it was last seen. One computer is active on a key at a time.

Moving the key to another computer is confirmed by an email code, and is limited to two moves in 30 days. A device-move code expires after 15 minutes. See [Your licence](../getting-started/licence.md).

## Usage statistics and how to opt out

The in-app label is **Send anonymous usage statistics**. Counts are sent every 30 minutes and at close, only while that switch is on.

Usage statistics contain no personal or network data. They are linked to your licence so they can be erased on opt-out.

A session row holds how long the app ran, how many connections it opened, how many errors it counted, and counts of tasks. It also holds the app version, OS family, OS major version, and architecture. The row is stored against the licence and the install id. The server drops a user name, company, hostname, or machine id if one is sent. The stored counts do not include device configs, hostnames, IP addresses, or the contents of the network.

Turn it off under **Settings → Privacy** by clearing **Send anonymous usage statistics**. You can delete the session rows from the app, or by emailing privacy@nodecontrol.io.

Session rows are kept for 365 days, then folded into monthly totals. Those totals are edition, version, OS family, and the counts. They do not include the licence or the install id.

## AI requests and the anonymiser

When **Anonymise identifiable data before sending to AI** is on, AI requests go through the anonymiser. Addresses, MAC addresses, serial numbers, and hostnames are replaced with tokens such as `[IP_1]` and `[HOST_1]`. You read real names. The provider sees the tokens.

**Show preview before sending data to AI** is off by default. The preview shows those tokens.

With Ollama, the request stays on your network. See [AI features overview](../settings/ai-features.md).

## Unattended device logins ([AUTO] lines)

**Allow the backend and background jobs to log into devices with my credentials** is off by default. Background Learning is a Pro and AI feature. On Free, the Settings → AI / LLM tab is not shown. Nothing on Free uses it. Unattended logins are opt-in. Every unattended login appears as an **[AUTO]** line in the log. See [How credentials are stored](credential-storage.md).

## Update checks and downloads

Update checks happen once at launch, right after the licence check, and from **Help → Check for Updates...**. There is no timer after that.

An update check sends the licence key and the install id so the server can answer, and it updates the last-seen time on that computer. The statistic that is kept is a daily count of edition, platform, and version. The key and the install id are not written into that count.

The installer file is downloaded from GitHub. See [Updating Node Control](../getting-started/updating.md).

## Next steps

- [Privacy notice](../../privacy.html)
- [How credentials are stored](credential-storage.md)
- [AI features overview](../settings/ai-features.md)
