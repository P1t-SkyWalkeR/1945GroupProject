# Recommendation prototype and evaluation

The study uses a frozen 15-course Spring 2026 / CC25 pool and four development and four test profiles. Method B adds workload and teaching clarity. Human review is pending.

## Run the preview

```bash
python src/demo.py --pool recommendation/pool.json --version C
```

Open http://127.0.0.1:8000. The form and evaluation use the same Python ranking function. The recommender commands use the Python standard library. Source links in the evidence panel require internet access and USTSPACE may ask for sign-in.

Try a topic with no hard conditions to see up to three results. Try requiring no final exam to see what happens when the available evidence cannot confirm any course meets that condition. To compare methods during development, start the demo with `--version A`, `B`, or `C`. The final demo can load `--selection <file>` after development evaluation.

## Candidate data

The study uses 15 CC25 courses from 2025–26 Spring (2530). This is a retrospective demonstration. The builder joins the seven-term Common Core snapshot to reviews by full course code, academic term, and instructor name after normalizing punctuation and case. It selects the scheduled instructor with the most matched reviews for each course and requires at least three. Reviews attributed to several instructors are excluded from this instructor-specific pool. The class presentation should state the candidate pool size and the review window.

Workload and teaching clarity use the most frequent known label for that offering. A tie or a leading conditional workload label stays unknown. Topic categories come from the repository's course topic table and apply to the full course code. Course and instructor details, term, counts, review IDs, evidence examples, and public syllabus links are retained. Cohort and archival version are recorded in the pool snapshot.

For soft preferences, affirmative checkboxes and explicit group-work labels can supply student-reported evidence. An unchecked box alone leaves the answer unknown. A required condition passes only after a matching assessment is verified and recorded in `recommendation/verified_assessments.json`. The preview uses official syllabuses for that verification. In the questionnaire, presentation means a required graded presentation, and group work means that working in a group is required.

To reproduce the frozen pool from the archived dataset, run the following in a checkout at `b5461c5`.
That commit contains the instructor-evidence export used for the study. A rebuild using the current
attribution data is a new candidate snapshot and should go through a separate freeze.

```bash
python src/build_recommendation_pool.py --archive /path/to/cc_courses_merged.json \
  --term 2530 --cohort CC25 --min-reviews 3 --limit 15 \
  --verified recommendation/verified_assessments.json --output /tmp/vibe-pool-check.json
cmp recommendation/pool.json /tmp/vibe-pool-check.json
```

## Scoring methods

| Version | Score |
| --- | --- |
| A | E |
| B | 0.60E + 0.30W + 0.10Q |
| C | 0.45E + 0.225W + 0.075Q + 0.25T |

All versions apply the same hard filter. E is the average match across expressed assessment preferences, using 1 for a match, 0 for a mismatch and 0.5 for unknown evidence. W applies a penalty only when observed workload exceeds the user's preferred maximum. Q is the teaching clarity score, with 0 for unclear, 0.5 for mixed, and 1 for clear. Unknown teaching clarity receives 0.5 and is flagged as missing evidence. Q is a shared preference in the ranking, with no additional survey question. T is cosine similarity between binary topic vectors. An unused preference contributes the declared neutral value of 0.5. Ties favor fewer missing active features, then course code. C inherits B's relative weights and gives 25% of its score to topic match.

## Human evaluation

The protocol records hashes for the candidate pool, preference profiles, review originals and ranking code, plus the three methods' weights. Each split has an evidence document, two blank rater sheets and an adjudication sheet. The evidence includes course information, syllabus links and the original review comments. Scores, ranks, method names and model labels are hidden from raters.

```bash
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json --protocol recommendation/study_protocol.json \
  prepare --split development --output /tmp/vibe-development
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json --protocol recommendation/study_protocol.json \
  prepare --split test --output /tmp/vibe-test
```

Two evaluators judge every course for every scenario. A third person resolves disagreements before seeing rankings. With 15 courses, each evaluator makes 60 judgments per split. Use the packet rubric and include an explanation for unresolved cases.

```bash
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json --protocol recommendation/study_protocol.json develop \
  --rater-a /tmp/vibe-development/judgments_a.csv --rater-b /tmp/vibe-development/judgments_b.csv \
  --judgments /tmp/vibe-development/judgments_adjudicated.csv \
  --selection /tmp/vibe-selection.json --output /tmp/vibe-development-results.json
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json --protocol recommendation/study_protocol.json test \
  --rater-a /tmp/vibe-test/judgments_a.csv --rater-b /tmp/vibe-test/judgments_b.csv \
  --judgments /tmp/vibe-test/judgments_adjudicated.csv \
  --selection /tmp/vibe-selection.json --output /tmp/vibe-test-results.json
```

The development command selects the highest mean Precision@3 among versions with zero confirmed hard violations. A tie favors the simpler version. The test command verifies the pool and profile hashes against that selection and reports each version on the same adjudicated judgments. The result identifies every missed suitable course and whether it was filtered or ranked below the top three. The separate 80-review label spot check still uses `src/score_spot_check.py`.
