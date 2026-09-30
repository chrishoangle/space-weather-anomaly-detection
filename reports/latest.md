# Space Weather: Latest Automated Detection

**Status: NOMINAL**. No anomaly on the most recent sample

_Generated 2026-09-30T12:32:11+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-30T12:28:04+00:00 |
| Data age | 0.07 h |
| Samples scored | 2589 |
| Samples flagged | 24 (0.9%) |
| Latest Kp | 1.33 |
| Storm class | quiet to unsettled |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 2.05 |
| speed | 6.21 |
| temperature | 26.87 |

> Scored 2589 samples; 24 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).