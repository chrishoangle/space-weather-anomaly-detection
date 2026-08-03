# Space Weather Anomaly Detection

## Project

Anomaly detection on NOAA and NASA OMNIWeb solar wind and geomagnetic time series data. Portfolio project demonstrating end-to-end ML pipeline from data ingestion through deployment.

## Architecture

- `src/data_loader.py` — Data loaders for NOAA SWPC (real-time) and NASA OMNIWeb (historical)
- `src/preprocessing.py` — Feature engineering and cleaning (in progress)
- `src/models.py` — Anomaly detection models (planned)
- `src/evaluation.py` — Metrics and validation against known storm catalog (planned)
- `notebooks/` — Exploratory analysis and results
- `scripts/` — Demonstration and utility scripts
- `data/raw/` — Cached raw data (gitignored)

## Conventions

- All datetimes are UTC and timezone-aware
- Column naming: 'speed', 'density', 'temperature', 'imf_magnitude', 'Kp'
- NOAA fill values (-9999) and OMNIWeb fill values (999.9, 9999999) are converted to NaN on load
- Cache files stored in data/raw/, one hour default TTL for real-time data

## Known Storm Events for Validation

- Halloween Storms: 2003-10-29 (Kp=9)
- Bastille Day: 2000-07-15 (Kp=9)
- St. Patrick's Day: 2015-03-17 (Kp=8)
- September 2017 Storm: 2017-09-08 (Kp=8+)
- Gannon Storm: 2024-05-10 (Kp=9)

## Style

- Type hints on all functions
- Docstrings explaining purpose, args, returns, and any physics/data-source context
- No hidden state or global variables in loaders
- Prefer explicit errors over silent failures

