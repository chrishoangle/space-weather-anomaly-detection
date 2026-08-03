"""Load and cache space-weather products published by NOAA SWPC.

The functions in this module return time-indexed :class:`pandas.DataFrame`
objects.  They deliberately cache the original JSON response, so a cached
response can be inspected or re-parsed if NOAA changes a product slightly.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Final, Mapping, Sequence

import pandas as pd
import requests


LOGGER = logging.getLogger(__name__)

PLASMA_URL: Final = "https://services.swpc.noaa.gov/products/solar-wind/plasma-7-day.json"
# NOAA occasionally retires product paths.  This real-time SWPC feed is kept
# as a fallback so the loader remains useful if the seven-day product moves.
PLASMA_FALLBACK_URL: Final = "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json"
KP_URL: Final = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
DEFAULT_CACHE_TTL: Final = timedelta(hours=1)
DEFAULT_TIMEOUT_SECONDS: Final = 20
DEFAULT_CACHE_DIR: Final = Path(__file__).resolve().parents[1] / "data" / "raw"


def load_solar_wind_plasma(
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
    cache_ttl: timedelta = DEFAULT_CACHE_TTL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Return NOAA's seven-day solar-wind plasma observations.

    The returned frame is indexed by UTC ``DatetimeIndex`` and normally
    contains ``density``, ``speed``, and ``temperature`` columns.  A stale
    cache is used if the NOAA request fails; if no data can be obtained, an
    empty, correctly indexed DataFrame is returned.
    """
    payload = _get_payload(
        PLASMA_URL,
        Path(cache_dir) / "solar_wind_plasma_7_day.json",
        force_refresh=force_refresh,
        cache_ttl=cache_ttl,
        timeout=timeout,
        session=session,
        fallback_url=PLASMA_FALLBACK_URL,
    )
    return _to_time_frame(payload)


def load_kp_index(
    *,
    cache_dir: Path | str = DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
    cache_ttl: timedelta = DEFAULT_CACHE_TTL,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    """Return NOAA's planetary Kp-index product as a UTC-indexed DataFrame.

    NOAA labels the main value ``Kp``.  Invalid or absent values are converted
    to ``NaN`` rather than causing an entire download to fail.  See
    :func:`load_solar_wind_plasma` for cache and failure behaviour.
    """
    payload = _get_payload(
        KP_URL,
        Path(cache_dir) / "planetary_k_index.json",
        force_refresh=force_refresh,
        cache_ttl=cache_ttl,
        timeout=timeout,
        session=session,
    )
    return _to_time_frame(payload)


def _get_payload(
    url: str,
    cache_path: Path,
    *,
    force_refresh: bool,
    cache_ttl: timedelta,
    timeout: int,
    session: requests.Session | None,
    fallback_url: str | None = None,
) -> Any:
    """Read a fresh cache or download JSON, falling back to any cache."""
    cached = _read_cache(cache_path)
    if cached is not None and not force_refresh and _cache_is_fresh(cached, cache_ttl):
        return cached["payload"]

    client = session or requests
    error: Exception | None = None
    for candidate_url in (url, fallback_url):
        if candidate_url is None:
            continue
        try:
            response = client.get(candidate_url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            _write_cache(cache_path, payload)
            if candidate_url != url:
                LOGGER.info("Primary NOAA product unavailable; used fallback %s", candidate_url)
            return payload
        except (requests.RequestException, ValueError) as request_error:
            error = request_error

    if cached is not None:
        LOGGER.warning("NOAA request failed; using cached data at %s: %s", cache_path, error)
        return cached["payload"]
    LOGGER.warning("NOAA request failed and no cache is available for %s: %s", url, error)
    return []


def _read_cache(cache_path: Path) -> dict[str, Any] | None:
    """Return a cache envelope, ignoring corrupt cache files safely."""
    try:
        with cache_path.open(encoding="utf-8") as cache_file:
            contents = json.load(cache_file)
        if isinstance(contents, dict) and "payload" in contents and "fetched_at" in contents:
            return contents
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.warning("Could not read cache %s: %s", cache_path, error)
    return None


def _cache_is_fresh(cache: Mapping[str, Any], cache_ttl: timedelta) -> bool:
    """Check freshness from the recorded UTC download time."""
    try:
        fetched_at = datetime.fromisoformat(str(cache["fetched_at"]))
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) - fetched_at <= cache_ttl
    except (TypeError, ValueError):
        return False


def _write_cache(cache_path: Path, payload: Any) -> None:
    """Atomically persist a successful raw NOAA response."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        envelope = {"fetched_at": datetime.now(timezone.utc).isoformat(), "payload": payload}
        with temporary_path.open("w", encoding="utf-8") as cache_file:
            json.dump(envelope, cache_file)
        temporary_path.replace(cache_path)
    except OSError as error:
        # A non-writable cache should not stop a successful data load.
        LOGGER.warning("Could not write NOAA cache %s: %s", cache_path, error)


def _to_time_frame(payload: Any) -> pd.DataFrame:
    """Convert NOAA's header-row JSON format into a clean time-indexed frame."""
    records = _normalise_records(payload)
    if not records:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="time_tag", tz="UTC"))

    frame = pd.DataFrame(records)
    time_column = next((name for name in frame.columns if "time" in str(name).lower()), None)
    if time_column is None:
        LOGGER.warning("NOAA payload has no timestamp column: %s", list(frame.columns))
        return pd.DataFrame(index=pd.DatetimeIndex([], name="time_tag", tz="UTC"))

    timestamps = pd.to_datetime(frame.pop(time_column), errors="coerce", utc=True)
    frame = frame.loc[timestamps.notna()].copy()
    frame.index = pd.DatetimeIndex(timestamps[timestamps.notna()], name="time_tag")
    # Data products are numeric apart from their timestamp; coercion makes
    # NOAA's null/sentinel-like text values consistently usable as NaN.
    for column in frame.columns:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def _normalise_records(payload: Any) -> list[dict[str, Any]]:
    """Support NOAA header-row arrays as well as object-style JSON responses."""
    if isinstance(payload, Mapping):
        # Some NOAA products wrap their rows in a named collection.
        for value in payload.values():
            if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                return _normalise_records(value)
        return [dict(payload)]
    if not isinstance(payload, Sequence) or isinstance(payload, (str, bytes)) or not payload:
        return []
    if all(isinstance(row, Mapping) for row in payload):
        return [dict(row) for row in payload]

    header, *rows = payload
    if not isinstance(header, Sequence) or isinstance(header, (str, bytes)):
        return []
    columns = [str(column) for column in header]
    return [dict(zip(columns, row)) for row in rows if isinstance(row, Sequence) and not isinstance(row, (str, bytes))]
