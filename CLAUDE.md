# Space Weather Anomaly Detection

## Project

Anomaly detection on NOAA and NASA OMNIWeb solar wind and geomagnetic time series data. Portfolio project demonstrating end-to-end ML pipeline from data ingestion through deployment.

## Architecture

- `src/data_loader.py`: Data loaders for NOAA SWPC (real-time) and NASA OMNIWeb (historical)
- `src/preprocessing.py`: Feature engineering and cleaning
- `src/models.py`: Anomaly detection models
- `src/evaluation.py`: Metrics and validation against the storm catalog
  (SCAFFOLDED, NOT IMPLEMENTED, see "Working agreement" below)
- `notebooks/`: Exploratory analysis and results
- `scripts/`: Demonstration and utility scripts
- `data/raw/`: Cached raw data (gitignored)

## Conventions

- All datetimes are UTC and timezone-aware
- Column naming: 'speed', 'density', 'temperature', 'imf_magnitude', 'Kp'
- NOAA fill values (-9999) and OMNIWeb fill values (999.9, 9999999) are converted to NaN on load
- Cache files stored in data/raw/, one hour default TTL for real-time data

## Known Storm Events for Validation

Ground truth lives in `data/storm_catalog.csv`: load it with
`src.evaluation.load_storm_catalog()`, do not hard-code event dates in
notebooks or tests. The `onset_utc` column is intentionally blank; see
ROADMAP Milestone 2.

Events: Bastille Day (2000-07-15, Kp 9), Halloween (2003-10-29, Kp 9),
St. Patrick's Day (2015-03-17, Kp 8), September 2017 (2017-09-08, Kp 8),
Gannon (2024-05-10, Kp 9).

## Style

- Type hints on all functions
- Docstrings explaining purpose, args, returns, and any physics/data-source context
- No hidden state or global variables in loaders
- Prefer explicit errors over silent failures


## Working agreement (READ THIS BEFORE WRITING CODE)

This is a learning project. The owner is building it to be able to defend
every design decision in an interview. **Handing over finished implementations
defeats its purpose.**

Default behaviour for any new analysis or modelling code:

1. Write the signature, type hints, and a docstring that explains the *why*, 
   including the statistical or physical reasoning and the traps involved.
2. Write failing tests that fully specify the behaviour, including edge cases
   and the values expected.
3. Leave the body as `raise NotImplementedError` with an `IMPLEMENT NOTES:`
   block naming the tricky parts.
4. Stop. Do not implement it.

Verify the spec is satisfiable before handing it over (write a throwaway
reference implementation, confirm the tests pass, then discard it). Shipping a
scaffold with a self-contradictory spec wastes the owner's time.

**Exceptions, just build these, they carry no learning value:** CI workflows,
packaging and config, dependency management, boilerplate plumbing, notebook
build scripts, docstring and README formatting, lint fixes.

If asked to "just write it," comply, but say once that it costs an interview
answer, and note which one.

## Reporting standards

- Never report accuracy on this data. The positive class is ~5%; a
  detect-nothing model scores 95%.
- Every recall figure must be quoted with its tolerance window. Recall without
  tolerance is not interpretable and inflates for free as tolerance grows.
- Report event-wise and point-wise metrics together, never whichever is more
  flattering.
- Prefer NaN over 0.0 for undefined metrics (zero events evaluated is an
  invalid experiment, not a failed detector).
- A model that loses to the statistical baseline gets reported as losing.

## Writing style (match the owner's voice)

All prose in this repository, including README, RESULTS, docstrings longer than
a line, and commit bodies, follows the owner's established technical-report
voice. The rules below are derived from his own writing. Match them.

**Lead with the context frame, not the subject.** The default sentence shape is
`[prepositional or participial frame], [subject] [verb] [claim]`. Examples of
the frame: "From the aggregate table, ...", "Considering the spread within each
column, ...", "With respect to the quiet label, ...", "Regarding the
contamination parameter, ...". The frame tells the reader which lens to apply
before the finding lands.

**Run the same four-beat scaffold in every metric subsection.** In order:
(1) define the metric in plain terms, (2) state what was manipulated and how it
was measured, (3) present the table or figure, (4) interpret the result and
where possible name the mechanism behind it. Close by pointing to where the
detailed evidence lives.

**Keep observation and interpretation in separate sentences.** State what
happened in a flat, factual sentence. Put the explanation in the next sentence,
and carry all the hedging there. Do not blend the two.

**Be exact on measurements, hedged on causes.** Measured quantities are
reported precisely: "precision 0.394", "1,172 of 3,696 samples", "54.0% of its
hours". Causal claims are softened: "may be", "appears to", "can be attributed
to", "suggests that", "would".

**Use transitions to carry the logic.** However, On the other hand, Conversely,
Similarly, Consequently, Therefore, Thus, In contrast, Ultimately. The document
compares configurations, so comparison and consequence markers do real work.

**Signpost to the evidence in a consistent form.** Repeat the same construction
every time, for example: "Detailed results are provided in
`reports/detector_comparison_per_window.csv`." Raw evidence stays reachable
without cluttering the body.

**Two failure modes to check before finishing.** First, verify every sentence
has a subject and a main verb. Front-loading a long context frame sometimes
leaves a noun phrase with no clause attached. Second, break up chains of
`of` / `for` / `between` prepositional phrases, particularly in interpretation
sentences, where shorter constructions read better.

**No em dashes or en dashes anywhere**, in prose, code comments, plot titles, or
generated reports. Use a comma, a colon, or a new sentence.
