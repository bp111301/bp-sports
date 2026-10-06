# Bounded additional NHL factor protocol

Recorded before results; no CFB changes. Development seasons: 2021–22 through
2024–25, each trained on earlier seasons beginning 2018–19. All factor inputs
are truncated at 2024–25. Existing team-stat leader is the reference. Fixed
logistic model C=.5, preprocessing fit only on each training fold. No parameter
or window search. Persist per-game out-of-fold probabilities for later auditing.

Candidates: reference; three 20-game opponent-strength/scoring-residual features;
four travel/congestion features; the two blocks together. If MoneyPuck's listed
public team-game CSV is available and matches at least 99% of development and
training team-games, also run a fixed 20-game expected-goals block and all blocks
combined as exploratory candidates only. No retrospective third-party xG model
can be promoted without evidence of its training vintage. Missing source does
not prevent the opponent/schedule tests from running and is explicitly reported.

Opponent features use the opponent's Elo and prior scoring/conceding averages
as they existed before the historical game. No full-season strength adjustment.
Travel is approximate great-circle distance from the previous game's venue to
the current home team's normal arena. Actual flights, neutral-site games and
some historic arena changes cannot be reconstructed; these are limitations.
Congestion counts previous games in the last 3/7 days, and away streak is based
only on previous games. Outcomes update after all predictions for each date.

Promotion requires improved aggregate Brier and log loss, accuracy at least as
high as the team-stat reference, and better Brier in at least 3/4 seasons. These
are reused development results, not confirmation of future performance. Retain
reference if no non-exploratory candidate passes. No deployment or frozen NHL
bundle is created by this experiment. Injuries and confirmed goalies remain
untested because timestamped historical pregame availability has not been secured.

MoneyPuck.com download source: https://moneypuck.com/data.htm
Listed CSV: https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv
Used for noncommercial research, with MoneyPuck.com credit in outputs.
