# Space Weather: Latest Automated Detection

**Status: NOMINAL**. No anomaly on the most recent sample

_Generated 2026-08-19T07:04:43+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-08-19T07:00:00+00:00 |
| Data age | 0.08 h |
| Samples scored | 2640 |
| Samples flagged | 53 (2.0%) |
| Latest Kp | 5.0 |
| Storm class | G1 minor |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 3.62 |
| speed | 3.67 |
| temperature | 3.26 |

> Scored 2640 samples; 53 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).