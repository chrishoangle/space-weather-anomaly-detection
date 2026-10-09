# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-10-09T13:14:11+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-09T13:09:04+00:00 |
| Data age | 0.09 h |
| Samples scored | 2330 |
| Samples flagged | 284 (12.2%) |
| Latest Kp | 4.0 |
| Storm class | quiet to unsettled |
| Driving features | temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 5.67 |
| speed | 5.92 |
| temperature | 8.75 |

> Scored 2330 samples; 284 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).