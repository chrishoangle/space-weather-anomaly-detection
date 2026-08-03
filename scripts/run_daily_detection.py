"""Run the storm detector against current NOAA data and write a status report.

Designed to run unattended from CI (see ``.github/workflows/daily.yml``). The
non-negotiable requirement is that it must distinguish three outcomes, never
collapsing them:

    OK      data retrieved, detector ran, verdict published
    NODATA  upstream unavailable or unusable -> exit 0, report says "unknown"
    ERROR   our own bug -> non-zero exit so CI goes red

Conflating NODATA with "no storm" is the failure mode that makes an automated
monitor actively harmful: a silent pipeline that always says "all clear"
because the fetch has been broken for a week is worse than no monitor at all.
So a stale or empty upstream produces an explicit ``unknown`` status, and the
report always carries the age of the newest sample it used.

Exit codes: 0 = published (including NODATA), 1 = internal error.

Usage::

    python scripts/run_daily_detection.py
    python scripts/run_daily_detection.py --hours 48 --sigma 3.5
"""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data_loader import load_kp_index, load_solar_wind_plasma  # noqa: E402
from src.models import StatisticalProcessControlDetector  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
FEATURES = ("speed", "density", "temperature")

#: A report built from data older than this is not trustworthy as a
#: "current conditions" statement.
STALENESS_LIMIT = timedelta(hours=6)

STATUS_OK = "ok"
STATUS_NODATA = "nodata"

#: Kp thresholds for the NOAA G-scale, used only for labelling the report.
G_SCALE = (
    (9.0, "G5 extreme"),
    (8.0, "G4 severe"),
    (7.0, "G3 strong"),
    (6.0, "G2 moderate"),
    (5.0, "G1 minor"),
)


@dataclass
class DailyResult:
    """Everything the report needs, in a JSON-serialisable shape."""

    status: str
    generated_at: str
    message: str
    latest_sample: str | None = None
    data_age_hours: float | None = None
    n_samples: int = 0
    n_flagged: int = 0
    flagged_fraction: float | None = None
    latest_kp: float | None = None
    storm_class: str | None = None
    active_now: bool | None = None
    peak_zscores: dict[str, float] | None = None
    driving_features: list[str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {key: value for key, value in self.__dict__.items()}


def _storm_class(kp: float | None) -> str | None:
    if kp is None:
        return None
    for threshold, label in G_SCALE:
        if kp >= threshold:
            return label
    return "quiet to unsettled"


def gather(hours: int) -> tuple[pd.DataFrame | None, str]:
    """Fetch recent NOAA plasma and Kp data, merged on a common index.

    Returns ``(frame, message)``; ``frame`` is None when upstream gave us
    nothing usable. Network failure is expected operational reality here, not
    an exceptional case, so it is caught and reported rather than raised.
    """
    try:
        plasma = load_solar_wind_plasma()
    except Exception as error:  # noqa: BLE001 - upstream can fail many ways
        return None, f"NOAA plasma feed unavailable: {type(error).__name__}: {error}"

    if plasma.empty:
        return None, "NOAA plasma feed returned an empty series."

    cutoff = datetime.now(UTC) - timedelta(hours=hours)
    recent = plasma.loc[plasma.index >= cutoff]
    if recent.empty:
        newest = plasma.index.max()
        return None, f"No samples within the last {hours} h; newest upstream sample is {newest}."

    try:
        kp = load_kp_index()
        if not kp.empty:
            kp_column = "Kp" if "Kp" in kp.columns else kp.columns[0]
            # Kp is 3-hourly; reindex forward so each plasma row carries the
            # Kp in force at that time.
            recent = recent.join(
                kp[[kp_column]].rename(columns={kp_column: "Kp"}).reindex(
                    recent.index, method="ffill"
                )
            )
    except Exception as error:  # noqa: BLE001
        print(f"warning: Kp feed unavailable ({type(error).__name__}: {error})", file=sys.stderr)

    return recent, f"Loaded {len(recent)} samples covering the last {hours} h."


def detect(frame: pd.DataFrame, sigma: float) -> DailyResult:
    """Fit the SPC detector on the quieter part of the window and score it all.

    With only a rolling window available there is no external quiet reference,
    so the first 60% of the window stands in as the baseline. That is a real
    weakness of running this unattended and is stated in the report rather
    than hidden: during a multi-day storm the baseline is contaminated and
    sensitivity drops.
    """
    features = [name for name in FEATURES if name in frame.columns]
    split = max(int(len(frame) * 0.6), 2)
    quiet_mask = pd.Series(False, index=frame.index)
    quiet_mask.iloc[:split] = True

    detector = StatisticalProcessControlDetector(sigma_threshold=sigma, features=features)
    predictions = detector.fit(frame, quiet_mask=quiet_mask).predict(frame)

    flags = predictions["anomaly"]
    newest = frame.index.max()
    age = (datetime.now(UTC) - newest.to_pydatetime()).total_seconds() / 3600.0

    latest_kp = None
    if "Kp" in frame.columns:
        kp_series = pd.to_numeric(frame["Kp"], errors="coerce").dropna()
        latest_kp = float(kp_series.iloc[-1]) if not kp_series.empty else None

    peaks = {
        name: float(predictions[f"{name}_zscore"].abs().max())
        for name in features
        if f"{name}_zscore" in predictions.columns
        and pd.notna(predictions[f"{name}_zscore"].abs().max())
    }
    driving = [
        name
        for name in features
        if bool(flags.iloc[-1]) and predictions[f"{name}_flag"].iloc[-1]
    ]

    stale = age > STALENESS_LIMIT.total_seconds() / 3600.0
    return DailyResult(
        status=STATUS_NODATA if stale else STATUS_OK,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        message=(
            f"Newest sample is {age:.1f} h old, beyond the {STALENESS_LIMIT} staleness "
            "limit; treating current conditions as unknown."
            if stale
            else f"Scored {len(frame)} samples; {int(flags.sum())} flagged."
        ),
        latest_sample=newest.isoformat(),
        data_age_hours=round(age, 2),
        n_samples=int(len(frame)),
        n_flagged=int(flags.sum()),
        flagged_fraction=round(float(flags.mean()), 4) if len(flags) else None,
        latest_kp=latest_kp,
        storm_class=_storm_class(latest_kp),
        active_now=bool(flags.iloc[-1]) if len(flags) else None,
        peak_zscores={name: round(value, 2) for name, value in peaks.items()},
        driving_features=driving,
    )


def render(result: DailyResult) -> str:
    """Render the result as a Markdown report."""
    if result.status == STATUS_NODATA:
        badge, headline = "UNKNOWN", "Upstream data unavailable or stale"
    elif result.active_now:
        badge, headline = "ANOMALY", "Detector is firing on the most recent sample"
    else:
        badge, headline = "NOMINAL", "No anomaly on the most recent sample"

    age_text = f"{result.data_age_hours} h" if result.data_age_hours is not None else "n/a"
    lines = [
        "# Space Weather — Latest Automated Detection",
        "",
        f"**Status: {badge}** — {headline}",
        "",
        f"_Generated {result.generated_at} by `scripts/run_daily_detection.py`._",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| Newest sample | {result.latest_sample or 'n/a'} |",
        f"| Data age | {age_text} |",
        f"| Samples scored | {result.n_samples} |",
        f"| Samples flagged | {result.n_flagged}"
        + (
            f" ({result.flagged_fraction:.1%})"
            if result.flagged_fraction is not None
            else ""
        )
        + " |",
        f"| Latest Kp | {result.latest_kp if result.latest_kp is not None else 'n/a'} |",
        f"| Storm class | {result.storm_class or 'n/a'} |",
    ]
    if result.driving_features:
        lines.append(f"| Driving features | {', '.join(result.driving_features)} |")
    if result.peak_zscores:
        lines.append("")
        lines.append("Peak |z| over the window:")
        lines.append("")
        lines.append("| Feature | Peak abs z-score |")
        lines.append("| --- | --- |")
        lines.extend(f"| {name} | {value} |" for name, value in sorted(result.peak_zscores.items()))

    lines += [
        "",
        f"> {result.message}",
        "",
        "---",
        "",
        "**How to read this.** The baseline is the first 60% of the rolling "
        "window, so during a multi-day storm the reference is contaminated and "
        "sensitivity drops. A single flagged sample is not a storm warning — "
        "see [RESULTS.md](../RESULTS.md) for measured precision (0.17–0.39 "
        "depending on configuration). This is a demonstration of an unattended "
        "pipeline, not an operational forecast. For real alerts use "
        "[NOAA SWPC](https://www.swpc.noaa.gov/).",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run daily space-weather anomaly detection.")
    parser.add_argument("--hours", type=int, default=72, help="Window of recent data to score.")
    parser.add_argument("--sigma", type=float, default=3.0, help="SPC sigma threshold.")
    args = parser.parse_args()

    REPORTS_DIR.mkdir(exist_ok=True)
    try:
        frame, message = gather(args.hours)
        if frame is None:
            result = DailyResult(
                status=STATUS_NODATA,
                generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
                message=message,
            )
        else:
            result = detect(frame, args.sigma)
    except Exception:  # noqa: BLE001 - an internal bug must fail loudly
        traceback.print_exc()
        print("internal error: detection pipeline raised; failing loudly.", file=sys.stderr)
        return 1

    (REPORTS_DIR / "latest.md").write_text(render(result), encoding="utf-8")
    (REPORTS_DIR / "latest.json").write_text(
        json.dumps(result.to_dict(), indent=2), encoding="utf-8"
    )
    print(f"status={result.status} flagged={result.n_flagged}/{result.n_samples}")
    print(result.message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
