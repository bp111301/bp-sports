# NHL fixed calibration protocol

Recorded before calibration results. Input is only the retained advanced_all_w20
season-walk-forward OOF predictions for 2021–22 through 2024–25. 2025–26 is never
loaded. Compare raw, scalar temperature (training log loss, bounds .25–4), and
sigmoid on probability logits (logistic C=1). Fit each season's calibration only
on earlier OOF seasons. First season remains raw for all methods. Compare methods
on the same 3,936 calibratable games in 2022–23 through 2024–25; report full 5,248
separately. No window/method/parameter search beyond these three fixed options.

Keep raw unless a method improves aggregate calibration-evaluation Brier and log
loss, preserves accuracy, and improves season Brier in at least three of four
seasons. The warm-up season is identical, so a calibrator must improve all three
remaining seasons. If both qualify, rank by Brier then log loss. Fit the selected
method on all development OOF labels for future use only, never evaluate that
refitted calibrator on the same development labels. Confidence buckets use
chronological calibrated probabilities, fixed intervals, and descriptive Wilson
intervals. These remain reused development diagnostics, not prospective results.
