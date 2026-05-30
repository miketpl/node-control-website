# Reading the crash log

When Node Control crashes — either with a Python exception or a Qt/C++ segfault — it writes a log file you can attach to a support ticket.

## Location

```
~/NodeControl_crash.log         (Mac, Linux)
%USERPROFILE%\NodeControl_crash.log   (Windows)
```

This is intentionally a top-level file in your home directory, not buried in app support folders. Easy to find when you need to.

## Format

Append-only — every crash adds to the bottom. The most recent crash is the last block in the file.

Each crash block has:

```
=== Crash at <ISO-8601 timestamp> ===
Node Control version: 0.9.29
Platform: macOS 14.5 (Darwin 23.5.0)
Python: 3.10.13

<Python traceback if available>

<Qt/C++ stack trace if available — captured via faulthandler>

=== End crash ===
```

## What to look for

### Python tracebacks (`Traceback (most recent call last):`)

These come from exceptions raised in Node Control's Python code. The last few lines show where the crash originated:

```
Traceback (most recent call last):
  File "controllers/find_device_task.py", line 412, in _on_done
    pd.finish(success=found > 0)
NameError: name 'found' is not defined
```

This kind of crash is usually a Node Control bug — please report.

### Qt / C++ stack traces

Crashes inside the Qt framework or PyInstaller's native bindings. Captured via Python's `faulthandler`:

```
Current thread 0x00007ff850dcb700 (most recent call first):
  File "ui/widgets/terminal_view.py", line 84 in resizeEvent
  ...

Stack (most recent call first):
0   QtCore        0x108450abc qt_message_output + 124
1   QtWidgets     0x108abcdef QWidget::resizeEvent + 88
```

These are harder to debug from the trace alone but the file/line context still helps.

### "Killed: 9" / "Segmentation fault"

The OS killed Node Control without a Python traceback. The `faulthandler` traceback may still be at the top of the crash block — that's the best clue. Common causes:

- Out of memory (very large topology runs on small machines)
- PySide6 library version mismatch
- macOS Gatekeeper interfering with an unsigned helper binary

## When to send the crash log

- Any reproducible crash — even if you can work around it
- Any crash you can't reproduce — we can still learn from the trace
- Crashes that started after upgrading — high-priority for us to investigate

## How to send

Email [info@nodecontrol.io](mailto:info@nodecontrol.io) with:

- The crash log (attach the whole file, or paste just the latest block)
- Node Control version (from Help → About, or the top of the crash log)
- OS version
- What you were doing when it crashed
- Repro steps if you can reliably trigger it

## Privacy

The crash log can contain:

- File paths from your filesystem (e.g., paths to libraries, settings)
- Hostnames or IPs from your library (if they appeared in the crashing function's local variables)
- Stack frames showing what code was running

It does NOT contain:

- Passwords or credentials (those are in the OS keychain, not in Python memory normally)
- Network device configurations
- Personal data of network end-users

You can review and redact the log before sending — it's a plain text file.

## Rotating / clearing the crash log

The crash log doesn't auto-rotate. If it grows large (>10 MB), feel free to:

- Rename it (`NodeControl_crash.log` → `NodeControl_crash_2026-05-25.log`) for archive
- Delete the file — Node Control re-creates it on next crash

## "Why did Node Control crash and not just show an error?"

Most user-facing errors (failed SSH, parser errors, network timeouts) are caught and shown in dialogs / run logs — they don't crash the app.

A crash happens when:

- An unexpected exception bubbles up to the top of a thread (Python error not caught)
- The Qt event loop hits an internal C++ assertion
- The OS sends a fatal signal (out of memory, segfault)

If you're seeing crashes for things that "should" be normal errors (e.g., a typo in a settings field crashes the app), that's a bug worth reporting.

## Debug mode for catching elusive issues

If a crash is happening intermittently and you want more context:

1. Settings → Advanced → enable **Debug logging**
2. Restart Node Control
3. Reproduce the issue
4. Quit Node Control

The debug log at:

```
~/Library/Application Support/netOps/debug.log
%APPDATA%\netOps\debug.log
```

Captures every internal event leading up to the crash. Larger and more verbose than the crash log, but often pinpoints the root cause more precisely.

Send both crash log AND debug log when reporting elusive issues.

## Recovery after a crash

After a crash:

- Your library and settings are safe (SQLite + JSON, both auto-saved frequently)
- Any in-progress task's results may be lost (re-run the task)
- Open SSH sessions are killed (re-open after relaunch)
- Recent UI state (e.g., which tab was active) may reset

If the app crashes immediately on launch (preventing you from using it at all):

1. Move `~/Library/Application Support/netOps/settings.json` aside — sometimes corrupted settings prevent launch
2. Launch — should come up with default settings
3. If still crashing, see [App won't launch](#app-wont-launch) below

## App won't launch

If launch fails:

1. **Mac**: try launching from terminal: `/Applications/Node\ Control\ Free.app/Contents/MacOS/Node\ Control\ Free` — captures any errors that the GUI launcher would silently swallow
2. **Windows**: try launching from Command Prompt: `"C:\Program Files\Node Control Free\Node Control Free.exe"` — same idea
3. **Linux**: launch from terminal directly — error output goes to stderr

Send the terminal output to support along with the crash log.

## Next steps

- [SSH connection problems](ssh-connection-issues.md) — most user-facing errors aren't crashes
- [Update problems](update-issues.md)
