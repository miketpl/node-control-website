# Where things are

The app opens on a Home page. A left sidebar is how you move between pages. The active page is marked with a rail on its left edge.

There is no top row of tabs. If an older page in these docs still says "tab" for Engineer, Reports, or Monitor, read that as the page of that name in the sidebar.

On Free the sidebar is **Home**, **Engineer**, **Reports**, and **File Transfer**. The status bar shows a **FREE VERSION** badge. Free does not show Monitor, Discover, IPAM, the Meraki Configurator, the Firewall Analyser, Update, or AI.

## Home

Home is the front of the app.

- Quick actions: Engineer, Find Device, and open the last report
- Your most recent reports, each one a row you can open
- On Pro and the AI edition, status cards for library size, the latest compliance result, and confirmed high vulnerabilities
- On Free, a library status card

## Engineer

Engineer is the library and the place tasks run from.

On Free the tasks that run are **None**, **L2 Topology Builder**, **Config Backup**, **Save Config**, and **Find Device**. Every other task is greyed out and reads **Upgrade to Pro**.

The bar across the top is a command bar, in labelled groups:

- **Task** — which task to run
- **Site** — which site
- **Run on** — which devices
- **Credentials** — which profile
- **Connections**

**Run** sits at the right of that bar.

Under the bar, a status strip shows the mode badge, the state, the progress, and the **Library** menu. The domain suffix setting lives in that Library menu.

## Settings

Settings is pinned at the bottom of the sidebar. It is also in the **Edit** menu.

## Other pages

These are their own sidebar pages, not tasks inside the Engineer command bar:

- **Reports** — on Free this page runs the Inventory report only
- **File Transfer** — on Free as well as Pro
- **Monitor** (Pro and AI; not on Free)
- **Discover** (Pro and AI; not on Free). This is not the subnet scan
- **IPAM** (Pro and AI; not on Free)
- **Meraki Configurator** (Pro and AI; not on Free)
- The firewall rule analyser (Pro and AI; not on Free)
- **Update** (Pro and AI; not on Free), for end-of-sale and end-of-life columns
- **AI** (AI edition; not on Free)

SSH sessions open in their own tabs inside the terminal. Those are session tabs, not the old top tab row.

## Next steps

- [Adding your first device](adding-first-device.md)
- [L2 Topology Builder](../tasks/topology-l2.md)
- [Config Backup and Save Config](../tasks/config-backup.md)
- [Tier comparison](../tiers/overview.md)
