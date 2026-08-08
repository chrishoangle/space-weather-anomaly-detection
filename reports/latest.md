# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-08-08T07:13:51+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-08-08T07:08:08+00:00 |
| Data age | 0.1 h |
| Samples scored | 2607 |
| Samples flagged | 442 (17.0%) |
| Latest Kp | 1.67 |
| Storm class | quiet to unsettled |
| Driving features | speed, density, temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 10.91 |
| speed | 12.79 |
| temperature | 20.13 |

> Scored 2607 samples; 442 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).