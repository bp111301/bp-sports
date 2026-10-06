# Pregame starting-goalie collection — 2026-10-06

Collection only. Existing NHL model weights, model predictions, CFB V1 and
Candidate B remain unchanged. No goalie-adjusted prediction is issued yet.

Use Daily Faceoff's dated public starting-goalie board and its explicit
NewsStrengthName, goalie identity, NewsCreatedAt and original report link.
Match team pair, date and exact UTC start to the NHL schedule. DFO player IDs
are distinct from NHL IDs: resolve a unique normalized name within that team's
current NHL goalie roster. Ambiguous/unresolved matches cannot supply features.

Confirmed eligibility requires exact status `Confirmed`, a valid timezone-aware
report timestamp no later than our capture, a report link, a resolved NHL player
ID, and our capture strictly before scheduled puck drop. Keep Likely,
Unconfirmed and Unknown observations as their actual statuses. Never infer
confirmation from a goalie appearing in a box score or a morning-skate quote.

Append the first observed state and each subsequent change. Duplicate polls do
not overwrite records. A downgrade invalidates confirmed availability until a
later observed confirmation. Starter substitutions remain separate observations.
Availability begins at our own capture time, even if the report was published
earlier. Never backfill past games or use later confirmations at earlier model
cutoffs. The `available_at` helper enforces this boundary.

Archive compact matchup/status/roster snapshots with hashes and source links;
exclude article bodies, odds and source goalie performance summaries. These
snapshots contain enough evidence to audit every saved observation. Keep source
or mapping failures visible in the health summary and CI. No silent fallback to
realized starters. Observe only the upcoming 36 hours in the 2026–27 regular season.

Poll every 30 minutes through a research workflow registered on the default
branch, explicitly checking out/writing only `nhl-v1-research`. GitHub scheduling
can be delayed and late confirmations can be missed; measure coverage instead
of treating an absent confirmation as a goalie choice.

Before a future goalie-model test, record its fixed method, prediction cutoff,
control population and evaluation rules. Build goalie histories only from
completed earlier games at that cutoff. Archive goalie-adjusted probabilities
before games begin in a separate experiment. Source coverage or historical
inferred-starter results do not establish prospective model improvement.
