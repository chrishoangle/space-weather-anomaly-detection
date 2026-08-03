"""Streamlit dashboard for space-weather anomaly detection.

Run locally with::

    streamlit run app.py

Two modes:

*   **Live** — pulls current NOAA SWPC data and scores it. Requires network.
*   **Historical** — scores a catalogued storm window from OMNI2, with the
    ground-truth window shaded so detections can be judged by eye against the
    metrics in ``RESULTS.md``.

Design note: the dashboard is a *view* over ``src.models`` and
``src.evaluation`` and computes no metrics of its own. If the dashboard and
``RESULTS.md`` ever disagreed, one of them would be lying, and there would be
no way to tell which.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.data_loader import (  # noqa: E402
    fetch_omniweb_historical,
    load_kp_index,
    load_solar_wind_plasma,
)
from src.evaluation import evaluate_detector, format_report, load_storm_catalog  # noqa: E402
from src.models import IsolationForestDetector, StatisticalProcessControlDetector  # noqa: E402

FEATURES = ["speed", "density", "temperature", "imf_magnitude"]
CACHE_DIR = Path(__file__).resolve().parent / "data" / "raw" / "omniweb"


def window_bounds(peak: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """Calendar month containing a storm peak -- matches the cache key used by
    ``scripts/compare_detectors.py`` so both reuse the same cached files."""
    start = peak.normalize().replace(day=1)
    return start, start + pd.offsets.MonthEnd(1)


def is_cached(peak: pd.Timestamp) -> bool:
    """Whether this storm's window is already on disk.

    Used to preselect a storm that will actually load. Defaulting to an
    uncached window means every first-time visitor without network access sees
    an error instead of the dashboard.
    """
    start, end = window_bounds(peak)
    return (CACHE_DIR / f"omni2_hourly_{start:%Y%m%d}_{end:%Y%m%d}.txt").exists()

st.set_page_config(page_title="Space Weather Anomaly Detection", layout="wide")


@st.cache_data(ttl=900, show_spinner=False)
def load_historical(peak_iso: str) -> pd.DataFrame:
    """Load the calendar-month OMNI2 window containing a storm peak."""
    start, end = window_bounds(pd.Timestamp(peak_iso))
    return fetch_omniweb_historical(start.to_pydatetime(), end.to_pydatetime())


@st.cache_data(ttl=900, show_spinner=False)
def load_live(hours: int) -> pd.DataFrame:
    """Load and merge recent NOAA plasma and Kp data."""
    plasma = load_solar_wind_plasma()
    recent = plasma.loc[plasma.index >= datetime.now(UTC) - timedelta(hours=hours)]
    try:
        kp = load_kp_index()
        if not kp.empty:
            column = "Kp" if "Kp" in kp.columns else kp.columns[0]
            recent = recent.join(
                kp[[column]].rename(columns={column: "Kp"}).reindex(recent.index, method="ffill")
            )
    except Exception as error:  # noqa: BLE001
        st.warning(f"Kp feed unavailable ({type(error).__name__}); continuing without it.")
    return recent


def build_detector(name: str, sigma: float, frame: pd.DataFrame):
    """Instantiate the selected detector plus its quiet mask."""
    features = [feature for feature in FEATURES if feature in frame.columns]
    kp_quiet = (
        pd.to_numeric(frame["Kp"], errors="coerce") < 3.0
        if "Kp" in frame.columns
        else pd.Series(frame.index < frame.index[len(frame) // 2], index=frame.index)
    )
    if name.startswith("Statistical"):
        return StatisticalProcessControlDetector(sigma_threshold=sigma, features=features), kp_quiet
    return IsolationForestDetector(n_estimators=300, features=features), None


def plot(frame: pd.DataFrame, flags: pd.Series, shade: tuple | None) -> go.Figure:
    """Series with detections overlaid, plus Kp."""
    panels = [feature for feature in FEATURES if feature in frame.columns]
    has_kp = "Kp" in frame.columns
    rows = len(panels) + (1 if has_kp else 0)
    titles = [*panels, *(["Kp"] if has_kp else [])]

    figure = make_subplots(rows=rows, cols=1, shared_xaxes=True, subplot_titles=titles,
                           vertical_spacing=0.045)

    for position, feature in enumerate(panels, start=1):
        figure.add_trace(
            go.Scatter(
                x=frame.index, y=frame[feature], name=feature, mode="lines",
                line={"color": "#4a4a4a", "width": 1.1}, showlegend=False,
            ),
            row=position, col=1,
        )
        hits = flags[flags].index
        if len(hits):
            figure.add_trace(
                go.Scatter(
                    x=hits, y=frame.loc[hits, feature], mode="markers", name="anomaly",
                    marker={"color": "#d62728", "size": 5},
                    showlegend=position == 1,
                ),
                row=position, col=1,
            )

    if has_kp:
        figure.add_trace(
            go.Scatter(x=frame.index, y=frame["Kp"], name="Kp", mode="lines",
                       line={"color": "#4a4a4a", "width": 1.1}, showlegend=False),
            row=rows, col=1,
        )
        figure.add_hline(
            y=3.0,
            line={"color": "#2ca02c", "dash": "dot", "width": 1},
            row=rows,
            col=1,
        )

    if shade is not None:
        start, end = shade
        for row in range(1, rows + 1):
            figure.add_vrect(
                x0=start,
                x1=end,
                fillcolor="#1f77b4",
                opacity=0.13,
                line_width=0,
                row=row,
                col=1,
                # Label once, on the top panel only: repeating it on every
                # subplot is noise.
                annotation_text="ground-truth window" if row == 1 else None,
                annotation_position="top left",
            )

    figure.update_layout(height=190 * rows, margin={"l": 60, "r": 20, "t": 50, "b": 40},
                         hovermode="x unified")
    return figure


st.title("Space Weather Anomaly Detection")
st.caption(
    "Unsupervised anomaly detection on NOAA SWPC and NASA OMNI2 solar-wind data. "
    "Measured precision is 0.17–0.39 depending on configuration — see RESULTS.md. "
    "Not an operational forecast; for real alerts use NOAA SWPC."
)

with st.sidebar:
    st.header("Configuration")
    mode = st.radio("Data source", ["Historical storm", "Live (NOAA)"])
    detector_name = st.selectbox(
        "Detector",
        ["Statistical process control (3σ baseline)", "Isolation Forest"],
    )
    sigma = st.slider("SPC sigma threshold", 1.5, 6.0, 3.0, 0.1,
                      disabled=not detector_name.startswith("Statistical"))
    tolerance_hours = st.slider("Hit tolerance (± hours)", 6, 48, 24, 6)
    st.divider()
    st.caption(
        "Widening the tolerance raises recall for free. That is why every metric "
        "below is reported with the tolerance that produced it."
    )

events = load_storm_catalog()
shade = None
tolerance = pd.Timedelta(hours=tolerance_hours)

try:
    if mode == "Historical storm":
        labels = {
            f"{event.name} — {event.peak:%Y-%m-%d} (Kp {event.max_kp:.0f})"
            + ("  ·  cached" if is_cached(event.peak) else ""): event
            for event in events
        }
        keys = list(labels)
        # Preselect a cached window so the dashboard loads offline.
        default = next((i for i, key in enumerate(keys) if "cached" in key), 0)
        choice = st.sidebar.selectbox("Storm", keys, index=default)
        event = labels[choice]
        frame = load_historical(event.peak.isoformat())
        scored_events = [event]
        shade = event.window(tolerance)
    else:
        hours = st.sidebar.slider("Hours of live data", 12, 168, 72, 12)
        frame = load_live(hours)
        scored_events = events
except (RuntimeError, OSError) as error:
    st.error(f"Could not load data: {error}")
    st.info(
        "The historical loader caches responses under `data/raw/omniweb/`, so a "
        "previously fetched window works offline. Live mode needs network access "
        "to services.swpc.noaa.gov."
    )
    st.stop()

if frame.empty:
    st.warning("No samples in the selected range.")
    st.stop()

detector, quiet_mask = build_detector(detector_name, sigma, frame)
flags = detector.fit_predict(frame, quiet_mask=quiet_mask)["anomaly"]

columns = st.columns(4)
columns[0].metric("Samples", f"{len(frame):,}")
columns[1].metric("Flagged", f"{int(flags.sum()):,}", f"{flags.mean():.1%} of window")
columns[2].metric(
    "Latest Kp",
    f"{pd.to_numeric(frame['Kp'], errors='coerce').dropna().iloc[-1]:.1f}"
    if "Kp" in frame.columns and pd.to_numeric(frame["Kp"], errors="coerce").notna().any()
    else "n/a",
)
last_label = "Anomaly now" if mode == "Live (NOAA)" else "Flagged at window end"
columns[3].metric(last_label, "Yes" if bool(flags.iloc[-1]) else "No")

st.plotly_chart(plot(frame, flags, shade), use_container_width=True)

if mode == "Historical storm":
    st.subheader("Evaluation against the storm catalog")
    report = evaluate_detector(flags, frame, events=scored_events, tolerance=tolerance)
    st.markdown(format_report(report))
    st.caption(
        "Event recall over a single storm window is uninformative (n=1). "
        "Judge configurations on precision and the quiet-time false-alarm rate."
    )
else:
    st.subheader("Live monitoring")
    st.info(
        "Ground-truth evaluation is unavailable in live mode: no catalog labels "
        "exist for right now. Switch to a historical storm to see measured metrics."
    )
