"""Aggregate review-level labels into course + instructor profiles and list conflicts.

Inputs
  cleaned/reviews_clean.csv, cleaned/review_instructor_map.csv, cleaned/review_labels.csv
  cleaned/course_topics.csv                      course-level topic categories and keywords
  cleaned/review/instructor_fill.csv             instructor_in_text -> instructor, for reviews with no instructor
  cleaned/review/instructor_name_variants.csv    optional; variant -> canonical name (applied only if the file exists)

Outputs
  cleaned/review_instructor_labels.csv   one row per (review, instructor)
  cleaned/conflicts.csv                  one row per (semester, course, instructor, dimension) with disagreeing labels
  cleaned/course_profiles.csv            one row per (course, instructor)

Rules (docs/labeling_guide.md, docs/METHODOLOGY.md section 4 step 6 and section 5)
  - `unknown` labels never vote.
  - Conflict: within one (semester, course, instructor), >= 2 different non-unknown labels for a dimension.
    adjacent = all labels within one step on the ordinal scale; opposite = otherwise.
  - Conflicts are listed for data-quality reporting only; they are not resolved label by label.
  - Profiles are numeric, because the goal is ranking and matching courses to student preferences:
      each label -> score in [0, 1] (SCORES below); {dim}_score = shrunk mean
      (sum + K * prior) / (n + K), where prior = the course-level mean (itself shrunk to the global mean).
      Factual display levels come directly from consistent labels. Other levels summarize the shrunk
      score. A factual disagreement or large score dispersion sets the disputed flag.
  - A profile with <= 2 reviews is flagged `insufficient_evidence`.

Usage: python src/aggregate.py
"""

import json
from collections import Counter
from pathlib import Path

import pandas as pd

from build_labels import DIMS

ROOT = Path(__file__).resolve().parent.parent
C = ROOT / "cleaned"
UNKNOWN = "Unknown instructor"
MIN_REVIEWS = 3

# Ordinal scales used to classify conflicts. Mixed-type values (conditional_mixed, varies) sit in the
# middle so that they are adjacent to every other value.
SCALES = {
    "memorization": ["low", "medium", "high"],
    "analytical": ["low", "medium", "high"],
    "background": ["beginner_friendly", "background_helpful", "background_dependent"],
    "workload": ["low", ("medium", "conditional_mixed"), "high"],
    "reading": ["low", "medium", "high"],
    "writing": ["low", "medium", "high"],
    "group_work": ["none", "optional", "required"],
    "participation": ["none", "voluntary", "required_or_graded"],
    "teaching_clarity": ["clear", "mixed", "unclear"],
    "assessment_difficulty": ["low", ("medium", "varies"), "high"],
    "grading_leniency": ["lenient", "mixed", "strict"],
    "recording": ["no", "partial", "yes"],
}
RANK = {d: {v: i for i, step in enumerate(s) for v in (step if isinstance(step, tuple) else (step,))}
        for d, s in SCALES.items()}
# Score direction: higher = more of the named property (more memorization, more workload, more background
# needed, clearer teaching, more lenient grading, more group work, more speaking, more recording).
SCORES = {
    **{d: {"low": 0.0, "medium": 0.5, "high": 1.0} for d in ["memorization", "analytical", "reading", "writing"]},
    "workload": {"low": 0.0, "medium": 0.5, "conditional_mixed": 0.5, "high": 1.0},
    "assessment_difficulty": {"low": 0.0, "medium": 0.5, "varies": 0.5, "high": 1.0},
    "background": {"beginner_friendly": 0.0, "background_helpful": 0.5, "background_dependent": 1.0},
    "teaching_clarity": {"unclear": 0.0, "mixed": 0.5, "clear": 1.0},
    "grading_leniency": {"strict": 0.0, "mixed": 0.5, "lenient": 1.0},
    "group_work": {"none": 0.0, "optional": 0.5, "required": 1.0},
    "participation": {"none": 0.0, "voluntary": 0.5, "required_or_graded": 1.0},
    "recording": {"no": 0.0, "partial": 0.5, "yes": 1.0},
}
LEVELS = {d: {0: min(m, key=m.get), 1: next(k for k, v in m.items() if v == 0.5), 2: max(m, key=m.get)}
          for d, m in SCORES.items()}
K = 2.0             # shrinkage strength, in pseudo-reviews
DISPUTE_STD = 0.35  # e.g. reviews split between 0 and 1 give std 0.5; 0 vs 0.5 gives 0.25
FACTUAL_DIMS = {"group_work", "participation", "recording"}
STRUCTURED = ["rating_content", "rating_teaching", "rating_grading", "rating_workload",
              "has_midterm", "has_final", "has_quiz", "has_assignment", "has_essay", "has_project",
              "has_attendance", "has_reading", "has_presentation"]


def conflict_type(dim: str, labels: set[str]) -> str:
    ranks = [RANK[dim][v] for v in labels]
    return "opposite" if max(ranks) - min(ranks) >= 2 else "adjacent"


def resolve_instructors(df: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    """One row per (review, instructor), with missing instructors filled from the review text."""
    imap = pd.read_csv(C / "review_instructor_map.csv", keep_default_na=False)
    fill = pd.read_csv(C / "review" / "instructor_fill.csv", keep_default_na=False)
    fill = {(r.course, r.instructor_in_text): (r.resolved_instructor, r.method) for r in fill.itertuples()}
    text = labels.set_index("hash").instructor_in_text
    rows = []
    for r in imap.itertuples():
        if r.instructor != UNKNOWN:
            rows.append((r.hash, r.instructor, "registered"))
            continue
        name = text.get(r.hash, "")
        resolved, method = fill.get((r.course, name), ("", "unresolved")) if name else ("", "no_name_in_text")
        if name and (r.course, name) not in fill:
            raise ValueError(f"{r.hash}: instructor_in_text {name!r} for {r.course} missing from instructor_fill.csv")
        if resolved:
            rows += [(r.hash, n.strip(), f"filled_{method}") for n in resolved.split(";")]
        else:
            rows.append((r.hash, UNKNOWN, "registered"))
    out = pd.DataFrame(rows, columns=["hash", "instructor", "instructor_source"])

    variants = C / "review" / "instructor_name_variants.csv"
    if variants.exists():
        v = pd.read_csv(variants, keep_default_na=False)
        mapping = dict(zip(v.variant, v.canonical))
        changed = out.instructor.isin(mapping)
        out.loc[changed, "instructor_source"] += "+name_variant_merged"
        out["instructor"] = out.instructor.replace(mapping)
    return out.drop_duplicates(["hash", "instructor"])


def main() -> None:
    df = pd.read_csv(C / "reviews_clean.csv", keep_default_na=False)
    labels = pd.read_csv(C / "review_labels.csv", keep_default_na=False)
    topics = pd.read_csv(C / "course_topics.csv", keep_default_na=False).set_index("course")

    long = (resolve_instructors(df, labels)
            .merge(df[["hash", "course", "course_name", "semester", *STRUCTURED]], on="hash")
            .merge(labels[["hash", *DIMS, *[f"{d}_evidence" for d in DIMS]]], on="hash"))
    long.to_csv(C / "review_instructor_labels.csv", index=False)

    # Conflicts within (semester, course, instructor).
    conflicts = []
    for (sem, course, ins), g in long.groupby(["semester", "course", "instructor"]):
        if ins == UNKNOWN:
            continue  # different unknown instructors cannot be compared
        for d in DIMS:
            known = g[g[d] != "unknown"]
            values = set(known[d])
            if len(values) < 2:
                continue
            conflicts.append({
                "semester": sem, "course": course, "instructor": ins, "dimension": d,
                "conflict_type": conflict_type(d, values), "n_labeled": len(known), "n_reviews": len(g),
                "label_counts": "; ".join(f"{k}:{v}" for k, v in Counter(known[d]).most_common()),
                "evidence": json.dumps([{"hash": r.hash, "label": r[d], "quote": r[f"{d}_evidence"]}
                                        for _, r in known.iterrows()], ensure_ascii=False),
            })
    conflicts = pd.DataFrame(conflicts)
    conflicts.to_csv(C / "conflicts.csv", index=False)
    # Priors: global mean per dimension, then course mean shrunk toward it (one vote per review).
    per_review = long.drop_duplicates(["course", "hash"])
    prior = {}
    for d in DIMS:
        sc = per_review[d].map(SCORES[d]).dropna()
        glob = sc.mean()
        for course, x in per_review.assign(_s=per_review[d].map(SCORES[d])).dropna(subset=["_s"]).groupby("course"):
            prior[(course, d)] = (x._s.sum() + K * glob) / (len(x) + K)
        prior[(None, d)] = glob

    # Profiles per (course, instructor).
    profiles = []
    for (course, ins), g in long.groupby(["course", "instructor"]):
        p = {"course": course, "course_name": g.course_name.iat[0], "instructor": ins,
             "n_reviews": g.hash.nunique(), "semesters": "; ".join(sorted(set(g.semester))),
             "evidence_status": "insufficient_evidence" if g.hash.nunique() < MIN_REVIEWS else "ok",
             "instructor_source": "; ".join(sorted(set(g.instructor_source))),
             "topic_categories": topics.at[course, "topic_categories"],
             "topic_keywords": topics.at[course, "topic_keywords"]}
        for d in DIMS:
            known = g[g[d] != "unknown"]
            counts = Counter(known[d])
            sc = known[d].map(SCORES[d])
            by_sem = {s: round(x[d].map(SCORES[d]).mean(), 2) for s, x in known.groupby("semester")}
            if len(sc):
                score = (sc.sum() + K * prior.get((course, d), prior[(None, d)])) / (len(sc) + K)
                if d in FACTUAL_DIMS:
                    disputed = len(counts) > 1
                    level = "conflicting" if disputed else next(iter(counts))
                else:
                    level = LEVELS[d][round(score * 2)]
                    disputed = bool(len(sc) >= 2 and sc.std(ddof=0) >= DISPUTE_STD)
            else:
                score, level, disputed = None, "unknown", False
            top = counts.most_common(1)[0][0] if counts else None
            ex = pd.concat([known[known[d] == top].head(1), known[known[d] != top].head(1)]) if top else known.head(0)
            p.update({
                f"{d}_score": None if score is None else round(score, 3),
                f"{d}_level": level,
                f"{d}_n": len(known),
                f"{d}_disputed": disputed,
                f"{d}_counts": "; ".join(f"{k}:{v}" for k, v in counts.most_common()),
                f"{d}_by_semester": "; ".join(f"{s}: {v}" for s, v in sorted(by_sem.items())),
                f"{d}_examples": " | ".join(f"[{r.semester}] {r[d]}: {r[f'{d}_evidence']}" for _, r in ex.iterrows()),
            })
        for s in STRUCTURED:
            p[f"{s}_mean"] = round(pd.to_numeric(g.drop_duplicates("hash")[s].replace({"True": 1, "False": 0})).mean(), 3)
        profiles.append(p)
    profiles = pd.DataFrame(profiles)
    profiles.to_csv(C / "course_profiles.csv", index=False)

    print(f"review-instructor rows: {len(long)}  (sources: {long.instructor_source.value_counts().to_dict()})")
    print(f"profiles: {len(profiles)}  insufficient_evidence: {(profiles.evidence_status != 'ok').sum()}")
    print(f"conflicts (data-quality report only): {len(conflicts)}")
    dis = profiles[[f"{d}_disputed" for d in DIMS]].sum()
    print("disputed dimensions:", {k.removesuffix("_disputed"): int(v) for k, v in dis.items() if v})
    if len(conflicts):
        print(conflicts.groupby(["dimension", "conflict_type"]).size().unstack(fill_value=0).to_string())


if __name__ == "__main__":
    main()
