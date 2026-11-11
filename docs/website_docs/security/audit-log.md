# Audit log

Node Control does not write a plain-text audit log. There is no `audit.log`, and Safe Mode changes, sessions, and credential changes are not written to one.

Find Device port actions on Pro are stored in the local database. You can record every SSH session to a plain-text log. That recording is off until you turn it on in Settings → General → Session Recording, or with the Record toggle on the connection toolbar.
