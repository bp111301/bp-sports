# CFB rivalry-week readiness — November 28, 2026

All 53 supported FBS-versus-FBS games on Saturday have both current forecasts and
immutable saved first picks. Exact kickoff times agree with official ESPN event
headers, and every saved capture precedes the official kickoff. All 13 Friday
games are settled with scores matching official completed finals. The CFB record
at the check is 303–137 over 440 graded games; 57 saved games remain pending,
including later games beyond Saturday.

The daily ESPN response returned only 25 Saturday games despite `limit=1000`.
The readiness check resolved the remaining 28 directly by saved event ID. Existing
score and grading code already has direct-event fallbacks and was not changed.
Live inspection confirmed current picks and probabilities on Compact and Detailed
CFB boards without an application exception. Backend rows establish the exact
53-game count; approximate visual counts are not used as coverage evidence.

The CFB producer's most recent completed refresh was Friday at 19:13 UTC. Its
scheduled runs have been arriving later than the intended morning slot, while
grading and score refreshes continue successfully. The existing watchdog covered
NHL, CBB and NFL but had no CFB producer backup. Add an overdue-only CFB dispatch
after 12 hours, using the existing five-minute watchdog loop, while skipping active
and queued runs. No cron expression changes.

Add a post-publish CFB coverage check for missing supported forecasts or features.
A gap is reported as a failed capture check only after valid forecasts and receipts
are preserved. Missing coverage metadata is not reported as healthy. Unsupported
FBS-versus-FCS coverage does not trigger a false supported-model failure.

Verification: 216 main tests and 13 challenger/input-receipt safety tests pass.
New regressions cover fresh/overdue/active/queued CFB dispatch decisions, supported
input/forecast gaps, missing coverage and preservation-before-alert step ordering.
No UI layout, frozen models, saved forecast fields, historical evaluations, grading
logic or workflow schedules change. Normal production refreshes may append eligible
new first forecasts and separately logged later input receipts.

Readiness evidence: `/workspace/bp-cfb-nov28-evidence/`.
