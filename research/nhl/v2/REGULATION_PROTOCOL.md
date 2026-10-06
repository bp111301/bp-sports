# NHL V2 regulation-strength protocol — 2026-10-06

Recorded after the bounded model-structure tournament found no eligible candidate,
but before regulation experiments. No V1 frozen artifact changes. CFB untouched.

Hypothesis: regulation scoring/team strength is less distorted by extra-time
winner noise than binary final-game form. Reconstruct regulation goal totals by
removing the one winning goal in an overtime/shootout final score. Treat those
games as a .5/.5 regulation result when updating Elo and rolling win form. This
is outcome reconstruction after completed games, never a current-game input.

Fixed five candidates: V1 reference; same logistic with regulation-form features;
three-class logistic for regulation home win/tie/away win; independent home/away
Poisson regressions with alpha=1 for regulation goals; fixed 50% V1 / 50%
three-class blend. Three-class and Poisson models convert regulation ties using
a fixed .5 extra-time home win chance. No probability or blend-weight tuning.
All logistic settings remain C=.5. Advanced 20-game team-stat features are held
constant to isolate outcome/form construction, including their limitations.

Development and training boundaries match the previous V2 protocol. No 2025–26
alternative-model scoring. Promotion as a research candidate requires better
aggregate Brier/log loss, preserved accuracy and Brier improvement in >=3/4
seasons. Development is already reused; later timestamped prospective results
are required before claiming reliable improvement. V1's failed release remains.
