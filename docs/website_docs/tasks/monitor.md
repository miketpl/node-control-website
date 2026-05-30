# Monitor tab

> Available on **Pro** and **AI** tiers only.

The Monitor tab is a continuous-polling dashboard for one or more devices — it samples interface counters, CPU, memory, and environmental data on a configurable interval and renders graphs and threshold alerts.

Think of it as Node Control's lightweight equivalent of an SNMP poller, but using SSH instead of SNMP.

## Open the Monitor tab

- Top-level **Monitor** tab (alongside Engineer, Discovery, Tasks, Reports)

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

## Next steps

- [Reports](../reports/overview.md) — for point-in-time snapshots
- [Find Device](find-device.md) — for "who's plugged into where" type questions
