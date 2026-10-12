# Methodological review: Space Weather Anomaly Detection

An adversarial re-examination of the project's statistical claims, run against the
committed data rather than from memory. Every number below was recomputed from
`docs/storms.json` and `reports/detector_comparison_per_window.csv`.

Disclosure: I designed most of this evaluation framework. Two of the findings below
are errors in my own design, including one in the claim I told you to lead with.

---

## Summary of findings

| # | Issue | Severity | Status of the affected claim |
| --- | --- | --- | --- |
| 1 | Detectors compared at different operating points | **Critical** | Headline effect shrinks by two thirds |
| 2 | Base-rate-shift mechanism unsupported across windows | **Critical** | Not defensible as stated |
| 3 | Hourly samples treated as independent | **High** | All metric precision overstated |
| 4 | No held-out evaluation; false-alarm rate is in-sample | **High** | Quiet FAR biased downward |
| 5 | IMF magnitude used instead of Bz | **High (domain)** | First question a space physicist asks |
| 6 | No multiple-comparison control | Moderate | Post hoc selection risk |
| 7 | Catalog under-labelling asymmetry | Moderate | Already disclosed, understated |

Two claims survive. Several do not.

---

## 1. The detectors are compared at different operating points

**This is the most serious problem and it undercuts the headline result.**

Precision and recall trade off against each other. A detector that flags fewer
hours will, all else equal, show higher precision. The published comparison does not
hold the flag rate fixed:

| Window | IF flags | SPC at 3 sigma | Ratio |
| --- | --- | --- | --- |
| Bastille Day | 89 | 35 | 2.54 |
| Halloween Storms | 71 | 85 | 0.84 |
| St. Patrick's Day | 129 | 77 | 1.68 |
| September 2017 | 90 | 36 | 2.50 |
| Gannon Storm | 92 | 29 | 3.17 |

Isolation Forest flags roughly twice as many hours as SPC in most windows, because
`contamination="auto"` sets a roughly fixed anomaly fraction while a 3 sigma
threshold produces a data-dependent one. The two detectors sit at different points
on their respective precision-recall curves, and the comparison declares a winner
without controlling for that.

I re-ran the comparison with the SPC threshold tuned per window so that it flags
exactly as many hours as Isolation Forest:

| Window | n flagged | IF precision | SPC precision | sigma used | Winner |
| --- | --- | --- | --- | --- | --- |
| Bastille Day | 89 | 0.292 | 0.315 | 1.69 | SPC |
| Halloween Storms | 71 | 0.113 | 0.296 | 3.57 | SPC |
| St. Patrick's Day | 130 | 0.225 | 0.315 | 2.44 | SPC |
| September 2017 | 90 | 0.356 | 0.300 | 2.21 | IF |
| Gannon Storm | 92 | 0.283 | 0.283 | 1.37 | IF |

**Result: mean precision 0.302 for SPC against 0.254 for Isolation Forest, a
difference of +0.048, paired t p = 0.306, SPC winning 3 of 5 windows.**

Compare with the published figures: 0.394 against 0.254, a difference of +0.141,
paired t p = 0.0126, SPC winning 5 of 5 windows.

**Roughly two thirds of the reported effect is an artifact of the operating point.**
What remains is in the right direction but is no longer statistically distinguishable
from zero at n = 5.

### What the project should have done

Sweep the threshold for both detectors and compare precision-recall curves, or
average precision, rather than comparing two arbitrary and unequal operating points.
Isolation Forest exposes `score_samples`, so a full curve is available for it. The
current export only ships the boolean, so the curve cannot currently be reconstructed
in the browser.

### How to state the claim honestly now

> At a matched flag rate, the statistical baseline retains a small precision
> advantage over Isolation Forest (0.302 against 0.254), but with five windows the
> difference is not statistically significant (paired t p = 0.31) and the baseline
> wins only three of five windows. The larger advantage reported at default settings
> is substantially an operating-point effect.

---

## 2. The base-rate-shift mechanism is not supported across windows

This is the claim I told you was your strongest interview answer. It does not hold.

The argument was: Isolation Forest degrades when the base rate shifts, evidenced by
October 2003, where 54.0% of hours record Kp >= 3 and Isolation Forest collapses to
F1 0.062 while SPC holds at 0.343.

If that mechanism were operating, the gap between the detectors should widen as the
disturbed fraction rises. Across the five available windows:

| Window | Kp >= 3 % | IF_all F1 | SPC_cal F1 | Gap (IF minus SPC) |
| --- | --- | --- | --- | --- |
| Gannon Storm | 22.2 | 0.369 | 0.410 | -0.041 |
| St. Patrick's Day | 35.1 | 0.326 | 0.476 | **-0.150** |
| Bastille Day | 35.5 | 0.377 | 0.310 | **+0.067** |
| September 2017 | 36.7 | 0.460 | 0.329 | **+0.131** |
| Halloween Storms | 54.0 | 0.133 | 0.343 | -0.210 |

**Pearson r = -0.444 (p = 0.45). Spearman r = -0.100 (p = 0.87).**

There is no monotonic relationship. Worse, look at the three middle rows: at
essentially identical disturbed fractions of 35.1%, 35.5% and 36.7%, the gap spans
-0.150 to +0.131. **The scatter at matched base rate is as large as the Halloween
effect being explained.**

The mechanism rests entirely on one window being simultaneously the most disturbed
and the worst for Isolation Forest. With five windows, one of them has to be the
extreme on both axes. That co-occurrence is weak evidence for a causal mechanism.

The underlying reasoning is still sound as *theory*. An unsupervised detector that
defines anomalous as rare in its training distribution should be vulnerable to base
rate shift. But this dataset does not demonstrate it, and presenting it as a
demonstrated finding is the clearest overclaim in the project.

### How to state it honestly now

> October 2003 is the window where Isolation Forest performs worst, and it is also
> the most disturbed window in the set. Base rate shift is a plausible mechanism and
> is consistent with how unsupervised isolation works. However, across the five
> available windows the correlation between disturbed fraction and the performance
> gap is not significant (Spearman r = -0.10), and two windows at nearly identical
> base rates show gaps of opposite sign. The mechanism remains a hypothesis that
> this dataset cannot confirm.

That version is still a good interview answer. Arguably a better one, because
knowing the difference between a mechanism you have demonstrated and one you have
merely proposed is the actual skill being tested.

---

## 3. Hourly samples are treated as independent when they are not

All point-wise metrics treat each of the 3,696 hours as an independent trial. Solar
wind is strongly autocorrelated on timescales of hours to days.

Measured lag-1 autocorrelation of solar wind speed, and the resulting integrated
decorrelation time:

| Window | N hours | lag-1 r | Decorrelation time | Effective N |
| --- | --- | --- | --- | --- |
| Bastille Day | 744 | 0.990 | 118.8 h | 6.3 |
| Halloween Storms | 685 | 0.983 | 38.3 h | 17.9 |
| St. Patrick's Day | 744 | 0.991 | 91.8 h | 8.1 |
| September 2017 | 714 | 0.989 | 60.0 h | 11.9 |
| Gannon Storm | 723 | 0.993 | 103.2 h | 7.0 |

**3,610 usable hourly samples correspond to roughly 51 effectively independent
observations. The nominal sample size overstates the information content by about
71 times.**

Consequences:

- Any confidence interval computed as if N = 3,696 is too narrow by roughly a factor
  of 8 in the standard error.
- Reporting precision to three decimal places implies a resolution the data cannot
  support.
- The statement in RESULTS.md that five events cannot support a tight interval is
  correct, but the reason given is the event count. The deeper reason is that even
  within a window, the hours are not independent replicates.

The paired per-window tests in section 1 are not affected by this, because they treat
each window as one observation, which is the correct unit. That is the right analysis
unit for this project and the per-window table should be the primary result rather
than the pooled means.

---

## 4. There is no held-out evaluation anywhere

The quiet-time false alarm rate is computed over rows with Kp < 3. Two of the four
configurations are also *fitted* on exactly those rows.

| Window | Kp<3 rows | SPC-Kp<3 overlap with its own training set | SPC-calendar overlap |
| --- | --- | --- | --- |
| Bastille Day | 480 | 100% | 51.2% |
| Halloween Storms | 342 | 100% | 71.9% |
| St. Patrick's Day | 483 | 100% | 55.3% |
| September 2017 | 456 | 100% | 47.4% |
| Gannon Storm | 579 | 100% | 43.5% |

The `SPC Kp<3` and `Isolation Forest Kp<3` configurations are scored for false alarms
on precisely the data they were fitted to. This biases their false-alarm rate
downward. The `SPC calendar half` configuration, which is the reported winner, has
roughly half its false-alarm evaluation inside its own training window.

No train/test split, no cross-validation, and no held-out window exists anywhere in
the project. Every reported number is in-sample.

A leave-one-storm-out protocol would be the natural fix and is cheap to implement
given the existing harness: fit the quiet baseline on four windows, evaluate on the
fifth, rotate.

---

## 5. The feature set omits the controlling physical parameter

This is the question a NASA, JPL, or any space weather researcher asks first, and the
project has no answer for it.

The loader requests OMNI2 variables 08, 22, 23, 24 and 38: scalar IMF magnitude,
temperature, density, speed, and Kp. **Scalar IMF magnitude is |B|. The project never
uses Bz.**

Southward interplanetary magnetic field Bz is the dominant control on solar wind to
magnetosphere coupling. The physical reason is dayside magnetic reconnection, which
requires an antiparallel field. The consequences for this project:

- A solar wind structure with large |B| but northward Bz produces little or no
  geomagnetic response. The detector will flag it, Kp will stay low, and the
  framework will score it as a false positive even though the detector correctly
  identified an anomalous solar wind structure.
- A moderate |B| with strongly southward Bz can drive a major storm. The detector may
  miss it entirely.

This means a meaningful share of what the project counts as false alarms may be real
solar wind anomalies that simply did not couple. The project is detecting solar wind
anomalies and grading them against a geomagnetic response index, and those are
different physical quantities.

It also makes the quiet-time false alarm rate less clean than claimed. RESULTS.md
argues that the Kp-based quiet label is robust to catalog under-labelling. That is
true with respect to the catalog, but it imports a different problem: Kp < 3 means
the magnetosphere was quiet, not that the solar wind was unremarkable.

Fixes, in order of effort:

1. Add OMNI2 variable 16 (Bz GSM) to the loader and the feature set. One line in the
   request, then regenerate.
2. Better, compute a coupling function such as the Newell universal coupling function
   or the epsilon parameter, and detect on that.
3. At minimum, state the limitation explicitly. Reframe the project as solar wind
   anomaly detection evaluated against geomagnetic outcome, and name the gap.

---

## 6. No multiple-comparison control

Four configurations are compared across seven metrics, with the winner selected after
seeing the results. Twenty-eight cells, no correction, no pre-registration of which
metric decides.

This matters less than it might because the direction is consistent across metrics,
but the specific claim "lowest false-alarm rate at 0.024" is a selected minimum from a
family of comparisons and should not be quoted as if it were a pre-specified endpoint.

---

## 7. The catalog asymmetry is disclosed but its effect is understated

RESULTS.md correctly notes that the catalog under-labels and that precision figures
are lower bounds. It also notes that the bias is largest in active windows, and that
Isolation Forest performs worst in exactly those windows.

What it does not do is quantify the interaction. The counter-argument offered is that
even in the quietest window the baseline leads. That is true but weaker than it
sounds, because the quietest window (Gannon, 22.2%) is also one of the two where
Isolation Forest wins at matched flag rate. The counter-argument should be withdrawn
or restated.

---

## What holds up

Not everything here is a problem. These parts are sound and would survive review:

- **Rejecting accuracy.** Correct and correctly reasoned for a 5% positive class.
- **Reporting event-wise and point-wise families together.** Good practice, and the
  reasoning about why each alone is misleading is right.
- **Diagnosing event recall as saturated.** Correct, and reporting it anyway with the
  saturation labelled is the honest choice.
- **The quiet-time false alarm rate as a concept.** The reasoning that it catches a
  detector gaming recall is sound, and it did catch exactly that: Isolation Forest on
  quiet rows flags 32% of every month. That finding survives all of the above.
- **Per-window fitting rather than a global baseline.** Correct, and well justified by
  solar cycle variation.
- **Holding contamination at auto.** Correct reasoning about label leakage, even
  though it created the operating-point problem in section 1.
- **The paired structure of the data.** Five windows, both detectors on each, is the
  right design. The analysis just was not run as a paired test.
- **NaN rather than 0.0 for undefined metrics.** Correct and unusual.

---

## Direct answers to the five questions

**Are the conclusions statistically defensible?**

Partly. "The baseline outperforms Isolation Forest" is defensible as a directional
claim at default settings (paired t p = 0.013, 5 of 5 windows), but most of the
magnitude is an operating-point artifact, and at matched flag rate the result is not
significant. "Base rate shift explains the gap" is not defensible on this data.

**Are there methodological weaknesses?**

Yes, four significant ones: unmatched operating points, no held-out evaluation,
treating autocorrelated hours as independent, and an unsupported causal mechanism.

**Is the evaluation framework rigorous?**

The *metric design* is unusually rigorous for a portfolio project. The *experimental
design* is not. The project thought carefully about what to measure and much less
carefully about how to compare. Those are different skills and the gap between them
is the main finding of this review.

**Did you accidentally overclaim?**

Twice. The base-rate-shift mechanism is presented as a finding when it is a
hypothesis. The precision advantage is presented at face value when most of it is an
operating-point effect. Both appear on the public page and in the project summary.

**Would a NASA or JPL researcher challenge any reasoning?**

Yes, and the first question would be about Bz, not about the statistics. The second
would be whether a "false alarm" at Kp < 3 is a detector error or a real solar wind
structure that did not couple. Neither question currently has an answer in the repo.


---

## Addendum: what has since been addressed

This review was written before the held-out and tolerance work. Status of each
finding as of the current commit.

| # | Issue | Status |
| --- | --- | --- |
| 1 | Unmatched operating points | **Addressed.** Quantified in RESULTS.md 4.6, reproduced interactively on the page via matched alert budget, and controlled in 4.7 |
| 2 | Base-rate-shift mechanism unsupported | **Addressed.** Demoted to an open hypothesis with the correlation reported, on the page and in 5.1 |
| 3 | Autocorrelation ignored | **Partly addressed.** Effective sample size is now stated in 2.1 and on the page. No interval in the document is yet recomputed on the effective N |
| 4 | No held-out evaluation | **Addressed.** Leave-one-storm-out in RESULTS.md 4.7 via `scripts/validate_heldout.py` |
| 5 | Bz absent from the feature set | **Partly addressed.** The loader now requests OMNI2 variable 16 and the parser handles it, but the committed windows predate the change, so no published result uses Bz yet. Refetching is the single remaining change most likely to alter conclusions |
| 6 | No multiple-comparison control | **Not addressed.** Still no correction and no pre-specified endpoint |
| 7 | Catalogue asymmetry understated | **Addressed.** The counter-argument that relied on the Gannon window is explicitly withdrawn in 5.4 |

The most important result from the follow-up work was not predicted here:
**held-out scoring is slightly better than in-sample**, at precision 0.327 against
0.301 at matched budget. Pooling quiet rows across four windows appears to give a
more stable reference than fitting on a contemporaneous one, which partially
contradicts the per-window rationale in Section 3 of RESULTS.md.
