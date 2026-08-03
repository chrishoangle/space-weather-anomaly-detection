# Space Weather Anomaly Detection

[![tests](https://github.com/chrishoangle/space-weather-anomaly-detection/actions/workflows/tests.yml/badge.svg)](https://github.com/chrishoangle/space-weather-anomaly-detection/actions/workflows/tests.yml)
[![daily detection](https://github.com/chrishoangle/space-weather-anomaly-detection/actions/workflows/daily.yml/badge.svg)](https://github.com/chrishoangle/space-weather-anomaly-detection/actions/workflows/daily.yml)

Detect anomalous events in NOAA solar wind and geomagnetic time series data
using unsupervised and semi-supervised methods.

## Motivation

Space weather events (coronal mass ejections, solar flares, high-speed streams)
can damage satellites, disrupt GPS, and affect power grids. Reliable early
detection of anomalous solar wind behavior enables mitigation.

## Approach

1. Ingest historical solar wind and geomagnetic data from NOAA SWPC / NASA
   OMNIWeb.
2. Establish baseline behavior via statistical characterization.
3. Apply anomaly detection methods (statistical process control today,
   Isolation Forest / autoencoder later) to identify deviations.
4. Validate detected anomalies against known geomagnetic storm events.
5. Deploy an interactive dashboard for real-time monitoring.

## Status

| Component | State |
| --- | --- |
| Data loaders (NOAA real-time, NASA OMNIWeb historical) | Done — `src/data_loader.py` |
| Exploratory notebooks | Done — `notebooks/01_exploratory.ipynb`, `notebooks/02_historical_analysis.ipynb` |
| Preprocessing / feature engineering | Done — `src/preprocessing.py` |
| Baseline anomaly detector (statistical process control) | Done — `src/models.py`, `notebooks/03_baseline_detection.ipynb` |
| Ground-truth storm catalog | Done — `data/storm_catalog.csv` |
| CI (ruff + pytest on 3.11/3.12/3.13) | Done — `.github/workflows/tests.yml` |
| Evaluation module (event-wise + point-wise) | Done — `src/evaluation.py`, 46 tests |
| Isolation Forest detector | Done — `src/models.py`, 17 tests |
| Detector comparison + results write-up | Done — [`RESULTS.md`](RESULTS.md) |
| Automated daily detection job | Done — `.github/workflows/daily.yml` |
| Streamlit dashboard | Done — `app.py` |
| Storm onset times for lead-time metrics | **Open** — `onset_utc` blank, so no lead-time results |
| Evaluation across all five storm windows | **Open** — only March 2015 evaluated so far |

See [ROADMAP.md](ROADMAP.md) for the milestone plan and design decisions.

## Repository Layout

- `src/data_loader.py` — NOAA SWPC and NASA OMNIWeb loaders with local caching.
- `src/preprocessing.py` — Gap interpolation, rolling statistics, first
  difference / rate of change, dynamic pressure, and quiet-baseline z-scores.
- `src/models.py` — `StatisticalProcessControlDetector`, a sigma-threshold
  detector fitted on a quiet reference window.
- `src/evaluation.py` — Event-wise and point-wise validation metrics against
  the storm catalog, plus quiet-time false-alarm rate and detection lead time.
- `data/storm_catalog.csv` — Ground-truth geomagnetic storm events.
- `app.py` — Streamlit dashboard (live NOAA mode and historical storm mode).
- `scripts/compare_detectors.py` — Head-to-head detector comparison; writes
  `reports/`.
- `scripts/run_daily_detection.py` — Unattended detection run for CI.
- `notebooks/01_exploratory.ipynb` — Initial data exploration and visualization.
- `notebooks/02_historical_analysis.ipynb` — Deeper historical analysis of the
  March 2015 storm window.
- `notebooks/03_baseline_detection.ipynb` — Baseline anomaly detection
  walkthrough with quantitative evaluation.
- `scripts/fetch_historical_data.py` — CLI helper for pulling OMNIWeb ranges.
- `scripts/fetch_noaa_data.py` — CLI helper for pulling NOAA real-time products.
- `scripts/_build_baseline_notebook.py` — Regenerates
  `notebooks/03_baseline_detection.ipynb` from a plain-Python cell definition
  and executes it.
- `tests/test_preprocessing.py` — Unit tests for the preprocessing module.
- `tests/test_evaluation.py` — Specification tests for the evaluation module.
- `tests/test_models.py` — Detector tests: index alignment, NaN handling,
  reproducibility, interface parity.
- `tests/test_daily_detection.py` — Operational contract of the unattended job.

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt   # runtime deps + pytest/jupyter
```

Runtime-only installs (e.g. for the dashboard) can use `requirements.txt`.

## Reproducing the Analyses

The OMNIWeb loader caches every response under `data/raw/omniweb/`, so once
the raw text has been fetched you can rerun everything offline.

**Exploratory notebook (`01_exploratory.ipynb`)** — realtime NOAA products.
Launch Jupyter and run all cells:

```bash
jupyter notebook notebooks/01_exploratory.ipynb
```

**Historical March 2015 analysis (`02_historical_analysis.ipynb`)** — hourly
OMNI2 data across the St. Patrick's Day storm window. Same instructions;
first run will fetch the data, subsequent runs use the cache.

**Baseline detection (`03_baseline_detection.ipynb`)** — regenerate and
execute end-to-end:

```bash
python scripts/_build_baseline_notebook.py
```

That script writes the notebook with cell outputs so it renders correctly on
GitHub without needing an active kernel.

## Running the Tests

```bash
python -m pytest tests/ -v
```

108 tests, all passing:

| Module | Tests | Focus |
| --- | --- | --- |
| `test_preprocessing.py` | 36 | Empty frames, single rows, all-NaN columns |
| `test_evaluation.py` | 46 | Metric definitions and undefined-value edge cases |
| `test_models.py` | 17 | Index alignment, NaN handling, seed reproducibility |
| `test_daily_detection.py` | 9 | Stale data reported as unknown, never "nominal" |

## Tech Stack

- Python (pandas, NumPy, scikit-learn)
- Matplotlib / Plotly for visualization
- Streamlit for the (planned) dashboard
- Pytest for unit tests

## Data Sources

- [NOAA SWPC](https://services.swpc.noaa.gov/) real-time and historical products
- [NASA OMNIWeb](https://omniweb.gsfc.nasa.gov/) historical archive
- Known storm event catalog (see `CLAUDE.md`) for validation

## Headline Result

Across **all five catalogued storms** (3,696 hourly samples), every
configuration detected every storm — so detection is not the discriminating
problem, restraint is. On restraint, **the 3σ statistical baseline beat
Isolation Forest decisively**: precision 0.394 vs 0.254 and a quiet-time
false-alarm rate of 2.4% vs 6.1%.

The gap widens where the problem gets hard. In October 2003 — a month with
Kp ≥ 3 in 54% of its hours — Isolation Forest collapses to F1 0.062 while the
baseline holds at 0.343. The reason is general: an unsupervised model that
defines "anomalous" as "rare in training data" fails when the base rate shifts,
which is exactly when a monitor matters most. The baseline is anchored to an
explicit quiet reference and survives.

Full numbers, per-window breakdown, and five stated limitations are in
[RESULTS.md](RESULTS.md).

## Evaluation Approach

Point-wise classification metrics are misleading for time-series anomaly
detection, so this project reports two families side by side:

- **Event-wise** — each catalogued storm is one unit. Was it detected within a
  stated tolerance window? This answers "would an operator have been warned?"
- **Point-wise** — each timestamp scored independently. Included because
  event-wise recall alone would reward a detector that fires constantly.

Also reported: **quiet-time false-alarm rate** (detections during independently
confirmed Kp < 3 periods) and **detection lead time** relative to storm onset.

Accuracy is deliberately never reported: with a ~5% positive class, a detector
that flags nothing scores 95%.

## Automation

`.github/workflows/daily.yml` runs `scripts/run_daily_detection.py` every day
at 06:15 UTC, scores the last 72 h of NOAA data, and commits
`reports/latest.md` and `reports/latest.json` back to the repository.

The design constraint worth noting: the job distinguishes "no storm" from "no
data". Stale or unavailable upstream data produces an explicit `unknown`
status, and only an internal bug exits non-zero. A monitor that silently
reports "all clear" because its fetch broke a week ago is worse than no
monitor.

## Dashboard

```bash
streamlit run app.py
```

Historical mode scores a catalogued storm window with the ground-truth window
shaded and the measured metrics shown beneath. Live mode pulls current NOAA
data. All metrics come from `src.evaluation`, so the dashboard and
`RESULTS.md` cannot disagree.

## Roadmap

See [ROADMAP.md](ROADMAP.md). Highest-value open items: populate `onset_utc`
so lead-time metrics become available, and evaluate all five storm windows
rather than one.
