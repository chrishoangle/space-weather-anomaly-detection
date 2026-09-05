# Space Weather: Latest Automated Detection

**Status: NOMINAL**. No anomaly on the most recent sample

_Generated 2026-09-05T10:33:15+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-05T10:28:00+00:00 |
| Data age | 0.09 h |
| Samples scored | 2290 |
| Samples flagged | 32 (1.4%) |
| Latest Kp | 2.0 |
| Storm class | quiet to unsettled |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 3.25 |
| speed | 3.29 |
| temperature | 5.37 |

> Scored 2290 samples; 32 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).