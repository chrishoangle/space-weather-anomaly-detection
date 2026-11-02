# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-11-02T15:46:27+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-11-02T15:42:00+00:00 |
| Data age | 0.07 h |
| Samples scored | 2392 |
| Samples flagged | 459 (19.2%) |
| Latest Kp | 1.67 |
| Storm class | quiet to unsettled |
| Driving features | speed |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 15.43 |
| speed | 5.93 |
| temperature | 3.62 |

> Scored 2392 samples; 459 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).