# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-09-14T12:43:37+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-14T12:38:05+00:00 |
| Data age | 0.09 h |
| Samples scored | 2523 |
| Samples flagged | 594 (23.5%) |
| Latest Kp | 2.0 |
| Storm class | quiet to unsettled |
| Driving features | density |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 16.67 |
| speed | 3.12 |
| temperature | 6.96 |

> Scored 2523 samples; 594 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).