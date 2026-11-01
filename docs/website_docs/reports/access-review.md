# Access Review

> On **Pro** and the **AI** edition. Free does not run this report. Cisco ASA has no general support. In this report it is a preview only.

The Access Review report is on the Reports tab. It lists the admin accounts on your firewalls. Each account shows its role, where it signs in from (local or a remote server), and notes such as two-factor or SSH key login.

It covers Palo Alto and FortiGate. Cisco ASA is a preview only. Other devices are skipped with a reason.

It reads only the configuration the app already collects. Password hashes, keys, and tokens are never read into the report.

A FortiGate list without the built-in super admin is marked as possibly incomplete, because a restricted login only sees its own account.

The report has a CSV file alongside it. It can be scheduled like the other reports.

## Next steps

- [Reports overview](overview.md)
- [Config Compliance](../tasks/config-compliance.md)
- [Palo Alto](../vendors/palo-alto.md)
