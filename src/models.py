"""Anomaly-detection models for space-weather time series.

This module currently provides a single detector,
:class:`StatisticalProcessControlDetector`, which flags samples whose values
exceed a configurable sigma threshold relative to a fitted "quiet" baseline.
The class is deliberately small so it can serve both as a real baseline and
as a reference for the more expressive detectors added later.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Mapping, Sequence

import numpy as np
import pandas as pd


DEFAULT_FEATURES: tuple[str, ...] = (
    "speed",
    "density",
    "temperature",
    "imf_magnitude",
)
QUIET_KP_THRESHOLD: float = 3.0


@dataclass
class StatisticalProcessControlDetector:
    """Sigma-threshold detector fitted on a quiet reference period.

    The detector treats each configured feature independently: it stores the
    mean and standard deviation over a caller-supplied quiet window (or over
    the rows in the training frame with ``Kp < kp_threshold`` if no window is
    given).  During :meth:`predict`, a sample is flagged if any feature's
    absolute z-score exceeds ``sigma_threshold``.  The per-feature contribution
    scores make it obvious which variable drove a given detection.
    """

    sigma_threshold: float = 3.0
    kp_threshold: float = QUIET_KP_THRESHOLD
    features: Sequence[str] = DEFAULT_FEATURES
    kp_column: str = "Kp"
    baseline_: dict[str, tuple[float, float]] = field(default_factory=dict, init=False, repr=False)

    def fit(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
    ) -> "StatisticalProcessControlDetector":
        """Estimate per-feature means and stds from a quiet reference sample.

        ``quiet_mask`` is a boolean series aligned with ``frame`` that selects
        the rows considered quiet.  If omitted, quiet rows are inferred from
        ``Kp < kp_threshold``.  Features whose quiet sample has fewer than two
        finite observations are marked with ``std=nan`` so subsequent
        :meth:`predict` calls skip them rather than flagging every sample.
        """
        if not self.features:
            raise ValueError("features must be non-empty")

        available = [feature for feature in self.features if feature in frame.columns]
        if not available:
            raise ValueError(
                "None of the configured features are present in the training frame; "
                f"expected any of {list(self.features)}, got {list(frame.columns)}."
            )

        mask = self._resolve_quiet_mask(frame, quiet_mask)
        quiet = frame.loc[mask, available]
        if quiet.empty:
            raise ValueError(
                "No quiet-period samples were selected; "
                "adjust kp_threshold or supply an explicit quiet_mask."
            )

        stats: dict[str, tuple[float, float]] = {}
        for feature in available:
            values = pd.to_numeric(quiet[feature], errors="coerce").dropna()
            if len(values) < 2:
                stats[feature] = (float("nan"), float("nan"))
                continue
            stats[feature] = (float(values.mean()), float(values.std(ddof=1)))
        self.baseline_ = stats
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return per-timestamp anomaly flags and contribution scores.

        Output columns:
            - ``{feature}_zscore``: signed z-score against the quiet baseline.
            - ``{feature}_flag``: boolean flag for that feature exceeding the
              sigma threshold.
            - ``max_abs_zscore``: the largest absolute z-score across features
              at each timestamp (useful for ranking events).
            - ``anomaly``: ``True`` whenever any feature is flagged.

        A feature with an undefined baseline (missing or zero std) contributes
        NaN to its z-score column and ``False`` to its flag column.
        """
        if not self.baseline_:
            raise RuntimeError("Detector must be fit before calling predict().")

        result = pd.DataFrame(index=frame.index)
        flag_columns: list[str] = []
        zscore_columns: list[str] = []
        for feature, (mean, std) in self.baseline_.items():
            zscore_column = f"{feature}_zscore"
            flag_column = f"{feature}_flag"
            zscore_columns.append(zscore_column)
            flag_columns.append(flag_column)
            if feature not in frame.columns or not np.isfinite(std) or std == 0.0:
                result[zscore_column] = np.nan
                result[flag_column] = False
                continue
            series = pd.to_numeric(frame[feature], errors="coerce")
            zscores = (series - mean) / std
            result[zscore_column] = zscores
            result[flag_column] = zscores.abs() > self.sigma_threshold

        result["max_abs_zscore"] = result[zscore_columns].abs().max(axis=1)
        result["anomaly"] = result[flag_columns].any(axis=1)
        return result

    def fit_predict(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
    ) -> pd.DataFrame:
        """Convenience helper for callers that want fitted flags in one call."""
        return self.fit(frame, quiet_mask=quiet_mask).predict(frame)

    @property
    def baseline(self) -> Mapping[str, tuple[float, float]]:
        """Read-only view of the fitted (mean, std) per feature."""
        return dict(self.baseline_)

    def _resolve_quiet_mask(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None,
    ) -> pd.Series:
        if quiet_mask is not None:
            if isinstance(quiet_mask, pd.Series):
                return quiet_mask.reindex(frame.index).fillna(False).astype(bool)
            mask = pd.Series(np.asarray(quiet_mask), index=frame.index)
            return mask.fillna(False).astype(bool)
        if self.kp_column not in frame.columns:
            raise ValueError(
                "Training frame lacks a Kp column; pass quiet_mask explicitly or "
                "supply frame[self.kp_column]."
            )
        kp = pd.to_numeric(frame[self.kp_column], errors="coerce")
        return (kp < self.kp_threshold).fillna(False)


__all__: Iterable[str] = ["StatisticalProcessControlDetector"]
