# Serial console

The **Console** button is on the Engineer tab, beside **SSH** and **HTTPS**. It is on Free and Pro. Safe Mode hides it.

## What you need

A USB serial cable or adapter.

## Opening a console

Open it with **Console**, beside **SSH** and **HTTPS** on the Engineer tab.

The **Open Console** dialog says **Plug the console cable in and pick its port.**

The port list has **Refresh**. Known console chips are listed first: FTDI, Prolific, Silicon Labs, Cisco, and WCH. Other USB devices follow. An entry looks like `COM3 (FTDI FT232)` on Windows, or `/dev/cu.usbserial-…` on macOS. Bluetooth and debug ports are hidden. The last working port and settings are preselected. Driver hints show if nothing is found.

Then **Baud rate**, **Data bits**, **Parity**, **Stop bits**, **Flow control**, and **Open**.

The default is 9600 baud, 8 data bits, no parity, 1 stop bit, and no flow control. The offered rates are 1200, 2400, 4800, 9600, 19200, 38400, 57600, and 115200.

## Send Break (Ctrl+Pause)

**Send Break** sends a break on the serial line. The shortcut is **Ctrl+Pause**.

## Pasting at the line's baud rate

A paste is paced to the baud rate of the line.

## Log to file

**Log to file…** opens **Log console session to file**. It defaults to the session recordings folder. That folder is the Output Directory session output, otherwise the app's sessions folder. The file is named `console_<port>_<date_time>.log`. The extension can be `.log` or `.txt`. The folder and the name can both be changed.

The Engineer bar's **Record** toggle also records console tabs automatically.

## Reconnecting by adapter

Reconnect by the adapter.

## Safe Mode

Safe Mode hides **Console**.

## Next steps

- [SSH Terminal](ssh-terminal.md)
- [Local network terminal](local-terminal.md)
- [Safe Mode](../settings/safe-mode.md)
