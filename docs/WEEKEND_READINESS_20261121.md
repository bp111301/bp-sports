# Weekend readiness check — November 21, 2026

Compared immutable snapshots of the five production branches against current official schedules, plus current source coverage receipts. No model execution or forecast writes were performed by the check itself.

## Initial findings

| Sport | Saturday, Nov 21 | Sunday, Nov 22 |
| --- | --- | --- |
| NFL | No scheduled games | All 11 games saved; Monday's game is also saved |
| CFB | All 54 FBS-versus-FBS games saved | No scheduled FBS-versus-FBS games |
| NHL primary reference control | All 14 games saved | Five games missing from the primary ledger |
| NBA | All six games saved | All seven games saved |
| CBB | 49 saved forecasts; two newly announced DI games missing | 36 saved forecasts; two newly announced DI games missing |

CFB's four FBS-versus-FCS games lack the frozen model's required source inputs and remain intentionally outside coverage. Other lower-division college games are not added to the frozen models.

The CBB source receipt quarantined four tournament games because the old archive contained placeholder team IDs `-1/-2`. A fresh read of the current archive confirmed that all four identities, conference IDs, neutral venues and tipoff times are now populated and match the official live schedule. A normal producer refresh can therefore capture them under the existing rules; no adapter or model change is needed.

The four games are Indiana State–Middle Tennessee and East Carolina–Southern Illinois on Saturday; Stephen F. Austin–Temple and Utah Valley–UT Martin on Sunday.

Five already-saved CBB games also differ from the current official home/away designation or start time. These are review cases, not permission to rewrite or replace the first saved forecasts: Mercyhurst–Western Illinois, Butler–Nebraska, Fordham–San Diego, UAlbany–Mercyhurst, and Maryland Eastern Shore–IU Indianapolis. Existing grading safeguards remain in force.

## Cause and operational repair

The primary NHL producer last ran Friday at 19:06 UTC, and its saved 36-hour horizon excluded Sunday. CBB last ran Saturday at 07:13 UTC and still held the earlier placeholder source snapshot. Both scheduled refreshes were delayed, while scores, grading and the existing watchdog were healthy. Rebooting Streamlit would not generate missing forecasts.

Extend the existing watchdog to request the unchanged NHL producer when its latest completed run is at least 12 hours old and the unchanged CBB producer when at least six hours old. It already checks every five minutes and skips queued/in-progress runs. Existing cron expressions, frozen model rules, source identity checks and append-only forecast behavior remain unchanged. These are backup producer executions using the existing Actions permission, not new forecasting algorithms.

## Verification

- 174 main tests pass, including eight new overdue/fresh/active/queued producer dispatch cases. The frozen-bundle test uses a byte-identical temporary decoded bundle; no repository model file was created or modified.
- Preservation and whitespace checks pass. This operational repair changes only the watchdog and its tests.
- All five live sport boards rendered without application exceptions during the check: NFL 11 cards, CFB 54, NHL 14, NBA six, CBB 49 for their selected dates.
- Latest observed grading checks succeeded for all sports; the score feed and the watchdog were active.
- Streamlit was still on the pre-restart UI release. Reboot remains necessary to verify the newer application code.

Production refresh results must be verified after this repair is merged. Local source snapshots and coverage details are in `/workspace/bp-weekend-check-20261121/`.
