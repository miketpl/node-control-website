# Security Audit report

> On **Pro** and the **AI** edition. Free does not run this report.

The Security Audit report connects to each device in scope, reads the running software, and lists published Cisco security advisories for that version. Advisories are grouped by severity. Each advisory names the devices it applies to.

Non-Cisco devices are skipped. Cisco's openVuln API is queried with the version string normalised to the form that API accepts.

## Run it

1. Open **Reports** in the left sidebar
2. Choose **Security Audit**
3. Set the scope the same way as any other report
4. Click **Run**

You can turn on an optional baseline section. In the same SSH session the report pulls the running config and checks it against your hardening template. The check itself is the same engine as the [Config Compliance](../tasks/config-compliance.md) task. The report is the place to read the result. The task is the place to push fixes.

## Platform check

Cisco indexes many advisories by software release alone. An advisory written for other hardware on that same release is not hidden. It is marked **platform mismatch**, sorted below the confirmed matches, and kept out of the confirmed High, Medium, and Low counts.

The product list is filled in from the advisory detail when the version query omits it. An advisory with no product data at all is called out in the report. It is not treated as a clean pass.

If the product list is only "Cisco IOS XE Software" but the title names hardware (for example Catalyst 3650 and 3850), the title is what gets checked. Those advisories do not pass as train-wide on an unrelated model.

## Vuln Plan

After the advisory data is in, **Vuln Plan** builds a remediation plan grouped by running version, with priorities and upgrade targets. For each advisory it also checks whether the device's configuration actually meets the vulnerable condition.

A platform-mismatch advisory stays in the plan, marked as such. It does not set the plan's priorities.

## Export and email

The HTML report has an **Export CSV** button above each table. You can email the report. The send runs in the background. If the email is skipped, the log says why: the option was unticked, or there were no recipients.

An AI executive summary is optional, and off unless you tick it for that run. It uses the provider in [Settings → AI / LLM](../settings/ai.md). Nothing is sent if you leave the box unticked.

## Next steps

- [Config Compliance](../tasks/config-compliance.md)
- [Lifecycle and EoX](lifecycle.md)
- [Reports overview](overview.md)
