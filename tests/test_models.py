"""Tests for the anomaly detectors in :mod:`src.models`.

Coverage priorities here are the things that would silently corrupt a results
table rather than raise: index alignment, NaN handling, reproducibility, and
the interface parity that lets one evaluation function consume both detectors.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.models import (
    IsolationForestDetector,
    StatisticalProcessControlDetector,
)


def _frame(n: int = 200, seed: int = 0) -> pd.DataFrame:
    """Synthetic quiet solar wind with a storm injected in the last 20 hours."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(pd.Timestamp("2015-03-01", tz="UTC"), periods=n, freq="h")
    frame = pd.DataFrame(
        {
            "speed": rng.normal(400, 20, n),
            "density": rng.normal(5, 1, n),
            "temperature": rng.normal(80_000, 8_000, n),
            "imf_magnitude": rng.normal(5, 1, n),
            "Kp": np.full(n, 2.0),
        },
        index=index,
    )
    storm = slice(n - 20, n)
    frame.iloc[storm, frame.columns.get_loc("speed")] = 750.0
    frame.iloc[storm, frame.columns.get_loc("imf_magnitude")] = 25.0
    frame.iloc[storm, frame.columns.get_loc("Kp")] = 8.0
    return frame


# ---------------------------------------------------------------------------
# Interface parity -- the property that makes the comparison meaningful
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "detector",
    [
        StatisticalProcessControlDetector(),
        IsolationForestDetector(n_estimators=50),
    ],
    ids=["spc", "iforest"],
)
def test_detectors_share_the_same_contract(detector):
    frame = _frame()
    result = detector.fit_predict(frame)
    assert "anomaly" in result.columns
    assert result["anomaly"].dtype == bool
    # Index alignment is the load-bearing property: evaluation joins detections
    # against the source frame, and a shifted index would silently misattribute
    # every detection to the wrong hour.
    assert result.index.equals(frame.index)


# ---------------------------------------------------------------------------
# IsolationForestDetector
# ---------------------------------------------------------------------------


def test_iforest_flags_the_injected_storm():
    frame = _frame()
    result = IsolationForestDetector(n_estimators=100).fit_predict(frame)
    storm_flags = result["anomaly"].iloc[-20:]
    assert storm_flags.sum() >= 10, "should flag at least half the injected storm hours"


def test_iforest_scores_are_higher_during_the_storm():
    frame = _frame()
    result = IsolationForestDetector(n_estimators=100).fit_predict(frame)
    quiet_score = result["anomaly_score"].iloc[:-20].mean()
    storm_score = result["anomaly_score"].iloc[-20:].mean()
    # Higher must mean more anomalous. score_samples is the other way round, so
    # a sign error here would invert every ranking downstream.
    assert storm_score > quiet_score


def test_iforest_is_reproducible_with_a_fixed_seed():
    frame = _frame()
    first = IsolationForestDetector(n_estimators=50, random_state=7).fit_predict(frame)
    second = IsolationForestDetector(n_estimators=50, random_state=7).fit_predict(frame)
    pd.testing.assert_frame_equal(first, second)


def test_iforest_keeps_nan_rows_in_the_index_as_false():
    frame = _frame()
    frame.iloc[5:9, frame.columns.get_loc("speed")] = np.nan
    result = IsolationForestDetector(n_estimators=50).fit_predict(frame)
    # Rows are retained so evaluation alignment holds, but flagged False with a
    # NaN score rather than imputed -- imputing a solar-wind dropout would
    # fabricate the signal we are trying to detect.
    assert result.index.equals(frame.index)
    assert not result["anomaly"].iloc[5:9].any()
    assert result["anomaly_score"].iloc[5:9].isna().all()


def test_iforest_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        IsolationForestDetector().predict(_frame())


def test_iforest_rejects_frame_with_no_known_features():
    frame = pd.DataFrame(
        {"unrelated": [1.0, 2.0, 3.0]},
        index=pd.date_range(pd.Timestamp("2015-03-01", tz="UTC"), periods=3, freq="h"),
    )
    with pytest.raises(ValueError, match="None of the configured features"):
        IsolationForestDetector().fit(frame)


def test_iforest_rejects_insufficient_complete_cases():
    frame = _frame(n=10)
    frame["speed"] = np.nan
    with pytest.raises(ValueError, match="at least two complete-case rows"):
        IsolationForestDetector().fit(frame)


def test_iforest_predict_rejects_missing_fitted_feature():
    frame = _frame()
    detector = IsolationForestDetector(n_estimators=50).fit(frame)
    with pytest.raises(ValueError, match="missing features seen during fit"):
        detector.predict(frame.drop(columns=["speed"]))


def test_iforest_fit_on_quiet_only_uses_the_kp_mask():
    frame = _frame()
    detector = IsolationForestDetector(n_estimators=50, fit_on_quiet_only=True).fit(frame)
    # Fitting only on Kp<3 rows excludes the injected storm, so the storm is
    # far outside the learned normal and must be flagged.
    result = detector.predict(frame)
    assert result["anomaly"].iloc[-20:].sum() >= 10


def test_iforest_fit_on_quiet_only_requires_kp_or_mask():
    frame = _frame().drop(columns=["Kp"])
    with pytest.raises(ValueError, match="requires either a quiet_mask"):
        IsolationForestDetector(fit_on_quiet_only=True).fit(frame)


# ---------------------------------------------------------------------------
# StatisticalProcessControlDetector -- previously untested
# ---------------------------------------------------------------------------


def test_spc_flags_the_injected_storm():
    frame = _frame()
    quiet = frame.index < frame.index[-20]
    result = StatisticalProcessControlDetector(sigma_threshold=3.0).fit_predict(
        frame, quiet_mask=quiet
    )
    assert result["anomaly"].iloc[-20:].all()


def test_spc_reports_which_feature_drove_the_detection():
    frame = _frame()
    quiet = frame.index < frame.index[-20]
    result = StatisticalProcessControlDetector().fit_predict(frame, quiet_mask=quiet)
    # Interpretability is the baseline's main advantage over the forest; the
    # per-feature flags are what deliver it.
    assert result["speed_flag"].iloc[-1]
    assert result["imf_magnitude_flag"].iloc[-1]
    assert not result["density_flag"].iloc[-1]


def test_spc_predict_before_fit_raises():
    with pytest.raises(RuntimeError):
        StatisticalProcessControlDetector().predict(_frame())


def test_spc_zero_variance_feature_is_skipped_not_flagged():
    frame = _frame()
    frame["density"] = 5.0  # constant -> std 0
    quiet = frame.index < frame.index[-20]
    result = StatisticalProcessControlDetector().fit_predict(frame, quiet_mask=quiet)
    # A zero-std baseline would divide by zero and flag every sample; it must
    # be skipped instead.
    assert not result["density_flag"].any()
    assert result["density_zscore"].isna().all()


def test_spc_empty_quiet_selection_raises():
    frame = _frame()
    with pytest.raises(ValueError, match="No quiet-period samples"):
        StatisticalProcessControlDetector().fit(
            frame, quiet_mask=pd.Series(False, index=frame.index)
        )
