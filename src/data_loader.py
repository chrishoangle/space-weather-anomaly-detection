"""Load and cache space-weather products published by NOAA SWPC.

The functions in this module return time-indexed :class:`pandas.DataFrame`
objects.  They deliberately cache the original JSON response, so a cached
response can be inspected or re-parsed if NOAA changes a product slightly.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timedelta, timezone
from html import unescape
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
OMNIWEB_URL: Final = "https://omniweb.gsfc.nasa.gov/cgi/nx1.cgi"
DEFAULT_CACHE_TTL: Final = timedelta(hours=1)
DEFAULT_TIMEOUT_SECONDS: Final = 20
DEFAULT_CACHE_DIR: Final = Path(__file__).resolve().parents[1] / "data" / "raw"


def fetch_omniweb_historical(
    start_date: datetime,
    end_date: datetime,
    resolution: str = "hourly",
) -> pd.DataFrame:
    """Fetch historical OMNI2 solar-wind and Kp observations from NASA OMNIWeb.

    Parameters are retrieved through NASA SPDF's `OMNIWeb Plus interface
    <https://omniweb.gsfc.nasa.gov/cgi/nx1.cgi>`_ for the inclusive date
    range.  The returned UTC-indexed frame has ``speed`` (km/s), ``density``
    (protons/cm³), ``temperature`` (K), ``imf_magnitude`` (nT), and ``Kp``.
    Raw ASCII replies are cached under ``data/raw/omniweb`` by date range.

    OMNI2 is an hourly, multi-spacecraft near-Earth/L1 compilation; its
    L1 data are time-shifted to estimated magnetospheric arrival times. Kp is
    a three-hour index repeated in hourly records. OMNIWeb supplies it as
    ``Kp * 10`` and this function converts it to conventional Kp units.
    OMNI fill values (for example 999.9, 9999, 9999999, and 99) are returned
    as ``NaN``.  ``resolution`` currently supports ``"hourly"`` only because
    the requested OMNI2 variables are the standard hourly product.

    Raises:
        ValueError: If dates or resolution are invalid.
        RuntimeError: If OMNIWeb cannot be reached or returns an unusable
            response.
    """
    if not isinstance(start_date, datetime) or not isinstance(end_date, datetime):
        raise ValueError("start_date and end_date must be datetime instances")
    if start_date > end_date:
        raise ValueError("start_date must be on or before end_date")
    if resolution != "hourly":
        raise ValueError("Only resolution='hourly' is supported for OMNI2 historical data")

    start = start_date.date()
    end = end_date.date()
    cache_path = (
        DEFAULT_CACHE_DIR
        / "omniweb"
        / f"omni2_{resolution}_{start:%Y%m%d}_{end:%Y%m%d}.txt"
    )
    raw_response = _read_omniweb_cache(cache_path)
    if raw_response is None:
        # OMNIWeb accepts one ``vars`` form field per selected variable.  The
        # historical nx1.cgi selector IDs are 08=scalar IMF, 23=density,
        # 22=temperature, 24=speed, and 38=Kp (the public table's physical
        # record-word numbers are offset for the plasma fields). Keep this
        # sequence aligned with the response columns parsed below.
        form_data: list[tuple[str, str]] = [
            ("activity", "retrieve"),
            ("res", "hour"),
            ("spacecraft", "omni2"),
            ("start_date", start.strftime("%Y%m%d")),
            ("end_date", end.strftime("%Y%m%d")),
            *(("vars", variable) for variable in ("08", "23", "22", "24", "38")),
        ]
        try:
            response = requests.post(OMNIWEB_URL, data=form_data, timeout=DEFAULT_TIMEOUT_SECONDS)
            response.raise_for_status()
        except requests.RequestException as error:
            raise RuntimeError(
                "OMNIWeb historical-data request failed for "
                f"{start.isoformat()} through {end.isoformat()} at {OMNIWEB_URL}: {error}"
            ) from error
        raw_response = response.text
        if not raw_response.strip() or _omniweb_response_is_error(raw_response):
            raise RuntimeError(
                "OMNIWeb returned no usable historical data for "
                f"{start.isoformat()} through {end.isoformat()}."
            )
        _write_omniweb_cache(cache_path, raw_response)

    frame = _parse_omniweb_response(raw_response)
    if frame.empty:
        raise RuntimeError(
            "OMNIWeb response contained no parseable hourly records for "
            f"{start.isoformat()} through {end.isoformat()}."
        )
    return frame


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
    return _normalise_plasma_columns(_to_time_frame(payload))


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


def _read_omniweb_cache(cache_path: Path) -> str | None:
    """Return a raw OMNIWeb response, ignoring a missing or unreadable cache."""
    try:
        return cache_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as error:
        LOGGER.warning("Could not read OMNIWeb cache %s: %s", cache_path, error)
        return None


def _write_omniweb_cache(cache_path: Path, raw_response: str) -> None:
    """Persist a successful raw OMNIWeb response without masking download success."""
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        temporary_path.write_text(raw_response, encoding="utf-8")
        temporary_path.replace(cache_path)
    except OSError as error:
        LOGGER.warning("Could not write OMNIWeb cache %s: %s", cache_path, error)


def _omniweb_response_is_error(raw_response: str) -> bool:
    """Identify common CGI error pages before caching them as data."""
    text = unescape(re.sub(r"<[^>]+>", " ", raw_response)).lower()
    return "internal server error" in text or "error processing" in text


def _parse_omniweb_response(raw_response: str) -> pd.DataFrame:
    """Parse OMNIWeb's HTML-wrapped ASCII listing into standard columns."""
    text = unescape(re.sub(r"<[^>]+>", " ", raw_response))
    rows: list[tuple[pd.Timestamp, list[float]]] = []
    for line in text.splitlines():
        values = re.findall(r"[-+]?\d+(?:\.\d+)?(?:[Ee][-+]?\d+)?", line)
        if len(values) < 8 or not re.match(r"^\s*\d{4}\s+", line):
            continue
        numbers = [float(value) for value in values]
        year = int(numbers[0])
        second = int(numbers[1])
        try:
            # OMNI2 listings use year, day-of-year, and hour.  Supporting a
            # calendar-date response as well makes the parser resilient to
            # minor OMNIWeb presentation changes.
            if 1 <= second <= 366 and 0 <= int(numbers[2]) <= 23:
                timestamp = pd.Timestamp(year=year, month=1, day=1, tz="UTC") + pd.Timedelta(
                    days=second - 1, hours=int(numbers[2])
                )
                metrics = numbers[3:8]
            elif 1 <= second <= 12 and 1 <= int(numbers[2]) <= 31 and 0 <= int(numbers[3]) <= 23:
                timestamp = pd.Timestamp(
                    year=year, month=second, day=int(numbers[2]), hour=int(numbers[3]), tz="UTC"
                )
                metrics = numbers[4:9]
            else:
                continue
        except ValueError:
            continue
        if len(metrics) == 5:
            rows.append((timestamp, metrics))

    columns = ["imf_magnitude", "density", "temperature", "speed", "Kp"]
    if not rows:
        empty_index = pd.DatetimeIndex([], name="time_tag", tz="UTC")
        return pd.DataFrame(
            columns=["speed", "density", "temperature", "imf_magnitude", "Kp"],
            index=empty_index,
        )

    frame = pd.DataFrame([metrics for _, metrics in rows], columns=columns)
    frame.index = pd.DatetimeIndex([timestamp for timestamp, _ in rows], name="time_tag")
    # Field-specific sentinels documented by OMNI2.  The threshold comparison
    # also safely covers equivalent all-9 fill values rendered with a variant
    # decimal precision by the CGI listing.
    for column, threshold in {
        "imf_magnitude": 999.0,
        "density": 999.0,
        "temperature": 999999.0,
        "speed": 9999.0,
    }.items():
        frame.loc[frame[column].abs() >= threshold, column] = float("nan")
    frame.loc[frame["Kp"].abs() >= 99, "Kp"] = float("nan")
    frame["Kp"] = frame["Kp"] / 10.0
    return frame[["speed", "density", "temperature", "imf_magnitude", "Kp"]].loc[
        lambda data: ~data.index.duplicated(keep="last")
    ].sort_index()


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


def _normalise_plasma_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Return standard plasma metric names across NOAA product schemas.

    NOAA's seven-day product uses ``density``, ``speed``, and
    ``temperature``, while the real-time fallback identifies these proton
    measurements as ``proton_density``, ``proton_speed``, and
    ``proton_temperature``.  Preserve an already-standard column when both
    variants are present.
    """
    aliases = {
        "proton_density": "density",
        "proton_speed": "speed",
        "proton_temperature": "temperature",
    }
    rename_map = {
        source: target
        for source, target in aliases.items()
        if source in frame.columns and target not in frame.columns
    }
    return frame.rename(columns=rename_map)


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
