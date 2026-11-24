"""Validate labels against the labeling guide; optionally write JSONL + flat CSV.

Usage:
  python src/build_labels.py check <file.json|file.py> [...]      # validate only
  python src/build_labels.py build <out_stem> <file.json|file.py|dir> [...]

Label file formats:
  .py   : defines dict L = {hash: {"kw": [...], "instructor_in_text": str|None, dim: (label, quote)}}
  .json : same structure, dims as [label, quote]
Checks: hash exists, label values are allowed, evidence quote appears verbatim in the review.
"""

import ast
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]

ALLOWED = {
    "memorization": {"low", "medium", "high"},
    "analytical": {"low", "medium", "high"},
    "background": {"beginner_friendly", "background_helpful", "background_dependent"},
    "workload": {"low", "medium", "high", "conditional_mixed"},
    "reading": {"low", "medium", "high"},
    "writing": {"low", "medium", "high"},
    "group_work": {"none", "required", "optional"},
    "participation": {"none", "voluntary", "required_or_graded"},
    "teaching_clarity": {"clear", "mixed", "unclear"},
    "assessment_difficulty": {"low", "medium", "high", "varies"},
    "grading_leniency": {"lenient", "mixed", "strict"},
    "recording": {"yes", "no", "partial"},
}
DIMS = list(ALLOWED)
META_KEYS = {"kw", "instructor_in_text", "annotation_source", "pending_dimensions", "review_notes"}


def norm(s: str) -> str:
    return " ".join(str(s).split())


def load(paths: list[str]) -> dict:
    files = []
    for p in map(Path, paths):
        files += sorted(p.glob("*.json")) if p.is_dir() else [p]
    labels = {}
    for f in files:
        if f.suffix == ".py":
            tree = ast.parse(f.read_text(encoding="utf-8"))
            part = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "L" for t in n.targets)))
        else:
            part = json.loads(f.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
        if not isinstance(part, dict):
            raise ValueError(f"{f}: expected a hash-keyed object")
        dup = labels.keys() & part.keys()
        if dup:
            raise ValueError(f"{f.name}: {len(dup)} duplicate hashes; resolve before building")
        labels.update(part)
    return labels


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def validate(labels: dict, df: pd.DataFrame):
    errors, records = [], []
    for h, lab in labels.items():
        if h not in df.index:
            errors.append(f"{h}: hash not found")
            continue
        if not isinstance(lab, dict):
            errors.append(f"{h}: expected a label object")
            continue
        text = norm(" ".join(df.loc[h, TEXT_COLS]))
        for k in lab:
            if k not in META_KEYS and k not in ALLOWED:
                errors.append(f"{h}: unknown key {k!r}")
        keywords = lab.get("kw", [])
        if not isinstance(keywords, list) or any(not isinstance(k, str) or not k.strip() for k in keywords):
            errors.append(f"{h}: keywords must be a list of non-empty strings")
        elif len(keywords) > 6 or len(set(keywords)) != len(keywords):
            errors.append(f"{h}: at most six distinct keywords are allowed")
        instructor = lab.get("instructor_in_text") or None
        if instructor is not None and not isinstance(instructor, str):
            errors.append(f"{h}: instructor_in_text must be text or null")
        pending = lab.get("pending_dimensions", [])
        if not isinstance(pending, list) or any(d not in {*DIMS, "topic_keywords", "instructor_in_text"} for d in pending):
            errors.append(f"{h}: invalid pending dimensions")
        rec = {"hash": h, "instructor_in_text": instructor,
               "topic_keywords": keywords,
               "annotation_source": lab.get("annotation_source", "unspecified"),
               "review_status": "pending_confirmation" if pending else "labeled",
               "pending_dimensions": pending,
               "review_notes": lab.get("review_notes", "")}
        for d in DIMS:
            v = lab.get(d)
            if v is not None and (not isinstance(v, (list, tuple)) or len(v) != 2):
                errors.append(f"{h} {d}: expected [label, evidence]")
                rec[d] = {"label": "unknown", "evidence": None}
                continue
            if v and v[0] != "unknown":
                value, quote = v
                if value not in ALLOWED[d]:
                    errors.append(f"{h} {d}: bad value {value!r}")
                if not isinstance(quote, str) or not quote or norm(quote) not in text:
                    errors.append(f"{h} {d}: quote not found: {quote!r}")
                elif len(quote.split()) > 30:
                    errors.append(f"{h} {d}: evidence exceeds 30 words")
                rec[d] = {"label": value, "evidence": quote}
            else:
                if v and v[1] is not None:
                    errors.append(f"{h} {d}: unknown must have null evidence")
                rec[d] = {"label": "unknown", "evidence": None}
        records.append(rec)
    return errors, records


def main() -> None:
    mode = sys.argv[1]
    if mode == "check":
        stem, paths = None, sys.argv[2:]
    elif mode == "build":
        stem, paths = sys.argv[2], sys.argv[3:]
        if Path(stem).name != stem:
            raise ValueError("output stem must be a filename without directories")
    else:
        raise ValueError("mode must be check or build")
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False).set_index("hash")
    if not df.index.is_unique:
        raise ValueError("duplicate hashes in cleaned source")
    errors, records = validate(load(paths), df)
    missing = set(df.index) - {r["hash"] for r in records}
    if stem is not None and missing:
        errors.append(f"incomplete coverage: {len(missing)} reviews missing")

    print(f"records: {len(records)}, errors: {len(errors)}")
    for e in errors:
        print("  ", e)
    print(f"coverage: {len(records)}/{len(df)}, missing: {len(missing)}")
    print(f"pending confirmation: {sum(bool(r['pending_dimensions']) for r in records)}")
    if errors:
        raise SystemExit(1)
    if stem is None:
        return

    out = ROOT / "cleaned"
    with open(out / f"{stem}.jsonl.tmp", "w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    flat = pd.DataFrame(
        [{"hash": r["hash"], "instructor_in_text": r["instructor_in_text"],
          "topic_keywords": "; ".join(r["topic_keywords"]),
          "annotation_source": r["annotation_source"], "review_status": r["review_status"],
          "pending_dimensions": "; ".join(r["pending_dimensions"]), "review_notes": r["review_notes"],
          **{d: r[d]["label"] for d in DIMS}, **{f"{d}_evidence": r[d]["evidence"] for d in DIMS}}
         for r in records]
    )
    flat.to_csv(out / f"{stem}.csv.tmp", index=False)
    (out / f"{stem}.jsonl.tmp").replace(out / f"{stem}.jsonl")
    (out / f"{stem}.csv.tmp").replace(out / f"{stem}.csv")
    print("\nnon-unknown labels per dimension:")
    print(flat[DIMS].ne("unknown").sum().to_string())


if __name__ == "__main__":
    main()
