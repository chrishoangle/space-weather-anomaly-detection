# Roadmap

Milestones are **self-contained and resumable**: each one leaves the repo in a
coherent, presentable state.

**Status: Milestones 0, 1, 3, 4, 5, 6 are complete.** The two open items are
Milestone 2 (storm onset times, which unlock lead-time metrics) and evaluating
all five storm windows instead of one, both listed under "Open work" below.

`[AI]` = generated infrastructure, no learning value, don't hand-write it.
`[ME]` = implement it yourself. These are the parts you will be asked about.

---

## Milestone 0, Repo hygiene `[AI]` ✅ done

- [x] Commit `notebooks/02_historical_analysis.ipynb` (README linked to a file
      that was never pushed, a 404 for anyone browsing the repo)
- [x] Split `requirements.txt` / `requirements-dev.txt`, add the missing
      `nbformat` + `nbclient` that `scripts/_build_baseline_notebook.py`
      imports (the documented build command could not have worked on a clean
      clone)
- [x] `pyproject.toml` with pytest + ruff config
- [x] GitHub Actions CI: ruff lint + pytest on Python 3.11/3.12/3.13
- [x] `data/storm_catalog.csv`: ground truth moved out of `CLAUDE.md` prose
      into a real data file

## Milestone 1, Evaluation module ✅ done

`src/evaluation.py` is scaffolded: signatures, docstrings, and design
rationale, with every body raising `NotImplementedError`.
`tests/test_evaluation.py` holds **46 failing tests that are the spec.**

```bash
pytest tests/test_evaluation.py -k window -v    # start here, 5 tests
```

Work the blocks in the order listed in the test file's docstring. Each block
is independently completable.

**Why this is Milestone 1 and not the Isolation Forest.** Right now your repo
reports no precision or recall anywhere a reader can see, the March 2015
evaluation is prose inside a notebook ("the detector fires strongly through
03-16 to 03-17"). Until there is a number, adding a second model is
unfalsifiable: you'd have no way to claim it is better. Build the ruler before
the thing you measure.

**The concept to actually absorb here**: this is the interview answer:
point-wise metrics are the wrong default for time-series anomaly detection. A
detector that fires on the single hour a shock arrives scores 4% point-wise
recall and is an operational success. One that flags every sample scores
perfect event recall and is worthless. The module reports both families plus a
quiet-time false-alarm rate for exactly this reason. `accuracy` is deliberately
absent, with a ~5% positive class, a detect-nothing model scores 95%.

Definition of done: 46 green, and you can explain event vs. point-wise recall
without notes.

## Milestone 2, Storm catalog onset times `[ME]` ← OPEN, highest value

`data/storm_catalog.csv` has an `onset_utc` column that is **deliberately
blank**. Fill it from NOAA SWPC event summaries and the NOAA/NCEI Kp record.

This is small but it is the most genuinely *data-science* task in the project:
you have to decide what "onset" means. Shock arrival at L1? Sudden storm
commencement at ground? First Kp≥5 hour? These differ by hours and the choice
changes every lead-time number you will report. Write the decision down in the
CSV header comment with your sources.

Once populated, `lead_time_summary` stops returning all-NaN and you have the
metric that actually matters operationally: **how much warning did we get?**

Definition of done: onset populated with a cited source per event, and a
paragraph in `RESULTS.md` defending your definition.

## Milestone 3, Isolation Forest ✅ done

Add `IsolationForestDetector` to `src/models.py`, matching the existing
`StatisticalProcessControlDetector` interface (`fit` / `predict` /
`fit_predict`, returning an `anomaly` column) so `evaluate_detector` accepts
both with no special-casing.

Ask me to scaffold it the same way, signatures, docstrings, failing tests, 
then implement.

Things that will bite you, and are worth hitting yourself:

- **Contamination is not optional.** `IsolationForest(contamination=...)` is
  effectively "what fraction of data is anomalous," and it silently determines
  your operating point. Setting it to the true storm rate is leaking test
  labels into the model. Justify whatever you pick.
- **NaN handling.** `sklearn` will refuse NaN. Your OMNI2 data has gaps you
  chose not to interpolate (correctly, see `interpolate_short_gaps`). Dropping
  those rows changes your index, so evaluation must still align.
- **Fit on quiet data or everything?** The SPC detector fits on a quiet window.
  Isolation Forest is unsupervised and conventionally fits on all data. That's
  not an apples-to-apples comparison. Decide and defend.

Definition of done: a table in `RESULTS.md` comparing SPC vs. Isolation Forest
on identical features, identical tolerance, both metric families, **including
if Isolation Forest loses.** A portfolio project where the fancy model
honestly underperforms the simple baseline, and you explain why, is worth more
than one where it conveniently wins.

## Milestone 4, Automated daily detection ✅ done

The automation that makes reviewers look twice: a scheduled GitHub Action that
runs without you.

- `scripts/run_daily_detection.py`: fetch the last N days of NOAA real-time
  data, run the fitted detector, write `reports/latest.md` + `reports/latest.json`
- `.github/workflows/daily.yml`: `schedule: cron` daily, commits the report back
- README badge showing current space-weather status from the last run

Why this reads well: it proves you can ship something that operates unattended,
handles a flaky upstream API, and fails loudly instead of silently. That is the
gap between "did a Kaggle notebook" and "ran a pipeline."

Note the failure modes you must handle, because CI will find them: NOAA
endpoints go down, return partial rows, and occasionally serve stale
timestamps. The job must distinguish "no storm" from "no data."

## Milestone 5, Results write-up ✅ done

`RESULTS.md`: the single most undervalued file in a portfolio repo. Most
reviewers read the README, skim one notebook, and leave. A results document
with actual numbers, a figure, and honest limitations is what separates this
from the hundreds of repos that are three notebooks and a hopeful README.

Structure that works:

1. Question asked, in one sentence
2. Data and its limitations (OMNI2 gaps, Kp being 3-hourly binned, five-event
   catalog being far too small for confident precision estimates)
3. Method, briefly
4. Results table, both metric families, tolerance stated
5. **What didn't work and why**: this section is the credibility multiplier
6. What you would do with more time

## Milestone 6, Streamlit dashboard ✅ done

Lowest priority despite being the most visually satisfying. A dashboard on top
of unvalidated models is decoration; a dashboard on top of Milestones 1-5 is a
demo. Do it last.

---

## Deliberately out of scope

- **Deep learning / LSTM autoencoder.** With a five-event ground-truth catalog
  you cannot validate a model of that capacity, and a reviewer who knows the
  domain will ask about your validation set. Saying "I considered a sequence
  autoencoder and concluded the labelled data couldn't support it" is a
  stronger answer than shipping one.
- **Real-time alerting / paging.** Scope creep. The daily job is enough.

## Interview questions this project should let you answer

Track these, if a milestone doesn't move you toward answering one, reconsider it.

1. Why is accuracy the wrong metric here, and what did you use instead?
2. How did you define ground truth, and what are the limits of that definition?
3. Your simple baseline vs. your ML model, which won, and why?
4. What does your detector do when the upstream data source fails?
5. What is the operational cost of a false positive vs. a false negative in
   this domain, and how did that shape your threshold?

---

## Open work

Ordered by how much each would improve the project's credibility.

1. **Populate `onset_utc` in `data/storm_catalog.csv`** (Milestone 2 above).
   Until this exists there is no lead-time number, and lead time is what
   decides whether any of this has operational value. Requires deciding what
   "onset" means, shock arrival at L1, sudden storm commencement at ground,
   or first Kp≥5 hour, and citing a source per event.

2. ~~Evaluate all five storm windows.~~ ✅ done, all five are scored in
   `RESULTS.md`. This surfaced the next item.

3. **Replace the five-event catalog with a Kp≥5-derived event list.** Now the
   highest-value change. Event recall is saturated at 1.000 for every
   configuration, five famous storms at ±24 h tolerance is too easy a target
   to discriminate between models. A Kp≥5 threshold over two decades yields
   hundreds of events, which would both restore recall as a useful metric and
   fix the under-labelling that makes every precision figure a lower bound.

4. **Sweep the hit tolerance** (±6 h to ±48 h) and publish precision/recall as
   a curve, rather than quoting a single ±24 h operating point.

5. **Try Isolation Forest on engineered features**: rolling std, rate of
   change, dynamic pressure, which `src/preprocessing.py` already computes but
   the comparison does not use. Interaction structure is likelier there than in
   raw levels, and it is the fairest remaining test of the model class.
