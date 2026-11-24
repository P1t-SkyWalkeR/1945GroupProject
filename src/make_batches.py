"""Split reviews (excluding already-labeled pilot hashes) into batch files for LLM extraction.

Usage: python src/make_batches.py <n_batches>
Writes cleaned/batches/input/batch_XX.jsonl
"""

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]


def main(n: int) -> None:
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False)
    pilot = set(pd.read_csv(ROOT / "cleaned" / "pilot_sample_hashes.csv")["hash"])
    df = df[~df["hash"].isin(pilot)].sort_values(["course", "instructor_names", "semester"])

    out = ROOT / "cleaned" / "batches" / "input"
    out.mkdir(parents=True, exist_ok=True)
    rows = df.to_dict("records")
    size = -(-len(rows) // n)
    for i in range(n):
        chunk = rows[i * size:(i + 1) * size]
        with open(out / f"batch_{i:02d}.jsonl", "w", encoding="utf-8") as f:
            for r in chunk:
                f.write(json.dumps({k: r[k] for k in
                        ["hash", "course", "course_name", "semester", "instructor_names", *TEXT_COLS]},
                        ensure_ascii=False) + "\n")
        print(f"batch_{i:02d}: {len(chunk)}")


if __name__ == "__main__":
    main(int(sys.argv[1]))
