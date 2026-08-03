"""Validation metrics for space-weather anomaly detectors.

Why this module exists
----------------------
Point-wise classification metrics are the wrong default for time-series
anomaly detection, and reporting them uncritically is one of the most common
mistakes in this literature.  Two illustrations of the problem:

1.  A geomagnetic storm occupies maybe 40 of the 744 hourly samples in a
    month.  A detector that flags *nothing* scores 95% accuracy.  Accuracy is
    therefore meaningless here and this module never computes it.

2.  Suppose a storm spans 24 hours and a detector fires on exactly one hour
    inside it -- the hour the shock arrives.  Point-wise recall is 1/24 = 4%,
    which sounds terrible.  Operationally it is a *complete success*: the
    detector caught the event, with hours of warning.  Point-wise metrics
    punish the behaviour we actually want.

So this module reports two families side by side:

*   **Event-wise** metrics treat each catalogued storm as one unit.  Did we
    detect it at all, within a tolerance window?  This answers "would this
    system have warned an operator?"
*   **Point-wise** metrics treat each timestamp independently.  These are
    still worth reporting because they expose a detector that fires
    constantly -- something event-wise recall alone would happily reward.

A detector is only credible when both are reported. Quoting whichever one
flatters the model is how portfolio projects lose credibility in interviews.

Conventions
-----------
All timestamps are timezone-aware UTC, matching :mod:`src.data_loader`.
Detection input is the boolean ``anomaly`` column produced by detectors in
:mod:`src.models`, or any boolean Series indexed by UTC timestamps.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "storm_catalog.csv"

#: Default half-width of the window around a storm in which a detection
#: counts as a hit.  24 hours is defensible for hourly OMNI2 data: shock
#: arrival to main phase typically spans several hours to a day.  Widen it and
#: recall inflates for free -- so this value must be reported alongside any
#: recall number you quote.
DEFAULT_TOLERANCE = pd.Timedelta(hours=24)

#: Kp below this is treated as geomagnetically quiet, matching
#: ``src.preprocessing.QUIET_KP_THRESHOLD``.
QUIET_KP_THRESHOLD: float = 3.0

#: Undefined metrics return NaN rather than 0.0.  See ``_safe_ratio``.
NAN = float("nan")

_HOUR = pd.Timedelta(hours=1)


def _safe_ratio(numerator: float, denominator: float) -> float:
    """Return ``numerator / denominator``, or NaN when the denominator is zero.

    Returning NaN rather than 0.0 for a zero denominator is a deliberate
    choice that runs through this whole module.  "We evaluated zero events"
    and "we evaluated events and detected none of them" are different
    situations: the first is an invalid experiment, the second is a real
    (bad) result.  Collapsing both to 0.0 makes a misconfigured run
    indistinguishable from a failed detector, and that mistake is very hard
    to notice once the number is in a table.
    """
    return float(numerator) / float(denominator) if denominator else NAN


def _harmonic_mean(precision: float, recall: float) -> float:
    """F1 from precision and recall, tolerating zeros and NaNs.

    F1 is 0.0 when both inputs are defined and zero -- that is a genuine
    "detector found nothing useful" result, not an undefined one -- but NaN
    propagates if either input is undefined.
    """
    if not np.isfinite(precision) or not np.isfinite(recall):
        return NAN
    total = precision + recall
    return 0.0 if total == 0 else 2.0 * precision * recall / total


@dataclass(frozen=True)
class StormEvent:
    """A single catalogued ground-truth storm.

    Attributes:
        name: Human-readable event name, e.g. ``"St. Patrick's Day"``.
        peak: UTC timestamp of maximum disturbance.
        max_kp: Peak planetary K index for the event.
        onset: UTC timestamp of shock arrival, or ``None`` when unknown.
            Lead-time metrics require this; see ROADMAP Milestone 2.
        storm_class: NOAA G-scale class, e.g. ``"G4"``.
        notes: Free-text provenance.
    """

    name: str
    peak: pd.Timestamp
    max_kp: float
    onset: pd.Timestamp | None = None
    storm_class: str = ""
    notes: str = ""

    def window(
        self, tolerance: pd.Timedelta = DEFAULT_TOLERANCE
    ) -> tuple[pd.Timestamp, pd.Timestamp]:
        """Return the ``(start, end)`` interval in which a detection is a hit.

        The window is centred on :attr:`onset` when it is known, and on
        :attr:`peak` otherwise.  Centring on onset is the better choice
        because it is what a forecaster cares about, but the catalog does not
        yet carry onset times for every event.

        The interval is closed on both ends: a detection landing exactly on a
        boundary counts as a hit, and :func:`match_events` compares with
        ``>=`` and ``<=`` to match.
        """
        centre = self.onset if self.onset is not None else self.peak
        return centre - tolerance, centre + tolerance


@dataclass(frozen=True)
class EventMatch:
    """Outcome of comparing one catalogued event against a detection series.

    Attributes:
        event: The catalogued storm this record describes.
        detected: Whether any detection fell inside the event's window.
        first_detection: Earliest in-window detection timestamp, or ``None``.
        n_detections: Count of in-window detected samples.
        lead_time: ``onset - first_detection`` when both are known, else
            ``None``.  Positive means the detector fired *before* onset
            (good); negative means it fired late.
    """

    event: StormEvent
    detected: bool
    first_detection: pd.Timestamp | None
    n_detections: int
    lead_time: pd.Timedelta | None


def load_storm_catalog(path: str | Path | None = None) -> list[StormEvent]:
    """Read the ground-truth storm catalog into :class:`StormEvent` objects.

    The CSV at ``data/storm_catalog.csv`` carries leading ``#`` comment lines
    that document each column; those are skipped.  Blank ``onset_utc`` cells
    become ``None`` rather than ``NaT``, so callers can use a plain
    ``if event.onset is None`` check.

    Args:
        path: Catalog location. Defaults to :data:`DEFAULT_CATALOG_PATH`.

    Returns:
        Events sorted ascending by ``peak``.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If a required column is missing.
    """
    catalog_path = Path(path) if path is not None else DEFAULT_CATALOG_PATH
    if not catalog_path.exists():
        raise FileNotFoundError(f"Storm catalog not found at {catalog_path}")

    frame = pd.read_csv(catalog_path, comment="#")
    missing = [column for column in ("name", "peak_utc", "max_kp") if column not in frame.columns]
    if missing:
        raise ValueError(f"Storm catalog at {catalog_path} is missing columns: {missing}")

    frame["peak_utc"] = pd.to_datetime(frame["peak_utc"], utc=True)
    if "onset_utc" in frame.columns:
        # errors="coerce" turns the intentionally blank onset cells into NaT
        # instead of raising.
        frame["onset_utc"] = pd.to_datetime(frame["onset_utc"], utc=True, errors="coerce")
    else:
        frame["onset_utc"] = pd.NaT

    # Indexed access rather than itertuples: the catalog has a column literally
    # named "class", and itertuples would rename that reserved word to a
    # positional placeholder like "_5".
    events: list[StormEvent] = []
    for position in range(len(frame)):
        onset = frame["onset_utc"].iloc[position]
        events.append(
            StormEvent(
                name=str(frame["name"].iloc[position]),
                peak=frame["peak_utc"].iloc[position],
                max_kp=float(frame["max_kp"].iloc[position]),
                # NaT is falsy but `NaT is None` is False, so converting here
                # rather than downstream avoids a whole class of silent bug.
                onset=None if pd.isna(onset) else onset,
                storm_class=_optional_string(
                    frame["class"].iloc[position] if "class" in frame.columns else ""
                ),
                notes=_optional_string(
                    frame["notes"].iloc[position] if "notes" in frame.columns else ""
                ),
            )
        )
    return sorted(events, key=lambda event: event.peak)


def _optional_string(value: object) -> str:
    """Coerce an optional CSV cell to a plain string, mapping NaN to ``""``."""
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return ""
    return str(value)


def _as_flags(detections: pd.Series) -> pd.Series:
    """Validate and normalise a detection Series to non-null booleans.

    Raises:
        TypeError: If the index is not a tz-aware ``DatetimeIndex``. Naive
            timestamps are rejected rather than assumed to be UTC: silently
            guessing a timezone on space-weather data would shift every
            detection by the local offset and quietly corrupt lead times.
    """
    index = detections.index
    if not isinstance(index, pd.DatetimeIndex) or index.tz is None:
        raise TypeError(
            "detections must be indexed by a timezone-aware DatetimeIndex (UTC); "
            f"got {type(index).__name__} with tz={getattr(index, 'tz', None)!r}."
        )
    if detections.empty:
        return detections.astype(bool)
    return detections.fillna(False).astype(bool)


def _truth_mask(
    index: pd.DatetimeIndex,
    events: Sequence[StormEvent],
    tolerance: pd.Timedelta,
) -> pd.Series:
    """Boolean Series marking timestamps that fall inside any event window."""
    mask = pd.Series(False, index=index)
    for event in events:
        start, end = event.window(tolerance)
        mask |= (index >= start) & (index <= end)
    return mask


def match_events(
    detections: pd.Series,
    events: Sequence[StormEvent],
    tolerance: pd.Timedelta = DEFAULT_TOLERANCE,
) -> list[EventMatch]:
    """Pair each catalogued event with the detections that fall in its window.

    Only events whose window overlaps the span of ``detections`` are
    evaluated.  This matters: scoring the Halloween 2003 storm as a "miss"
    when you only fed the detector March 2015 data would be a bug that
    silently destroys your recall number.  Events outside the data span are
    omitted from the result entirely.

    Args:
        detections: Boolean Series indexed by tz-aware UTC timestamps. Truthy
            values are detections. NaN is treated as ``False``.
        events: Catalogued events, e.g. from :func:`load_storm_catalog`.
        tolerance: Half-width of the hit window around each event.

    Returns:
        One :class:`EventMatch` per in-span event, ordered as ``events`` was.

    Raises:
        TypeError: If ``detections`` lacks a tz-aware DatetimeIndex.
    """
    flags = _as_flags(detections)
    if flags.empty:
        return []

    span_start = flags.index.min()
    span_end = flags.index.max()

    matches: list[EventMatch] = []
    for event in events:
        start, end = event.window(tolerance)
        # Interval-overlap test, not containment: a storm whose window is only
        # partly covered by the data is still a fair thing to score.
        if end < span_start or start > span_end:
            continue

        in_window = flags.loc[(flags.index >= start) & (flags.index <= end)]
        hits = in_window[in_window]
        detected = bool(len(hits))
        first_detection = hits.index.min() if detected else None
        lead_time = (
            event.onset - first_detection
            if detected and event.onset is not None
            else None
        )
        matches.append(
            EventMatch(
                event=event,
                detected=detected,
                first_detection=first_detection,
                n_detections=int(len(hits)),
                lead_time=lead_time,
            )
        )
    return matches


def event_metrics(
    matches: Sequence[EventMatch],
    detections: pd.Series,
    tolerance: pd.Timedelta = DEFAULT_TOLERANCE,
) -> dict[str, float]:
    """Compute event-wise recall and precision.

    Definitions used here -- write these down, because reviewers will ask and
    the literature is not consistent:

    *   **Event recall** = (events with >=1 in-window detection) / (events in
        span).  This is the headline number: what fraction of real storms
        would this system have caught?
    *   **Event precision** = (detections falling inside some event window) /
        (total detections).  Note this is *detection*-weighted, not
        event-weighted, because there is no natural way to group consecutive
        false detections into "false events" without another arbitrary
        parameter.
    *   **F1** = harmonic mean of the two above.

    Returns:
        Keys: ``n_events``, ``n_detected_events``, ``event_recall``,
        ``n_detections``, ``n_true_detections``, ``event_precision``,
        ``event_f1``, ``tolerance_hours``.
    """
    flags = _as_flags(detections)
    n_events = len(matches)
    n_detected_events = sum(1 for match in matches if match.detected)
    recall = _safe_ratio(n_detected_events, n_events)

    n_detections = int(flags.sum())
    truth = _truth_mask(flags.index, [match.event for match in matches], tolerance)
    n_true_detections = int((flags & truth).sum())
    precision = _safe_ratio(n_true_detections, n_detections)

    return {
        "n_events": n_events,
        "n_detected_events": n_detected_events,
        "event_recall": recall,
        "n_detections": n_detections,
        "n_true_detections": n_true_detections,
        "event_precision": precision,
        "event_f1": _harmonic_mean(precision, recall),
        # The tolerance travels with the metrics: a recall figure quoted
        # without its window is not interpretable, and widening the window
        # inflates recall for free.
        "tolerance_hours": tolerance / _HOUR,
    }


def pointwise_metrics(
    detections: pd.Series,
    events: Sequence[StormEvent],
    tolerance: pd.Timedelta = DEFAULT_TOLERANCE,
) -> dict[str, float]:
    """Compute per-timestamp confusion-matrix metrics.

    Every timestamp in ``detections`` is labelled positive if it falls inside
    any event window, negative otherwise.  Then:

    *   ``precision`` = TP / (TP + FP)
    *   ``recall`` = TP / (TP + FN)
    *   ``f1`` = harmonic mean
    *   ``false_positive_rate`` = FP / (FP + TN)

    Deliberately absent: accuracy. With ~5% positive class it is dominated by
    the negatives and tells you nothing. Do not add it.

    Returns:
        Keys: ``tp``, ``fp``, ``tn``, ``fn``, ``precision``, ``recall``,
        ``f1``, ``false_positive_rate``, ``n_samples``, ``positive_rate``.
    """
    flags = _as_flags(detections)
    truth = _truth_mask(flags.index, events, tolerance)

    # Cast to plain int: the daily automation serialises this dict to JSON and
    # numpy.int64 is not JSON-serialisable.
    true_positives = int((flags & truth).sum())
    false_positives = int((flags & ~truth).sum())
    false_negatives = int((~flags & truth).sum())
    true_negatives = int((~flags & ~truth).sum())

    precision = _safe_ratio(true_positives, true_positives + false_positives)
    recall = _safe_ratio(true_positives, true_positives + false_negatives)

    return {
        "tp": true_positives,
        "fp": false_positives,
        "tn": true_negatives,
        "fn": false_negatives,
        "precision": precision,
        "recall": recall,
        "f1": _harmonic_mean(precision, recall),
        "false_positive_rate": _safe_ratio(false_positives, false_positives + true_negatives),
        "n_samples": int(len(flags)),
        "positive_rate": _safe_ratio(int(truth.sum()), len(flags)),
    }


def false_alarm_rate(
    detections: pd.Series,
    frame: pd.DataFrame,
    kp_column: str = "Kp",
    kp_threshold: float = QUIET_KP_THRESHOLD,
) -> dict[str, float]:
    """Measure how often the detector fires during geomagnetically quiet time.

    This is the metric that catches a detector gaming event recall by firing
    constantly.  It is scoped to rows where ``Kp < kp_threshold``, i.e. time
    when by independent measurement nothing was happening.

    Using Kp as the quiet label -- rather than "not inside a catalog window"
    -- is the more honest choice, because the catalog only lists five famous
    storms and the real record contains hundreds of moderate ones. Anything
    the catalog omits would otherwise be scored as a false alarm.

    Args:
        detections: Boolean Series of detections.
        frame: Source data containing ``kp_column``, sharing an index with
            ``detections``.
        kp_column: Name of the Kp column.
        kp_threshold: Kp below this counts as quiet.

    Returns:
        Keys: ``n_quiet_samples``, ``n_quiet_detections``,
        ``quiet_false_alarm_rate``, ``kp_threshold``.

    Raises:
        ValueError: If ``kp_column`` is absent from ``frame``.
    """
    if kp_column not in frame.columns:
        raise ValueError(
            f"frame has no {kp_column!r} column; cannot identify quiet periods. "
            f"Available columns: {list(frame.columns)}."
        )

    flags = _as_flags(detections)
    kp = pd.to_numeric(frame[kp_column], errors="coerce")
    # Rows with unknown Kp are neither quiet nor active. Excluding them keeps
    # them out of the denominator instead of deflating the rate.
    quiet = (kp < kp_threshold) & kp.notna()
    quiet = quiet.reindex(flags.index, fill_value=False)

    n_quiet = int(quiet.sum())
    n_quiet_detections = int((flags & quiet).sum())

    return {
        "n_quiet_samples": n_quiet,
        "n_quiet_detections": n_quiet_detections,
        "quiet_false_alarm_rate": _safe_ratio(n_quiet_detections, n_quiet),
        "kp_threshold": float(kp_threshold),
    }


def lead_time_summary(matches: Sequence[EventMatch]) -> dict[str, float]:
    """Summarise warning time across detected events.

    For space weather this is arguably the single most valuable metric: a
    detector that reliably fires two hours before shock arrival has real
    operational worth, and one that fires two hours after has almost none,
    even at identical recall.

    Only events that were both detected *and* have a known ``onset``
    contribute.  Events missing onset are counted in ``n_missing_onset`` so
    the caller can see how much of the catalog was unusable.

    Returns:
        Keys: ``n_with_lead_time``, ``n_missing_onset``, ``mean_lead_hours``,
        ``median_lead_hours``, ``min_lead_hours``, ``max_lead_hours``.  All
        hour values are NaN when ``n_with_lead_time`` is zero -- which is the
        correct output while the catalog's onset column is blank, not a bug.
    """
    leads = [
        match.lead_time / _HOUR
        for match in matches
        if match.detected and match.lead_time is not None
    ]
    n_missing_onset = sum(1 for match in matches if match.event.onset is None)

    if not leads:
        return {
            "n_with_lead_time": 0,
            "n_missing_onset": n_missing_onset,
            "mean_lead_hours": NAN,
            "median_lead_hours": NAN,
            "min_lead_hours": NAN,
            "max_lead_hours": NAN,
        }

    values = np.asarray(leads, dtype=float)
    return {
        "n_with_lead_time": len(leads),
        "n_missing_onset": n_missing_onset,
        "mean_lead_hours": float(values.mean()),
        "median_lead_hours": float(np.median(values)),
        "min_lead_hours": float(values.min()),
        "max_lead_hours": float(values.max()),
    }


def evaluate_detector(
    detections: pd.Series,
    frame: pd.DataFrame,
    events: Sequence[StormEvent] | None = None,
    tolerance: pd.Timedelta = DEFAULT_TOLERANCE,
    kp_column: str = "Kp",
) -> dict[str, object]:
    """Run the full evaluation suite and return one nested report.

    This is the function notebooks and the daily automation should call.
    Having a single entry point means every reported number comes from the
    same code path, so a notebook figure and the automated daily summary can
    never disagree.

    Args:
        detections: Boolean detection Series.
        frame: Source data (needs ``kp_column`` for false-alarm rate).
        events: Catalog to score against; loads the default catalog if
            ``None``.
        tolerance: Hit-window half-width.
        kp_column: Kp column name in ``frame``.

    Returns:
        ``{"event": {...}, "pointwise": {...}, "false_alarm": {...} | None,
        "lead_time": {...}, "matches": [EventMatch, ...],
        "span": {"start": ..., "end": ..., "n_samples": int}}``
    """
    if events is None:
        events = load_storm_catalog()

    flags = _as_flags(detections)
    matches = match_events(flags, events, tolerance=tolerance)
    # Point-wise metrics are scored only against in-span events, so the two
    # metric families describe the same experiment.
    in_span_events = [match.event for match in matches]

    quiet_stats = None
    if kp_column in frame.columns:
        quiet_stats = false_alarm_rate(flags, frame, kp_column=kp_column)

    return {
        "event": event_metrics(matches, flags, tolerance=tolerance),
        "pointwise": pointwise_metrics(flags, in_span_events, tolerance=tolerance),
        "false_alarm": quiet_stats,
        "lead_time": lead_time_summary(matches),
        "matches": matches,
        "span": {
            "start": flags.index.min() if len(flags) else None,
            "end": flags.index.max() if len(flags) else None,
            "n_samples": int(len(flags)),
        },
    }


def _format_number(value: object, digits: int = 3) -> str:
    """Render a metric for Markdown, showing undefined values as ``n/a``."""
    if value is None:
        return "n/a"
    if isinstance(value, (int, np.integer)) and not isinstance(value, bool):
        return str(int(value))
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return "n/a" if not np.isfinite(number) else f"{number:.{digits}f}"


def format_report(report: Mapping[str, object]) -> str:
    """Render :func:`evaluate_detector` output as a Markdown block.

    Used by notebooks for display and by the scheduled daily job to write
    ``reports/latest.md``. Plain Markdown so it renders on GitHub with no
    extra tooling.

    The configuration (tolerance, Kp threshold) is printed with the metrics:
    a metrics table that omits its own configuration is not reproducible.
    """
    event = report["event"]
    pointwise = report["pointwise"]
    lead = report["lead_time"]
    quiet = report.get("false_alarm")
    span = report.get("span", {})

    tolerance_hours = _format_number(event.get("tolerance_hours"), 1)
    lines: list[str] = []

    start, end = span.get("start"), span.get("end")
    if start is not None and end is not None:
        lines.append(
            f"**Window evaluated:** {start:%Y-%m-%d %H:%M} to {end:%Y-%m-%d %H:%M} UTC "
            f"({span.get('n_samples', 0)} samples)"
        )
    lines.append(f"**Hit tolerance:** +/-{tolerance_hours} h around storm onset (or peak)")
    if quiet:
        lines.append(f"**Quiet threshold:** Kp < {_format_number(quiet['kp_threshold'], 1)}")
    lines.append("")

    lines.extend(
        [
            "| Metric | Value |",
            "| --- | --- |",
            f"| Events evaluated | {_format_number(event['n_events'])} |",
            f"| Events detected | {_format_number(event['n_detected_events'])} |",
            f"| **Event recall** | {_format_number(event['event_recall'])} |",
            f"| **Event precision** | {_format_number(event['event_precision'])} |",
            f"| Event F1 | {_format_number(event['event_f1'])} |",
            f"| Point-wise precision | {_format_number(pointwise['precision'])} |",
            f"| Point-wise recall | {_format_number(pointwise['recall'])} |",
            f"| Point-wise F1 | {_format_number(pointwise['f1'])} |",
            f"| Point-wise FPR | {_format_number(pointwise['false_positive_rate'])} |",
            f"| Samples flagged | {_format_number(event['n_detections'])} "
            f"of {_format_number(pointwise['n_samples'])} |",
        ]
    )
    if quiet:
        lines.append(
            f"| Quiet-time false-alarm rate | "
            f"{_format_number(quiet['quiet_false_alarm_rate'])} "
            f"({_format_number(quiet['n_quiet_detections'])}"
            f"/{_format_number(quiet['n_quiet_samples'])}) |"
        )
    lines.append(f"| Mean detection lead time (h) | {_format_number(lead['mean_lead_hours'], 2)} |")

    if lead["n_with_lead_time"] == 0 and lead["n_missing_onset"]:
        lines.append("")
        lines.append(
            f"> Lead time is unavailable: {lead['n_missing_onset']} of the evaluated "
            "events have no recorded onset time in the catalog. See ROADMAP Milestone 2."
        )
    return "\n".join(lines)


__all__: Iterable[str] = [
    "DEFAULT_CATALOG_PATH",
    "DEFAULT_TOLERANCE",
    "QUIET_KP_THRESHOLD",
    "StormEvent",
    "EventMatch",
    "load_storm_catalog",
    "match_events",
    "event_metrics",
    "pointwise_metrics",
    "false_alarm_rate",
    "lead_time_summary",
    "evaluate_detector",
    "format_report",
]
