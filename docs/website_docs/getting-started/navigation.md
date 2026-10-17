# Where things are

The app opens on a Home page. A left sidebar is how you move between pages. The active page is marked with a rail on its left edge.

There is no top row of tabs. If an older page in these docs still says "tab" for Engineer, Reports, or Monitor, read that as the page of that name in the sidebar.

On Free the sidebar is **Home**, **Engineer**, **Reports**, and **File Transfer**. The status bar shows a **FREE VERSION** badge. Free does not show Monitor, Discover, IPAM, the Meraki Configurator, the Firewall Analyser, or AI. The **Update** tab is the AI edition only. It is not on Pro or Free.

## Home

Home is the front of the app.

- Quick actions: Engineer, Find Device, and open the last report
- Your most recent reports, each one a row you can open
- On Pro and the AI edition, status cards for library size, the latest compliance result, and confirmed high vulnerabilities
- On Free, a library status card

## Engineer

Engineer is the library and the place tasks run from.

The Engineer task dropdown is the same list on Free, Pro, and the AI edition, in this order:

1. **None**
2. **L2 Topology Builder**
3. **L3 Topology Builder**
4. **Watcher of The WAN**
5. **Config Backup**
6. **Config Compliance Audit**
7. **Config Compliance Remediate**
8. **Config from File**
9. **Save Config**
10. **File Transfer**
11. **Packet Capture**
12. **Library Updater**
13. **VLAN Port Finder**
14. **Config Push**
15. **Refresh Hostnames**
16. **Verify Device Types**
17. **Discover Variables**
18. **Find Device**
19. **Change ISE Password**

**Config Push Script** appears only when **Settings → Paths → Config Push Script** points at an existing file. A configured custom script appears as `Script: <name>`.

On Free only **None**, **L2 Topology Builder**, **Config Backup**, **Save Config**, and **Find Device** are enabled. The rest are greyed out, with the tooltip **Upgrade to Pro to unlock this feature**.

In Safe Mode the list is cut to **None**, **L2 Topology Builder**, **L3 Topology Builder**, **Watcher of The WAN**, **Config Backup**, **Library Updater**, **VLAN Port Finder**, **Refresh Hostnames**, **Verify Device Types**, **Discover Variables**, and **Find Device**. See [Safe Mode](../settings/safe-mode.md).

The bar across the top is a command bar, in labelled groups:

- **Task** — which task to run
- **Site** — which site
- **Run on** — which devices
- **Credentials** — which profile
- **Connections**

**Run** sits at the right of that bar.

Under the bar, a status strip shows the mode badge, the state, the progress, and the **Library** menu. The domain suffix setting lives in that Library menu.

## Settings and the menus

**Settings** is in the navigation footer (the sidebar). It is also **Edit → Settings...**.

The **Edit** menu holds only **Switch to Config Mode** / **Switch to Safe Mode**, and **Settings...**.

The **Help** menu holds **Check for Updates...** and **About Node Control**.

There is no Tools menu. There is no Ctrl+, or Cmd+, shortcut. On macOS, Qt moves **Settings...** into the application menu, and nothing more.

## Other pages

These are their own sidebar pages, not tasks inside the Engineer command bar:

- **Reports** — on Free this page runs the Inventory report only
- **File Transfer** — the page is on Free, Pro, and the AI edition, including the local server and the remote client. The File Transfer task in the dropdown is Pro
- **Monitor** (Pro and AI; not on Free)
- **Discover** (Pro and AI; not on Free). This is not the Library Updater
- **IPAM** (Pro and AI; not on Free)
- **Meraki Configurator** (Pro and AI; not on Free)
- The firewall rule analyser (Pro and AI; not on Free)
- **Update** (AI edition only; not on Pro or Free)
- **AI** (AI edition; not on Free)

SSH sessions open in their own tabs inside the terminal. Those are session tabs, not the old top tab row.

## Next steps

- [Adding your first device](adding-first-device.md)
- [L2 Topology Builder](../tasks/topology-l2.md)
- [Config Backup and Save Config](../tasks/config-backup.md)
- [Config from File](../tasks/config-from-file.md)
- [Discover Variables](../tasks/discover-variables.md)
- [Tier comparison](../tiers/overview.md)
