"""Build the human spot-check sample (report Section 6).

Draws a stratified random sample of reviews, writes a blank annotation sheet per annotator (review text
only, no LLM labels) and keeps the LLM labels in a separate answer file used only after annotation.

Strata: annotation source (subagent vs Codex) x broad subject area of the course (first topic category).
Usage: python src/make_spot_check.py [n=80]
Writes spot_check/sheet_annotator_A.csv, sheet_annotator_B.csv, spot_check/llm_labels_HIDDEN.csv
"""

import argparse
from pathlib import Path

import pandas as pd

from build_labels import DIMS

ROOT = Path(__file__).resolve().parent.parent
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]
SEED = 1945
FILES = ("sheet_annotator_A.csv", "sheet_annotator_B.csv", "llm_labels_HIDDEN.csv")


def spreadsheet_text(value):
    """Neutralize formula-like text in the annotator CSV, leaving source reviews intact."""
    if isinstance(value, str) and (
        value.startswith(("\t", "\r", "\n"))
        or value.lstrip(" \t\r\n\ufeff").startswith(("=", "+", "-", "@", "＝", "＋", "－", "＠"))
    ):
        return "'" + value
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n", type=int, nargs="?", default=80)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "spot_check")
    args = parser.parse_args()
    n, out = args.n, args.output_dir
    if any((out / name).exists() for name in FILES):
        parser.error("Sample files already exist. Use --output-dir for a new sample.")
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False)
    lab = pd.read_csv(ROOT / "cleaned" / "review_labels.csv", keep_default_na=False)
    topics = pd.read_csv(ROOT / "cleaned" / "course_topics.csv", keep_default_na=False)
    df = df.merge(lab, on="hash").merge(topics[["course", "topic_categories"]], on="course")
    df["source"] = df.annotation_source.map(lambda s: "codex" if "codex" in s else "subagent")
    df["area"] = df.topic_categories.str.split(";").str[0].str.strip()
    df["stratum"] = df.source + "|" + df.area
    # proportional allocation, at least one per stratum that has >= 5 reviews
    share = df.stratum.value_counts(normalize=True)
    alloc = (share * n).round().astype(int).clip(lower=1)
    alloc = alloc[df.stratum.value_counts() >= 5]
    while alloc.sum() > n:
        alloc[alloc.idxmax()] -= 1
    while alloc.sum() < n:
        alloc[(share[alloc.index] * n - alloc).idxmax()] += 1
    sample = pd.concat([df[df.stratum == s].sample(k, random_state=SEED) for s, k in alloc.items()])
    sample = sample.sample(frac=1, random_state=SEED).reset_index(drop=True)
    sample.insert(0, "item", range(1, len(sample) + 1))

    out.mkdir(parents=True, exist_ok=True)
    sheet = sample[["item", "hash", "course", "course_name", "instructor_names", *TEXT_COLS]].copy()
    for d in DIMS:
        sheet[d] = ""
    sheet["notes"] = ""
    sheet = sheet.map(spreadsheet_text)
    for name in FILES[:2]:
        sheet.to_csv(out / name, index=False, encoding="utf-8-sig", mode="x")
    sample[["item", "hash", "source", "area", *DIMS, *[f"{d}_evidence" for d in DIMS]]].to_csv(
        out / FILES[2], index=False, encoding="utf-8-sig", mode="x")
    print(f"sample: {len(sample)} reviews in {len(alloc)} strata; source mix {sample.source.value_counts().to_dict()}")


if __name__ == "__main__":
    main()
