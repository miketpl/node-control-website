# Change Summary report

> On **Pro** and the **AI** edition. Free does not run this report.

Change Summary reports what was configured, not only that a change happened. The timeline lists the commands and who entered them.

## Run it

1. Open **Reports** in the left sidebar
2. Choose **Change Summary**
3. Set the scope
4. Click **Run**

## Devices with no archive

Some devices have no configuration archive, so they cannot record which commands ran. The report names those devices and prints the configuration they need. The Action column is not left blank with no explanation.

## Export

The HTML report has an **Export CSV** button above each table. Email works the same way as the other reports: background send, and the log says why if the mail is skipped.

Change Summary skips a vendor it cannot serve before any command is sent. The row reads `SKIP, "Change Summary not supported on <type>"`. It does not send Cisco archive commands to ProCurve, Dell, Extreme, or FortiGate.

Findings are saved to the local network memory: how many config changes were made, and by whom. On Pro and the AI edition, Ask Network AI and Architect Review on the Monitor tab can use what was saved.

## Next steps

- [Reports overview](overview.md)
- [Config Compliance](../tasks/config-compliance.md)
