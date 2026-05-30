# Sharing libraries via GitHub

> Available on **Pro** and **AI** tiers only.

Node Control can synchronise your device library with a private GitHub repository. Useful when:

- Multiple engineers need to work from the same device list
- You want a backup beyond the local SQLite file
- You want change history (every library edit becomes a Git commit)
- You're handing a project off and want the new engineer to inherit your library

## How it works

Node Control serialises your library to a JSON file and pushes it to a GitHub repo of your choice. Other Node Control installations pull from the same repo and import the JSON.

- **Pushes** require a GitHub personal access token with write access to the repo
- **Pulls** can use either the same write token OR a separate read-only token (recommended for workstations that should never accidentally push)

## Setup

### 1. Create the GitHub repo

A private GitHub repo, owned by your account or org. Empty initially.

Suggested naming: `nodecontrol-library-<company>` or `network-inventory-<customer>`.

### 2. Generate personal access tokens

You'll typically generate **two** tokens:

**Write token** (for the engineer who owns the library):
- GitHub → Settings → Developer settings → Personal access tokens → Fine-grained tokens
- Repository access: only your library repo
- Permissions: **Contents → Read and Write**

**Read-only token** (for everyone else who pulls):
- Same flow, different permissions
- Permissions: **Contents → Read-only**

### 3. Configure in Node Control

**Settings → General → Default Library** tab:

- **Library repo**: `your-org/nodecontrol-library-acme` (or full URL)
- **Push PAT**: paste your write token (only needed on machines that push)
- **Pull PAT**: paste your read-only token (used for pulls; if blank, push PAT is used)
- **Auto-sync on library change**: optional — pushes a commit every time you edit a device

### 4. First push

If the repo is empty:

1. **Tools → Library → Push to GitHub**
2. Confirm — your local library JSON is committed to the repo
3. The commit message records the action and your machine name

### 5. First pull (on another machine)

1. Install Node Control Pro / AI with the same Library repo configured
2. **Tools → Library → Pull from GitHub**
3. A diff dialog appears showing:
   - **New sites**: sites in the remote library but not yours
   - **Removed sites**: sites in yours but not the remote
   - **Per-tab IP changes**: devices added, removed, or modified
4. Click **Apply** to overwrite your local library with the remote contents
5. Or **Cancel** to abort and review the diff

The diff-and-confirm flow is intentional — you won't accidentally nuke your local library on a fetch.

## Conflict resolution

If two engineers edit and push at the same time, the second push fails with a Git conflict. Resolution:

1. The losing engineer pulls (Tools → Library → Pull)
2. Reviews the diff to see what changed
3. Re-applies their local edits on top
4. Pushes again

There's no automatic merge — the library JSON is treated as a single document. For teams that edit concurrently, the practice is "pull before edit, push after edit, in short cycles."

## What's in the synced JSON

The library JSON includes:

- All devices (IPs, hostnames, site codes, tabs, device types, notes)
- Site detection regex
- Custom command preferences (if `device_command_prefs` table has entries)

It does **not** include:

- Credentials (passwords stay in the local OS keychain)
- App settings (UI state, paths, recent files)
- The `last_license_check` timestamps

So the JSON is safe to share — no secrets in it.

## Auto-sync vs manual

**Auto-sync on library change** (Settings → General → Default Library): commits a push every time you edit, add, or delete a device.

Pros:
- Always in sync; no risk of forgetting to push
- Full change history in the repo

Cons:
- A new commit on every keystroke during edits — repo gets noisy
- Slower app (each edit blocks on a GitHub API round-trip, ~500ms)

Most teams turn auto-sync **off** and push manually at end-of-session.

## Multiple libraries (per customer / per site)

If you manage networks for several customers, you can have a separate library repo per customer:

1. Switch the **Library repo** field in Settings to point at a different repo
2. **Tools → Library → Pull from GitHub** to load that customer's library
3. Your local library DB is fully replaced with the pulled contents

Switching libraries effectively "checks out" a different customer's network. Your previous local edits are gone unless they were pushed first — be deliberate about the order.

A future release may add named library profiles to make this switching less destructive — let us know if this is important to you.

## Audit trail

Every push and pull is logged locally in `library_sync.log` next to the DB file. The GitHub repo's commit history is the authoritative record of changes — `git log` shows who pushed what when, and `git diff` shows the device-level changes.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "401 Unauthorized" on push | Token expired or wrong permissions | Regenerate the token with Contents: Read and Write |
| "Push rejected — non-fast-forward" | Someone else pushed since your last pull | Pull first, then push |
| Pull shows no diff but you know the remote changed | Cache issue — restart the app | The library JSON is fetched once per session |
| "Repo not found" | Typo in repo path, or token doesn't have access to it | Verify in a browser that you can see the repo with the same account |

## Next steps

- [Library overview](overview.md)
- [Credential storage](../security/credential-storage.md) — why credentials don't sync
