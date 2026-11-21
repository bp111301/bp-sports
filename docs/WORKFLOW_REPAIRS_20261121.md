# Workflow failures investigated November 21, 2026

## Repeated NHL confidence-research failures

The latest failed run was [44898834398](https://github.com/bp111301/bp-sports/actions/runs/44898834398), November 21 at 11:22 UTC. Its collection step raised `Official stat feeds disagree: powerPlayGoalsFor`. Reference receipt replay and the existing safety tests passed before collection; the failure was in live source ingestion, not model weights.

The NHL REST reports now cap a response at 100 rows even for `limit=-1`. At investigation time, summary, powerplay and penaltykill each advertised 716 total rows but returned only 100. Their truncated subsets did not align. The merged inputs therefore had 84 summary rows with missing special-team fields, and the independent game-center parity check correctly rejected them.

A read-only reproduction against game 2026020123 produced the exact original error. Explicitly paging each report retrieved all 716 rows in eight pages, removed the missing fields, and passed the unchanged independent count-parity check. A full input-only validation then covered 358 current-season final games, 10,139 total historical/current games and 20,278 team-input rows without any fallback games. No forecast generation, model fitting, settlement writes or historical evaluation was performed during this validation.

The repair uses deterministic game/team sorting, follows the advertised total, preserves every page's source receipt, and rejects duplicate identities, empty premature pages, changing totals, malformed totals and excess rows. Genuine source disagreements still fail. Historical source files, frozen recipes and qualification rules are untouched.

## CFB publication conflict

[Run 44789251644](https://github.com/bp111301/bp-sports/actions/runs/44789251644), November 20 at 18:04 UTC, built and validated its CFB outputs but failed while rebasing `data/cfb/ledger/summary.json`. Checkout used the scheduled event's old commit, even though the existing CFB concurrency group serialized it behind more recent grading.

CFB now explicitly checks out current `main`, as the NFL and confidence collectors already do. Its existing concurrency group and schedule remain intact. The repair does not resolve conflicts by overwriting data or force-pushing.

## Other historical alerts

- November 17 NBA grading publication encountered repeated GitHub `Internal Server Error` responses. Add short backoff between the existing bounded push retries rather than immediately repeating all attempts. Latest grading runs were successful during investigation.
- November 18 goalie collection received HTTP 403 from Daily Faceoff. Latest goalie collection succeeded on November 21. Provider blocks are still reported; no access restriction is bypassed and no missing starter is fabricated.
- November 18 CBB grading reported degraded source checks, while preserving valid grades and health receipts. Latest grading runs succeeded. These legitimate provider failures are not hidden.
- November 16 score publication received GitHub bot HTTP 403. Current score publication runs succeed with the existing write permission. No permission policies changed.

A pre-existing NFL UI regression test also assumed the checked-in slate always contained an unfinished game. The local full-suite run exposed that assumption after the slate had finished. It now uses a deterministic, read-only test fixture instead of depending on current saved-game status.

## Validation and deployment

- 162 main tests passed: 158 general tests, three saved-snapshot/config tests and the frozen-bundle test using a byte-identical temporary decoded bundle.
- 31 confidence-collector, official-count, frozen-history and projection safeguards passed, including seven new pagination cases.
- Full live NHL input validation and an independent official game-center count comparison passed.
- Preservation and whitespace checks passed. No model artifacts, saved forecasts, historical evaluations, workflow schedules or historical sources changed.
- Prospective app release marker: `dashboard-source-repairs-20261121`.

The separate mobile UI PR is not included in this repair. Production workflow results and the hosted app's release marker must be checked after merge; a successful repository merge alone does not prove Streamlit has reloaded.

## Follow-up: make refreshed NFL forecasts visible without preview lag

Post-merge checks confirmed successful production NHL collection (19 new paired forecasts, 12 settlements, no source errors), successful CFB/NFL publication, and successful grading for all five sports. They also exposed a presentation dependency: newly saved NFL games had no date until the separate matchup-preview feed and score archive had caught up. Overview consequently counted zero upcoming NFL games while 12 new forecasts were already saved.

The dashboard and presentation-only score builder now fall back to the verified kickoff in the saved NFL availability check, but only when the game key and both teams match. Existing verified score starts retain precedence; missing or mismatched metadata remains unavailable. No forecast, probability or grading decision is changed. This uses an already loaded source and adds no dashboard feed requests.

With the current saved data and no previews/scores, Overview now renders 12 upcoming NFL picks; the NFL board defaults to November 22 and displays that day's 11 games, with the remaining game on November 23. The score archive can resolve the same newly published games directly, without waiting for preview generation.

Four regression tests cover unchanged saved probabilities, date selection without previews, identity rejection, official-score precedence and archive targeting. The follow-up passes 166 main tests (162 general plus the four frozen/saved-snapshot checks). The earlier 31 research safeguards remain applicable to the unchanged collector. Updated release marker: `dashboard-source-repairs-20261121.1`.
