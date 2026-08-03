# Space Weather Anomaly Detection

## Project

Anomaly detection on NOAA and NASA OMNIWeb solar wind and geomagnetic time series data. Portfolio project demonstrating end-to-end ML pipeline from data ingestion through deployment.

## Architecture

- `src/data_loader.py` — Data loaders for NOAA SWPC (real-time) and NASA OMNIWeb (historical)
- `src/preprocessing.py` — Feature engineering and cleaning
- `src/models.py` — Anomaly detection models
- `src/evaluation.py` — Event-wise + point-wise metrics, quiet-time
  false-alarm rate, and detection lead time, validated against the storm catalog
- `app.py` — Streamlit dashboard (a view only; computes no metrics of its own)
- `scripts/compare_detectors.py` — Detector comparison; writes `reports/`
- `scripts/run_daily_detection.py` — Unattended run for the daily CI job
- `notebooks/` — Exploratory analysis and results
- `scripts/` — Demonstration and utility scripts
- `data/raw/` — Cached raw data (gitignored)

## Conventions

- All datetimes are UTC and timezone-aware
- Column naming: 'speed', 'density', 'temperature', 'imf_magnitude', 'Kp'
- NOAA fill values (-9999) and OMNIWeb fill values (999.9, 9999999) are converted to NaN on load
- Cache files stored in data/raw/, one hour default TTL for real-time data

## Known Storm Events for Validation

Ground truth lives in `data/storm_catalog.csv` — load it with
`src.evaluation.load_storm_catalog()`, do not hard-code event dates in
notebooks or tests. The `onset_utc` column is intentionally blank; see
ROADMAP Milestone 2.

Events: Bastille Day (2000-07-15, Kp 9), Halloween (2003-10-29, Kp 9),
St. Patrick's Day (2015-03-17, Kp 8), September 2017 (2017-09-08, Kp 8),
Gannon (2024-05-10, Kp 9).

## Style

- Type hints on all functions
- Docstrings explaining purpose, args, returns, and any physics/data-source context
- No hidden state or global variables in loaders
- Prefer explicit errors over silent failures


## Working agreement (READ THIS BEFORE WRITING CODE)

Note: the owner explicitly asked for a full end-to-end build in one session, so
Milestones 1 and 3-6 were implemented directly rather than scaffolded. That was
a deliberate one-time override. The default below still applies to new work.

This is a learning project. The owner is building it to be able to defend
every design decision in an interview. **Handing over finished implementations
defeats its purpose.**

Default behaviour for any new analysis or modelling code:

1. Write the signature, type hints, and a docstring that explains the *why* —
   including the statistical or physical reasoning and the traps involved.
2. Write failing tests that fully specify the behaviour, including edge cases
   and the values expected.
3. Leave the body as `raise NotImplementedError` with an `IMPLEMENT NOTES:`
   block naming the tricky parts.
4. Stop. Do not implement it.

Verify the spec is satisfiable before handing it over (write a throwaway
reference implementation, confirm the tests pass, then discard it). Shipping a
scaffold with a self-contradictory spec wastes the owner's time.

**Exceptions — just build these, they carry no learning value:** CI workflows,
packaging and config, dependency management, boilerplate plumbing, notebook
build scripts, docstring and README formatting, lint fixes.

If asked to "just write it," comply — but say once that it costs an interview
answer, and note which one.

## Reporting standards

- Never report accuracy on this data. The positive class is ~5%; a
  detect-nothing model scores 95%.
- Every recall figure must be quoted with its tolerance window. Recall without
  tolerance is not interpretable and inflates for free as tolerance grows.
- Report event-wise and point-wise metrics together, never whichever is more
  flattering.
- Prefer NaN over 0.0 for undefined metrics (zero events evaluated is an
  invalid experiment, not a failed detector).
- A model that loses to the statistical baseline gets reported as losing.
