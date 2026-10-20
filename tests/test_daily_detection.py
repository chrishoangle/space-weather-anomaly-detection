"""Tests for the unattended daily detection job.

The behaviour under test is not "does it detect storms" -- that is
``test_models.py`` and ``RESULTS.md``. It is the operational contract: an
automated monitor must never report "all clear" when it actually has no idea.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from scripts.run_daily_detection import (
    STATUS_NODATA,
    STATUS_OK,
    VERDICT_FIELDS,
    WEB_STATUS_FIELDS,
    WEB_STATUS_SCHEMA,
    DailyResult,
    detect,
    render,
    web_status,
)


def _recent_frame(n: int = 200, storm: bool = False, age_hours: float = 0.5) -> pd.DataFrame:
    """Synthetic recent NOAA-style window ending ``age_hours`` ago."""
    end = datetime.now(UTC) - timedelta(hours=age_hours)
    index = pd.date_range(end - timedelta(minutes=n - 1), periods=n, freq="min", tz="UTC")
    rng = np.random.default_rng(0)
    frame = pd.DataFrame(
        {
            "speed": rng.normal(400, 10, n),
            "density": rng.normal(5, 0.5, n),
            "temperature": rng.normal(80_000, 4_000, n),
            "Kp": np.full(n, 2.0),
        },
        index=index,
    )
    if storm:
        frame.iloc[-20:, frame.columns.get_loc("speed")] = 800.0
        frame.iloc[-20:, frame.columns.get_loc("Kp")] = 7.0
    return frame


def test_detect_reports_ok_on_fresh_quiet_data():
    result = detect(_recent_frame(), sigma=3.0)
    assert result.status == STATUS_OK
    assert result.active_now is False
    assert result.n_samples == 200


def test_detect_flags_an_ongoing_storm():
    result = detect(_recent_frame(storm=True), sigma=3.0)
    assert result.status == STATUS_OK
    assert result.active_now is True
    assert result.n_flagged > 0
    # Interpretability must survive into the automated report.
    assert "speed" in (result.driving_features or [])


def test_detect_marks_stale_data_as_unknown_not_quiet():
    # THE critical test. A pipeline whose fetch silently broke a week ago must
    # not keep publishing "nominal" -- that is worse than no monitor at all.
    result = detect(_recent_frame(age_hours=30), sigma=3.0)
    assert result.status == STATUS_NODATA
    assert "staleness" in result.message


def test_detect_reports_storm_class_from_kp():
    result = detect(_recent_frame(storm=True), sigma=3.0)
    assert result.latest_kp == pytest.approx(7.0)
    assert result.storm_class == "G3 strong"


def test_detect_handles_missing_kp_column():
    frame = _recent_frame().drop(columns=["Kp"])
    result = detect(frame, sigma=3.0)
    assert result.latest_kp is None
    assert result.storm_class is None


def test_render_nodata_says_unknown_never_nominal():
    result = DailyResult(
        status=STATUS_NODATA,
        generated_at="2026-08-03T00:00:00+00:00",
        message="upstream down",
    )
    text = render(result)
    assert "UNKNOWN" in text
    assert "NOMINAL" not in text


def test_render_marks_an_active_anomaly():
    text = render(detect(_recent_frame(storm=True), sigma=3.0))
    assert "ANOMALY" in text


def test_render_is_markdown_with_a_table():
    text = render(detect(_recent_frame(), sigma=3.0))
    assert text.startswith("#")
    assert "| Field | Value |" in text


def test_result_is_json_serialisable():
    # The workflow writes this to reports/latest.json; numpy scalars would
    # break it at 06:00 UTC with nobody watching.
    result = detect(_recent_frame(storm=True), sigma=3.0)
    json.dumps(result.to_dict())


def test_web_status_is_json_serialisable_and_versioned():
    payload = web_status(detect(_recent_frame(storm=True), sigma=3.0))
    json.dumps(payload)
    assert payload["schema"] == WEB_STATUS_SCHEMA
    assert set(payload) == {"schema", *WEB_STATUS_FIELDS}


def test_web_status_withholds_diagnostic_detail():
    # peak_zscores and driving_features are report-only. Adding a field to
    # DailyResult must not publish it to the web by accident.
    payload = web_status(detect(_recent_frame(storm=True), sigma=3.0))
    assert "peak_zscores" not in payload
    assert "driving_features" not in payload


def test_web_status_carries_both_ages_needed_to_detect_a_dead_pipeline():
    # The tile needs the age of the DATA and the age of the RUN. With only the
    # first, a job that stopped publishing a fortnight ago still looks healthy.
    payload = web_status(detect(_recent_frame(), sigma=3.0))
    assert payload["generated_at"]
    assert payload["data_age_hours"] is not None


def test_web_status_propagates_unknown_rather_than_the_last_good_verdict():
    # The same critical contract as the markdown report, at the web boundary.
    payload = web_status(detect(_recent_frame(age_hours=30), sigma=3.0))
    assert payload["status"] == STATUS_NODATA
    # Every verdict field blanked. detect() populates these from the stale
    # window; publishing them would let a careless reader take active_now as
    # an all-clear from a pipeline that has not had fresh data in days.
    for field in VERDICT_FIELDS:
        assert payload[field] is None, field
    # What it legitimately knows about its own ignorance survives.
    assert payload["data_age_hours"] > 6
    assert "unknown" in payload["message"]


def test_web_status_keeps_the_verdict_when_the_data_is_fresh():
    payload = web_status(detect(_recent_frame(storm=True), sigma=3.0))
    assert payload["status"] == STATUS_OK
    assert payload["active_now"] is True
    assert payload["storm_class"] == "G3 strong"
