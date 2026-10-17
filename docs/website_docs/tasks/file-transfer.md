# File Transfer

The File Transfer page is a server your devices can copy to, and, on Pro and the AI edition, a client that reaches out to a remote SFTP server.

The local server is in Free as well as Pro. The remote client is Pro and AI.

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

On Pro and the AI edition, the **Remote client** section takes a host, a port, and a login. It uploads or downloads files or folders. Each file is logged with its outcome and its size.

Those fields accept typing. If they look greyed out, you are on a build before that fix.

## Next steps

- [Packet Capture](packet-capture.md)
- [Credential storage](../security/credential-storage.md)
