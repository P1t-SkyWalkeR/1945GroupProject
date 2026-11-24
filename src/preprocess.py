"""Clean raw ust.space reviews.

Steps (see docs/METHODOLOGY.md, step 1):
- strip HTML tags and entities from the four comment columns
- drop reviewer identity columns (author, is_author)
- deduplicate by hash
- fill missing instructors with "Unknown instructor"
- write a review-level table and an exploded (one row per instructor) table
"""

import html
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "reviews_2023-2026.csv"
OUT_DIR = ROOT / "cleaned"

TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]
DROP_COLS = ["author", "is_author"]
UNKNOWN_INSTRUCTOR = "Unknown instructor"
# Privacy: personal e-mail addresses left by reviewers are removed; university staff addresses (ust.hk) are
# public contact details and are kept.
PERSONAL_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?![A-Za-z0-9.-]*ust\.hk\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def clean_text(s) -> str:
    if pd.isna(s):
        return ""
    s = str(s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    s = PERSONAL_EMAIL.sub("[email removed]", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def split_instructors(s: str) -> list[str]:
    return sorted({p.strip() for p in s.split(";") if p.strip()})


def main() -> None:
    df = pd.read_csv(RAW)
    n_raw = len(df)

    df = df.drop(columns=[c for c in DROP_COLS if c in df.columns])
    df = df.drop_duplicates(subset="hash")
    for c in TEXT_COLS:
        df[c] = df[c].map(clean_text)

    df["instructor_names"] = df["instructor_names"].fillna(UNKNOWN_INSTRUCTOR)
    df["instructor_list"] = df["instructor_names"].map(split_instructors)
    df["n_instructors"] = df["instructor_list"].map(len)
    df["has_chinese"] = df[TEXT_COLS].agg(" ".join, axis=1).str.contains(r"[一-鿿]")

    OUT_DIR.mkdir(exist_ok=True)
    review_level = df.drop(columns=["instructor_list"])
    review_level.to_csv(OUT_DIR / "reviews_clean.csv", index=False)

    exploded = df.explode("instructor_list").rename(columns={"instructor_list": "instructor"})
    exploded = exploded[["hash", "course", "course_name", "semester", "instructor", "instructor_names"]]
    exploded.to_csv(OUT_DIR / "review_instructor_map.csv", index=False)

    print(f"raw rows: {n_raw}, after dedup: {len(df)}")
    print(f"unknown instructor: {(df['instructor_names'] == UNKNOWN_INSTRUCTOR).sum()}")
    print(f"co-taught reviews: {(df['n_instructors'] > 1).sum()}")
    print(f"review-instructor rows: {len(exploded)}")
    print(f"course+instructor groups: {exploded.groupby(['course', 'instructor']).ngroups}")


if __name__ == "__main__":
    main()
