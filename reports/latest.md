# Space Weather: Latest Automated Detection

**Status: ANOMALY**. Detector is firing on the most recent sample

_Generated 2026-10-19T13:10:08+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-19T13:03:03+00:00 |
| Data age | 0.12 h |
| Samples scored | 2067 |
| Samples flagged | 171 (8.3%) |
| Latest Kp | 1.0 |
| Storm class | quiet to unsettled |
| Driving features | density |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 4.15 |
| speed | 2.49 |
| temperature | 3.1 |

> Scored 2067 samples; 171 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).