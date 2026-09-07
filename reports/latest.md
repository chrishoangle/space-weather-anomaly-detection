# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-09-07T12:29:42+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-09-07T12:24:00+00:00 |
| Data age | 0.1 h |
| Samples scored | 2163 |
| Samples flagged | 531 (24.6%) |
| Latest Kp | 4.0 |
| Storm class | quiet to unsettled |
| Driving features | speed, temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 31.52 |
| speed | 18.21 |
| temperature | 30.42 |

> Scored 2163 samples; 531 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).