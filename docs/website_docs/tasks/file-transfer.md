# File Transfer

Two different things share this name.

The **File Transfer** sidebar page is on **Free**, **Pro**, and the **AI** edition. Nothing on that page is tier gated.

The **File Transfer** Engineer task is Pro and the AI edition. On Free it is greyed out, with the tooltip **Upgrade to Pro to unlock this feature**. Safe Mode hides the task. Safe Mode does not remove the sidebar page.

## The File Transfer page

There is no TFTP server on this page.

### Local server

The server speaks SFTP and SCP.

- **Listen on**
- **Port**, default `2222`
- **Root Directory**, default `~/sftp_root`
- **Start Server** / **Stop Server**
- Username `ncuser`, with a random 16-character password shown while the server is running
- Example commands for Cisco, PAN-OS, and Linux

### Remote client

The section is collapsed, and its title is **Remote client - send / fetch to an SFTP server**. It is on Free as well as Pro and the AI edition.

## The File Transfer task

The task pushes or pulls a file to or from device flash over SCP or TFTP, via Netmiko.

The dialog is **File Transfer**:

- **Upload to device** / **Download from device**
- **Local File Path**
- **Remote File Path** (for example `flash:filename.bin`)
- **Transfer Method**, SCP or TFTP
- **Start Transfer**

## Next steps

- [Packet Capture](packet-capture.md)
- [Config Backup](config-backup.md)
