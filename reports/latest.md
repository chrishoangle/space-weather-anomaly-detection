# Space Weather: Latest Automated Detection

**Status: NOMINAL**. No anomaly on the most recent sample

_Generated 2026-10-02T12:31:46+00:00 by `scripts/run_daily_detection.py`._

| Field | Value |
| --- | --- |
| Newest sample | 2026-10-02T12:27:04+00:00 |
| Data age | 0.08 h |
| Samples scored | 2517 |
| Samples flagged | 101 (4.0%) |
| Latest Kp | 0.67 |
| Storm class | quiet to unsettled |

Peak |z| over the window:

| Feature | Peak abs z-score |
| --- | --- |
| density | 2.08 |
| speed | 8.65 |
| temperature | 14.27 |

> Scored 2517 samples; 101 flagged.

---

**How to read this.** The baseline is the first 60% of the rolling window, so during a multi-day storm the reference is contaminated and sensitivity drops. A single flagged sample is not a storm warning; see [RESULTS.md](../RESULTS.md) for measured precision (0.17 to 0.39 depending on configuration). This is a demonstration of an unattended pipeline, not an operational forecast. For real alerts use [NOAA SWPC](https://www.swpc.noaa.gov/).