# Recommendation prototype and evaluation

The local prototype is ready to try. The candidate pool, preference profiles, and method configuration are a draft pending team confirmation. No human recommendation metrics have been collected.

## Run the preview

```bash
python src/demo.py --pool recommendation/preview_pool.json --version C
```

Open http://127.0.0.1:8000. The form and evaluation use the same Python ranking function. The recommender commands use the Python standard library. Source links in the evidence panel require internet access and USTSPACE may ask for sign-in.

Try a topic with no hard conditions to see up to three results. Try requiring no final exam to see what happens when the available evidence cannot confirm any course meets that condition. To compare methods during development, start the demo with `--version A`, `B`, or `C`. The final demo can load `--selection <file>` after development evaluation.

## Candidate data

The preview uses 15 CC25 courses from 2025–26 Spring (2530). This is a retrospective demonstration. The builder joins the seven-term Common Core snapshot to reviews by full course code, academic term, and instructor name after normalizing punctuation and case. It selects the scheduled instructor with the most matched reviews for each course and requires at least three in the preview. Reviews attributed to several instructors are excluded from this instructor-specific pool. The class presentation should state the candidate pool size and the review window.

Workload and optional teaching clarity use the most frequent known label for that offering. A tie or a leading conditional workload label stays unknown. Topic categories come from the repository's course topic table and apply to the full course code. Course and instructor details, term, counts, review IDs, evidence examples, and public syllabus links are retained. Cohort and archival version are recorded in the pool snapshot.

For soft preferences, affirmative checkboxes and explicit group-work labels can supply student-reported evidence. An unchecked box alone leaves the answer unknown. A required condition passes only after a matching assessment is verified and recorded in `recommendation/verified_assessments.json`. The preview uses official syllabuses for that verification. In the questionnaire, presentation means a required graded presentation, and group work means that working in a group is required.

Rebuild from the archived dataset after approving the scope:

```bash
python src/build_recommendation_pool.py --archive /path/to/cc_courses_merged.json \
  --term 2530 --cohort CC25 --min-reviews 3 --limit 15 \
  --verified recommendation/verified_assessments.json --output recommendation/pool.json
```

## Scoring methods

| Version | Score |
| --- | --- |
| A | E |
| B | 0.60E + 0.40W |
| C | 0.45E + 0.30W + 0.25T |

All versions apply the same hard filter. E is the average match across expressed assessment preferences, using 1 for a match, 0 for a mismatch and 0.5 for unknown evidence. W applies a penalty only when observed workload exceeds the user's preferred maximum. T is cosine similarity between binary topic vectors. An unused preference contributes the declared neutral value of 0.5. Ties favor fewer missing active features, then course code.

The repository methodology describes a teaching clarity variant. The optional `--include-teaching` flag assigns B a 0.10 teaching weight and a 0.30 workload weight. C then uses 0.075 for teaching and 0.225 for workload. These are proposed weights for that variant. Choose the setup before development scoring and keep it fixed for the test.

## Human evaluation

Confirm the pool and the four development and four held-out scenarios in `recommendation/profiles.json`. Generate one packet per split. Each packet has an evidence document, two blank rater sheets and an adjudication sheet. The packets omit scores, ranks and method names.

```bash
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json \
  prepare --split development --output /tmp/vibe-development
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json \
  prepare --split test --output /tmp/vibe-test
```

Two evaluators judge every course for every scenario. A third person resolves disagreements before seeing rankings. With 15 courses, each evaluator makes 60 judgments per split. Use the packet rubric and include an explanation for unresolved cases.

```bash
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json develop \
  --rater-a /tmp/vibe-development/judgments_a.csv --rater-b /tmp/vibe-development/judgments_b.csv \
  --judgments /tmp/vibe-development/judgments_adjudicated.csv \
  --selection /tmp/vibe-selection.json --output /tmp/vibe-development-results.json
python src/evaluate.py --pool recommendation/pool.json --profiles recommendation/profiles.json test \
  --rater-a /tmp/vibe-test/judgments_a.csv --rater-b /tmp/vibe-test/judgments_b.csv \
  --judgments /tmp/vibe-test/judgments_adjudicated.csv \
  --selection /tmp/vibe-selection.json --output /tmp/vibe-test-results.json
```

The development command selects the highest mean Precision@3 among versions with zero confirmed hard violations. A tie favors the simpler version. The test command verifies the pool and profile hashes against that selection and reports each version on the same adjudicated judgments. The result identifies every missed suitable course and whether it was filtered or ranked below the top three. The separate 80-review label spot check still uses `src/score_spot_check.py`.
