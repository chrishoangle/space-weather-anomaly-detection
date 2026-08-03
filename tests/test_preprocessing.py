"""Unit tests for :mod:`src.preprocessing`."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.preprocessing import (
    build_storm_feature_frame,
    dynamic_pressure,
    first_difference,
    interpolate_short_gaps,
    quiet_baseline_zscore,
    rate_of_change,
    rolling_statistics,
)


def _hourly_index(n: int, start: str = "2015-03-15") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="h", tz="UTC", name="time_tag")


def _sample_frame(n: int = 24) -> pd.DataFrame:
    index = _hourly_index(n)
    rng = np.random.default_rng(0)
    return pd.DataFrame(
        {
            "speed": 400 + rng.normal(0, 20, size=n),
            "density": 5 + rng.normal(0, 1, size=n),
            "temperature": 1.0e5 + rng.normal(0, 1000, size=n),
            "imf_magnitude": 5 + rng.normal(0, 1, size=n),
            "Kp": rng.uniform(0, 2, size=n),
        },
        index=index,
    )


class TestInterpolateShortGaps:
    def test_fills_short_gap(self) -> None:
        frame = pd.DataFrame(
            {"speed": [400.0, np.nan, np.nan, 460.0]},
            index=_hourly_index(4),
        )
        result = interpolate_short_gaps(frame, max_gap=3)
        assert result["speed"].isna().sum() == 0
        assert result["speed"].iloc[1] == pytest.approx(420.0)
        assert result["speed"].iloc[2] == pytest.approx(440.0)

    def test_preserves_long_gap(self) -> None:
        frame = pd.DataFrame(
            {"speed": [400.0, np.nan, np.nan, np.nan, np.nan, 500.0]},
            index=_hourly_index(6),
        )
        result = interpolate_short_gaps(frame, max_gap=3)
        assert result["speed"].iloc[1:5].isna().all()

    def test_empty_frame_returns_empty(self) -> None:
        frame = pd.DataFrame({"speed": []}, index=_hourly_index(0))
        result = interpolate_short_gaps(frame)
        assert result.empty
        assert list(result.columns) == ["speed"]

    def test_all_nan_column_stays_nan(self) -> None:
        frame = pd.DataFrame({"speed": [np.nan] * 5}, index=_hourly_index(5))
        result = interpolate_short_gaps(frame, max_gap=3)
        assert result["speed"].isna().all()

    def test_single_row_input(self) -> None:
        frame = pd.DataFrame({"speed": [400.0]}, index=_hourly_index(1))
        result = interpolate_short_gaps(frame)
        assert len(result) == 1
        assert result["speed"].iloc[0] == 400.0

    def test_non_numeric_columns_pass_through(self) -> None:
        frame = pd.DataFrame(
            {"speed": [400.0, np.nan, 420.0], "label": ["a", "b", "c"]},
            index=_hourly_index(3),
        )
        result = interpolate_short_gaps(frame, max_gap=3)
        assert list(result["label"]) == ["a", "b", "c"]
        assert result["speed"].iloc[1] == pytest.approx(410.0)

    def test_zero_max_gap_rejected(self) -> None:
        with pytest.raises(ValueError):
            interpolate_short_gaps(_sample_frame(), max_gap=0)


class TestRollingStatistics:
    def test_basic_shape_and_naming(self) -> None:
        frame = _sample_frame(24)
        result = rolling_statistics(frame, window=6, columns=["speed"])
        expected_columns = {
            "speed_rolling_mean_6",
            "speed_rolling_std_6",
            "speed_rolling_min_6",
            "speed_rolling_max_6",
        }
        assert set(result.columns) == expected_columns
        assert len(result) == len(frame)

    def test_first_five_are_nan_for_window_six(self) -> None:
        frame = _sample_frame(24)
        result = rolling_statistics(frame, window=6, columns=["speed"], statistics=("mean",))
        assert result["speed_rolling_mean_6"].iloc[:5].isna().all()
        assert not np.isnan(result["speed_rolling_mean_6"].iloc[5])

    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(columns=["speed"], index=_hourly_index(0))
        result = rolling_statistics(frame, window=3)
        assert result.empty

    def test_all_nan_column_returns_all_nan(self) -> None:
        frame = pd.DataFrame({"speed": [np.nan] * 10}, index=_hourly_index(10))
        result = rolling_statistics(frame, window=3, columns=["speed"], statistics=("mean",))
        assert result["speed_rolling_mean_3"].isna().all()

    def test_single_row_returns_nan_for_larger_window(self) -> None:
        frame = pd.DataFrame({"speed": [400.0]}, index=_hourly_index(1))
        result = rolling_statistics(frame, window=3, columns=["speed"], statistics=("mean",))
        assert result["speed_rolling_mean_3"].isna().all()

    def test_invalid_window_rejected(self) -> None:
        with pytest.raises(ValueError):
            rolling_statistics(_sample_frame(), window=0)

    def test_unknown_statistic_rejected(self) -> None:
        with pytest.raises(ValueError):
            rolling_statistics(_sample_frame(), window=3, statistics=("median",))


class TestFirstDifference:
    def test_basic_difference(self) -> None:
        frame = pd.DataFrame({"speed": [400.0, 410.0, 425.0]}, index=_hourly_index(3))
        result = first_difference(frame)
        assert np.isnan(result["speed_diff"].iloc[0])
        assert result["speed_diff"].iloc[1] == pytest.approx(10.0)
        assert result["speed_diff"].iloc[2] == pytest.approx(15.0)

    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(columns=["speed"], index=_hourly_index(0))
        result = first_difference(frame)
        assert result.empty

    def test_all_nan_column(self) -> None:
        frame = pd.DataFrame({"speed": [np.nan] * 4}, index=_hourly_index(4))
        result = first_difference(frame)
        assert result["speed_diff"].isna().all()

    def test_single_row(self) -> None:
        frame = pd.DataFrame({"speed": [400.0]}, index=_hourly_index(1))
        result = first_difference(frame)
        assert len(result) == 1
        assert result["speed_diff"].isna().all()


class TestRateOfChange:
    def test_default_periods_matches_first_difference(self) -> None:
        frame = pd.DataFrame({"speed": [400.0, 410.0, 425.0]}, index=_hourly_index(3))
        result = rate_of_change(frame)
        assert result["speed_roc"].iloc[1] == pytest.approx(10.0)
        assert result["speed_roc"].iloc[2] == pytest.approx(15.0)

    def test_multi_period(self) -> None:
        frame = pd.DataFrame({"speed": [400.0, 410.0, 430.0, 460.0]}, index=_hourly_index(4))
        result = rate_of_change(frame, periods=2)
        assert result["speed_roc"].iloc[2] == pytest.approx((430.0 - 400.0) / 2)

    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(columns=["speed"], index=_hourly_index(0))
        result = rate_of_change(frame)
        assert result.empty

    def test_zero_periods_rejected(self) -> None:
        with pytest.raises(ValueError):
            rate_of_change(_sample_frame(), periods=0)


class TestDynamicPressure:
    def test_matches_physics_formula(self) -> None:
        frame = pd.DataFrame(
            {"density": [10.0], "speed": [500.0]},
            index=_hourly_index(1),
        )
        result = dynamic_pressure(frame)
        assert result.iloc[0] == pytest.approx(1.6726e-6 * 10.0 * 500.0**2)

    def test_missing_columns_returns_nan_series(self) -> None:
        frame = pd.DataFrame({"other": [1.0, 2.0]}, index=_hourly_index(2))
        result = dynamic_pressure(frame)
        assert len(result) == 2
        assert result.isna().all()

    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(columns=["density", "speed"], index=_hourly_index(0))
        result = dynamic_pressure(frame)
        assert result.empty

    def test_nans_propagate(self) -> None:
        frame = pd.DataFrame(
            {"density": [np.nan, 5.0], "speed": [500.0, np.nan]},
            index=_hourly_index(2),
        )
        result = dynamic_pressure(frame)
        assert result.isna().all()


class TestQuietBaselineZscore:
    def test_uses_quiet_kp_rows(self) -> None:
        index = _hourly_index(6)
        frame = pd.DataFrame(
            {
                "speed": [400.0, 400.0, 400.0, 400.0, 800.0, 800.0],
                "Kp": [1.0, 1.0, 1.0, 1.0, 8.0, 8.0],
            },
            index=index,
        )
        result = quiet_baseline_zscore(frame, columns=["speed"])
        # Quiet mean is 400 with std 0 -> divide-by-zero must not produce inf.
        assert result["speed_zscore"].isna().all()

    def test_nonzero_std_produces_finite_zscore(self) -> None:
        index = _hourly_index(6)
        frame = pd.DataFrame(
            {
                "speed": [380.0, 400.0, 420.0, 400.0, 800.0, 800.0],
                "Kp": [1.0, 1.0, 1.0, 1.0, 8.0, 8.0],
            },
            index=index,
        )
        result = quiet_baseline_zscore(frame, columns=["speed"])
        assert np.isfinite(result["speed_zscore"].iloc[-1])
        assert result["speed_zscore"].iloc[-1] > 0

    def test_explicit_baseline_mapping(self) -> None:
        frame = pd.DataFrame({"speed": [420.0, 440.0]}, index=_hourly_index(2))
        result = quiet_baseline_zscore(
            frame,
            baseline={"speed": (400.0, 10.0)},
            columns=["speed"],
        )
        assert result["speed_zscore"].iloc[0] == pytest.approx(2.0)
        assert result["speed_zscore"].iloc[1] == pytest.approx(4.0)

    def test_explicit_baseline_dataframe(self) -> None:
        frame = pd.DataFrame({"speed": [420.0]}, index=_hourly_index(1))
        baseline = pd.DataFrame({"speed": [390.0, 400.0, 410.0]})
        result = quiet_baseline_zscore(frame, baseline=baseline, columns=["speed"])
        assert np.isfinite(result["speed_zscore"].iloc[0])

    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(columns=["speed", "Kp"], index=_hourly_index(0))
        result = quiet_baseline_zscore(frame)
        assert result.empty

    def test_all_nan_column(self) -> None:
        frame = pd.DataFrame(
            {"speed": [np.nan] * 5, "Kp": [1.0] * 5},
            index=_hourly_index(5),
        )
        result = quiet_baseline_zscore(frame, columns=["speed"])
        assert result["speed_zscore"].isna().all()

    def test_single_row(self) -> None:
        frame = pd.DataFrame({"speed": [400.0], "Kp": [1.0]}, index=_hourly_index(1))
        result = quiet_baseline_zscore(frame, columns=["speed"])
        # A single observation cannot yield a defined std.
        assert result["speed_zscore"].isna().all()


class TestBuildStormFeatureFrame:
    def test_empty_frame(self) -> None:
        frame = pd.DataFrame(
            columns=["speed", "density", "temperature", "imf_magnitude", "Kp"],
            index=_hourly_index(0),
        )
        result = build_storm_feature_frame(frame)
        assert result.empty

    def test_returns_expected_derived_columns(self) -> None:
        frame = _sample_frame(48)
        result = build_storm_feature_frame(frame, rolling_window=6)
        expected_present = {
            "speed_rolling_mean_6",
            "speed_diff",
            "speed_roc",
            "dynamic_pressure",
            "speed_zscore",
        }
        assert expected_present.issubset(result.columns)
        assert len(result) == len(frame)

    def test_single_row_input_does_not_raise(self) -> None:
        frame = _sample_frame(1)
        result = build_storm_feature_frame(frame, rolling_window=3)
        assert len(result) == 1
