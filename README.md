# UST Course Vibe Match

COMP 1945 group project. We turn ~3,000 ust.space course reviews (2023–2026, 150 courses) into structured
**course + instructor profiles** along 13 dimensions (topic, memorization, analytical demand, background
needed, workload, reading, writing, group work, participation, teaching clarity, assessment difficulty,
grading leniency, lecture recording), so that students can later be matched to courses that fit their
preferences.

> The full design rationale, decision log and all numbers are in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md)
> (written in Chinese). The labeling rules are in [`docs/labeling_guide.md`](docs/labeling_guide.md).
> Everything else in the repo is in English.

## Design: two tracks

The project deliberately runs **two tracks** over the same reviews. They answer different questions.

### Track 1 — LLM extraction (produces the data we use)

An LLM reads every review (all four comment columns) and labels the 12 review-level dimensions following
the labeling guide. Every label other than `unknown` must come with a verbatim quote from the review, and a
validator rejects any quote that is not in the text. "Not mentioned" is always `unknown`, never `low`/`none`.

1. **Preprocess** (`src/preprocess.py`): strip HTML, drop reviewer identity columns, record the instructors
   listed on each review, and mark missing instructors.
2. **Label** all 3,070 reviews (batches of LLM subagents + a completion pass), merge with exactly one label
   per review (`src/merge_batches.py`), validate (`src/build_labels.py`).
3. **Review rounds**: corrections are never edits to the original labels; each round is a separate override
   file in `cleaned/review/`, applied in the fixed order `OVERRIDE_ORDER` in `src/merge_batches.py`.
4. **Rule cross-check** (`src/rule_check.py`): keyword rules re-extract the four factual dimensions
   (group work, participation, recording, writing); every rule/LLM disagreement is adjudicated by hand.
5. **Aggregate** (`src/aggregate.py`) into course and instructor profiles. For teacher-specific labels, use
   explicit attribution in the evidence, followed by a confirmed review instructor or a sole lecturer in
   the same semester. Retain unresolved evidence under its original course and semester.

### Track 2 — classic course models (comparison experiment only)

Question: *how far can the models taught in class reproduce the LLM's judgments?*
BoW and averaged pretrained GloVe vectors × Perceptron / KNN / MLP, plus a majority baseline, trained on the
LLM labels with GroupKFold by course (`src/classic_models.py`). Metric: macro-F1. The results feed the
report's evaluation section; **they are not used in the profiles**. Note that this measures agreement with
the LLM, not with the truth — that is what the human spot check is for.

### Human spot check (validates Track 1)

Two teammates independently label a stratified sample of 80 reviews; we compute Cohen's kappa between them
and against the LLM. See [`spot_check/README.md`](spot_check/README.md).

## Status (2026-11-25)

| Step | Status | Main output |
|---|---|---|
| Preprocess | done | `cleaned/reviews_clean.csv` |
| LLM labeling + 3 review rounds | done, 0 validation errors | `cleaned/review_labels.csv` |
| Rule cross-check | done (agreement 70–94%; 3 LLM errors found and fixed) | `cleaned/review/rule_*` |
| Course + instructor profiles | 305 individual profiles and 129 unresolved course–semester profiles | `cleaned/course_profiles.csv` |
| Classic model experiment | done (best: BoW + Perceptron, macro-F1 ≈ 0.39 / 0.43) | `cleaned/experiments/` |
| Human spot check | **waiting for two annotators** | `spot_check/` |
| Recommender (methods A / B / C) | local prototype; 15-course Spring 2026 / CC25 pool frozen | `src/demo.py`, `recommendation/pool.json` |
| Recommendation evaluation | frozen protocol and blind review packets ready; human judgments pending | `src/evaluate.py`, `recommendation/study_protocol.json` |

Run the prototype from the repository root with Python 3.11 or newer:

```bash
python src/demo.py --pool recommendation/pool.json --version C
```

Open http://127.0.0.1:8000. C is the preview method. See [the recommender guide](docs/RECOMMENDATION.md)
or the [中文版运行与评分说明](docs/RECOMMENDATION.zh-CN.md) for the candidate data, scoring rules, and evaluation workflow.

Class balance: the Perceptron uses class weighting, and KNN and MLP use oversampling (`knn_bal`, `mlp_bal`).
The balanced MLP holds out original reviews for early stopping before oversampling its training subset.
Its BoW results are 0.34 and 0.39 across the two tasks. BoW + Perceptron remains the highest on average.
See METHODOLOGY section 4, step 4.

## ⚠️ Spot check: do not open the answer file

`spot_check/llm_labels_HIDDEN.csv` contains the LLM labels for the spot-check sample. It is committed so the
scoring script works, but **if you are one of the two annotators, do not open it, search it, or diff it
until your sheet is finished.** Looking at it makes the agreement numbers meaningless.

## Repository layout

```
docs/
  METHODOLOGY.md          design, decisions, results (Chinese)
  labeling_guide.md       labeling rules, analytical decision procedure, review rounds
src/
  preprocess.py           raw CSV -> cleaned/reviews_clean.csv, review_instructor_map.csv
  make_batches.py         split reviews into labeling batches
  build_labels.py         validate labels; build review_labels.{csv,jsonl}
  merge_batches.py        merge batch outputs + override files (OVERRIDE_ORDER)
  find_analytical_gaps.py candidates for the analytical re-check (review round 2)
  rule_check.py           keyword-rule cross-check (step 3)
  aggregate.py            course + instructor profiles, conflict list
  build_semester_instructors.py  extract lecture rosters from the pinned schedule archive
  classic_models.py       Track 2 experiment (step 4)
  make_spot_check.py      build the spot-check sample
  score_spot_check.py     score the spot check
cleaned/
  reviews_clean.csv            cleaned reviews (no reviewer identity)
  review_labels.csv / .jsonl   final review-level labels with evidence
  review_instructor_labels.csv one row per (review, instructor)
  course_profiles.csv          individual instructor profiles and unresolved course–semester evidence
  course_topics.csv            course-level topic categories and keywords
  conflicts.csv                same-semester disagreements (data-quality report)
  rule_labels.csv              keyword-rule labels
  batches/input, output        labeling batches and raw LLM outputs
  review/                      override files, adjudications, instructor fill/alias tables
  experiments/                 Track 2 results and out-of-fold predictions
spot_check/                    annotation sheets and instructions
```

## Reproducing

Python 3.11 with pandas 3.1.1, numpy 2.4.6, scikit-learn 1.9.1, gensim 4.4.0 (`requirements.txt`).

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cd src
python merge_batches.py                                   # merge labels + overrides
python build_labels.py build review_labels ../cleaned/batches/merged_labels.json
python rule_check.py                                      # step 3
python aggregate.py                                       # profiles
python classic_models.py                                  # step 4 (needs GloVe, see below)
```

- **Raw data is not in the repo.** `reviews_2023-2026.csv` contains reviewer usernames, so it is shared
  privately. Put it in the project root only if you need to re-run `preprocess.py`; everything downstream
  starts from `cleaned/reviews_clean.csv`, which is committed.
- **GloVe**: `classic_models.py` expects
  `~/gensim-data/glove-wiki-gigaword-100/glove-wiki-gigaword-100.gz`
  (download from the gensim-data GitHub release `glove-wiki-gigaword-100`).

## Handing over

If you (or your agent) take over labeling or corrections:
- Follow `docs/labeling_guide.md`; add new judgment rules there before applying them.
- Never edit `cleaned/batches/output` or `cleaned/review_labels.*` by hand. Write a new
  `cleaned/review/overrides_<name>.json`, append it to `OVERRIDE_ORDER`, and rebuild; the merge must end with
  0 errors and full coverage.
- Record decisions in the decision log of `docs/METHODOLOGY.md`.
