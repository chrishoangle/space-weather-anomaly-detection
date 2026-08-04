# Results

## 1. Objective and Summary

The purpose of this evaluation is to determine whether an unsupervised anomaly
detector can flag geomagnetic storm conditions in solar-wind time series with
enough restraint to be operationally meaningful, and whether a machine-learning
detector outperforms a conventional statistical baseline on that task.

Across all five catalogued storms, every detector configuration flagged every
storm. Detection is therefore not the discriminating problem. On precision and
on quiet-time false-alarm rate, the 3-sigma statistical process control (SPC)
baseline outperforms Isolation Forest in every configuration tested, and the
margin widens in the most geomagnetically disturbed window.

To reproduce the results in this document:

```bash
python scripts/compare_detectors.py            # fetches any missing windows
python scripts/compare_detectors.py --offline  # cached windows only
```

Detailed results are provided in `reports/detector_comparison.csv` (aggregate)
and `reports/detector_comparison_per_window.csv` (per event).

---

## 2. Data

Hourly records were retrieved from [NASA OMNI2](https://omniweb.gsfc.nasa.gov/)
via the OMNIWeb interface. The variables used are `speed` (km/s), `density`
(cm^-3), `temperature` (K), `imf_magnitude` (nT), and `Kp`.

For each catalogued storm, one calendar-month window containing the storm peak
was retrieved. Calendar months were chosen over a fixed offset from the peak so
that the window boundaries are a deterministic function of the catalog alone,
which keeps the cache key identical across runs and across machines.

All five catalogued storms were evaluated, totalling 3,696 hourly samples.

| Event | Peak | Kp | Samples | Kp>=3 hours | Kp>=5 hours |
| --- | --- | --- | --- | --- | --- |
| Bastille Day | 2000-07-15 | 9 | 744 | 35.5% | 8.9% |
| Halloween Storms | 2003-10-29 | 9 | 744 | **54.0%** | **17.3%** |
| St. Patrick's Day | 2015-03-17 | 8 | 744 | 35.1% | 6.0% |
| September 2017 | 2017-09-08 | 8 | 720 | 36.7% | 7.5% |
| Gannon Storm | 2024-05-10 | 9 | 744 | 22.2% | 10.1% |

Ground truth is defined in `data/storm_catalog.csv`. A detection is counted as
a hit when it falls within 24 hours of the catalogued storm peak.

### 2.1 Limitations

Given that all four configurations detected all five storms, event recall is
saturated at 1.000 and cannot discriminate between them. These are the five
largest storms in two decades and the hit tolerance is 24 hours, so the
detection bar is low enough that every configuration clears it. Consequently,
every conclusion in this document rests on precision and on false-alarm rate.
Recall is still reported so that its saturation remains visible.

Regarding the ground truth itself, the catalog labels one storm per month-long
window, whereas October 2003 records Kp >= 5 in 17.3% of its hours. Those hours
represent genuine storm conditions that the catalog treats as quiet. All
precision figures are therefore lower bounds, and the underestimate is largest
in the most active windows. This bias is not uniformly distributed across
configurations, and its direction is examined in Section 5.

With respect to the quiet label, Kp in OMNI2 is a three-hourly index repeated
across three consecutive hourly rows. The effective sample size of the quiet
period is therefore approximately one third of the row count, which suggests
that the false-alarm denominator is optimistic.

Because the `onset_utc` field of the catalog is unpopulated, hit windows are
centred on the storm peak rather than on shock arrival, and lead-time metrics
return NaN throughout. Detection timing relative to storm onset is consequently
not measured in this study.

Finally, five events cannot support a tight interval on any of the means
reported below. The per-window spread documented in Section 4.4 is large
relative to the differences between configurations.

---

## 3. Method

Four configurations were compared under identical features, an identical hit
tolerance of 24 hours, and a single shared evaluation code path
(`src.evaluation.evaluate_detector`). A fresh detector was fitted for each
window.

| Configuration | Fitted on |
| --- | --- |
| SPC, 3 sigma | Rows with Kp < 3 |
| SPC, 3 sigma | First half of the window (calendar) |
| Isolation Forest, 300 trees, `contamination="auto"` | All rows |
| Isolation Forest, 300 trees, `contamination="auto"` | Rows with Kp < 3 |

Both fitting regimes were run against both detectors. Pairing a single regime
with each detector would allow the experimental setup rather than the model to
determine the outcome, so the full cross was evaluated instead.

Regarding the contamination parameter, `contamination` was held at `"auto"`
throughout. Tuning it toward the observed storm rate would introduce label
information into an otherwise unsupervised model, which would inflate every
downstream metric.

Considering the variation in solar activity across a solar cycle, a per-window
baseline was used rather than a single global one. Quiet conditions in October
2003, near solar maximum, are not comparable to quiet conditions in May 2024,
so a reference period fitted across the full 2000 to 2024 span would not be
defensible.

---

## 4. Results

All figures below are means across the five evaluated windows, covering 3,696
hourly samples.

| Configuration | Event recall | Precision | PW recall | PW F1 | PW FPR | Quiet FAR | Flagged |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **SPC, calendar quiet half** | 1.000 * | **0.394** | 0.392 | 0.374 | **0.048** | **0.024** | 262 / 3696 |
| SPC, Kp<3 quiet rows | 1.000 * | 0.282 | 0.616 | **0.383** | 0.119 | 0.043 | 561 / 3696 |
| Isolation Forest, all data | 1.000 * | 0.254 | 0.494 | 0.333 | 0.101 | 0.061 | 471 / 3696 |
| Isolation Forest, Kp<3 rows | 1.000 * | 0.136 | **0.661** | 0.225 | 0.293 | 0.156 | 1172 / 3696 |

\* Saturated. See Section 2.1. PW denotes point-wise. Quiet FAR is the fraction
of Kp<3 hours flagged. Detailed results are provided in
`reports/detector_comparison.csv`.

### 4.1 Precision

Precision here is the share of flagged hours that fall inside a catalogued
storm window. It is the metric most directly tied to operational cost, since
each false positive is an alert a human would have to dismiss.

Precision was computed per window and averaged across the five windows, with
the hit tolerance held at 24 hours for every configuration.

From the aggregate table, the SPC baseline fitted on the calendar quiet half
achieves the highest precision at 0.394, followed by SPC fitted on Kp<3 rows at
0.282. Both Isolation Forest configurations fall below both SPC configurations,
at 0.254 and 0.136 respectively.

Considering the ordering of the four results, both SPC configurations outrank
both Isolation Forest configurations, which suggests that the separation
follows the detector family rather than the fitting regime. Detailed per-window
precision is provided in `reports/detector_comparison_per_window.csv`.

### 4.2 Point-wise recall

Point-wise recall is the share of in-storm hours that were flagged. Unlike
event recall, it is sensitive to how much of a storm a detector covers rather
than merely whether it fired at all.

Recall was computed over the same labelled windows used for precision, with no
change to the tolerance.

Isolation Forest fitted on Kp<3 rows records the highest point-wise recall of
any configuration at 0.661, ahead of SPC fitted on Kp<3 rows at 0.616. The two
conservative configurations follow at 0.494 and 0.392.

However, that same configuration flags 1,172 of 3,696 samples, approximately
32% of every month. This indicates that its recall advantage may be a
consequence of indiscriminate firing rather than of improved sensitivity. Read
in isolation, recall would rank the weakest configuration first, which is the
principal argument for reporting the quiet-time false-alarm rate alongside it.

### 4.3 Quiet-time false-alarm rate

The quiet-time false-alarm rate is the fraction of hours with Kp < 3 that a
detector flags. Because those hours are independently measured as
geomagnetically quiet, the metric is not dependent on the completeness of the
storm catalog, which makes it the most robust discriminator available here.

The rate was computed over all Kp<3 rows in each window and averaged across
windows.

SPC fitted on the calendar quiet half records the lowest rate at 0.024,
followed by SPC on Kp<3 rows at 0.043, Isolation Forest on all data at 0.061,
and Isolation Forest on Kp<3 rows at 0.156.

In contrast to precision, this metric is unaffected by the catalog
under-labelling described in Section 2.1, and it preserves the same ordering.
Therefore the ranking of the four configurations appears to be robust to the
main known weakness in the ground truth.

### 4.4 Per-window variation

Point-wise F1 was computed separately for each of the five windows in order to
assess whether the aggregate ordering holds event by event.

| Event | SPC calendar | SPC Kp<3 | IF all | IF Kp<3 |
| --- | --- | --- | --- | --- |
| Bastille Day | 0.310 | 0.324 | **0.377** | 0.226 |
| Halloween Storms | **0.343** | 0.307 | 0.133 | 0.062 |
| St. Patrick's Day | **0.476** | 0.449 | 0.326 | 0.284 |
| September 2017 | 0.329 | **0.525** | 0.460 | 0.303 |
| Gannon Storm | **0.410** | 0.311 | 0.369 | 0.252 |

Isolation Forest leads in one window only, Bastille Day, and by a margin of
0.053 over the nearest SPC configuration. Across the remaining four windows an
SPC configuration leads.

Considering the spread within each column, F1 varies by roughly 0.1 across
windows for every configuration, which is comparable to the differences between
configurations in the aggregate table. This suggests that the aggregate means
should not be read to three significant figures on a sample of five events.

### 4.5 Trade-off between the two SPC configurations

The two SPC configurations record nearly identical F1 scores, at 0.374 and
0.383, yet they differ substantially in behaviour.

Fitting on the calendar quiet half yields precision 0.394, a quiet-time
false-alarm rate of 0.024, and 262 flags. Fitting on Kp<3 rows yields recall
0.616 against 0.392, at approximately twice the flag count and 1.8 times the
false-alarm rate.

Consequently, F1 obscures rather than resolves the choice between them. Which
configuration is preferable depends on the relative cost of a false alarm
against a missed storm hour, which is a domain decision rather than a modelling
one.

---

## 5. Discussion

### 5.1 Failure behaviour under a shifted base rate

The October 2003 window is the most informative case in the study. It is the
hardest window for all four configurations, but the degradation is not uniform
across detector families. SPC declines to F1 0.343 and 0.307, whereas Isolation
Forest declines to 0.133 and 0.062. In the latter configuration, precision
falls to 0.039.

Considering the composition of that window, October 2003 records Kp >= 3 in
54.0% of its hours, meaning the month is predominantly disturbed. This
performance gap can be attributed to the way each detector defines normal
behaviour. Isolation Forest infers normality from the distribution of the data
supplied to it, so a predominantly disturbed month may cause disturbance itself
to be treated as typical, which would suppress the model's ability to isolate
it. SPC, by contrast, is anchored to an externally specified quiet reference,
so its notion of normal is not displaced by the composition of the evaluation
window.

Ultimately this behaviour is not specific to space weather. Any unsupervised
detector that defines anomalous as rare within its training distribution
appears vulnerable to base-rate shift, which is precisely the regime in which a
monitoring system is most needed.

### 5.2 Signal structure

With respect to the shape of the storm signature itself, disturbances in this
dataset present largely as marginal excursions. Speed and IMF magnitude move
well outside their quiet ranges individually during a storm. A per-feature
sigma threshold is therefore well matched to the signal.

Isolation Forest's advantage lies in identifying unusual joint configurations
of individually unremarkable values. On this dataset that capability appears to
be largely unexercised, which may account for the absence of any offsetting
gain.

### 5.3 Interpretability

Beyond the quantitative comparison, SPC reports which feature drove each
detection. Across the five windows the flags are attributable predominantly to
`speed` and `imf_magnitude`, which is consistent with CME-driven storm physics.
Isolation Forest returns a single opaque score. For an alerting application,
the per-feature attribution is actionable in a way that the score is not.

### 5.4 Counter-argument

The under-labelling described in Section 2.1 depresses precision most severely
in the most active windows, and Isolation Forest performs worst in exactly
those windows. A portion of its October 2003 false positives may therefore
correspond to genuine but unlabelled disturbance.

However, this consideration bears on the magnitude of the gap rather than its
direction. In the quietest window evaluated, the Gannon storm at 22.2% Kp>=3,
SPC on the calendar quiet half still leads on precision by 0.552 to 0.283.

---

## 6. Negative Findings

Isolation Forest underperformed the statistical baseline on every aggregate
metric except raw recall. It is retained in the repository and reported as
underperforming.

Fitting Isolation Forest on quiet rows alone produced the weakest configuration
tested. Restricting the training distribution to quiet conditions appears to
narrow the learned notion of normal to the point where ordinary variability
registers as anomalous, yielding 1,172 flags and a 15.6% quiet-time false-alarm
rate.

The quiet window originally used in `notebooks/03_baseline_detection.ipynb`,
covering 1 to 7 March 2015, contains hours at Kp near 5. This inflates the
fitted baseline and reduces sensitivity. Replacing it with the calendar first
half improved precision on that window from 0.348 to 0.390.

F1 was evaluated as a summary metric and rejected for that role. As shown in
Section 4.5, it ranks the two SPC configurations as near-equivalent while they
differ by 1.6 times in recall and 1.8 times in false-alarm rate.

---

## 7. Further Work

Populating `onset_utc` in the storm catalog would enable lead-time measurement,
which is the metric that determines whether detection carries operational
value.

Replacing the five-event catalog with a Kp >= 5 derived event list over two
decades would address two limitations simultaneously. It would restore event
recall as a discriminating metric, since a larger and more varied event set
would no longer be uniformly detected, and it would reduce the under-labelling
that currently bounds precision from below.

Sweeping the hit tolerance from 6 to 48 hours would allow precision and recall
to be reported as a function of tolerance rather than at a single operating
point.

Supplying Isolation Forest with the engineered features already computed in
`src/preprocessing.py`, specifically rolling standard deviation, rate of
change, and dynamic pressure, would test whether interaction structure exists
in the derived features even though it appears absent in the raw levels. This
constitutes the fairest remaining test of the model class.

Reporting per-window variance alongside the means would represent the
uncertainty in Section 4 more honestly than the aggregate figures alone.
