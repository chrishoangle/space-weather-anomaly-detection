# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-08-06T09:05:25+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-08-06T08:58:08+00:00 |
| Data age | 0.12 h |
| Samples scored | 2242 |
| Samples flagged | 543 (24.2%) |
| Latest Kp | 0.67 |
| Storm class | quiet to unsettled |
| Driving features | speed |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 2.75 |
| speed | 6.04 |
| temperature | 5.21 |

> Scored 2242 samples; 543 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).