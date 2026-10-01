# Space Weather: Latest Automated Detection

**Status: NOMINAL**. No anomaly on the most recent sample

_Generated 2026-10-01T13:10:19+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-01T13:05:00+00:00 |
| Data age | 0.09 h |
| Samples scored | 2640 |
| Samples flagged | 32 (1.2%) |
| Latest Kp | 1.0 |
| Storm class | quiet to unsettled |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 2.92 |
| speed | 5.38 |
| temperature | 10.26 |

> Scored 2640 samples; 32 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).