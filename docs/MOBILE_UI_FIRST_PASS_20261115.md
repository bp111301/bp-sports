# Mobile UI first pass

This is a UI-only change for review. It has not been merged or deployed.

## Changes

- Overview starts with Game Center in the Games tab, defaulting to today's Central-time slate. Season Records is the next tab; its summary and record tiles no longer precede the games.
- All, Live, Upcoming and Final are native, tappable radio filters with counts computed after date/view, sport, search and My teams selection. All restores the entire selected slate, including postponed or unknown-status games. Finals include saved picks still awaiting grading. An elapsed start time alone does not imply that a game is live.
- Date, sport, search and My teams controls remain in a compact expander. Choosing a date switches to Selected date; Today restores the current Central date. Existing results/upcoming/all-tracked views remain available.
- Overview, daily results and all five default Compact sport boards reuse `compact_html` and the existing full-card matchup button. Cards show sport/status/time, teams and available scores, then saved pick/probability and Pick won, Pick lost, or Final · Awaiting grading. Ties remain excluded; unavailable probabilities and NFL QB review remain explicitly labeled.
- Game cards and season records use one column below 640px and two columns at tablet widths. Overview tabs and status filters wrap instead of requiring sideways scrolling.
- Existing theme, data paths, detailed model/research views and matchup dialogs are retained. The specialized Detailed board renderers are unchanged in this first pass.

## Verification

170 tests passed: 166 general tests, three saved-snapshot/config tests, and one frozen-bundle test against a previously decoded, byte-identical temporary copy. No model file was created or rewritten in the repository. The preservation gate and `git diff --check` passed.

New regression cases cover Central midnight, default Today and custom-date/reset behavior, status counts including ungraded finals, unknown and postponed games, empty slates, grade/probability rendering across all five sports, ties, and unavailable confidence. Existing snapshot, grading and workflow tests were retained.

Launched the real app locally on port 8511 and a deterministic UI preview on port 8512. Chromium viewport checks covered:

| Check | Widths |
| --- | --- |
| Overview, all status filters and season records | 360, 390, 768, 1024 px |
| NFL, CFB, NHL, NBA and CBB Compact boards | 360, 390, 768, 1024 px |
| Upcoming, live, graded win/loss and final awaiting grading, plus matchup taps | All four widths, all five sports |
| Real app with current data feeds | 390 and 768 px, Overview and all five boards |

The controlled run performs 44 layout checks, plus matchup-dialog interactions. No application exceptions, page-level horizontal overflow or clipped card/record containers remained. Phone cards were checked for full-width layout. Current-feed boards displayed 12 NFL, 1 CFB, 5 NHL, 9 NBA and 36 CBB matchups during the test.

## Findings and limits

Phone screenshots initially exposed paired record tiles with awkwardly wrapped percentages and labels. Explicitly stacking the native Streamlit columns below 640px resolved this; the final screenshots show full-width records and intact values. Tablet records retain two columns.

Tests use Chromium viewport emulation, not physical iPhone/iPad Safari. Analytics tables retain their existing intentional horizontal table scrolling. Data-source or grading exceptions remain governed by the existing pipeline; this change does not resolve them or change a saved prediction.

Local screenshots, browser scripts and JSON results are in `/workspace/bp-mobile-evidence/`, including `360-card.png`, `360-records.png`, `768-records.png`, `browser-results.json` and `real-results.json`.

Frozen weights, saved forecasts, historical evaluations, grading code and workflow schedules are unchanged. The prospective release marker is `dashboard-mobile-20261115`; production remains untouched pending review.
