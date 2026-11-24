# Labeling Guide

This guide defines how each review is labeled. It is the single source of truth for LLM extraction, rule cross-checks, and human spot checks. All three must follow it.

## General rules

1. **Unit.** One review = the four text columns together (`comment_content`, `comment_teaching`, `comment_grading`, `comment_workload`), plus the course code and course name as context.
2. **Not mentioned ≠ absent.** If the review does not address a dimension, label it `unknown`. Never infer `none` or `low` from silence.
3. **Text only.** Do not use the structured columns (`rating_*`, `has_*`). They are kept as separate features.
4. **Evidence required.** Every label other than `unknown` must include one short verbatim quote (≤ 30 words) from the review that supports it. If no quote supports a label, the label is `unknown`.
5. **Relative to HKUST undergraduate courses.** "High" means heavy compared with a typical HKUST course, not compared with no work at all.
6. **The reviewer's own experience counts.** "I had no background and got an A" is valid evidence for `background`.
7. **Mixed language.** Chinese or Cantonese text is labeled the same way. Quotes keep the original language.
8. **Hedged or sarcastic statements.** Label by the intended meaning. If the meaning is genuinely unclear, use `unknown`.
9. **Only the listed instructor.** For instructor-dependent dimensions (`teaching_clarity`, `grading_leniency`, `participation`, `recording`), use only evidence about the instructor the review is filed under. Ignore statements about other instructors ("Henry's notes are clearer than hers", "I skipped my section and went to Henry's"). Course-level dimensions (topic, memorization, analytical, background) may use any evidence about the course.
10. **Instructor named in text.** Also output `instructor_in_text`: the name of the instructor the reviewer says they were taught by, if stated (e.g. "Plato Tse was my professor"). Leave it empty if the reviewer only mentions other instructors. This is used to fill missing instructor fields.
11. **Hearsay counts.** Second-hand statements ("I heard the grading is harsh", "another forum says the workload is light") are valid evidence, labeled the same way as first-hand experience.
12. **Registered instructor is kept.** Reviews are attributed to the instructor in `instructor_names` as registered, even when the text suggests a different or aliased name. `instructor_in_text` is only used to fill a missing instructor field.

## Dimensions

### topic_keywords (review level)
3–6 short English keywords describing what the course content is about, e.g. `game theory`, `Chinese history`, `linear algebra`. Use only content stated or clearly implied by the review. Leave empty if the review says nothing about content.

### topic_categories (course level, assigned during aggregation)
Choose one or more from this fixed list:

| Code | Covers |
|---|---|
| `mathematics_statistics` | calculus, linear algebra, probability, statistics |
| `computing_programming` | programming, algorithms, data, AI |
| `physical_sciences` | physics, chemistry, earth and ocean science |
| `life_sciences_health` | biology, medicine, health, wellbeing |
| `engineering_technology` | engineering design, electronics, mechanics |
| `business_finance` | accounting, finance, marketing, operations |
| `economics` | micro, macro, econometrics |
| `management_entrepreneurship` | management, leadership, startups |
| `social_sciences` | psychology, sociology, political science, law |
| `history_culture` | history, cultural studies, anthropology |
| `philosophy_religion` | philosophy, ethics, religion |
| `language_literature_writing` | languages, literature, writing, communication |
| `arts_music_film` | art, music, film, design |
| `environment_sustainability` | environment, climate, sustainability |
| `interdisciplinary_other` | anything not covered above |

### memorization
How much the course requires remembering concepts, facts, terms, or large amounts of material.
- `high`: heavy memorization is explicitly required ("lots to memorize", "need to recite", "exam is pure memory", "many definitions to remember").
- `medium`: some memorization is needed alongside understanding ("need to remember key concepts and formulas").
- `low`: little or no memorization ("open book", "cheat sheet allowed and that's enough", "no need to memorize").
- `unknown`: not addressed.

### analytical
How much the course requires reasoning, analysis, calculation, proofs, or programming.
- `high`: substantial problem solving, proofs, heavy calculation, or non-trivial programming ("proofs are hard", "coding assignments take hours", "need strong logical thinking").
- `medium`: some calculation, analysis, or simple coding.
- `low`: mostly descriptive or conceptual content with little problem solving ("no math", "just concepts").
- `unknown`: not addressed.
- **A topic name alone is not evidence.** "Differentiation and integration", "Python programming", "optimization problems" describe content, not demand → `unknown`. Evidence must describe what students have to do or how hard the reasoning is ("proof-based questions", "you need to build a program to solve it", "requires a lot of logical thinking"). Time spent alone ("labs take 4 hours") is workload, not analytical difficulty.

**Decision procedure for `analytical`** (used in review round 2; apply in this order):

1. Does the quote say what **students** must do that involves calculation, proof, coding, or reasoning? If not → `unknown`. The following are *not* evidence (reason codes in brackets are used in `cleaned/review/analytical_supplement.jsonl`):
   - syllabus or topic lists, even if they contain "proofs" or "calculation of X" [`topic`]
   - formulas for computing the course grade ("two ways to calculate your score") [`grade_calc`]
   - a bare count or list of assessment components ("5 programming assignments", "36 MC, 1 calculation, 2 essays") [`count`]
   - derivations or proofs the **lecturer** shows in class, or proofs explicitly not tested [`teaching_style`, `optional_content`]
   - "hard / tricky questions", "difficult webwork", "the final was hard" without saying the difficulty is reasoning — this is `assessment_difficulty` [`assess`]
   - "need to understand the concepts deeply", "concepts are hard to grasp" [`understanding_only`]
   - total time spent ("each lab takes 4–5 hours", "3~5 hr per homework") [`workload`]
   - statements about prior knowledge [`background`], other courses or sections [`other_course`, `other_section`]
   - generic or template-like text not describing this course ("Encourage student participation… Assign regular coding exercises") [`generic`]
   - statements covering only one narrow part ("the exam does not involve calculus", "one test has no calculation") [`partial_scope`]
   - aural or perceptual skills (music "analytical listening") [`perceptual_skill`]
2. If it is evidence, choose the level:
   - `high`: the review says the reasoning itself is hard, heavy, or rigorous — "rigorous proofs", "olympiad level problems", "require deep thinking", "challenging to acquire the logical thinking you need", "it's hard and you have to think for a long time" on a single problem, an honors syllabus stating "strong emphasis on … logical reasoning skills".
   - `medium`: students calculate, prove, code, analyze, or apply concepts, with no statement that it is heavy — including *simple* coding and *simple* calculation ("2 coding assignments… should be simple", "just plugging in numbers", "exams test the application of formulas", "critical thinking is required").
   - `low`: the review says reasoning demand is minimal for the course as a whole — "no math", "0 maths, all theory", "only memorization can answer such questions, understanding and calculation do not work".
3. Time per *single problem* can support `high` only when combined with difficulty ("some are very tricky and might take you 1–2 hours"); total weekly time never does.

### background
Whether a student without prior knowledge can keep up.
- `beginner_friendly`: explicitly fine with no background ("no prior knowledge needed", "I'm new to X and could follow").
- `background_helpful`: possible without background, but it helps ("having taken DSE M2 helps", "easier if you know Python").
- `background_dependent`: hard to follow without background ("assumes you know calculus", "you will struggle without programming experience").
- `unknown`: not addressed.

### workload
The overall time and effort for the whole course.
- `low`: "light", "chill", "little workload", "easy to manage".
- `medium`: "manageable", "average", "reasonable", "moderate".
- `high`: "heavy", "time-consuming", "spent many hours every week".
- `conditional_mixed`: the workload depends on something, or varies sharply ("light until the final project, then very heavy", "depends on your group", "easy if you have background, heavy otherwise").
- `unknown`: not addressed.
- If the review states an overall level and only adds "you need more effort for a high grade", use the stated level, not `conditional_mixed`. Use `conditional_mixed` only when the review frames the overall workload itself as contingent (on groupmates, background, timing) without one overall level.

### reading
Amount and frequency of assigned reading, and whether it must be done carefully.
- `high`: regular weekly reading that must be done carefully, or long or dense readings.
- `medium`: some reading, occasionally required, or moderate amount.
- `low`: little reading, or reading is optional and can be skipped without consequence.
- `unknown`: not addressed. (Reading lecture slides only does not count as assigned reading; label `low` only if the review says something like "no readings, just slides".)

### writing
Number and length of essays, reports, reflections, or other written tasks.
- `high`: several essays or reports, or long ones (e.g. ≥ 2000 words in total, or described as "a lot of writing").
- `medium`: one or two moderate pieces (e.g. one short essay, a few short reflections).
- `low`: no writing tasks, or only trivial ones ("no essays", "just MCQ").
- `unknown`: not addressed.

### group_work
- `required`: group project or group presentation is part of assessment.
- `optional`: students may choose to work in groups or alone.
- `none`: explicitly all individual work ("no group project", "all individual").
- `unknown`: not addressed.

### participation
Requirements to speak in class: answering questions, discussion, cold calls, or participation marks.
- `required_or_graded`: speaking participation counts toward the grade, cold calling, or mandatory discussion or presentation in class.
- **iPRS / clicker / Mentimeter / Kahoot answers do not count as speaking**, even when graded. A review that only mentions graded iPRS is `unknown` for this dimension.
- `voluntary`: discussion exists but is optional and ungraded.
- `none`: explicitly no need to speak ("just sit and listen", "no participation marks").
- `unknown`: not addressed.

### teaching_clarity
Whether explanations, organization, and materials are easy to understand. Judge clarity, not friendliness or entertainment.
- `clear`: "explains clearly", "well organized", "slides are easy to follow".
- `mixed`: some parts clear and others not, or "average".
- `unclear`: "hard to follow", "messy slides", "confusing". **Reading the slides aloud counts as `unclear`** ("just reads from the PowerPoint"), unless the same review also says the explanations are clear, in which case use `mixed`.
- `unknown`: not addressed, or the review only comments on personality ("he is nice").

### assessment_difficulty
How hard the assignments, quizzes, and exams are to complete or score well on.
- `low`: "easy exams", "free marks", "straightforward assignments".
- `medium`: "fair", "reasonable", "some hard questions".
- `high`: "exams are very hard", "impossible to finish in time", "assignments are tough".
- `varies`: different assessments differ clearly ("midterm easy, final very hard", "homework easy but exams hard").
- `unknown`: not addressed.

### grading_leniency
Explicit statements about how strict the grading is. Do not infer from the reviewer's own grade alone. "I got an A" is not evidence by itself, but "I got an A without much effort, generous grading" is.
- `lenient`: "generous grading", "lenient", "curve is nice", "easy to get A".
- `mixed`: "fair", "average", or conflicting statements within the review.
- `strict`: "harsh grading", "strict", "very few As", "deducts marks for small mistakes".
- `unknown`: not addressed.

### recording
Whether lecture recordings are available for review.
- `yes`: "lectures are recorded", "videos uploaded", "Panopto available".
- `partial`: only some lectures are recorded, recordings are delayed or of poor quality, or only slides with voice-over for some topics.
- `no`: "no recording", "not recorded".
- `unknown`: not addressed.

## Output format (per review)

```json
{
  "hash": "<review hash>",
  "instructor_in_text": "<name or null>",
  "topic_keywords": ["...", "..."],
  "memorization":          {"label": "high",    "evidence": "..."},
  "analytical":            {"label": "unknown", "evidence": null},
  "background":            {"label": "...",     "evidence": "..."},
  "workload":              {"label": "...",     "evidence": "..."},
  "reading":               {"label": "...",     "evidence": "..."},
  "writing":               {"label": "...",     "evidence": "..."},
  "group_work":            {"label": "...",     "evidence": "..."},
  "participation":         {"label": "...",     "evidence": "..."},
  "teaching_clarity":      {"label": "...",     "evidence": "..."},
  "assessment_difficulty": {"label": "...",     "evidence": "..."},
  "grading_leniency":      {"label": "...",     "evidence": "..."},
  "recording":             {"label": "...",     "evidence": "..."}
}
```

## Review rounds and override files

Labels were produced in batches and then corrected in review rounds. Corrections never edit the original label files; they are stored as override files in `cleaned/review/` and applied by `src/merge_batches.py` in the fixed order of `OVERRIDE_ORDER` (later files win). Format: `{hash: {dimension: [label, quote] | null}}`, where `null` means `unknown`. The merge refuses to run if an `overrides_*.json` file is not listed in `OVERRIDE_ORDER`.

| Order | File | What it does |
|---|---|---|
| 1 | `overrides_codex_strict.json` | Round 1. Strict re-review of Codex labels: analytical topic-only evidence → unknown; `conditional_mixed` workload → stated level; hearsay relabels. |
| 2 | `overrides_codex_analytical_r2.json` | Round 2. Codex analytical labels checked against the decision procedure above (43 → unknown, 11 → medium). |
| 3 | `overrides_subagent_analytical.json` | Round 2. Subagent reviews with analytical = unknown but containing demand keywords (`src/find_analytical_gaps.py`, 413 candidates) were re-read; 125 received a label. Every decision, including the 288 left unknown, is recorded with a reason code in `analytical_supplement.jsonl`. |
| 4 | `overrides_rulecheck.json` | Round 3. LLM errors found by the keyword-rule cross-check (`src/rule_check.py`); every rule/LLM disagreement is adjudicated in `rule_adjudication.csv`. |

`pending_decisions.json` records items resolved by the user (rule name → hashes); the merge clears their pending flag.

To add a new round: write a new `overrides_<name>.json`, append it to `OVERRIDE_ORDER`, re-run `python src/merge_batches.py` and `python src/build_labels.py build review_labels cleaned/batches/merged_labels.json`. Both must finish with 0 errors and full coverage.

## Conflict definition (used after labeling)

Within the same (semester, course, instructor), a dimension is in **conflict** when ≥ 2 reviews have different non-`unknown` labels.
- **Adjacent conflict:** neighboring values on an ordinal scale (low vs medium, clear vs mixed).
- **Opposite conflict:** non-neighboring values (low vs high, lenient vs strict, none vs required).

Conflicts are reported for joint review and are **not** resolved automatically.
