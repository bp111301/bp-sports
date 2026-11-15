# Operational repairs — November 15, 2026

These changes repair forecast persistence, grading orchestration and presentation. They do not change model coefficients, feature formulas, historical evaluation results, or existing forecast data. No production forecast or settlement job was run while implementing the repairs.

## Changes

- Remove an obsolete Weekly results revision check that reloaded the overview module on every visit and discarded offline test fixtures. Keep deployment revision expectations aligned.
- Recheck CFB V1 and Candidate B kickoff eligibility after inference. Reject unknown/TBD times and games that started while processing.
- Preserve the original strings of existing CSV forecast cells when appending or settling; avoid probability precision drift. Replace settlement files atomically and skip unchanged ledgers.
- Route both NFL grading entry points through official completed/post evidence, matching teams and valid pregame timestamps. Reject fractional or otherwise invalid final scores. Legacy missing-kickoff rows use independently verified actual kickoff evidence without editing their saved fields.
- Preserve other verified results when an individual provider request times out. Record degraded/failed attempt health and still fail the Action after saving valid results and health. CFB can resolve official event results from saved identities if the bulk schedule endpoint is down.
- Keep NHL, NBA and CBB forecast times separate from results-check times. Overview freshness uses the primary model's saved captures, so a grader or parallel experiment cannot hide stopped primary capture.
- Publish lifecycle annotations separately from forecasts for postponed, cancelled and mismatched basketball events. Keep CFB confidence-shadow start reviews visible. Do not grade a saved matchup against a replacement opponent.
- Keep NHL predictions available if optional goalie endpoints fail.
- Check CBB capture health after saving valid results. Require existing frozen CFB/NHL artifacts in recurring jobs; missing bundles must not silently trigger a refit.
- Add a publishing guard that rejects removed/duplicate forecast identities, changes to existing forecast fields, and modified frozen artifacts or historical results. Enable it for NFL/CFB publishing and all five final-check jobs.

## Validation

The main test suite runs in a disposable copy with the committed NFL base64 bundle restored there. The selected confidence-shadow/challenger tests run in their required research dependency versions. Regression coverage includes kickoff crossing, TBD times, exact forecast precision, wrong/live final evidence, provider failure isolation, failure-health persistence, forecast freshness, optional goalie outages and preservation-gate rejection.

The updated graders were also exercised against disposable copies of the saved NFL, CFB, NHL, NBA and CBB branch snapshots with fixture-only provider responses. Existing forecast fields and every model artifact hash remained unchanged. These checks do not regenerate forecasts, refit models or replay historical evaluations.

Workflow YAML and embedded Bash syntax are checked separately. Local validation does not establish that every live upstream provider or GitHub schedule will be available after deployment.

## Deployment and follow-up

The shared final-check runner and its preservation guard are loaded from `main`, including for the NHL/NBA/CBB data branches. The CBB post-capture health helper is also loaded from `main`. Merge the operational PR before invoking those workflows. The sport branches' frozen inference code and manifests remain unchanged.

Known event identity and start-time disputes stay ungraded until their evidence is reviewed. Postponed games remain outside the graded record. No old predictions should be overwritten, deleted, backfilled or recreated to clear those annotations.

Watch the first genuine capture and final-check runs after deployment, not just green gated no-op runs. Polling/watchdog optimization and publishing all dashboard components as a single versioned snapshot remain follow-up work; this patch preserves existing schedules rather than removing fallback checks without runtime measurements.
