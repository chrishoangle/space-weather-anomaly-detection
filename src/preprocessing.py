"""Feature engineering and cleaning for space-weather time series.

All functions here are pure: they accept :class:`pandas.DataFrame` inputs and
return new DataFrames without touching the filesystem, network, or global
state.  They are designed to compose on the UTC-indexed frames returned by
:mod:`src.data_loader`, whose canonical columns are ``speed``, ``density``,
``temperature``, ``imf_magnitude``, and ``Kp``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

DEFAULT_STORM_COLUMNS: tuple[str, ...] = (
    "speed",
    "density",
    "temperature",
    "imf_magnitude",
)
QUIET_KP_THRESHOLD: float = 3.0


def interpolate_short_gaps(
    frame: pd.DataFrame,
    max_gap: int = 3,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Linearly interpolate runs of NaNs no longer than ``max_gap``.

    Longer gaps are preserved as NaN because linearly bridging a multi-hour
    dropout in solar-wind data would silently invent physics we cannot
    justify.  ``max_gap`` counts consecutive missing samples; the default of
    three matches the informal rule-of-thumb for OMNI2 hourly data.

    Args:
        frame: Time-indexed DataFrame to fill.
        max_gap: Maximum consecutive NaNs eligible for interpolation.
        columns: Optional subset of columns; other columns pass through.

    Returns:
        A new DataFrame with the same index and columns.
    """
    if max_gap < 1:
        raise ValueError("max_gap must be at least 1")
    if frame.empty:
        return frame.copy()

    target_columns = list(columns) if columns is not None else list(frame.columns)
    result = frame.copy()
    for column in target_columns:
        if column not in result.columns:
            continue
        series = result[column]
        if not pd.api.types.is_numeric_dtype(series):
            continue
        interpolated = series.interpolate(method="linear", limit=max_gap, limit_area="inside")
        # ``interpolate`` fills every gap up to ``max_gap`` samples but does not
        # know whether a gap is longer than the limit; restore NaNs for runs
        # that exceed the allowed length so we never partially bridge them.
        gap_lengths = _consecutive_nan_lengths(series)
        interpolated = interpolated.where(gap_lengths <= max_gap, other=np.nan)
        result[column] = interpolated
    return result


def rolling_statistics(
    frame: pd.DataFrame,
    window: int,
    columns: Sequence[str] | None = None,
    statistics: Sequence[str] = ("mean", "std", "min", "max"),
    min_periods: int | None = None,
) -> pd.DataFrame:
    """Return rolling ``mean``, ``std``, ``min``, and ``max`` per column.

    Output column names follow ``{column}_rolling_{stat}_{window}``.  A
    non-positive ``window`` is rejected; requesting an unknown statistic is a
    ``ValueError`` rather than a silent no-op.

    Args:
        frame: Time-indexed DataFrame with numeric columns.
        window: Rolling window size in samples.
        columns: Optional subset of columns; defaults to all numeric columns.
        statistics: Which statistics to compute.
        min_periods: Minimum observations in the window; defaults to ``window``.
    """
    if window < 1:
        raise ValueError("window must be at least 1")
    if not statistics:
        raise ValueError("statistics must contain at least one entry")
    allowed = {"mean", "std", "min", "max"}
    unknown = [name for name in statistics if name not in allowed]
    if unknown:
        raise ValueError(f"Unknown rolling statistics: {unknown}")

    if frame.empty:
        return pd.DataFrame(index=frame.index)

    target_columns = _numeric_columns(frame, columns)
    if not target_columns:
        return pd.DataFrame(index=frame.index)

    effective_min = min_periods if min_periods is not None else window
    rolling = frame[target_columns].rolling(window=window, min_periods=effective_min)
    computed: dict[str, pd.Series] = {}
    for stat in statistics:
        stat_frame = getattr(rolling, stat)()
        for column in target_columns:
            computed[f"{column}_rolling_{stat}_{window}"] = stat_frame[column]
    return pd.DataFrame(computed, index=frame.index)


def first_difference(
    frame: pd.DataFrame,
    columns: Sequence[str] | None = None,
) -> pd.DataFrame:
    """Return the first difference of each column as ``{column}_diff``.

    The first sample is always NaN because there is no prior observation. The
    difference respects the natural row order, not the timestamp spacing;
    callers should resample to a uniform cadence first if that matters.
    """
    if frame.empty:
        return pd.DataFrame(index=frame.index)

    target_columns = _numeric_columns(frame, columns)
    if not target_columns:
        return pd.DataFrame(index=frame.index)

    diff = frame[target_columns].diff()
    diff.columns = [f"{column}_diff" for column in target_columns]
    return diff


def rate_of_change(
    frame: pd.DataFrame,
    columns: Sequence[str] | None = None,
    periods: int = 1,
) -> pd.DataFrame:
    """Return the per-sample rate of change as ``{column}_roc``.

    Rate of change is computed as ``(x_t - x_{t-periods}) / periods``. The
    caller controls whether that "per unit" is per-hour or per-minute via the
    cadence of the input frame.  Using a plain difference (rather than a
    percentage change) keeps units interpretable for physical variables like
    velocity where a zero baseline is meaningful.
    """
    if periods < 1:
        raise ValueError("periods must be at least 1")
    if frame.empty:
        return pd.DataFrame(index=frame.index)

    target_columns = _numeric_columns(frame, columns)
    if not target_columns:
        return pd.DataFrame(index=frame.index)

    diff = frame[target_columns].diff(periods=periods) / periods
    diff.columns = [f"{column}_roc" for column in target_columns]
    return diff


def dynamic_pressure(
    frame: pd.DataFrame,
    density_column: str = "density",
    speed_column: str = "speed",
) -> pd.Series:
    """Return a dynamic-pressure proxy proportional to n * v**2.

    The true solar-wind dynamic pressure is ``P_dyn = m_p * n * v**2`` in SI
    units, which reduces to ``1.6726e-6 * n * v**2`` nPa when ``n`` is in
    cm^-3 and ``v`` is in km/s.  We apply that conversion so the returned
    series carries physically meaningful nPa values, useful for direct
    comparison with common magnetopause standoff estimates.
    """
    if frame.empty:
        return pd.Series(dtype=float, index=frame.index, name="dynamic_pressure")
    if density_column not in frame.columns or speed_column not in frame.columns:
        return pd.Series(np.nan, index=frame.index, name="dynamic_pressure")

    density = pd.to_numeric(frame[density_column], errors="coerce")
    speed = pd.to_numeric(frame[speed_column], errors="coerce")
    pressure = 1.6726e-6 * density * speed**2
    pressure.name = "dynamic_pressure"
    return pressure


def quiet_baseline_zscore(
    frame: pd.DataFrame,
    baseline: pd.DataFrame | Mapping[str, tuple[float, float]] | None = None,
    columns: Sequence[str] | None = None,
    kp_threshold: float = QUIET_KP_THRESHOLD,
    kp_column: str = "Kp",
) -> pd.DataFrame:
    """Z-score each column against a "quiet" reference mean and std.

    If ``baseline`` is ``None``, the reference is derived from rows where
    ``kp_column`` is below ``kp_threshold`` (the geomagnetic "quiet" regime).
    A mapping ``{column: (mean, std)}`` or a DataFrame subset can also be
    supplied when the caller already knows a quiet period.

    Columns whose baseline standard deviation is zero, missing, or NaN yield
    all-NaN z-scores rather than divide-by-zero infinities, so downstream
    detectors do not flag artefacts.
    """
    if frame.empty:
        return pd.DataFrame(index=frame.index)

    target_columns = _numeric_columns(frame, columns, exclude={kp_column})
    if not target_columns:
        return pd.DataFrame(index=frame.index)

    baseline_stats = _resolve_baseline(
        frame,
        baseline,
        target_columns=target_columns,
        kp_threshold=kp_threshold,
        kp_column=kp_column,
    )

    zscores: dict[str, pd.Series] = {}
    for column in target_columns:
        mean, std = baseline_stats.get(column, (np.nan, np.nan))
        if not np.isfinite(std) or std == 0.0:
            zscores[f"{column}_zscore"] = pd.Series(np.nan, index=frame.index)
            continue
        series = pd.to_numeric(frame[column], errors="coerce")
        zscores[f"{column}_zscore"] = (series - mean) / std
    return pd.DataFrame(zscores, index=frame.index)


def build_storm_feature_frame(
    frame: pd.DataFrame,
    rolling_window: int = 6,
    max_gap: int = 3,
    baseline: pd.DataFrame | Mapping[str, tuple[float, float]] | None = None,
    kp_threshold: float = QUIET_KP_THRESHOLD,
) -> pd.DataFrame:
    """Assemble the standard storm-detection features in a single call.

    Applies short-gap interpolation, rolling statistics, first differences,
    rates of change, dynamic pressure, and quiet-baseline z-scores and returns
    the merged feature DataFrame alongside the interpolated raw columns.
    """
    if frame.empty:
        return frame.copy()

    interpolated = interpolate_short_gaps(frame, max_gap=max_gap)
    storm_columns = [column for column in DEFAULT_STORM_COLUMNS if column in interpolated.columns]
    parts: list[pd.DataFrame] = [interpolated]
    if storm_columns:
        parts.extend(
            [
                rolling_statistics(interpolated, window=rolling_window, columns=storm_columns),
                first_difference(interpolated, columns=storm_columns),
                rate_of_change(interpolated, columns=storm_columns),
            ]
        )
    if {"density", "speed"}.issubset(interpolated.columns):
        parts.append(dynamic_pressure(interpolated).to_frame())
    if storm_columns:
        parts.append(
            quiet_baseline_zscore(
                interpolated,
                baseline=baseline,
                columns=storm_columns,
                kp_threshold=kp_threshold,
            )
        )
    return pd.concat(parts, axis=1)


def _numeric_columns(
    frame: pd.DataFrame,
    columns: Sequence[str] | None,
    exclude: Iterable[str] = (),
) -> list[str]:
    """Return the numeric subset of ``columns`` (defaulting to all numeric)."""
    excluded = set(exclude)
    if columns is None:
        candidates = list(frame.columns)
    else:
        candidates = [column for column in columns if column in frame.columns]
    return [
        column
        for column in candidates
        if column not in excluded and pd.api.types.is_numeric_dtype(frame[column])
    ]


def _resolve_baseline(
    frame: pd.DataFrame,
    baseline: pd.DataFrame | Mapping[str, tuple[float, float]] | None,
    target_columns: Sequence[str],
    kp_threshold: float,
    kp_column: str,
) -> dict[str, tuple[float, float]]:
    """Normalise the caller's baseline argument into a column->(mean, std) map."""
    if isinstance(baseline, pd.DataFrame):
        return {
            column: (float(baseline[column].mean()), float(baseline[column].std()))
            for column in target_columns
            if column in baseline.columns
        }
    if isinstance(baseline, Mapping):
        resolved: dict[str, tuple[float, float]] = {}
        for column in target_columns:
            if column not in baseline:
                continue
            mean, std = baseline[column]
            resolved[column] = (float(mean), float(std))
        return resolved

    if kp_column in frame.columns:
        quiet_mask = pd.to_numeric(frame[kp_column], errors="coerce") < kp_threshold
        quiet = frame.loc[quiet_mask.fillna(False), list(target_columns)]
        if not quiet.empty:
            return {
                column: (float(quiet[column].mean()), float(quiet[column].std()))
                for column in target_columns
            }
    return {
        column: (float(frame[column].mean()), float(frame[column].std()))
        for column in target_columns
    }


def _consecutive_nan_lengths(series: pd.Series) -> pd.Series:
    """Length of the NaN run containing each element (0 for non-NaN samples)."""
    is_nan = series.isna().to_numpy()
    lengths = np.zeros(len(is_nan), dtype=int)
    run_length = 0
    for i, missing in enumerate(is_nan):
        if missing:
            run_length += 1
        else:
            run_length = 0
        lengths[i] = run_length
    max_so_far = 0
    for i in range(len(lengths) - 1, -1, -1):
        if lengths[i] > 0:
            max_so_far = max(max_so_far, lengths[i])
            lengths[i] = max_so_far
        else:
            max_so_far = 0
    return pd.Series(lengths, index=series.index)
