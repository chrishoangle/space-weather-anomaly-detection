# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-09-11T11:19:24+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-11T11:15:06+00:00 |
| Data age | 0.07 h |
| Samples scored | 2160 |
| Samples flagged | 149 (6.9%) |
| Latest Kp | 1.67 |
| Storm class | quiet to unsettled |
| Driving features | speed, density |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 3.34 |
| speed | 3.95 |
| temperature | 7.17 |

> Scored 2160 samples; 149 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).