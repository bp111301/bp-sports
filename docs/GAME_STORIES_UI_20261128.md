# Game stories and navigation — review build, November 28, 2026

This branch incorporates the unmerged mobile foundation from PR #18 and adds a friendlier interface and sourced matchup stories. It is not deployed; the earlier instruction to leave UI deployment for review still applies.

## User experience

- Overview opens with today’s games in Central time. Season records remain one tap away. Existing date, sport, search and My teams controls are retained.
- All, Live, Upcoming and Final show counts using the existing game status logic. Show more renders 24 additional cards and resets after any slate/filter change, including an empty filter.
- Shared cards across all five Compact boards show sport/status, teams/scores, saved pick/probability, and graded or awaiting-grading state. Tapping opens the shared details dialog, now also used by CBB.
- Responsive navigation, reduced blank space, readable records and metrics, and accessible native controls retain the Streamlit theme.
- Matchup synopsis tells the story through scoring versus opponent allowance, sourced season records, the last five results, side-by-side comparisons and verified prior meetings when available. Recent-game details and source links are expandable. Missing context is explicit; no injuries, stakes or rankings are invented.

## Source and preservation boundaries

Stories are presentation-only. The builder never loads model weights or writes forecasts. Existing saved context for games already started is not refreshed. Result cutoffs exclude same-day and future results; reconstructed historical context carries an observed timestamp and a disclosure rather than claiming to be an original pregame receipt.

Current regular-season sources provide team form. NFL/CFB/NBA/CBB also look back one season for meetings; NHL uses available current-season club schedules. CBB stories are generated within a three-day upcoming window. The NBA source uses schedule archives instead of unreliable per-team requests. The dashboard prefers the refreshed remote story feed with saved local fallback. The existing preview refresh schedule is unchanged; its dependency and safeguard tests are updated.

No model artifacts, forecast files, historical evaluations, grading rules or workflow schedules are changed. Newly generated review context is outside the repository and is not included in this PR.

## Verification

- Full existing suite plus regressions: **240 passed**.
- Source build: all five sports, **zero source errors**, isolated output. Added 11 NFL, 58 CFB, 14 NHL, 280 NBA and 165 CBB contexts; generated context is not committed.
- Local Streamlit browser checks with read-only production feed snapshots: **36 checks** at 390, 768 and 1280px, including each sport and its story dialog. All 15 opened stories contain comparisons.
- Synthetic upcoming/live/won/lost/final-awaiting-grading scenarios: **44 checks** at 360, 390, 768 and 1024px. Each sport opens correctly; no browser exceptions, clipped records or horizontal page scrolling detected. These are labeled synthetic scenarios, not live results.
- Show more and empty-filter reset covered in both AppTest and browser checks.
- Local screenshots and logs: `/workspace/bp-ui-stories-evidence/`. Tested Chromium viewport emulation, not physical iOS Safari. Live deployment and the post-deployment scheduled refresh are not verified because this change awaits review.
