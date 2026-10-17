# Config Compliance

> On **Pro** and the **AI** edition. On Free both tasks are greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode hides **Config Compliance Remediate**. **Config Compliance Audit** is not in the Safe Mode task list either. Remediation is Cisco IOS, IOS-XE, and NX-OS only.

Two tasks:

- **Config Compliance Audit** checks that selected switches and routers carry your baseline. It does not change anything.
- **Config Compliance Remediate** pushes the missing lines from a stored audit, after you confirm.

Baseline lines are never sent on the read path. The only way config is pushed is the remediate dialog.

## Audit

The baseline is either a hardening template file or one or more lines you paste (ad-hoc mode). Ad-hoc mode checks that the selected devices, or all devices, have those lines. Everything else in the config is ignored.

### How a line matches

Matching is hierarchy-aware. A line counts only inside the right parent block.

- `ip access-group 1 in` also matches the variant that names a VRF as well
- `line vty` covers every VTY block. A required child line must be present in every matching block, or the audit counts it missing
- `*` or `{}` matches any one word. You can name a brace placeholder for readability, for example `ip access-list extended {acl-name}`
- `*` inside a value matches part of it. `ntp server 10.*.111.1` accepts any second octet and pins the rest

A template that is not indented still understands modes. Lines that follow a mode opener such as `line vty 0 4` or `interface` bind to that block.

### After the run

Every audit run is stored. The last 20 runs are kept. The HTML report has an **Export CSV** button above each table.

An optional AI summary of posture and the common gaps is available if you tick it for that run. See [AI provider](../settings/ai.md).

## Remediate

You can remediate at the end of an audit, or later with **Config Compliance Remediate**, which opens a stored run. The later task does not re-audit before the push. It re-audits each device after the push to verify.

1. Review what is missing, per device
2. Tick the lines you actually want applied. This is per line, not all-or-nothing
3. Read the command script. Edit it if you need to. What you see is what will be sent
4. Type `REMEDIATE` to confirm

Options on the way through:

- Write memory, if you tick it
- Safe Mode blocks remediation. Turn Safe Mode off only for the run you intend to push

After the push, the config is pulled again and audited again. A full transcript is saved next to the reports.

### What will not be pushed

- A placeholder in the line itself stays a manual fix
- A placeholder only in the block header does not stop the push. The missing child line goes into the device's real matching block
- A wildcard line, or a parent block that is not on the device, is flagged for you to do by hand
- Remediation does not run against vendors other than Cisco IOS, IOS-XE, and NX-OS

## Next steps

- [Security Audit](../reports/security-audit.md) — optional baseline section in the same SSH session as the PSIRT check
- [Safe Mode](../settings/safe-mode.md)
- [Config Push](config-push.md) — a different task, for per-port templates
