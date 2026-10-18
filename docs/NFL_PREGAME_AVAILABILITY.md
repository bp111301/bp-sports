# NFL pregame availability refresh

The NFL V4 bundle and its coefficients remain frozen. New regular-season inputs
can change pregame forecasts; no historical evaluation is rerun or retuned.

The existing prediction workflow keeps its Thursday/Sunday morning refresh and
also checks actual kickoff times every 15 minutes. A full refresh is eligible
within 100 minutes before any unstarted game, including international games,
Monday games and Saturday games. This is an approximate pregame window: GitHub
queues and source publication can delay checks. The UI displays actual check times.

Sources are the official NFL injury tables, the linked current-week official
inactive article, and explicit official NFL starter headlines. NFLverse supplies
schedule inputs and a unique GSIS player identity when a replacement is resolved.
Team-sourced manual QB confirmations remain supported in `config/qb_overrides.json`.
Current-week confirmation URLs and verification times are retained.

An explicit starter announcement is eligible for automatic resolution only with
matching team/opponent, publication within seven days and before capture, a
unique QB identity, and an unambiguous will/to-start headline. Expected, likely,
planning and questionable reports do not qualify. Missing or ambiguous evidence
stays unconfirmed. The system does not infer a replacement from depth-chart order.

Out and Inactive differ from Questionable and Doubtful. A missing inactive section
means pending, not an active roster. A player absent from the injury report is not
claimed confirmed active. Report season/week and both matchup teams must match.
The collector preserves already-started game contexts rather than backfilling
availability after kickoff.

Confirmed QB changes use the existing tested V4 QB inputs. If the assumed QB is
confirmed out/inactive and a replacement cannot be verified, the new forecast is
flagged QB_INPUT_REVIEW_REQUIRED and is not appended as an eligible forecast.
Other offensive, line and defensive absences are visible context only: no new
probability penalties have been invented for them.

Latest valid pregame forecasts are displayed on pending compact cards and game
details with an Updated pregame label. The original first-snapshot prospective
record is retained; settled cards use that record snapshot. Data, model identity,
capture time and kickoff are checked before applying a display-only refresh.
The original ledger is never changed merely to improve its historical record.

`data/current/nfl_availability.json` stores source receipts, player statuses, QB
assumptions, actual check times and latest valid pregame context. Runtime effective
overrides are generated separately from the owner-maintained confirmation file.
Current feeds and new ledger rows are written only for games still unstarted when
forecast computation completes. Late or missing reports remain visible as pending
or delayed. No claim of comprehensive all-news analysis or automatic confirmation
of every starting player is made.
