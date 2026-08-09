# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-08-09T07:15:33+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-08-09T07:09:08+00:00 |
| Data age | 0.11 h |
| Samples scored | 2676 |
| Samples flagged | 593 (22.2%) |
| Latest Kp | 2.33 |
| Storm class | quiet to unsettled |
| Driving features | temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 4.34 |
| speed | 7.37 |
| temperature | 9.81 |

> Scored 2676 samples; 593 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).