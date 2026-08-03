# Space Weather Anomaly Detection

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
| Evaluation against storm catalog | Partial — inline in the baseline notebook |
| Isolation Forest / autoencoder detectors | Planned |
| Streamlit dashboard | Planned |

## Repository Layout

- `src/data_loader.py` — NOAA SWPC and NASA OMNIWeb loaders with local caching.
- `src/preprocessing.py` — Gap interpolation, rolling statistics, first
  difference / rate of change, dynamic pressure, and quiet-baseline z-scores.
- `src/models.py` — `StatisticalProcessControlDetector`, a sigma-threshold
  detector fitted on a quiet reference window.
- `src/evaluation.py` — Reserved for storm-catalog validation metrics.
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

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

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

The current suite covers `src/preprocessing.py` (36 tests exercising empty
frames, single-row inputs, and all-NaN columns for every public function).

## Tech Stack

- Python (pandas, NumPy, scikit-learn)
- Matplotlib / Plotly for visualization
- Streamlit for the (planned) dashboard
- Pytest for unit tests

## Data Sources

- [NOAA SWPC](https://services.swpc.noaa.gov/) real-time and historical products
- [NASA OMNIWeb](https://omniweb.gsfc.nasa.gov/) historical archive
- Known storm event catalog (see `CLAUDE.md`) for validation

## Roadmap

- Isolation Forest detector fitted on the same features as the SPC baseline.
- Sequence autoencoder for reconstruction-error anomalies.
- Formal evaluation module (`src/evaluation.py`) with precision / recall
  against the storm-event catalog.
- Streamlit dashboard for near-real-time monitoring.
