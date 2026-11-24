"""Merge batch outputs into one label set with exactly one label per review.

Rules:
- Each review hash belongs to exactly one batch (cleaned/batches/input/batch_XX.jsonl).
- A label is accepted only from that batch's own output files (batch_XX_part*.json).
  Entries found in another batch's files (cross-contamination) are discarded.
- Repeated entries from the owning batch must agree on dimension labels.
- Completion labels and explicitly marked review decisions override historical fragments.
- Pilot labels (cleaned/pilot_labels_raw.py) are included as-is.

Usage: python src/merge_batches.py
Writes cleaned/batches/merged_labels.json and prints coverage.
"""

import json
import re
from pathlib import Path

import pandas as pd

from build_labels import DIMS, load, unique_keys, validate

ROOT = Path(__file__).resolve().parent.parent
B = ROOT / "cleaned" / "batches"
OVERRIDE_ORDER = [
    "overrides_codex_strict.json",          # round 1: strict re-review of Codex labels (analytical, workload, hearsay)
    "overrides_codex_analytical_r2.json",   # round 2: Codex analytical vs. the extended analytical rules
    "overrides_subagent_analytical.json",   # round 2: subagent analytical gaps (cleaned/review/analytical_supplement.jsonl)
    "overrides_rulecheck.json",             # round 3: LLM errors found by the keyword-rule cross-check (src/rule_check.py)
]


def main() -> None:
    owner = {}
    for f in sorted((B / "input").glob("batch_*.jsonl")):
        bid = f.stem.split("_")[1]
        for line in f.open(encoding="utf-8"):
            owner[json.loads(line)["hash"]] = bid

    merged, foreign, repeats = {}, 0, 0
    files = sorted((B / "output").glob("batch_*_part*.json"),
                   key=lambda p: (p.stem.split("_")[1], int(re.search(r"part(\d+)", p.stem).group(1))))
    for f in files:
        bid = f.stem.split("_")[1]
        for h, lab in json.loads(f.read_text(encoding="utf-8"), object_pairs_hook=unique_keys).items():
            if owner.get(h) != bid:
                foreign += 1
                continue
            if h in merged:
                repeats += 1
                differences = [d for d in DIMS if merged[h].get(d, ["unknown", None])[0]
                               != lab.get(d, ["unknown", None])[0]]
                if differences:
                    raise ValueError(f"{h}: unresolved same-batch label differences: {differences}")
            merged[h] = {**lab, "annotation_source": "claude"}

    pilot = load([str(ROOT / "cleaned" / "pilot_labels_raw.py")])
    for h, lab in pilot.items():
        if h in merged:
            raise ValueError(f"pilot hash duplicated in batch output: {h}")
        merged[h] = {**{k: (list(v) if isinstance(v, tuple) else v) for k, v in lab.items()},
                     "annotation_source": "claude"}

    completion_path = ROOT / "cleaned" / "completion_labels.json"
    completed = load([str(completion_path)]) if completion_path.exists() else {}
    for h, lab in completed.items():
        merged[h] = {**lab, "annotation_source": "claude_reviewed_by_codex" if h in merged else "codex"}

    # Review overrides, applied last in this fixed order (later files win).
    # Value None -> unknown; [label, quote] -> set. See docs/labeling_guide.md "Review rounds".
    n_override = 0
    review_dir = ROOT / "cleaned" / "review"
    unlisted = {f.name for f in review_dir.glob("overrides_*.json")} - set(OVERRIDE_ORDER)
    if unlisted:
        raise ValueError(f"override files not in OVERRIDE_ORDER: {sorted(unlisted)}")
    for f in (review_dir / name for name in OVERRIDE_ORDER):
        for h, dims in json.loads(f.read_text(encoding="utf-8")).items():
            for d, v in dims.items():
                if v is None:
                    merged[h].pop(d, None)
                else:
                    merged[h][d] = v
                n_override += 1
            merged[h]["review_notes"] = "; ".join(
                filter(None, [merged[h].get("review_notes"), f"{f.stem.removeprefix('overrides_')}: {', '.join(dims)}"]))

    # Pending items resolved by the user.
    decisions_path = ROOT / "cleaned" / "review" / "pending_decisions.json"
    if decisions_path.exists():
        for rule, hashes in next(iter(json.loads(decisions_path.read_text()).values())).items():
            for h in hashes:
                merged[h].pop("pending_dimensions", None)
                merged[h]["review_notes"] = "; ".join(filter(None, [merged[h].get("review_notes"), f"user decision: {rule}"]))
    print(f"review overrides applied: {n_override}")

    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False).set_index("hash")
    if not df.index.is_unique or set(merged) != set(df.index):
        raise ValueError(f"coverage mismatch: missing={len(set(df.index)-set(merged))}, extra={len(set(merged)-set(df.index))}")
    errors, _ = validate(merged, df)
    if errors:
        for error in errors:
            print(error)
        raise SystemExit(1)

    temporary = B / "merged_labels.json.tmp"
    temporary.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")
    temporary.replace(B / "merged_labels.json")
    missing = [h for h in owner if h not in merged]
    print(f"labeled: {len(merged)} / {len(owner) + len(pilot)}")
    print(f"discarded cross-batch entries: {foreign}")
    print(f"same-batch repeats (labels agree; latest evidence kept): {repeats}")
    print(f"completion/review records: {len(completed)}")
    print(f"still missing: {len(missing)}")


if __name__ == "__main__":
    main()
