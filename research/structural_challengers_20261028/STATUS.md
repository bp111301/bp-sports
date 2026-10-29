# Status of structural-model research

The registered CatBoost/scoring-model experiment ran locally and reported no recipe passing all joint accuracy-and-confidence rules. Its final code and complete prediction artifacts were not committed before the workspace was cleared. It has not completed artifact preservation and independent reproduction, so it is not a deployable or promoted challenger.

Preserve the registered protocol. Rebuild and rerun all planned recipes before relying on their detailed metrics. Do not reconstruct prediction rows or evaluations from remembered summaries. The separately saved confidence-projection package uses previously committed immutable archives and has been rebuilt and independently reproduced; it does not depend on this unfinished structural run.
