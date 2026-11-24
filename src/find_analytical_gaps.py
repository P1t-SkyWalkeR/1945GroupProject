"""List subagent-labeled reviews whose analytical label is unknown but whose text
contains analytical-demand keywords. These are candidates for a targeted re-check.

Usage: python src/find_analytical_gaps.py
Writes cleaned/review/analytical_candidates.jsonl (hash, course, keyword-in-context snippets).
"""

import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]

# Phrases that usually describe what students must do (reasoning, calculation, proofs, coding).
KEYWORDS = [
    r"proofs?\b", r"\bprov(e|ing)\b", r"derivations?", r"\bderiv(e|ing)\b",
    r"calculations?", r"\bcalculat(e|ing)\b", r"computations?", r"problem[- ]solving", r"problem sets?",
    r"(coding|programming) (assignments?|projects?|labs?|tasks?|questions?|exercises?)",
    r"(lots of|a lot of|heavy|intensive|no|little|much) (math|maths|coding|programming|calculation)",
    r"math[- ](heavy|intensive|based)", r"(logical|critical|analytical) (thinking|skills?|reasoning)",
    r"\banalytical\b", r"tricky (questions?|problems?)", r"(apply|application of) (the )?(concepts?|knowledge)",
    r"just (concepts|memori[sz]ation|theory)", r"(purely|mostly) (conceptual|descriptive|theoretical)",
    r"证明", r"推导", r"计算", r"编程", r"逻辑", r"思维",
]
PATTERN = re.compile("|".join(KEYWORDS), re.IGNORECASE)


def snippets(text: str, width: int = 160) -> list[str]:
    spans = []
    for m in PATTERN.finditer(text):
        a, b = max(0, m.start() - width), min(len(text), m.end() + width)
        if spans and a <= spans[-1][1]:
            spans[-1][1] = b
        else:
            spans.append([a, b])
    return [text[a:b] for a, b in spans]


def main() -> None:
    labels = pd.read_csv(ROOT / "cleaned" / "review_labels.csv", keep_default_na=False).set_index("hash")
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False).set_index("hash")
    cand = labels[(labels.annotation_source == "claude") & (labels.analytical == "unknown")].index
    out = []
    for h in cand:
        text = " ".join(" ".join(str(df.loc[h, c]).split()) for c in TEXT_COLS)
        sn = snippets(text)
        if sn:
            out.append({"hash": h, "course": f"{df.loc[h, 'course']} {df.loc[h, 'course_name']}", "snippets": sn})
    path = ROOT / "cleaned" / "review" / "analytical_candidates.jsonl"
    with open(path, "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"subagent reviews with analytical=unknown: {len(cand)}; keyword candidates: {len(out)}")


if __name__ == "__main__":
    main()
