"""Leave-one-storm-out validation, and a tolerance sweep.

Why this script exists
----------------------
Every figure in `scripts/compare_detectors.py` is in-sample. The quiet baseline is
fitted inside the same window it is then scored on, and the two Kp<3 configurations
are evaluated for quiet-time false alarms on exactly the rows they were fitted to.
That inflates their apparent restraint.

This script removes the leakage two ways.

**Leave-one-storm-out.** The quiet reference is estimated from the four windows the
detector is not being scored on, then applied to the held-out fifth. No row
contributes to both the baseline and the evaluation. The cost is that the reference
is no longer contemporaneous with the event, which matters because solar activity
varies across a cycle; that cost is the thing being measured.

**Matched alert budget.** Precision and recall trade off, so a detector flagging
fewer hours shows higher precision independently of quality. Comparing two detectors
at whatever threshold their defaults happen to produce is not a comparison. Each
configuration is therefore also evaluated with its threshold tuned so every detector
flags the same number of hours in a given window.

**Tolerance sweep.** A single hit tolerance is one arbitrary operating point on a
second axis. Recall rises monotonically with tolerance for free, so the sweep
reports precision and recall as functions of it rather than at one value.

Run from the project root::

    python scripts/validate_heldout.py
    python scripts/validate_heldout.py --offline

Detailed results are written to `reports/heldout_validation.csv`,
`reports/tolerance_sweep.csv` and `reports/heldout_summary.json`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import fetch_omniweb_historical  # noqa: E402
from src.evaluation import StormEvent, load_storm_catalog  # noqa: E402
from src.models import (  # noqa: E402
    IsolationForestDetector,
    StatisticalProcessControlDetector,
)

FEATURES = ["speed", "density", "temperature", "imf_magnitude"]
DEFAULT_TOLERANCE = pd.Timedelta(hours=24)
SWEEP_HOURS = (6, 12, 18, 24, 30, 36, 42, 48)
QUIET_KP = 3.0
ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"


def window_bounds(event: StormEvent) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar month containing the peak, matching the other scripts."""
    start = event.peak.normalize().replace(day=1)
    return start, start + pd.offsets.MonthEnd(1)


def load_windows(offline: bool) -> list[tuple[StormEvent, pd.DataFrame]]:
    """Return every storm window that can be loaded, skipping the rest."""
    out: list[tuple[StormEvent, pd.DataFrame]] = []
    for event in load_storm_catalog():
        lower, upper = window_bounds(event)
        try:
            frame = fetch_omniweb_historical(
                lower.to_pydatetime().astimezone(UTC),
                upper.to_pydatetime().astimezone(UTC),
            )
        except RuntimeError as error:
            reason = "not cached" if offline else str(error).split(":")[-1].strip()
            print(f"  SKIP {event.name}: {reason}", file=sys.stderr)
            continue
        out.append((event, frame))
        print(f"  OK   {event.name}: {len(frame)} rows")
    return out


def truth_mask(frame: pd.DataFrame, event: StormEvent, tolerance: pd.Timedelta) -> np.ndarray:
    """Hours inside the catalogued storm window, closed on both ends."""
    delta = (frame.index - event.peak).to_series().abs()
    return (delta <= tolerance).to_numpy()


def scores(frame: pd.DataFrame, baseline: dict[str, tuple[float, float]]) -> np.ndarray:
    """Max absolute z-score per row against a supplied (mean, std) per feature.

    Returning a score rather than a decision is what allows the threshold to be
    swept later without refitting.
    """
    best = np.full(len(frame), np.nan)
    for feature, (mean, std) in baseline.items():
        if feature not in frame.columns or not np.isfinite(std) or std == 0.0:
            continue
        z = ((pd.to_numeric(frame[feature], errors="coerce") - mean) / std).abs().to_numpy()
        best = np.fmax(best, z)
    return best


def pooled_quiet_baseline(windows, exclude_name: str) -> dict[str, tuple[float, float]]:
    """Fit mean and std per feature on quiet rows from every OTHER window.

    This is the held-out part. The returned statistics never saw a single row of
    the window they will be used to score.
    """
    parts = []
    for event, frame in windows:
        if event.name == exclude_name:
            continue
        kp = pd.to_numeric(frame["Kp"], errors="coerce")
        parts.append(frame.loc[(kp < QUIET_KP) & kp.notna(), FEATURES])
    pooled = pd.concat(parts)
    return {
        f: (float(pooled[f].mean()), float(pooled[f].std(ddof=1)))
        for f in FEATURES
        if f in pooled.columns
    }


def metrics_from_flags(flag: np.ndarray, truth: np.ndarray, kp: np.ndarray) -> dict[str, float]:
    """Precision, recall and quiet-time false-alarm rate. NaN where undefined."""
    tp = int((flag & truth).sum())
    fp = int((flag & ~truth).sum())
    fn = int((~flag & truth).sum())
    quiet = (kp < QUIET_KP) & ~np.isnan(kp)
    n_quiet = int(quiet.sum())
    nan = float("nan")
    return {
        "flagged": int(flag.sum()),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": tp / (tp + fp) if tp + fp else nan,
        "recall": tp / (tp + fn) if tp + fn else nan,
        "quiet_far": int((flag & quiet).sum()) / n_quiet if n_quiet else nan,
        "n_quiet": n_quiet,
    }


def threshold_for_budget(score: np.ndarray, budget: int) -> float:
    """Smallest threshold flagging at most `budget` rows, so budgets are matched."""
    finite = np.sort(score[np.isfinite(score)])[::-1]
    if budget <= 0 or len(finite) == 0:
        return float("inf")
    if budget >= len(finite):
        return float(finite[-1]) - 1e-9
    return float(finite[budget - 1]) - 1e-12


def run_heldout(windows) -> pd.DataFrame:
    """Score every configuration on each window, in-sample and held out."""
    rows: list[dict[str, object]] = []
    for event, frame in windows:
        kp = pd.to_numeric(frame["Kp"], errors="coerce").to_numpy()
        truth = truth_mask(frame, event, DEFAULT_TOLERANCE)
        kp_quiet = pd.Series((kp < QUIET_KP) & ~np.isnan(kp), index=frame.index)

        in_sample = StatisticalProcessControlDetector(features=FEATURES).fit(
            frame, quiet_mask=kp_quiet
        )
        score_in = scores(frame, dict(in_sample.baseline))
        score_out = scores(frame, pooled_quiet_baseline(windows, event.name))

        forest = IsolationForestDetector(n_estimators=300, features=FEATURES).fit_predict(
            frame, quiet_mask=kp_quiet
        )["anomaly"].to_numpy()
        budget = int(forest.sum())

        for label, score in (("SPC in-sample", score_in), ("SPC held-out", score_out)):
            for mode, thr in (
                ("default 3 sigma", 3.0),
                ("matched budget", threshold_for_budget(score, budget)),
            ):
                flag = np.nan_to_num(score, nan=-np.inf) > thr
                rows.append(
                    {"event": event.name, "configuration": label, "threshold_mode": mode,
                     "threshold": round(thr, 3), **metrics_from_flags(flag, truth, kp)}
                )
        rows.append(
            {"event": event.name, "configuration": "Isolation Forest",
             "threshold_mode": "contamination auto", "threshold": float("nan"),
             **metrics_from_flags(forest, truth, kp)}
        )
    return pd.DataFrame(rows)


def run_sweep(windows) -> pd.DataFrame:
    """Precision and recall as a function of the hit tolerance."""
    rows: list[dict[str, object]] = []
    for event, frame in windows:
        kp = pd.to_numeric(frame["Kp"], errors="coerce").to_numpy()
        kp_quiet = pd.Series((kp < QUIET_KP) & ~np.isnan(kp), index=frame.index)
        score_in = scores(
            frame,
            dict(
                StatisticalProcessControlDetector(features=FEATURES)
                .fit(frame, quiet_mask=kp_quiet)
                .baseline
            ),
        )
        spc = np.nan_to_num(score_in, nan=-np.inf) > 3.0
        forest = IsolationForestDetector(n_estimators=300, features=FEATURES).fit_predict(
            frame, quiet_mask=kp_quiet
        )["anomaly"].to_numpy()
        for hours in SWEEP_HOURS:
            truth = truth_mask(frame, event, pd.Timedelta(hours=hours))
            for label, flag in (("SPC 3 sigma", spc), ("Isolation Forest", forest)):
                rows.append(
                    {"event": event.name, "configuration": label, "tolerance_h": hours,
                     "storm_hours": int(truth.sum()),
                     **metrics_from_flags(flag, truth, kp)}
                )
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="Use only windows already cached under data/raw/omniweb/.")
    args = parser.parse_args()

    print("Loading storm windows...")
    windows = load_windows(args.offline)
    if len(windows) < 2:
        print("Leave-one-storm-out needs at least two windows.", file=sys.stderr)
        return 1

    heldout = run_heldout(windows)
    sweep = run_sweep(windows)

    REPORTS.mkdir(exist_ok=True)
    heldout.to_csv(REPORTS / "heldout_validation.csv", index=False)
    sweep.to_csv(REPORTS / "tolerance_sweep.csv", index=False)

    pd.set_option("display.width", 200)
    summary = (
        heldout.groupby(["configuration", "threshold_mode"], sort=False)
        .agg(precision=("precision", "mean"), recall=("recall", "mean"),
             quiet_far=("quiet_far", "mean"), flagged=("flagged", "sum"))
        .reset_index()
    )
    print(f"\n=== Leave-one-storm-out, {len(windows)} windows, tolerance 24 h ===")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    sweep_summary = (
        sweep.groupby(["configuration", "tolerance_h"], sort=False)
        .agg(precision=("precision", "mean"), recall=("recall", "mean"))
        .reset_index()
        .pivot(index="tolerance_h", columns="configuration")
    )
    print("\n=== Tolerance sweep, mean across windows ===")
    print(sweep_summary.to_string(float_format=lambda v: f"{v:.3f}"))

    (REPORTS / "heldout_summary.json").write_text(
        json.dumps(
            {"windows": [e.name for e, _ in windows],
             "tolerance_hours": 24,
             "sweep_hours": list(SWEEP_HOURS),
             "heldout_summary": summary.to_dict(orient="records"),
             "sweep": sweep.to_dict(orient="records")},
            indent=2, default=str),
        encoding="utf-8",
    )
    print(f"\nWrote {(REPORTS / 'heldout_validation.csv').relative_to(ROOT)}, "
          f"{(REPORTS / 'tolerance_sweep.csv').relative_to(ROOT)} and "
          f"{(REPORTS / 'heldout_summary.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
