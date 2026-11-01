# Draft copy for the 0.9.46 Pro trial

Not live. Do not paste this into the site until Mike says so.

The Free Edition is still 25 devices with no time limit. The new thing is a 14-day Pro trial that can run on a Free licence. These lines replace the sentences that say Free is not a trial. Nearby lines that only say "no time limit" stay as they are.

## Announcement — template `trial-0.9.46`

Respects the product-notice opt-out.

Subject: A 14-day Pro trial is in Node Control 0.9.46

Hi,

Node Control 0.9.46 includes a 14-day Pro trial on the Free Edition.

Update from inside the app, or from https://nodecontrol.io. On a new install the trial starts when you activate. If you already use Free, open Help and choose Start 14-day trial. The 14 days start when you press that button.

The trial covers the engineer tasks and reports, and bring-your-own AI. It stays on the first computer. After day 14 the app goes back to Free. Your library stays.

If anything does not work, reply to this email.

Mike
Node Control

## Day 11 — template `trial-day11`

Does not respect the product-notice opt-out. It is part of the trial the person started.

Subject: Your Node Control Pro trial ends in a few days

Hi,

Your 14-day Pro trial has three days left. After it ends, Node Control goes back to the Free Edition. Your library stays on this computer.

If you want to keep the Pro tasks, upgrade from inside the app. Billing starts on the day you pay.

Mike
Node Control

## Day 14 — template `trial-day14`

Does not respect the product-notice opt-out.

Subject: Your Node Control Pro trial ends today

Hi,

Your 14-day Pro trial ends today. Tomorrow Node Control is the Free Edition again. Your library stays on this computer.

If you want to keep the Pro tasks, upgrade from inside the app. Billing starts on the day you pay.

Mike
Node Control

## Privacy line

Proposed addition to `privacy.html`, under "The app and the licence server" (after the paragraph at line 99). Not applied.

We store a one-way, keyed hash of a computer identifier to allow one trial per computer. It cannot be turned back into the identifier and is deleted on request.

Retention, for the "How long we keep it" list (after line 149): the trial row is kept with the licence, and deleted or anonymised on request. It holds the keyed hashes, the start time, and the end time. It does not hold the computer identifier.

## Proposed replacements

### `index.html` line 60

Current: Free Edition is up to 25 devices, with no time limit. It is not a trial.

Proposed: Free Edition is up to 25 devices, with no time limit. A 14-day Pro trial is included. It starts on a new install, or from Help if you already use Free.

### `index.html` line 655

Current: Free Edition is up to 25 devices, with no time limit. It is not a trial.

Proposed: Free Edition is up to 25 devices, with no time limit. A 14-day Pro trial is included. After it ends, the app is Free again.

### `terms.html` line 58

Current: The Free Edition runs on your computer. It covers up to 25 devices and has no time limit. It is not a trial.

Proposed: The Free Edition runs on your computer. It covers up to 25 devices and has no time limit. A 14-day Pro trial may run on that licence. The trial stays on the first computer and ends after 14 days.

### `docs/index.html` line 164

Current: Install it, add your switches, and draw an L2 map from SSH. Free is 25 devices, with no time limit. It is not a trial.

Proposed: Install it, add your switches, and draw an L2 map from SSH. Free is 25 devices, with no time limit. A 14-day Pro trial is included.

### `docs/website_docs/index.md` line 5

Current: Free is 25 devices, with no time limit. It is not a trial.

Proposed: Free is 25 devices, with no time limit. A 14-day Pro trial is included.

### `docs/tiers/overview.html` line 153

Current: Node Control is one codebase with three gates. Free is the one to start with: 25 devices, no time limit, not a trial.

Proposed: Node Control is one codebase with three gates. Free is the one to start with: 25 devices, no time limit, plus a 14-day Pro trial.

The rest of that paragraph stays.

### `docs/website_docs/tiers/overview.md` line 3

Same current sentence and the same proposed change as the HTML above.

### `AGENTS.md` line 32

This is the agent brief, not a public page.

Current: Free Edition is up to 25 devices, no time limit, not a trial. Say so on the free section.

Proposed: Free Edition is up to 25 devices, no time limit. A 14-day Pro trial can run on it. Say both on the free section, once the trial copy is live.

Lines that say only "no time limit" and do not say "not a trial" are left alone. That includes the Free card, the compare table, the docs index link text, and the library overview.
