"""Anomaly-detection models for space-weather time series.

Two detectors, deliberately sharing one interface
-------------------------------------------------
*   :class:`StatisticalProcessControlDetector` -- per-feature sigma threshold
    against a fitted "quiet" baseline. Interpretable, no training beyond two
    moments, and a genuinely hard baseline to beat on this data.
*   :class:`IsolationForestDetector` -- unsupervised ensemble that isolates
    points requiring few random splits. Sees feature *interactions* the
    per-feature z-score cannot.

Both expose ``fit`` / ``predict`` / ``fit_predict`` and return a frame with an
``anomaly`` boolean column, so :func:`src.evaluation.evaluate_detector`
consumes either with no special-casing. That symmetry is the point: it is what
makes a head-to-head comparison meaningful rather than two separate stories.

A note on which one "should" win: the SPC baseline is not a strawman. Storm
signatures in solar wind are largely marginal excursions -- speed and IMF
magnitude go far outside their quiet range -- which is exactly what a
per-feature sigma test is built to catch. See ``RESULTS.md`` for how the
comparison actually turned out.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

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
    ) -> StatisticalProcessControlDetector:
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


class AnomalyDetector(Protocol):
    """Structural interface both detectors satisfy.

    Declared as a :class:`typing.Protocol` rather than an inherited base class
    so the detectors stay independent of each other: neither needs to know the
    other exists, and a third-party estimator that happens to match the shape
    can be dropped into the evaluation pipeline without subclassing anything.
    """

    def fit(self, frame: pd.DataFrame, quiet_mask: object | None = ...) -> AnomalyDetector: ...

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame: ...


@dataclass
class IsolationForestDetector:
    """Isolation Forest detector over the standard storm features.

    How it differs from the SPC baseline, and why that might matter: the
    z-score test asks "is any single feature far from its quiet mean?" The
    forest asks "is this *combination* of values hard to explain?" A sample
    with unremarkable speed and unremarkable density but an unusual pairing of
    the two is invisible to the first and visible to the second. Whether that
    extra sensitivity buys anything on this data is an empirical question, and
    the answer is in ``RESULTS.md``.

    Three design decisions worth defending:

    **Contamination.** ``contamination`` is effectively "what fraction of the
    data is anomalous", and it alone sets the decision threshold. Tuning it to
    the storm rate measured from the catalog would leak label information into
    an unsupervised model and inflate every metric downstream. The default is
    therefore ``"auto"`` (scikit-learn's offset heuristic). If you override it,
    justify the number from something other than the test labels -- for
    instance a published storm-day climatology.

    **No feature scaling.** Isolation Forest splits one feature at a time at
    uniformly random thresholds within that feature's observed range, so
    monotone rescaling does not change the partitioning. Standardising first
    would add a fitted transform to maintain for no benefit. (This is *not*
    true of distance-based detectors -- do not carry the habit over.)

    **NaN rows are excluded, not imputed.** ``src.preprocessing`` deliberately
    refuses to bridge long data gaps, so gaps survive into the feature frame.
    scikit-learn will not accept NaN, and imputing a multi-hour solar-wind
    dropout would invent the very signal we are trying to detect. Rows with
    any missing feature are dropped for fitting, and at predict time they
    return ``anomaly=False`` with a NaN score -- present in the output index so
    evaluation alignment never silently shifts.

    Attributes:
        contamination: Expected anomaly fraction, or ``"auto"``.
        n_estimators: Number of trees.
        features: Feature columns to use.
        random_state: Seed. Fixed by default -- an unseeded forest gives
            different metrics on every run, which makes a results table
            impossible to reproduce.
        fit_on_quiet_only: When ``True``, restrict fitting to the quiet mask
            the way the SPC detector does. Defaults to ``False``, the
            conventional unsupervised setting: the forest learns "normal" from
            the whole record. Note that this makes the two detectors *not*
            strictly comparable in what they train on -- ``RESULTS.md`` reports
            both settings for that reason.
    """

    contamination: float | str = "auto"
    n_estimators: int = 200
    features: Sequence[str] = DEFAULT_FEATURES
    random_state: int | None = 42
    kp_threshold: float = QUIET_KP_THRESHOLD
    kp_column: str = "Kp"
    fit_on_quiet_only: bool = False
    forest_: IsolationForest | None = field(default=None, init=False, repr=False)
    fitted_features_: list[str] = field(default_factory=list, init=False, repr=False)

    def fit(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
    ) -> IsolationForestDetector:
        """Fit the forest on complete-case rows of the configured features.

        ``quiet_mask`` is accepted for interface parity with
        :class:`StatisticalProcessControlDetector` and is honoured only when
        :attr:`fit_on_quiet_only` is ``True``; otherwise it is ignored and the
        whole frame is used.

        Raises:
            ValueError: If no configured feature is present, or if fewer than
                two complete-case rows survive.
        """
        if not self.features:
            raise ValueError("features must be non-empty")

        available = [feature for feature in self.features if feature in frame.columns]
        if not available:
            raise ValueError(
                "None of the configured features are present in the training frame; "
                f"expected any of {list(self.features)}, got {list(frame.columns)}."
            )

        training = frame
        if self.fit_on_quiet_only:
            training = frame.loc[self._resolve_quiet_mask(frame, quiet_mask)]

        matrix = training[available].apply(pd.to_numeric, errors="coerce").dropna()
        if len(matrix) < 2:
            raise ValueError(
                f"Isolation Forest needs at least two complete-case rows; got {len(matrix)}. "
                "Check for all-NaN feature columns or an over-restrictive quiet mask."
            )

        self.forest_ = IsolationForest(
            n_estimators=self.n_estimators,
            contamination=self.contamination,
            random_state=self.random_state,
        ).fit(matrix.to_numpy())
        self.fitted_features_ = available
        return self

    def predict(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Return anomaly flags and scores aligned to ``frame.index``.

        Output columns:
            - ``anomaly_score``: higher means more anomalous. This is the
              negated scikit-learn ``score_samples`` output, flipped so the
              direction matches intuition and the SPC detector's
              ``max_abs_zscore``.
            - ``anomaly``: ``True`` where the forest predicts an outlier.

        Rows with any missing feature yield ``NaN`` score and ``False`` flag.

        Raises:
            RuntimeError: If called before :meth:`fit`.
        """
        if self.forest_ is None:
            raise RuntimeError("Detector must be fit before calling predict().")

        missing = [f for f in self.fitted_features_ if f not in frame.columns]
        if missing:
            raise ValueError(f"Frame is missing features seen during fit: {missing}")

        matrix = frame[self.fitted_features_].apply(pd.to_numeric, errors="coerce")
        complete = matrix.dropna()

        result = pd.DataFrame(
            {
                "anomaly_score": pd.Series(np.nan, index=frame.index, dtype=float),
                "anomaly": pd.Series(False, index=frame.index, dtype=bool),
            }
        )
        if complete.empty:
            return result

        values = complete.to_numpy()
        # score_samples: lower = more anomalous. Negate so higher = more
        # anomalous, matching every other score in this project.
        result.loc[complete.index, "anomaly_score"] = -self.forest_.score_samples(values)
        result.loc[complete.index, "anomaly"] = self.forest_.predict(values) == -1
        return result

    def fit_predict(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None = None,
    ) -> pd.DataFrame:
        """Convenience helper for callers that want fitted flags in one call."""
        return self.fit(frame, quiet_mask=quiet_mask).predict(frame)

    def _resolve_quiet_mask(
        self,
        frame: pd.DataFrame,
        quiet_mask: pd.Series | np.ndarray | Sequence[bool] | None,
    ) -> pd.Series:
        if quiet_mask is not None:
            if isinstance(quiet_mask, pd.Series):
                return quiet_mask.reindex(frame.index).fillna(False).astype(bool)
            return pd.Series(np.asarray(quiet_mask), index=frame.index).fillna(False).astype(bool)
        if self.kp_column not in frame.columns:
            raise ValueError(
                "fit_on_quiet_only=True requires either a quiet_mask or a "
                f"{self.kp_column!r} column in the training frame."
            )
        kp = pd.to_numeric(frame[self.kp_column], errors="coerce")
        return (kp < self.kp_threshold).fillna(False)


__all__: Iterable[str] = [
    "AnomalyDetector",
    "StatisticalProcessControlDetector",
    "IsolationForestDetector",
]
