# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-11-17T15:57:25+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-11-17T15:52:00+00:00 |
| Data age | 0.09 h |
| Samples scored | 2873 |
| Samples flagged | 273 (9.5%) |
| Latest Kp | 0.67 |
| Storm class | quiet to unsettled |
| Driving features | speed |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 2.02 |
| speed | 16.11 |
| temperature | 40.63 |

> Scored 2873 samples; 273 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).