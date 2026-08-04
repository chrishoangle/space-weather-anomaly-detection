"""Head-to-head comparison of the SPC baseline and Isolation Forest.

Evaluates every detector configuration over every storm window in
``data/storm_catalog.csv`` for which OMNI2 data is available, using identical
features and an identical hit tolerance throughout.

Windows are fetched per event and evaluated separately, then aggregated.
Fitting one global "quiet baseline" across the whole 2000-2024 span would be
wrong: solar activity varies enormously over a solar cycle, so quiet in 2003
(near solar maximum) is not quiet in 2019. A per-window baseline keeps the
reference contemporaneous with the event.

One window is the calendar month containing the storm peak, extended if the
hit window would otherwise fall outside it. Calendar months rather than
"peak +/- N days" because the boundaries are then a deterministic function of
the catalog alone -- the same cache key every run, on any machine, with no
dependence on when the script happened to be executed.

Windows whose data cannot be retrieved are skipped with a logged warning and
excluded from the denominators -- never silently counted as misses.

Run from the project root::

    python scripts/compare_detectors.py
    python scripts/compare_detectors.py --offline   # cached windows only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import fetch_omniweb_historical  # noqa: E402
from src.evaluation import StormEvent, evaluate_detector, load_storm_catalog  # noqa: E402
from src.models import (  # noqa: E402
    IsolationForestDetector,
    StatisticalProcessControlDetector,
)

FEATURES = ["speed", "density", "temperature", "imf_magnitude"]
TOLERANCE = pd.Timedelta(hours=24)
ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"

CONFIGURATIONS = (
    "SPC (3-sigma, Kp<3 quiet rows)",
    "SPC (3-sigma, calendar quiet half)",
    "Isolation Forest (fit on all data)",
    "Isolation Forest (fit on Kp<3 rows)",
)


def make_detector(label: str, frame: pd.DataFrame) -> tuple[object, pd.Series | None]:
    """Build a fresh detector plus its fit mask for one window.

    A fresh instance per window matters: reusing a fitted detector across
    windows would carry a baseline from one solar-cycle phase into another.
    """
    kp_quiet = pd.to_numeric(frame["Kp"], errors="coerce") < 3.0
    midpoint = frame.index[len(frame) // 2]
    calendar_quiet = pd.Series(frame.index < midpoint, index=frame.index)

    if label == "SPC (3-sigma, Kp<3 quiet rows)":
        return StatisticalProcessControlDetector(sigma_threshold=3.0, features=FEATURES), kp_quiet
    if label == "SPC (3-sigma, calendar quiet half)":
        return (
            StatisticalProcessControlDetector(sigma_threshold=3.0, features=FEATURES),
            calendar_quiet,
        )
    if label == "Isolation Forest (fit on all data)":
        return IsolationForestDetector(n_estimators=300, features=FEATURES), None
    if label == "Isolation Forest (fit on Kp<3 rows)":
        return (
            IsolationForestDetector(n_estimators=300, features=FEATURES, fit_on_quiet_only=True),
            kp_quiet,
        )
    raise ValueError(f"Unknown configuration {label!r}")


def window_bounds(event: StormEvent) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar month containing the peak, widened to cover the hit window."""
    month_start = event.peak.normalize().replace(day=1)
    month_end = month_start + pd.offsets.MonthEnd(1)
    hit_start, hit_end = event.window(TOLERANCE)
    return min(month_start, hit_start.normalize()), max(month_end, hit_end.normalize())


def load_window(event: StormEvent, offline: bool) -> pd.DataFrame | None:
    """Fetch the OMNI2 window around one event, or None if unavailable."""
    lower, upper = window_bounds(event)
    start = lower.to_pydatetime().astimezone(UTC)
    end = upper.to_pydatetime().astimezone(UTC)
    try:
        frame = fetch_omniweb_historical(start, end)
    except RuntimeError as error:
        reason = "not cached" if offline else str(error).split(":")[-1].strip()
        print(f"  SKIP {event.name}: {reason}", file=sys.stderr)
        return None
    if frame.empty or frame["Kp"].isna().all():
        print(f"  SKIP {event.name}: window has no usable Kp", file=sys.stderr)
        return None
    return frame


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only windows already cached under data/raw/omniweb/.",
    )
    args = parser.parse_args()

    events = load_storm_catalog()
    print(f"Catalog: {len(events)} events. Loading one calendar-month window each...")

    windows: list[tuple[StormEvent, pd.DataFrame]] = []
    for event in events:
        frame = load_window(event, args.offline)
        if frame is not None:
            windows.append((event, frame))
            print(f"  OK   {event.name}: {len(frame)} rows")

    if not windows:
        print(
            "No storm windows available. Run once with network access to populate "
            "data/raw/omniweb/, then re-run.",
            file=sys.stderr,
        )
        return 1

    skipped = [event.name for event in events if event.name not in {e.name for e, _ in windows}]
    per_window: list[dict[str, object]] = []

    for label in CONFIGURATIONS:
        for event, frame in windows:
            detector, mask = make_detector(label, frame)
            flags = detector.fit_predict(frame, quiet_mask=mask)["anomaly"]
            report = evaluate_detector(flags, frame, events=[event], tolerance=TOLERANCE)
            per_window.append(
                {
                    "configuration": label,
                    "event": event.name,
                    "detected": bool(report["event"]["n_detected_events"]),
                    "event_precision": report["event"]["event_precision"],
                    "pw_precision": report["pointwise"]["precision"],
                    "pw_recall": report["pointwise"]["recall"],
                    "pw_f1": report["pointwise"]["f1"],
                    "pw_fpr": report["pointwise"]["false_positive_rate"],
                    "flagged": report["event"]["n_detections"],
                    "n_samples": report["pointwise"]["n_samples"],
                    "quiet_far": report["false_alarm"]["quiet_false_alarm_rate"],
                }
            )

    detail = pd.DataFrame(per_window)
    summary = (
        detail.groupby("configuration", sort=False)
        .agg(
            events=("event", "count"),
            events_detected=("detected", "sum"),
            event_recall=("detected", "mean"),
            event_precision=("event_precision", "mean"),
            pw_precision=("pw_precision", "mean"),
            pw_recall=("pw_recall", "mean"),
            pw_f1=("pw_f1", "mean"),
            pw_fpr=("pw_fpr", "mean"),
            quiet_far=("quiet_far", "mean"),
            flagged=("flagged", "sum"),
            n_samples=("n_samples", "sum"),
        )
        .reset_index()
    )

    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 24)
    print(f"\n=== Aggregate over {len(windows)} storm window(s), tolerance +/-24 h ===")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    if skipped:
        print(f"\nExcluded (no data): {', '.join(skipped)}")
    print("\n=== Per window ===")
    print(detail.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    REPORTS_DIR.mkdir(exist_ok=True)
    summary.to_csv(REPORTS_DIR / "detector_comparison.csv", index=False)
    detail.to_csv(REPORTS_DIR / "detector_comparison_per_window.csv", index=False)
    (REPORTS_DIR / "detector_comparison.json").write_text(
        json.dumps(
            {
                "tolerance_hours": TOLERANCE / pd.Timedelta(hours=1),
                "window": "calendar month containing peak",
                "features": FEATURES,
                "events_evaluated": [event.name for event, _ in windows],
                "events_excluded": skipped,
                "summary": summary.to_dict(orient="records"),
                "per_window": per_window,
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    _plot(windows)
    return 0


def _plot(windows: list[tuple[StormEvent, pd.DataFrame]]) -> None:
    """Plot detector flags against each available storm window."""
    for event, frame in windows:
        start, end = event.window(TOLERANCE)
        n_rows = len(CONFIGURATIONS) + 2
        fig, axes = plt.subplots(n_rows, 1, figsize=(12, 1.7 * n_rows), sharex=True)

        axes[0].plot(frame.index, frame["speed"], color="0.25", linewidth=0.9)
        axes[0].set_ylabel("speed\n(km/s)", fontsize=8)
        axes[1].plot(frame.index, frame["Kp"], color="0.25", linewidth=0.9)
        axes[1].axhline(3.0, color="seagreen", linestyle=":", linewidth=1)
        axes[1].set_ylabel("Kp", fontsize=8)

        for label, axis in zip(CONFIGURATIONS, axes[2:], strict=True):
            detector, mask = make_detector(label, frame)
            flags = detector.fit_predict(frame, quiet_mask=mask)["anomaly"]
            axis.vlines(flags[flags].index, 0, 1, color="crimson", linewidth=0.7)
            axis.set_ylim(0, 1)
            axis.set_yticks([])
            axis.text(
                0.995,
                0.86,
                f"{label}: {int(flags.sum())} of {len(flags)} flagged",
                transform=axis.transAxes,
                ha="right",
                va="top",
                fontsize=8,
            )

        for axis in axes:
            axis.axvspan(start, end, color="steelblue", alpha=0.15)

        axes[-1].set_xlabel("UTC time")
        fig.suptitle(
            f"{event.name} ({event.peak:%Y-%m-%d}): detector flags vs. "
            f"storm window (shaded, +/-24 h of peak)",
            fontsize=11,
        )
        fig.tight_layout()
        slug = event.name.lower().replace(" ", "_").replace("'", "").replace(".", "")
        path = REPORTS_DIR / f"comparison_{slug}.png"
        fig.savefig(path, dpi=140, bbox_inches="tight")
        plt.close(fig)
        print(f"Wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    raise SystemExit(main())
