# File Transfer

**File Transfer** is a sidebar page on **Free**, **Pro**, and the **AI** edition. Free shows this page. It does not show Monitor, Discover, IPAM, the Meraki Configurator, the Firewall Analyser, Update, or AI.

## Local server

The server speaks SFTP and SCP. Device-initiated SCP, such as `copy running-config scp://...`, used to hang because only SFTP was implemented. SCP is implemented now.

### Which address it listens on

Every address on the machine is listed with its interface name, so a VPN tunnel is easy to pick out. The example commands on the page always match the address you chose.

### Port 22

Only root can bind ports below 1024. If you choose port 22, the page offers a one-time command that forwards port 22 to the port the server can actually bind, and the line that removes that forward.

### When it fails

A port already in use, a blocked bind, or anything else that stops the server is written to the log and shown on screen. It does not fail silently.

If the switch says SCP is administratively disabled, the task tells you the switch's SCP server is off and names `ip scp server enable`.

## Remote client

The Pro release notes describe a **Remote client** section: a host, a port, and a login, then upload or download of files or folders. Each file is logged with its outcome and its size.

Whether that section is hidden on Free is not confirmed. The page itself is on Free.

## Next steps

- [Packet Capture](packet-capture.md)
- [Credential storage](../security/credential-storage.md)
