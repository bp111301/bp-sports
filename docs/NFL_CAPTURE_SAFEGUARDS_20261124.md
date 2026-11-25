# NFL capture and QB evidence safeguards

The next NFL slate can begin before the Thursday morning refresh, and a green
Actions result can mean all generation steps were skipped. Capture now checks
saved coverage within 72 hours of the first kickoff of the next unstarted
regular-season week. Missing coverage or forecasts older than 24 hours request
generation, with a one-hour early retry cooldown. The existing 100-minute kickoff
window and Thursday/Sunday morning checks remain. No cron expression, model
formula, weight, risk threshold, grading rule or historical evaluation changed.

The watchdog uses the same standard-library gate to dispatch overdue NFL
generation. Active/queued runs are skipped. Gate and post-build health report
actual saved forecast times separately from build and grading times. Post-build
missing/stale coverage and QB holds fail the job after preserving valid outputs.
Availability warnings remain separate: coverage ready does not mean confirmed starters.

QB evidence records each side's identity, assumption source, observation and
confirmation times, uncertainty and contradictions. Explicit official starter
headlines are considered even when the schedule QB is not marked Out; they must
match team/opponent, have timely publication and resolve to a unique GSIS identity.
Fresh saved confirmations survive a headline leaving the front page. Conflicting
confirmations, missing identities, future-dated overrides, stale/wrong-matchup
context, and unresolved confirmed absences block new snapshots. An outage cannot
clear a saved absence hold. Known schedule QBs without explicit confirmation remain
labeled, eligible early assumptions. Missing injury designations never confirm activity.

Each new eligible prediction has an append-only audit receipt with the same ID.
Input hashes are checked against runtime files, and receipts after capture are
rejected. Receipts retain feature values/missingness, component probabilities,
source evidence, feature cutoff and bundle identity. They do not alter saved
predictions or backfill old provenance. Raw PBP is not committed. The publishing
verifier protects existing audit records.

## Validation

- Offline regressions cover early Wednesday games, complete/missing/stale
  coverage, fresh build times hiding stale forecasts, kickoff windows, retry
  cooldown, invalid snapshots, starter changes, contradictions, retained evidence,
  missing IDs, future timestamps, input tampering and append-only capture.
- An isolated run with fresh 2026 schedule/PBP produced all 16 Week 12 forecasts
  and 16 matching receipts, preserving all 2,056 saved rows and exact decimals.
- The original builder with identical inputs and feature cutoff returned identical
  V3/V4 picks, confidence columns and risk flags for all 16 games.
- Decoded bundle SHA256 remains
  `e048a8ab2602c911cb8cd6027f6b944273ffe9761dfcdda15da6325c39d6efc3`.
- The official injury page still served another week at validation. Forecasts
  explicitly retain unconfirmed QB assumptions and source warnings. This change
  does not claim to solve unpublished or unavailable official reports.

Local evidence: `/workspace/bp-nfl-safeguards-evidence/`.
