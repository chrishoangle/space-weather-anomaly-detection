"""Export precomputed detector output for the static web dashboard.

Purpose
-------
GitHub Pages serves static files and cannot run Python, so the interactive
dashboard at `docs/index.html` cannot refit a model when the visitor moves a
slider. This script removes the need to. It precomputes everything that does
not depend on a slider, and the browser does the remaining arithmetic.

The key observation is that neither slider requires refitting:

*   The sigma threshold is applied to z-scores, and z-scores do not depend on
    sigma. Thresholding a fixed array is trivial in JavaScript.
*   The hit tolerance only changes which timestamps count as inside a storm
    window. That is an interval test against the storm peak.

Consequently only the fitted quantities need to cross the boundary: per-feature
z-scores under each fitting regime, the Isolation Forest decisions, the raw
series for plotting, and Kp for the quiet-time false-alarm rate.

Isolation Forest is the exception to the slider rule. Its decision comes from
its own contamination-derived threshold rather than from sigma, so the boolean
it produced at fit time is exported directly and the sigma slider is disabled
in the browser when a forest configuration is selected.

Run from the project root::

    python scripts/export_web_data.py

Detailed output is written to `docs/storms.json`.
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import fetch_omniweb_historical  # noqa: E402
from src.evaluation import StormEvent, load_storm_catalog  # noqa: E402
from src.models import (  # noqa: E402
    IsolationForestDetector,
    StatisticalProcessControlDetector,
)

FEATURES = ("speed", "density", "temperature", "imf_magnitude")
ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "docs" / "storms.json"

#: Rounding applied before serialising. Raw series are only plotted, so screen
#: resolution is the limit and one decimal is ample.
RAW_DECIMALS = 1

#: Z-scores need far more precision than plotting would suggest, because the
#: browser reproduces Python's strict `abs(z) > sigma` test. At two decimals a
#: z-score of 3.001 serialises as 3.00 and then fails a comparison it passes in
#: Python, which shifted flag counts by up to three hours per window. Six
#: decimals puts the rounding error ten thousand times below the slider step,
#: at a cost of roughly 30 KB gzipped.
Z_DECIMALS = 6


def window_bounds(event: StormEvent) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar month containing the peak, matching `compare_detectors.py`."""
    start = event.peak.normalize().replace(day=1)
    return start, start + pd.offsets.MonthEnd(1)


def _round(values, decimals: int) -> list[float | None]:
    """Round a series for serialisation, mapping NaN to null."""
    return [None if pd.isna(v) else round(float(v), decimals) for v in values]


def build_record(event: StormEvent, frame: pd.DataFrame) -> dict[str, object]:
    """Compute every fitted quantity the browser cannot derive for itself."""
    features = [f for f in FEATURES if f in frame.columns]
    kp_quiet = pd.to_numeric(frame["Kp"], errors="coerce") < 3.0
    midpoint = frame.index[len(frame) // 2]
    calendar_quiet = pd.Series(frame.index < midpoint, index=frame.index)

    record: dict[str, object] = {
        "name": event.name,
        "peak": int(event.peak.timestamp()),
        "maxKp": event.max_kp,
        "stormClass": event.storm_class,
        "t": [int(x.timestamp()) for x in frame.index],
        "Kp": _round(frame["Kp"], 2),
        "features": features,
        "raw": {f: _round(frame[f], RAW_DECIMALS) for f in features},
    }

    # SPC: export z-scores, not decisions. The browser applies the threshold.
    for key, mask in (("spc_kp", kp_quiet), ("spc_cal", calendar_quiet)):
        predictions = (
            StatisticalProcessControlDetector(features=features)
            .fit(frame, quiet_mask=mask)
            .predict(frame)
        )
        record[key] = {
            f: _round(predictions[f"{f}_zscore"], Z_DECIMALS)
            for f in features
            if f"{f}_zscore" in predictions.columns
        }

    # Isolation Forest: the decision comes from contamination, not sigma, so
    # the boolean is exported as-is and the sigma slider is disabled for it.
    for key, kwargs in (("if_all", {}), ("if_quiet", {"fit_on_quiet_only": True})):
        predictions = IsolationForestDetector(
            n_estimators=300, features=features, **kwargs
        ).fit_predict(frame, quiet_mask=kp_quiet)
        record[key] = [bool(v) for v in predictions["anomaly"]]

    return record


def main() -> int:
    events = load_storm_catalog()
    print(f"Catalog: {len(events)} events. Building web export...")

    payload: dict[str, object] = {"storms": [], "features": list(FEATURES)}
    for event in events:
        lower, upper = window_bounds(event)
        try:
            frame = fetch_omniweb_historical(lower.to_pydatetime(), upper.to_pydatetime())
        except RuntimeError as error:
            print(f"  SKIP {event.name}: {error}", file=sys.stderr)
            continue
        payload["storms"].append(build_record(event, frame))
        print(f"  OK   {event.name}: {len(frame)} rows")

    if not payload["storms"]:
        print("No windows available; nothing exported.", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"))
    OUTPUT_PATH.write_text(text, encoding="utf-8")

    compressed = len(gzip.compress(text.encode())) / 1024
    print(
        f"\nWrote {OUTPUT_PATH.relative_to(ROOT)}: "
        f"{len(text)/1024:.0f} KB raw, {compressed:.0f} KB gzipped "
        f"({sum(len(s['t']) for s in payload['storms'])} hourly samples)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
