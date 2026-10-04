# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-10-04T12:19:34+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-04T12:13:04+00:00 |
| Data age | 0.11 h |
| Samples scored | 2537 |
| Samples flagged | 987 (38.9%) |
| Latest Kp | 5.0 |
| Storm class | G1 minor |
| Driving features | speed, temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 8.97 |
| speed | 15.87 |
| temperature | 47.97 |

> Scored 2537 samples; 987 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).