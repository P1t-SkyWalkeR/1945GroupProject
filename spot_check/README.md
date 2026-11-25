# Human spot check of LLM labels

Purpose: measure how reliable the LLM labels are (report Section 6). Two people label the same 80 reviews
independently; we then compute agreement between the two people (Cohen's kappa) and between each person
and the LLM.

## What to do

1. Pick one workbook each, `sheet_annotator_A.xlsx` or `sheet_annotator_B.xlsx`. Open it in Excel or Google Sheets. The comment fields are stored as text.
2. For each row, read the four comment columns, then fill the 12 label columns using
   `docs/labeling_guide.md` (read the "General rules" section and the dimension definitions first).
3. Allowed values (anything else will be rejected by the scoring script):

   | Column | Values |
   |---|---|
   | memorization, analytical, reading, writing | low / medium / high / unknown |
   | background | beginner_friendly / background_helpful / background_dependent / unknown |
   | workload | low / medium / high / conditional_mixed / unknown |
   | group_work | none / optional / required / unknown |
   | participation | none / voluntary / required_or_graded / unknown |
   | teaching_clarity | clear / mixed / unclear / unknown |
   | assessment_difficulty | low / medium / high / varies / unknown |
   | grading_leniency | lenient / mixed / strict / unknown |
   | recording | yes / partial / no / unknown |

4. Most important rules:
   - **Not mentioned = `unknown`.** Never guess `none` or `low` from silence.
   - Use only the review text, not the star ratings.
   - Only label something if you can point to a sentence that supports it.
   - Teaching clarity, grading, participation and recording: only count statements about the instructor in
     `instructor_names`.
5. Use `notes` for anything you are unsure about.
6. **Do not open `llm_labels_HIDDEN.csv`** and do not discuss items with the other annotator until both
   sheets are finished. Expect about 2–3 hours for 80 reviews.
7. Save the finished workbooks and run the following from the repository root. If you already filled the CSV sheets, run the script without `--a` and `--b` to score those sheets.

   ```
   python src/score_spot_check.py --a spot_check/sheet_annotator_A.xlsx --b spot_check/sheet_annotator_B.xlsx
   ```

## Files

| File | Content |
|---|---|
| `sheet_annotator_A.xlsx`, `sheet_annotator_B.xlsx` | identical blank workbooks, with review text and drop-down label choices |
| `sheet_annotator_A.csv`, `sheet_annotator_B.csv` | CSV sheets for existing annotations and programmatic use |
| `llm_labels_HIDDEN.csv` | the LLM labels and evidence for the same items; used only by the scoring script |

Sample design: 80 reviews, stratified random sample (seed 1945) by annotation source (subagent / Codex)
and the course's main subject area, proportional to their share of the data (`src/make_spot_check.py`).

To draw a fresh sample, use `python src/make_spot_check.py --output-dir /path/to/new/sample`. The
generator refuses to overwrite existing sheets. Pass the new sample's A, B and answer files to
`score_spot_check.py` with `--a`, `--b` and `--answers`. Keep the review hashes intact. Scoring aligns
rows by hash and checks for duplicate, missing and extra reviews.
