# Monitor

> **Monitor** is a sidebar page on **Pro** and the **AI** edition. Free does not show it.

The Monitor tab is a continuous-polling dashboard for one or more devices — it samples interface counters, CPU, memory, and environmental data on a configurable interval and renders graphs and threshold alerts.

Think of it as Node Control's lightweight equivalent of an SNMP poller, but using SSH instead of SNMP.

## Open Monitor

- **Monitor** in the left sidebar. It is not in the Engineer task list.

## Adding devices to monitor

1. Click **+ Add Device** in the Monitor tab
2. Pick from your library
3. Choose which metrics to poll:
   - **Interface counters** (in/out octets, errors, drops)
   - **CPU utilisation**
   - **Memory utilisation**
   - **Environmental** (temperature, fans, PSU)
   - **PoE** (per-port power draw, total budget)
   - **BGP / OSPF peer state**
4. Set polling interval (15s, 30s, 1m, 5m)
5. Click **Start**

The device appears as a tile in the Monitor tab with live-updating graphs.

## Tile layout

Each monitored device gets a tile showing:

- **Hostname + IP** header
- **CPU / Memory** sparkline
- **Interface error rate** graph
- **Up/down indicator** with last-successful-poll timestamp
- **Alerts** badge (red number = how many threshold breaches active)

Click a tile to expand it to a full-screen detailed view.

## Which interfaces are counted

Interface tables list physical ports and port-channels only. VLAN interfaces, tunnels, and loopbacks are excluded. Their counters repeat traffic already counted on the ports underneath, and that made every utilisation figure suspect. Threshold alerts use the same rule, so a "link at 90%" alert cannot point at an SVI.

## Threshold alerts

For each metric, set:

- **Warning** threshold (e.g., CPU > 80%)
- **Critical** threshold (e.g., CPU > 95%)
- **Recovery** threshold (the value the metric must drop below to clear the alert)

When a threshold is breached:

- The tile turns yellow (warning) or red (critical)
- An entry appears in the **Alerts** sub-panel
- Optionally: a desktop notification fires

Alert history is logged to:

```
~/Library/Application Support/netOps/monitor_alerts.log
```

## Polling interval and SSH usage

Each polled device opens an SSH session and reuses it across polls — Monitor doesn't reconnect on every interval, which would be heavy. The session is kept alive with periodic keepalives.

A typical poll runs 3–8 SSH commands and takes ~2 seconds per device. Polling 20 devices at 30-second intervals is comfortable; 100 devices at 30s starts to strain the SSH connection pool.

For larger-scale monitoring, increase the interval to 1m or 5m, or split devices across multiple Monitor sessions.

## What gets graphed

- **Time series**: in-memory rolling window of the last N samples (configurable, default 1 hour)
- **Long-term storage**: optional persistence to SQLite for historical lookback (Settings → Monitor → Persist samples)

Graphs are zoomable and pannable. Click and drag to select a time range for closer inspection.

## Link status on L2 maps

**Link status** is a tick box, on by default. It colours the cables on L2 maps from the port status Monitor already polls: green for up, red dashed for down, grey when unknown. Hover a cable to see both ports. Link status covers Cisco IOS, IOS-XE, and NX-OS ports.

After each poll round, the latest status is written into the map's own page. A map opened outside Node Control shows how the network looked at the last poll, with the time. It is marked stale after 24 hours.

After an L2 or L3 topology run, the map page says **Open in Monitor for live status**.

## Refused logins

Monitor stops trying a device after 2 refused logins, and it backs off from devices that do not answer. A **Retry** button on that device starts it again. Every poll goes through the same safe-command check as the rest of the app.

A refused login shows grey with **Login refused**, not red as if the device were down. Alerts and hover tips use short reasons: **login refused (1 of 2)**, **Stopped**, **Backing off**, and **Unreachable**. They do not show the raw connection error.

## Vendor coverage

Same as the rest of Node Control:

| Vendor | Interface | CPU/Mem | Environmental | PoE | BGP / OSPF |
|---|---|---|---|---|---|
| Cisco IOS / IOS-XE | ✓ | ✓ | ✓ | ✓ | ✓ |
| Cisco NX-OS | ✓ | ✓ | ✓ | ✓ | ✓ |
| HP ProCurve | ✓ | ✓ | partial | ✓ | ✓ |
| Aruba CX | ✓ | ✓ | ✓ | ✓ | ✓ |
| Juniper | ✓ | ✓ | ✓ | — | ✓ |
| Arista | ✓ | ✓ | ✓ | — | ✓ |
| Palo Alto | partial | ✓ | ✓ | — | ✓ |

Vendor-specific gaps are documented in [Vendors](../vendors/overview.md).

On AOS-CX, Health Monitor reads CPU and memory. On Arista EOS, Health Monitor reads memory from `show version`. CPU is reported as well, on recent EOS versions where the old command was refused, in the Health Monitor report and in Monitor.

Device names and other text read from devices are shown as plain text on the Health Monitor and Firewall Health report pages. A device name containing page code cannot change or run anything in the page.

## Stopping / removing

- **Pause** a tile to stop polling without removing it
- **Remove** to delete the tile (clears its history if not persisted)
- **Pause all** stops polling across every tile (useful when you need to free SSH sessions for other tasks)

## When to use Monitor vs Reports

| Use case | Tool |
|---|---|
| One-off snapshot ("what's the CPU now?") | Reports → Port Utilisation |
| Watching a problem unfold in real-time | Monitor |
| Hours-long observation during change windows | Monitor with **Persist samples** ON |
| Historical analysis ("how loaded was this port last month?") | Not currently supported — Monitor's persistence is a rolling window, not a full TSDB. For long-term, use a dedicated NMS |

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Tile shows "Disconnected" intermittently | SSH idle timeout on device | Lower the keepalive interval (Settings → Monitor → SSH keepalive) |
| All tiles slow to update | Network latency or polling interval too aggressive | Increase interval to 1m or longer |
| CPU graph showing 0% on devices that are clearly loaded | Vendor's CPU command output not parsed correctly | Open a support ticket with the device's `show processes cpu` output |

## AI on Monitor

From 0.9.41, on Pro and the AI edition, the Monitor tab has three buttons. They use the provider in [Settings → AI / LLM](../settings/ai.md).

- **Ask AI**, per device
- **Ask Network AI**, which opens the dialog **Ask AI — Network**
- **Architect Review**, for the whole estate or one site

On every poll, alerted devices are reviewed. The narrative appears in the alert row tooltip and fills the bottom **Findings** tab. The columns are When, Device, Category, Sev, Headline, and Narrative. **Enable AI analysis by default across all features** is off on a fresh install, so the alert narratives and the analyst review do not run until you turn it on. There is no separate switch. It never runs on Free.

**AI Chat** and the **AI Dashboard** stay on the AI edition. See [AI features overview](../settings/ai-features.md).

Firewall Health & Logs, Change Summary, and Asset Lifecycle save findings to the local network memory, so **Ask Network AI** and **Architect Review** can use them. From Firewall Health & Logs that is the model, serial, software version, CPU, memory, and GlobalProtect user counts, critical system logs, and a degraded HA pair. From Change Summary, how many config changes were made and by whom. From Asset Lifecycle, the model, serial, and software version, not the end-of-life status.

## Next steps

- [Reports](../reports/overview.md) — for point-in-time snapshots
- [Find Device](find-device.md) — for "who's plugged into where" type questions
