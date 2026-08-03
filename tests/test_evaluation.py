"""Specification tests for :mod:`src.evaluation`.

READ THIS FIRST
---------------
These tests are the spec. Every function in ``src/evaluation.py`` currently
raises ``NotImplementedError``; your job is to make this file go green
without editing it.

Suggested order -- each block is independently completable, so you can stop
after any one of them and the repo is still in a coherent state:

    1. StormEvent.window          (5 tests)  -- warm-up, pure arithmetic
    2. load_storm_catalog         (6 tests)  -- I/O and parsing
    3. match_events               (9 tests)  -- the core logic, and the only
                                               genuinely tricky one
    4. event_metrics              (6 tests)
    5. pointwise_metrics          (6 tests)
    6. false_alarm_rate           (4 tests)
    7. lead_time_summary          (4 tests)
    8. evaluate_detector          (4 tests)
    9. format_report              (2 tests)

Run one block at a time:

    pytest tests/test_evaluation.py -k window -v

If you find a test that seems wrong, say so rather than bending the
implementation to fit it. Arguing with the spec is part of the exercise.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from src.evaluation import (
    DEFAULT_TOLERANCE,
    EventMatch,
    StormEvent,
    evaluate_detector,
    event_metrics,
    false_alarm_rate,
    format_report,
    lead_time_summary,
    load_storm_catalog,
    match_events,
    pointwise_metrics,
)


def ts(value: str) -> pd.Timestamp:
    """Shorthand for a tz-aware UTC timestamp."""
    return pd.Timestamp(value, tz="UTC")


def hourly(start: str, periods: int) -> pd.DatetimeIndex:
    return pd.date_range(ts(start), periods=periods, freq="h")


def detections_from(index: pd.DatetimeIndex, true_at: list[str]) -> pd.Series:
    """Boolean Series over ``index``, True at the given timestamps."""
    series = pd.Series(False, index=index)
    for stamp in true_at:
        series.loc[ts(stamp)] = True
    return series


@pytest.fixture
def storm() -> StormEvent:
    """The March 2015 storm, with a known onset for lead-time tests."""
    return StormEvent(
        name="St. Patrick's Day",
        peak=ts("2015-03-17 22:00"),
        max_kp=8.0,
        onset=ts("2015-03-17 04:00"),
        storm_class="G4",
    )


@pytest.fixture
def storm_no_onset() -> StormEvent:
    return StormEvent(name="Unknown Onset", peak=ts("2015-03-17 22:00"), max_kp=8.0)


# ---------------------------------------------------------------------------
# 1. StormEvent.window
# ---------------------------------------------------------------------------


def test_window_centres_on_onset_when_known(storm):
    start, end = storm.window(pd.Timedelta(hours=6))
    assert start == ts("2015-03-16 22:00")
    assert end == ts("2015-03-17 10:00")


def test_window_falls_back_to_peak_without_onset(storm_no_onset):
    start, end = storm_no_onset.window(pd.Timedelta(hours=6))
    assert start == ts("2015-03-17 16:00")
    assert end == ts("2015-03-18 04:00")


def test_window_default_tolerance_is_24h(storm_no_onset):
    start, end = storm_no_onset.window()
    assert end - start == 2 * DEFAULT_TOLERANCE


def test_window_zero_tolerance_is_a_point(storm):
    start, end = storm.window(pd.Timedelta(0))
    assert start == end == storm.onset


def test_window_returns_tz_aware_timestamps(storm):
    start, end = storm.window()
    assert start.tz is not None and end.tz is not None


# ---------------------------------------------------------------------------
# 2. load_storm_catalog
# ---------------------------------------------------------------------------


def test_load_catalog_returns_storm_events():
    events = load_storm_catalog()
    assert len(events) == 5
    assert all(isinstance(event, StormEvent) for event in events)


def test_load_catalog_is_sorted_by_peak():
    events = load_storm_catalog()
    peaks = [event.peak for event in events]
    assert peaks == sorted(peaks)
    assert events[0].name == "Bastille Day"
    assert events[-1].name == "Gannon Storm"


def test_load_catalog_peaks_are_tz_aware_utc():
    for event in load_storm_catalog():
        assert event.peak.tz is not None
        assert event.peak.utcoffset() == pd.Timedelta(0)


def test_load_catalog_blank_onset_becomes_none():
    # The shipped catalog has no onset times yet. They must come back as None,
    # not NaT, so `if event.onset is None` works. NaT is falsy but not None,
    # and `NaT is None` is False -- a classic source of silent bugs.
    for event in load_storm_catalog():
        assert event.onset is None


def test_load_catalog_parses_kp_as_float():
    events = load_storm_catalog()
    kp_by_name = {event.name: event.max_kp for event in events}
    assert kp_by_name["Gannon Storm"] == pytest.approx(9.0)
    assert isinstance(kp_by_name["Gannon Storm"], float)


def test_load_catalog_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_storm_catalog(tmp_path / "nope.csv")


# ---------------------------------------------------------------------------
# 3. match_events  -- the core logic
# ---------------------------------------------------------------------------


def test_match_detects_event_inside_window(storm):
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(index, ["2015-03-17 06:00"])
    (match,) = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    assert match.detected is True
    assert match.first_detection == ts("2015-03-17 06:00")
    assert match.n_detections == 1


def test_match_reports_miss_when_detection_outside_window(storm):
    index = hourly("2015-03-15 00:00", 96)
    # 2015-03-15 is well outside onset +/- 12h.
    detections = detections_from(index, ["2015-03-15 03:00"])
    (match,) = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    assert match.detected is False
    assert match.first_detection is None
    assert match.n_detections == 0


def test_match_first_detection_is_the_earliest_not_the_strongest(storm):
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(
        index, ["2015-03-17 08:00", "2015-03-17 02:00", "2015-03-17 12:00"]
    )
    (match,) = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    assert match.first_detection == ts("2015-03-17 02:00")
    assert match.n_detections == 3


def test_match_skips_events_outside_the_data_span(storm):
    # Only March 2015 data supplied, but the catalog spans 2000-2024. Scoring
    # the 2003 Halloween storm as a miss here would be a bug: it would drag
    # recall down for an event we never gave the detector a chance at.
    halloween = StormEvent(name="Halloween Storms", peak=ts("2003-10-29 06:00"), max_kp=9.0)
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(index, ["2015-03-17 06:00"])
    matches = match_events(detections, [halloween, storm])
    assert [m.event.name for m in matches] == ["St. Patrick's Day"]


def test_match_computes_positive_lead_time_when_detection_precedes_onset(storm):
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(index, ["2015-03-17 01:00"])  # onset is 04:00
    (match,) = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    assert match.lead_time == pd.Timedelta(hours=3)


def test_match_lead_time_is_negative_when_detection_is_late(storm):
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(index, ["2015-03-17 09:00"])  # onset is 04:00
    (match,) = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    assert match.lead_time == pd.Timedelta(hours=-5)


def test_match_lead_time_is_none_without_onset(storm_no_onset):
    index = hourly("2015-03-15 00:00", 96)
    detections = detections_from(index, ["2015-03-17 20:00"])
    (match,) = match_events(detections, [storm_no_onset], tolerance=pd.Timedelta(hours=12))
    assert match.detected is True
    assert match.lead_time is None


def test_match_empty_detections_yields_no_matches(storm):
    empty = pd.Series(dtype=bool, index=pd.DatetimeIndex([], tz="UTC"))
    assert match_events(empty, [storm]) == []


def test_match_rejects_naive_index(storm):
    naive = pd.Series([True], index=pd.DatetimeIndex(["2015-03-17 06:00"]))
    with pytest.raises(TypeError):
        match_events(naive, [storm])


# ---------------------------------------------------------------------------
# 4. event_metrics
# ---------------------------------------------------------------------------


def test_event_metrics_perfect_detection(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 05:00"])
    matches = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    metrics = event_metrics(matches, detections, tolerance=pd.Timedelta(hours=12))
    assert metrics["n_events"] == 1
    assert metrics["n_detected_events"] == 1
    assert metrics["event_recall"] == pytest.approx(1.0)
    assert metrics["event_precision"] == pytest.approx(1.0)
    assert metrics["event_f1"] == pytest.approx(1.0)


def test_event_metrics_precision_penalises_out_of_window_detections(storm):
    index = hourly("2015-03-16 00:00", 48)
    # One good detection near onset, three spurious ones far away.
    detections = detections_from(
        index, ["2015-03-17 05:00", "2015-03-16 01:00", "2015-03-16 02:00", "2015-03-16 03:00"]
    )
    matches = match_events(detections, [storm], tolerance=pd.Timedelta(hours=6))
    metrics = event_metrics(matches, detections, tolerance=pd.Timedelta(hours=6))
    assert metrics["event_recall"] == pytest.approx(1.0)
    assert metrics["n_detections"] == 4
    assert metrics["n_true_detections"] == 1
    assert metrics["event_precision"] == pytest.approx(0.25)


def test_event_metrics_recall_is_nan_with_no_events_in_span():
    index = hourly("2015-03-16 00:00", 24)
    detections = detections_from(index, ["2015-03-16 05:00"])
    metrics = event_metrics([], detections)
    # NaN, not 0.0: zero events means the experiment was invalid, which is a
    # different situation from a detector that missed everything.
    assert math.isnan(metrics["event_recall"])


def test_event_metrics_precision_is_nan_with_no_detections(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = pd.Series(False, index=index)
    matches = match_events(detections, [storm], tolerance=pd.Timedelta(hours=12))
    metrics = event_metrics(matches, detections, tolerance=pd.Timedelta(hours=12))
    assert metrics["event_recall"] == pytest.approx(0.0)
    assert math.isnan(metrics["event_precision"])


def test_event_metrics_f1_is_zero_not_error_when_both_zero(storm):
    index = hourly("2015-03-16 00:00", 48)
    detections = detections_from(index, ["2015-03-16 01:00"])
    matches = match_events(detections, [storm], tolerance=pd.Timedelta(hours=2))
    metrics = event_metrics(matches, detections, tolerance=pd.Timedelta(hours=2))
    assert metrics["event_recall"] == pytest.approx(0.0)
    assert metrics["event_precision"] == pytest.approx(0.0)
    assert metrics["event_f1"] == pytest.approx(0.0)


def test_event_metrics_echoes_tolerance(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 05:00"])
    matches = match_events(detections, [storm], tolerance=pd.Timedelta(hours=9))
    metrics = event_metrics(matches, detections, tolerance=pd.Timedelta(hours=9))
    # A recall number without its tolerance is not interpretable, so the
    # tolerance travels with the metrics.
    assert metrics["tolerance_hours"] == pytest.approx(9.0)


# ---------------------------------------------------------------------------
# 5. pointwise_metrics
# ---------------------------------------------------------------------------


def test_pointwise_confusion_counts(storm):
    # 12 hourly samples 00:00-11:00. Window = onset(04:00) +/- 2h = 02:00-06:00,
    # so positives are 02,03,04,05,06 -> 5 samples, 7 negatives.
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 03:00", "2015-03-17 09:00"])
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    assert metrics["n_samples"] == 12
    assert metrics["tp"] == 1
    assert metrics["fp"] == 1
    assert metrics["fn"] == 4
    assert metrics["tn"] == 6


def test_pointwise_precision_and_recall(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 03:00", "2015-03-17 09:00"])
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.2)
    assert metrics["f1"] == pytest.approx(2 * 0.5 * 0.2 / 0.7)


def test_pointwise_counts_are_json_serialisable(storm):
    # numpy.int64 is not JSON-serialisable and the Milestone 4 scheduled job
    # writes this dict straight to JSON.
    import json

    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 03:00"])
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    for key in ("tp", "fp", "tn", "fn", "n_samples"):
        assert type(metrics[key]) is int
    json.dumps({k: v for k, v in metrics.items()})


def test_pointwise_no_accuracy_key(storm):
    # Accuracy is meaningless on a ~5% positive class. If you add it, a
    # detect-nothing model scores 95% and the metric misleads a reader.
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 03:00"])
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    assert "accuracy" not in metrics


def test_pointwise_precision_nan_when_nothing_flagged(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = pd.Series(False, index=index)
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    assert math.isnan(metrics["precision"])
    assert metrics["recall"] == pytest.approx(0.0)


def test_pointwise_positive_rate(storm):
    index = hourly("2015-03-17 00:00", 12)
    detections = detections_from(index, ["2015-03-17 03:00"])
    metrics = pointwise_metrics(detections, [storm], tolerance=pd.Timedelta(hours=2))
    # 5 of 12 samples are inside the storm window.
    assert metrics["positive_rate"] == pytest.approx(5 / 12)


# ---------------------------------------------------------------------------
# 6. false_alarm_rate
# ---------------------------------------------------------------------------


def test_false_alarm_rate_counts_only_quiet_rows():
    index = hourly("2015-03-01 00:00", 6)
    frame = pd.DataFrame({"Kp": [1.0, 1.0, 1.0, 7.0, 7.0, 7.0]}, index=index)
    # Two detections in quiet rows, one during an active row.
    detections = detections_from(
        index, ["2015-03-01 00:00", "2015-03-01 01:00", "2015-03-01 04:00"]
    )
    result = false_alarm_rate(detections, frame)
    assert result["n_quiet_samples"] == 3
    assert result["n_quiet_detections"] == 2
    assert result["quiet_false_alarm_rate"] == pytest.approx(2 / 3)


def test_false_alarm_rate_excludes_nan_kp_from_denominator():
    index = hourly("2015-03-01 00:00", 4)
    frame = pd.DataFrame({"Kp": [1.0, float("nan"), 1.0, 8.0]}, index=index)
    detections = detections_from(index, ["2015-03-01 00:00"])
    result = false_alarm_rate(detections, frame)
    # NaN Kp is neither quiet nor active -- it is unknown, so it must not pad
    # the denominator and quietly deflate the false-alarm rate.
    assert result["n_quiet_samples"] == 2
    assert result["quiet_false_alarm_rate"] == pytest.approx(0.5)


def test_false_alarm_rate_missing_kp_column_raises():
    index = hourly("2015-03-01 00:00", 3)
    frame = pd.DataFrame({"speed": [400.0, 410.0, 420.0]}, index=index)
    with pytest.raises(ValueError):
        false_alarm_rate(pd.Series(False, index=index), frame)


def test_false_alarm_rate_respects_custom_threshold():
    index = hourly("2015-03-01 00:00", 4)
    frame = pd.DataFrame({"Kp": [1.0, 2.0, 4.0, 4.0]}, index=index)
    detections = detections_from(index, ["2015-03-01 02:00"])
    result = false_alarm_rate(detections, frame, kp_threshold=5.0)
    assert result["n_quiet_samples"] == 4
    assert result["n_quiet_detections"] == 1
    assert result["kp_threshold"] == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# 7. lead_time_summary
# ---------------------------------------------------------------------------


def _match(name: str, lead_hours: float | None, detected: bool = True, onset=True) -> EventMatch:
    event = StormEvent(
        name=name,
        peak=ts("2015-03-17 22:00"),
        max_kp=8.0,
        onset=ts("2015-03-17 04:00") if onset else None,
    )
    return EventMatch(
        event=event,
        detected=detected,
        first_detection=ts("2015-03-17 02:00") if detected else None,
        n_detections=1 if detected else 0,
        lead_time=pd.Timedelta(hours=lead_hours) if lead_hours is not None else None,
    )


def test_lead_time_summary_basic_statistics():
    matches = [_match("a", 3.0), _match("b", 1.0), _match("c", -2.0)]
    summary = lead_time_summary(matches)
    assert summary["n_with_lead_time"] == 3
    assert summary["mean_lead_hours"] == pytest.approx(2 / 3)
    assert summary["median_lead_hours"] == pytest.approx(1.0)
    assert summary["min_lead_hours"] == pytest.approx(-2.0)
    assert summary["max_lead_hours"] == pytest.approx(3.0)


def test_lead_time_summary_counts_missing_onset():
    matches = [_match("a", 3.0), _match("b", None, onset=False)]
    summary = lead_time_summary(matches)
    assert summary["n_with_lead_time"] == 1
    assert summary["n_missing_onset"] == 1


def test_lead_time_summary_ignores_undetected_events():
    matches = [_match("a", 3.0), _match("b", None, detected=False)]
    summary = lead_time_summary(matches)
    assert summary["n_with_lead_time"] == 1


def test_lead_time_summary_all_nan_when_nothing_usable():
    matches = [_match("a", None, onset=False)]
    summary = lead_time_summary(matches)
    assert summary["n_with_lead_time"] == 0
    # All-NaN is the honest answer while the catalog's onset column is blank.
    for key in ("mean_lead_hours", "median_lead_hours", "min_lead_hours", "max_lead_hours"):
        assert math.isnan(summary[key])


# ---------------------------------------------------------------------------
# 8. evaluate_detector
# ---------------------------------------------------------------------------


@pytest.fixture
def small_frame() -> pd.DataFrame:
    index = hourly("2015-03-17 00:00", 12)
    return pd.DataFrame(
        {
            "speed": [400.0] * 6 + [700.0] * 6,
            "Kp": [1.0] * 6 + [8.0] * 6,
        },
        index=index,
    )


def test_evaluate_detector_returns_all_sections(small_frame, storm):
    detections = detections_from(small_frame.index, ["2015-03-17 05:00"])
    report = evaluate_detector(
        detections, small_frame, events=[storm], tolerance=pd.Timedelta(hours=6)
    )
    for section in ("event", "pointwise", "false_alarm", "lead_time", "matches", "span"):
        assert section in report


def test_evaluate_detector_span_describes_the_data(small_frame, storm):
    detections = detections_from(small_frame.index, ["2015-03-17 05:00"])
    report = evaluate_detector(detections, small_frame, events=[storm])
    assert report["span"]["n_samples"] == 12
    assert report["span"]["start"] == ts("2015-03-17 00:00")
    assert report["span"]["end"] == ts("2015-03-17 11:00")


def test_evaluate_detector_handles_frame_without_kp(storm):
    index = hourly("2015-03-17 00:00", 12)
    frame = pd.DataFrame({"speed": [400.0] * 12}, index=index)
    detections = detections_from(index, ["2015-03-17 05:00"])
    report = evaluate_detector(detections, frame, events=[storm])
    # Missing Kp must degrade gracefully -- the rest of the report is valid.
    assert report["false_alarm"] is None
    assert report["event"]["n_events"] == 1


def test_evaluate_detector_loads_default_catalog_when_events_omitted(small_frame):
    detections = detections_from(small_frame.index, ["2015-03-17 05:00"])
    report = evaluate_detector(detections, small_frame)
    # Only the March 2015 storm is in span, so the other four are dropped.
    assert report["event"]["n_events"] == 1


# ---------------------------------------------------------------------------
# 9. format_report
# ---------------------------------------------------------------------------


def test_format_report_returns_markdown(small_frame, storm):
    detections = detections_from(small_frame.index, ["2015-03-17 05:00"])
    report = evaluate_detector(detections, small_frame, events=[storm])
    text = format_report(report)
    assert isinstance(text, str)
    assert "|" in text  # a Markdown table


def test_format_report_includes_configuration(small_frame, storm):
    detections = detections_from(small_frame.index, ["2015-03-17 05:00"])
    report = evaluate_detector(
        detections, small_frame, events=[storm], tolerance=pd.Timedelta(hours=9)
    )
    text = format_report(report)
    # A metrics table that omits its own tolerance is not reproducible.
    assert "9" in text
