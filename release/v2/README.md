# UST Course Vibe Match v2

UST Course Vibe Match helps HKUST students shortlist Common Core courses using course areas, assessment preferences and review-based learning experience signals.

## Run the app

Download [UST-Course-Vibe-Match-v2.html](UST-Course-Vibe-Match-v2.html) using GitHub’s download button, then open the saved file in a browser. The course data and JavaScript are embedded in the file, so it runs offline.

## How the ranking works

1. **Filter by Common Core area.** A course passes if it belongs to any selected area. With no area selected, the app displays the full catalogue.
2. **Calculate the assessment match.** For each of nine assessment types, choose **Yes**, **No** or **Don’t care**. The ranker divides the number of matches by the number of selected items with a known course value. It skips Don’t care and unknown values. A course with zero comparable items has no assessment score and appears after scored courses. **Bingo** appears when every comparable item matches.
3. **Resolve ties.** Optional preferences for memorization, assessment difficulty and workload each earn +1 for the same level, 0 for adjacent levels and −1 for opposite levels. An unset preference or unknown level contributes 0. The app also adds +1 each for lenient grading and clear teaching when those labels are present. The total experience score breaks ties in the assessment match. Course code breaks any remaining ties.

For example, choose **No** for Midterm exam and Final exam and **Yes** for Project. CENG1800 matches all three choices in the v2 snapshot, so its card shows **3/3 (100%)**. HUMA3810 matches only the midterm choice, so it shows **1/3 (33%)**. The app displays the full filtered list.

The nine assessment types are midterm, final, quiz, assignment, essay, project, attendance, reading and presentation. The three adjustable experience controls use the following levels.

| Control | Levels |
| --- | --- |
| Memorization | Weak, Moderate, Strong |
| Preferred difficulty | Easy, Moderate, Hard |
| Acceptable workload | Light, Moderate, Heavy |

## Data and preparation

- **Catalogue.** The snapshot contains 280 different course codes from seven Fall and Spring terms, from Fall 2023 through Fall 2026. The app pools the area codes associated with a course across terms and cohorts. It normalizes S, T and S&T to S/T, and Arts and A to A, producing 18 area labels.
- **Assessment checkboxes.** The project cleaned 3,070 USTSPACE reviews across 150 course codes. Of those, 2,998 reviews matched 138 courses in this release. For each course and assessment type, the value is **Yes** when checked responses outnumber unchecked responses and **No** otherwise, including a tie. The other 142 courses have **Unknown** for all nine types.
- **Learning experience.** The build rolls 415 course–instructor profiles up to course level. For each dimension, the supporting review count weights the vote across instructor labels. Five dimensions appear in v2.

| Experience dimension | Courses with a known label |
| --- | ---: |
| Workload | 132 |
| Grading leniency | 128 |
| Teaching clarity | 124 |
| Assessment difficulty | 110 |
| Memorization | 108 |

See the [data and labeling methodology](../../docs/METHODOLOGY.md) for the upstream cleaning, LLM annotation and validation steps.

## Interpretation and release files

Assessment values summarize past review checkboxes. An unchecked box provides limited evidence that the assessment was absent. Assessment formats and learning experiences can vary by term and instructor, and eligibility depends on the student’s curriculum and the current offerings. Check the official course list and current syllabus before making an enrolment decision.

This folder contains the generated HTML and its release notes. The original build template and generator are separate from this snapshot. The app can be used directly from the included HTML.
