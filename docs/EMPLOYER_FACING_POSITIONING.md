# Employer-facing positioning

Purpose: make the project read as what it actually is. The repositioning instinct in
the brief is correct. The specific sentence proposed for the hero is not supportable,
and this document explains what to use instead.

Audiences optimised for: data science, analytics, operations research, aerospace
systems, technical analysis. Not machine learning research.

---

## Important correction before anything else

The brief proposes that visitors should remember:

> "Complex models can fail under base-rate shift, and I built an evaluation
> framework that demonstrated why."

The second half is true. The first half is not demonstrated by this data.

Re-running the comparison across all five windows, the correlation between a
window's disturbed fraction and the Isolation Forest performance gap is
**Spearman r = -0.100, p = 0.87**. Three windows at nearly identical base rates
(35.1%, 35.5%, 36.7%) show gaps of -0.150, +0.067 and +0.131. The scatter at matched
base rate is as large as the Halloween effect being explained.

Base-rate shift is a sound hypothesis and a correct description of how unsupervised
isolation works. It is not a finding this dataset establishes. Putting it in the hero
as a demonstrated result places an unsupported causal claim at the top of the page,
and the aerospace and operations research readers are precisely the ones who will
test it.

**The good news: the honest version is a stronger pitch.** See the revised hero.

---

## What this project actually demonstrates

In order of how well the evidence supports them.

**1. Metric selection determines the conclusion in rare-event detection.** Certain,
and demonstrated three separate ways:

- Accuracy is useless at a 5% positive rate. A detector flagging nothing scores 95%.
- Recall alone ranks the *worst* configuration first. Isolation Forest fitted on
  quiet rows has the highest point-wise recall of anything tested (0.661) and
  achieves it by flagging 1,172 of 3,696 hours, about a third of every month, with a
  15.6% quiet-period false-alarm rate.
- Event recall saturates. All four configurations detect all five storms, so the
  headline metric carries zero discriminating information.

**2. Comparing detectors at unmatched operating points inflates apparent
differences.** Quantified on this project's own published result:

| Comparison | Mean precision gap | Paired t | Windows won |
| --- | --- | --- | --- |
| At default settings (as published) | +0.141 | p = 0.013 | 5 of 5 |
| At matched flag rate | +0.048 | p = 0.306 | 3 of 5 |

Roughly two thirds of the published effect is an operating-point artifact. This is
the single most transferable finding in the project and it currently appears nowhere
on the site.

**3. A quiet-period false-alarm rate catches over-firing that precision and recall
miss.** Demonstrated: it is the only metric in the set that cleanly exposes the
32%-of-the-month configuration.

**4. Autocorrelated time series carry far less information than their row count
suggests.** Measured: 3,610 hourly samples correspond to about 51 effectively
independent observations, an overstatement factor of roughly 71. Any error bar
computed on the nominal N is too narrow by about 8 times.

**5. An unattended monitor must distinguish "no signal" from "no data."** Built and
tested: the scheduled job returns an explicit unknown state when upstream is stale or
unreachable, and exits non-zero only for internal defects.

**6. Base-rate shift may degrade unsupervised detectors.** Hypothesis, not
demonstrated. State as such.

---

## One-sentence description per audience

**Data science hiring manager**

> I built an evaluation framework for rare-event anomaly detection, then used it to
> show that two thirds of my own headline result was an artifact of comparing models
> at different operating points.

**Operations research manager**

> I quantified the false-alarm cost of four detector configurations on a rare-event
> monitoring problem and showed that the apparent best choice depends entirely on the
> operating point, which is a threshold-selection decision rather than a modelling
> one.

**Aerospace systems engineer**

> I built a monitoring pipeline over NASA OMNI2 and NOAA SWPC telemetry that fails
> safe, reporting an explicit unknown state rather than a false all-clear when
> upstream data is stale, and validated detection performance against a catalogue of
> five major geomagnetic storms.

**Data engineering manager**

> I built a reproducible ingestion and evaluation pipeline with deterministic cache
> keys, committed source data so results reproduce offline, 108 tests, CI across
> three Python versions, and a scheduled job that publishes its own status.

---

## What employers should remember after 30 seconds

One sentence, and it should not be about space weather:

> **The metric you choose decides the answer. I built the framework that proves it,
> and it caught errors in my own work.**

Supporting facts, in priority order:

1. Recall alone would have ranked the worst detector first.
2. Two thirds of my own headline result turned out to be an operating-point artifact,
   which I found by re-testing it.
3. Accuracy would have scored a do-nothing detector at 95%.

Space weather should read as the substrate, not the subject.

---

## What employers should remember after 5 minutes

- The problem class is rare-event detection with imperfect ground truth, which covers
  fraud, predictive maintenance, intrusion detection, clinical monitoring and quality
  control.
- The evaluation framework reports event-wise and point-wise families together, plus
  a quiet-period false-alarm rate, and deliberately never reports accuracy.
- A simple statistical baseline held up against Isolation Forest, but the honest
  margin is small and not statistically significant at n = 5.
- The candidate re-examined his own result, found the confound, and published the
  corrected version.
- The limitations are stated and quantified rather than gestured at: five events,
  saturated recall, under-labelled catalogue, no held-out evaluation, no Bz in the
  feature set, autocorrelation reducing effective sample size by about 71 times.
- The pipeline is reproducible offline, tested, and runs unattended.

The thing to be remembered is judgment under uncertainty, not a model score.

---

## Revised hero section

Replace the current hero copy with the following. Keep the existing layout and
buttons.

**Kicker**

> EVALUATION METHODOLOGY · RARE-EVENT DETECTION

**Headline**

> When the metric picks the winner

**Subhead**

> I built an evaluation framework for rare-event anomaly detection on NASA and NOAA
> solar wind telemetry, then used it to dismantle my own headline result. Two thirds
> of the advantage I first reported turned out to be an artifact of comparing models
> at different operating points.

**Buttons**

> What the framework measures · Try the detector · Code on GitHub

Why this beats both the current version and the proposed one:

- The current hero ("The Sun breaks things") sells the domain. The domain is the
  least transferable part.
- The proposed hero asserts a mechanism the data does not support.
- This version leads with a methodological claim that is fully supported, and it
  front-loads self-correction, which is the trait the operations research and
  aerospace readers are actually screening for.

---

## Claim audit

### Overclaims to fix

| Location | Current wording | Problem | Replace with |
| --- | --- | --- | --- |
| Hero, page title, preview card | "The simple model won" | Survives only at unmatched operating points. At matched flag rate p = 0.31 and it wins 3 of 5. | "When the metric picks the winner" |
| Section "Why the simple model won" | "The reason is the interesting part... storm becomes normal, so it loses the ability to call it out" | Presented as demonstrated. Spearman r = -0.10, p = 0.87 across windows. | Reframe as a hypothesis with the correlation reported |
| RESULTS.md section 5.1 | "This performance gap can be attributed to the way each detector defines normal behaviour" | "Can be attributed to" reads as established causation from n = 1 | "is consistent with, though the five-window correlation does not support it" |
| Social preview card | "The simple model won." | Same as hero | Regenerate with the new headline |
| RESULTS.md section 5.4 | Counter-argument says even the quietest window favours the baseline | Gannon is one of the two windows Isolation Forest wins at matched flag rate | Withdraw or restate |
| Project summary, Results bullet 4 | "Identified base-rate shift as the mechanism" | Not identified, proposed | "Proposed base-rate shift as a candidate mechanism and reported that the five-window correlation does not support it" |

### Underclaims to strengthen

| Location | Current state | Evidence is stronger than the wording |
| --- | --- | --- |
| Nowhere on the site | The operating-point finding does not appear at all | This is the project's most transferable result and it is quantified: +0.141 to +0.048, p 0.013 to 0.306 |
| Limitations, item 5 | "Five events cannot support a tight interval" | True but weakly stated. The measured effective sample size is about 51 independent observations from 3,610 rows, a 71x overstatement |
| "What I built", automation bullet | "A scheduled job that scores live NOAA data" | Understates the design. It distinguishes no-storm from no-data, returns an explicit unknown on stale feeds, and exits non-zero only for internal defects. That is a fail-safe design decision, which is the single most relevant thing on the page to an aerospace reader |
| Interactive dashboard caption | "numbers match src/evaluation.py exactly" | Buried. 180 configuration combinations were verified equal between the browser and Python. That is a verification protocol, not a footnote |
| Test suite | Mentioned only in the README | 108 tests, CI on three Python versions, and the specification tests define behaviour before implementation |
| Reproducibility | Not mentioned on the page | Source data committed, deterministic cache keys, reproduces offline on any machine |

### Claims that are correctly stated

Leave these alone. Accuracy rejection, the recall-trap finding, event recall
saturation, the catalogue under-labelling disclosure, and the "this is not an
operational forecast" section are all accurate and appropriately hedged.

---

## Recommended narrative ordering

Current order leads with the domain and arrives at the method last. Invert it.

| # | Section | Change | Why |
| --- | --- | --- | --- |
| 1 | Hero: the methodological claim | Rewritten | Transferable idea first |
| 2 | **The problem: rare events break normal metrics** | **New** | Establishes the problem class before the domain. Accuracy at 95%, recall ranking the worst detector first |
| 3 | What I built: the evaluation framework | Moved up, reframed | The framework is the contribution, so it comes before results |
| 4 | The finding, and the confound I found in it | Merged, rewritten | Result plus self-correction in one place. This is the credibility moment |
| 5 | Try it yourself | Unchanged position | Interactive proof sits directly after the claim it supports |
| 6 | Operating under uncertainty | **New**, absorbs "Why the simple model won" | Base-rate shift as hypothesis, autocorrelation, no held-out set, missing Bz |
| 7 | The domain: what space weather is | **Moved down from position 2** | Context for the curious, not the lead |
| 8 | Why anyone cares | Moved down, kept | Concrete stakes, still worth having |
| 9 | What this is not | Unchanged | Limitations close the page |

The single highest-value structural change is moving "What is space weather" from
second to seventh. A recruiter who bounces at 30 seconds currently leaves having
learned about the magnetosphere.

---

## Strongest resume bullets supported by evidence

Every number here is recomputed and defensible.

- Built an evaluation framework for rare-event anomaly detection over 3,696 hours of
  NASA OMNI2 and NOAA SWPC telemetry, reporting event-wise and point-wise metrics
  alongside a quiet-period false-alarm rate, after determining that accuracy was
  invalid on a 5% positive class.
- Identified that two thirds of an initially reported performance difference was an
  artifact of comparing detectors at unmatched operating points, reducing the
  measured gap from 0.141 to 0.048 and the result from significant to not
  significant, then published the corrected finding.
- Demonstrated that point-wise recall alone ranks the weakest configuration first,
  since the highest-recall detector achieved 0.661 by flagging 32% of every month at
  a 15.6% quiet-period false-alarm rate.
- Measured the effective sample size of an autocorrelated hourly series at
  approximately 51 independent observations from 3,610 rows, a 71-fold overstatement,
  and revised the precision of all reported figures accordingly.
- Designed and deployed an unattended monitoring job that distinguishes no-signal
  from no-data, publishing an explicit unknown state rather than a false all-clear
  when upstream telemetry is stale.
- Built a reproducible pipeline with deterministic cache keys and committed source
  data, verified by 108 tests and CI across three Python versions.
- Verified a browser-side reimplementation of the evaluation logic against the Python
  reference across all 180 configuration combinations.

Do not use: any bullet claiming base-rate shift was demonstrated, or that the
statistical baseline beat Isolation Forest without the operating-point qualifier.

---

## Highest-impact copy changes

Ranked by effect per unit of effort.

| # | Change | Effort | Effect |
| --- | --- | --- | --- |
| 1 | Rewrite the hero per the section above | 15 min | Changes what every visitor remembers. Also removes the main overclaim |
| 2 | Add the operating-point confound to the finding section, with the before and after table | 45 min | Adds the most transferable result and converts a weakness into the credibility moment |
| 3 | Move "What is space weather" from second to seventh | 10 min | Recovers the first 30 seconds for the contribution |
| 4 | Reframe "Why the simple model won" as hypothesis, with the correlation reported | 30 min | Removes the second overclaim |
| 5 | Add the new section 2, "rare events break normal metrics" | 40 min | Establishes the problem class before the domain |
| 6 | Promote the fail-safe design of the monitoring job to its own callout | 20 min | Directly targets the aerospace and operations readers |
| 7 | Regenerate the preview card with the new headline | 10 min | Link previews currently carry the overclaim |
| 8 | Add effective sample size to the limitations list | 10 min | Converts a vague caveat into a measured one |

Items 1, 2 and 4 are not optional if the page is going to recruiters, because they
are the three places the site currently claims more than the data supports.
