# Space Weather: Latest Automated Detection

**Status: UNKNOWN**. Upstream data unavailable or stale

_Generated 2026-09-01T11:37:40+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-01T02:05:00+00:00 |
| Data age | 9.54 h |
| Samples scored | 2316 |
| Samples flagged | 16 (0.7%) |
| Latest Kp | 1.0 |
| Storm class | quiet to unsettled |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 15.3 |
| speed | 10.17 |
| temperature | 21.95 |

> Newest sample is 9.5 h old, beyond the 6:00:00 staleness limit; treating current conditions as unknown.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).