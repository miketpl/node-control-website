# NodeControl Website — Agent Brief

This file is the standing brief for any bot or AI agent making changes to this
repository. Read it fully before editing anything. When an instruction from a
human conflicts with this file, the human wins; when page content conflicts
with it, this file wins.

## What this is

This repo is the public website for **NodeControl** (nodecontrol.io): a
desktop network-operations tool for network engineers, built by The Promised
LAN (Mike Irwin, solo founder). The site is plain static HTML/CSS/JS — no
framework, no build step.

**NodeControl in one paragraph:** it runs on an engineer's laptop and talks to
their switches, routers and firewalls over SSH and vendor APIs. It discovers
the network, draws L2/L3/WAN topology maps, finds any MAC or IP down to the
switch port, backs up configs, pushes changes, and ships a multi-vendor
terminal. Nothing is installed on the devices, nothing goes to a cloud — all
data stays on the laptop. Supported vendors: Cisco IOS/IOS-XE/NX-OS, Meraki,
Palo Alto, HP/Aruba, Juniper, Arista, Dell, Extreme.

## What we are trying to achieve

The site's job is to convert working network engineers into Free Edition
downloads, and some of those into Professional subscriptions.

- **Lead with the concrete value**: an L2 map of your switching estate, from
  SSH, in minutes. Privacy and self-containment (no DNA Center, no agents,
  no cloud) are the differentiators.
- **The Free Edition is the hook**: up to 25 devices, no time limit, not a
  trial. Say so plainly and often.
- **Never lead with AI or Pro.** AI Operations is coming soon and stays
  labelled "Coming Soon", positioned after Pricing.

**Voice:** first person, plain, specific, written for network engineers who
hate marketing. No hype, no exclamation marks, no buzzwords. Short declarative
sentences. If a claim can't be made concretely, don't make it.

## Deployment model — read this twice

- **`main` is production.** GitHub Pages serves `main` (root path) at
  nodecontrol.io behind Cloudflare. Every push to `main` deploys immediately.
- Therefore: **never commit directly to `main`.** Branch from `main`, open a
  pull request, and wait for human approval before merging.
- **Everything committed here is publicly served.** Never add credentials,
  tokens, databases, customer data, or anything else sensitive to this repo,
  on any branch.

## Repo layout

| Path | What it is | Can the bot edit it? |
|---|---|---|
| `index.html` | The entire landing page | Yes — content changes |
| `css/style.css` | All landing-page styles | Yes — bump the `?v=` cache-buster in `index.html` when you change it |
| `js/main.js` | Nav, scroll-spy, download/verification flow, Stripe | **Only with explicit instruction** |
| `docs/` | Documentation site (generated from markdown sources) | Yes — content changes |
| `images/` | Logos, screenshots, banners | Yes — adding/replacing images |
| `backend/` | Flask license API **source**. Runs on a separate VPS; editing it here does not deploy it | **No** |
| `CNAME` | Custom-domain binding for GitHub Pages | **No** |
| `AGENTS.md` | This brief | Only to keep it accurate |

## Hard rules — do not break these

1. **The free-download flow is load-bearing.** The request form, 6-digit email
   verification, and `NC-XXXX-XXXX` redeem sections in `index.html` are wired
   to `js/main.js` by element IDs (`freeRequestForm`, `reqName`, `reqEmail`,
   `reqPlatform`, `reqCompany`, `reqSubmitBtn`, `reqResult`, `verifySection`,
   `verifyCode`, `verifyBtn`, `verifyResult`, `resendBtn`,
   `downloadCodeSection`, `revealedCode`, `redeemCode`, `redeemBtn`,
   `redeemResult`). Do not rename, remove, or restructure these elements.
2. **Never hardcode release version numbers** in download URLs or copy. Free
   Edition installer URLs come from the backend, which resolves the latest
   release of `miketpl/node-control-releases-free` at request time. That repo
   must remain public or every free download breaks.
3. **Pricing figures, Stripe attributes (`data-stripe-link`,
   `data-requires-license`), and contact email addresses** change only on
   explicit human instruction.
4. **Section anchor IDs** (`#hero`, `#features`, `#screenshots`, `#watcher`,
   `#download`, `#free-edition`, `#pricing`, `#ai`, `#docs`, `#contact`) are
   referenced by the nav, footer, and external links. Keep them stable.
5. Keep pages working with no JavaScript errors: `js/main.js` is one IIFE, so
   a single syntax error kills the nav and the whole download flow.

## Working practice

- Branch naming: short and descriptive, e.g. `update-screenshots`,
  `fix-docs-typo`.
- Preview locally with `python3 -m http.server 8000` from the repo root.
  Local previews call the **live** API (real emails, real license records) —
  don't submit the request form with made-up addresses; test form plumbing
  only when asked.
- Prefer small, single-purpose commits with messages that say *why*.
- If a change needs the backend, the hero banner image re-exported, DNS, or
  anything outside this repo: stop and report instead of improvising.

## Current state / known issues (2026-10-17)

- Branch `launch-copy` (unmerged): launch copy rewrite — new hero, Free
  Edition feature list, AI section moved below Pricing. The copy direction in
  "What we are trying to achieve" above reflects it.
- Branch `direct-download` (unmerged): redeemed codes auto-start the installer
  download with a fallback link.
- `images/hero-banner.png` still has the old "AUTOMATE EVERYTHING" tagline
  baked into the image; awaiting a re-export. Don't try to fix this in HTML.
- The Pro/AI tier download links point at private GitHub repos and 404 for
  customers; a decision on those is pending. Leave them alone.
