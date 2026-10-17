# Spectra benchmark

NMR shift predictors against experimental shifts of nmrshiftdb2 molecules held out of the local index, produced by `backend/scripts/eval_spectra.py`. Each run is appended below.

"local" is the index on its own, per atom; "site" is what the Spectra card shows, one shift per symmetry
class (measured shifts are never used here, since the test molecules are left out of the index). The
nmrshiftdb2 prediction service in S0 already contains the test molecules, so its numbers are close to
a lookup and not comparable; it is also why the card now shows a compound's measured shifts directly.
S0 waited for three examples before trusting an environment; S1 and later take the widest match. S3
leaves out the predicted spectra some records carry (their Program field), in the index and the test set.

## S0 baseline: rules on the card, local index alongside (2026-10-16)

4355 held-out nmrshiftdb2 molecules, scored in 225 s.

**13C**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 2 | within 5 |
|---|---|---|---|---|---|---|---|
| local | 4355 | 35772 | 99.3% | 2.97 | 5.75 | 62.3% | 82.0% |
| rules | 4355 | 35772 | 100.0% | 8.86 | 13.72 | 21.7% | 43.5% |
| nmrshiftdb2 service (sample) | 126 | 975 | 95.9% | 0.54 | 2.45 | 94.7% | 97.2% |
| local (same sample) | 150 | 1106 | 99.6% | 2.91 | 5.73 | 63.2% | 83.5% |

**1H**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 0.2 | within 0.5 |
|---|---|---|---|---|---|---|---|
| local | 4355 | 12791 | 99.3% | 0.29 | 0.57 | 62.7% | 83.9% |
| rules | 4355 | 12791 | 100.0% | 0.66 | 1.20 | 31.6% | 60.8% |
| nmrshiftdb2 service (sample) | 126 | 388 | 45.6% | 0.07 | 0.20 | 91.5% | 96.0% |
| local (same sample) | 150 | 496 | 99.6% | 0.32 | 0.59 | 58.1% | 82.8% |

## S1 card: measured, then local index, then rules (first 600 molecules) (2026-10-17)

600 held-out nmrshiftdb2 molecules, scored in 642 s.

**13C**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 2 | within 5 |
|---|---|---|---|---|---|---|---|
| local | 600 | 6836 | 99.4% | 2.64 | 5.33 | 66.5% | 84.4% |
| rules | 600 | 6836 | 100.0% | 8.62 | 12.85 | 21.5% | 43.4% |
| site | 600 | 6836 | 100.0% | 2.75 | 5.84 | 66.2% | 84.0% |

**1H**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 0.2 | within 0.5 |
|---|---|---|---|---|---|---|---|
| local | 600 | 439 | 97.9% | 0.23 | 0.53 | 72.6% | 88.8% |
| rules | 600 | 439 | 100.0% | 0.43 | 0.78 | 37.6% | 73.1% |
| site | 600 | 439 | 100.0% | 0.26 | 0.61 | 71.3% | 87.7% |

## S2 widest matching environment, calibrated error bars (all held-out molecules) (2026-10-17)

4355 held-out nmrshiftdb2 molecules, scored in 5 s.

**13C**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 2 | within 5 |
|---|---|---|---|---|---|---|---|
| local | 4355 | 35772 | 99.3% | 2.43 | 4.97 | 68.7% | 85.9% |
| rules | 4355 | 35772 | 100.0% | 8.86 | 13.72 | 21.7% | 43.5% |

**1H**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 0.2 | within 0.5 |
|---|---|---|---|---|---|---|---|
| local | 4355 | 12791 | 99.3% | 0.24 | 0.52 | 69.1% | 87.3% |
| rules | 4355 | 12791 | 100.0% | 0.66 | 1.20 | 31.6% | 60.8% |

## S3 measured spectra only (predicted ones in records left out) (2026-10-17)

4352 held-out nmrshiftdb2 molecules, scored in 5 s.

**13C**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 2 | within 5 |
|---|---|---|---|---|---|---|---|
| local | 4352 | 34433 | 99.3% | 2.48 | 4.82 | 67.5% | 85.4% |
| rules | 4352 | 34433 | 100.0% | 8.86 | 13.70 | 21.7% | 43.4% |

**1H**

| predictor | molecules | atoms | coverage | MAE (ppm) | RMSE (ppm) | within 0.2 | within 0.5 |
|---|---|---|---|---|---|---|---|
| local | 4352 | 12791 | 99.3% | 0.24 | 0.52 | 69.1% | 87.3% |
| rules | 4352 | 12791 | 100.0% | 0.66 | 1.20 | 31.6% | 60.8% |
