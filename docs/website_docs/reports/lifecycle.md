# Lifecycle and EoX

> On **Pro** and the **AI** edition. Free does not run this report.

This report answers a plain question: which hardware and which software in scope are at end of sale or end of life, and when.

On AOS-CX, Asset Lifecycle reads model, serial, version, and uptime. On Arista EOS it reads the EOS inventory and the EOS version.

## Where the dates come from

**Catalyst Center** is the authoritative source for devices it manages. A completed Catalyst Center answer is never overwritten by another source. A failed Catalyst Center scan is not the same thing as "this device has no end-of-life date". An empty answer from a failed scan does not wipe the other sources either.

If Catalyst Center is unreachable (VPN down, DNS failure), the log says so in one line. You do not get a traceback. A refused login — wrong password, or a password that has expired — is a plain message that names the account.

Devices Catalyst Center does not manage, Nexus in particular, get dates from Cisco's public End-of-Sale and End-of-Life notices. Those notices ship with the app. This release covers the Nexus 2000, 3000, 5000, 7000, and 9000 families. A row answered that way has a **Source** column that links the notice.

The report uses the scope you set on the Reports page, not only the devices Catalyst Center happens to know. Library devices outside Catalyst are listed. If the model is not already known, the report identifies the device over SSH with `show inventory`. What it learns is cached, so a later run of this report does not ask again.

## Catalyst Center in Settings

**Settings → API Platforms**, group **Catalyst Center**:

- **Enable**
- **Base URL:** placeholder `https://dnac.example.com`
- **Username:** placeholder `admin`
- **Password:** with **Set Credentials**, and a status that reads **Configured** or **Not set**
- **Test Connection**

There is no verify-SSL control. Certificate verification is off for all API clients.

## What a row means

Dates are scoped. A chassis date is not a module date, and a software date comes only from a software end-of-life record.

Columns include:

- End of Sale
- SW Maint End
- SW Support End
- Last Support HW
- Modules

Module and power-supply end of life is its own column, not folded into the chassis date.

**Switches only** means switches. Routers are decided from Catalyst's inventory family or the product ID, not from the library's driver. Routers are left out, and the log says how many. A device Catalyst knows by a different address is listed once.

The report keeps a keyword search, so you can narrow by site or by any other text in the row.

## Lifecycle Assessment

After a lifecycle run, a popup builds a replacement and upgrade plan. Each phase is split:

- **Hardware end-of-life — replace**
- **Software end-of-life — upgrade**

A banner marks where one ends and the other begins. The same split is in the popup and the exported report.

Wording in the plan:

- **UPGRADE IOS** for a software action
- **plan now** when the date is inside 18 months
- for a device further out, the plan states when planning should begin (from one year before end of life)

The assessment exports and emails as its own document. **AI headline on emailed assessment** is off by default and applies only when the Lifecycle report is emailed. It uses your own provider. See [AI provider](../settings/ai.md).

## Update tab

The **Update** tab is the AI edition. It is not on Pro, and it is not on Free. The end-of-sale and end-of-life columns in this Lifecycle report are on Pro.

**Vuln Plan** is a button on that Update tab, next to **Check PSIRT**. It works from the tab's PSIRT results. Pro does not have the button.

On Cisco NX-OS, Asset Lifecycle reads the Nexus model (for example N9K-C93180YC-EX) and the NX-OS version instead of the BIOS version, and it reads the `Processor Board ID` serial. The host name comes from `Device name:` and is not `Kernel`.

Asset Lifecycle reports model and serial for HP ProCurve / Aruba OS-Switch, Juniper Junos, Dell OS10, Extreme EXOS, and FortiGate.

Findings are saved to the local network memory: the model, serial, and software version. The end-of-life status is not saved. Network Chat and Architect Review can use what was saved.

## Next steps

- [Security Audit](security-audit.md)
- [Reports overview](overview.md)
- [Cisco](../vendors/cisco.md)
