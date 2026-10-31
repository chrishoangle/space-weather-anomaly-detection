# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-10-31T12:23:55+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-31T12:19:02+00:00 |
| Data age | 0.08 h |
| Samples scored | 2385 |
| Samples flagged | 762 (31.9%) |
| Latest Kp | 3.0 |
| Storm class | quiet to unsettled |
| Driving features | speed, temperature |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 8.18 |
| speed | 12.02 |
| temperature | 13.59 |

> Scored 2385 samples; 762 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).