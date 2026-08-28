# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-08-28T18:40:15+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-08-28T18:35:00+00:00 |
| Data age | 0.09 h |
| Samples scored | 2490 |
| Samples flagged | 416 (16.7%) |
| Latest Kp | 3.33 |
| Storm class | quiet to unsettled |
| Driving features | speed, temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 3.98 |
| speed | 9.72 |
| temperature | 24.55 |

> Scored 2490 samples; 416 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).