"""Score the human spot check (see spot_check/README.md).

For every dimension: Cohen's kappa and raw agreement for A vs B, A vs LLM, B vs LLM, and for the items
where A and B agree, LLM accuracy against that consensus. Empty cells are treated as missing.

Usage: python src/score_spot_check.py
Writes spot_check/spot_check_results.csv and spot_check/disagreements_with_llm.csv
"""

import argparse
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from build_labels import ALLOWED, DIMS

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "spot_check"


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".xlsx":
        x = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        x = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    missing_columns = {"hash", *DIMS} - set(x.columns)
    if missing_columns:
        raise ValueError(f"{path.name}: missing columns {sorted(missing_columns)}")
    x["hash"] = x["hash"].str.strip()
    if x["hash"].eq("").any() or x["hash"].duplicated().any():
        raise ValueError(f"{path.name}: blank or duplicate review hash")
    x = x.set_index("hash")
    for d in DIMS:
        x[d] = x[d].astype(str).str.strip().str.lower()
        bad = x[(x[d] != "") & ~x[d].isin(ALLOWED[d] | {"unknown"})]
        if len(bad):
            raise ValueError(f"{path.name} {d}: invalid values at hashes {list(bad.index)}: {sorted(set(bad[d]))}")
    return x


def align_sample(frame, expected, name):
    missing = expected.difference(frame.index)
    extra = frame.index.difference(expected)
    if len(missing) or len(extra):
        raise ValueError(f"{name}: sample mismatch ({len(missing)} missing, {len(extra)} extra hashes)")
    return frame.reindex(expected)


def pair(a: pd.Series, b: pd.Series) -> dict:
    b = align_sample(b, a.index, "comparison")
    m = (a != "") & (b != "")
    if m.sum() == 0:
        return {"n": 0, "agreement": None, "kappa": None}
    return {"n": int(m.sum()), "agreement": round((a[m] == b[m]).mean(), 3),
            "kappa": round(cohen_kappa_score(a[m], b[m]), 3) if len(set(a[m]) | set(b[m])) > 1 else None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--a", type=Path, default=S / "sheet_annotator_A.csv")
    parser.add_argument("--b", type=Path, default=S / "sheet_annotator_B.csv")
    parser.add_argument("--answers", type=Path, default=S / "llm_labels_HIDDEN.csv")
    parser.add_argument("--output-dir", type=Path, default=S)
    args = parser.parse_args()
    L = load(args.answers)
    A = align_sample(load(args.a), L.index, args.a.name)
    B = align_sample(load(args.b), L.index, args.b.name)
    rows, dis = [], []
    for d in DIMS:
        r = {"dimension": d}
        for tag, (x, y) in {"A_vs_B": (A[d], B[d]), "A_vs_LLM": (A[d], L[d]), "B_vs_LLM": (B[d], L[d])}.items():
            r.update({f"{tag}_{k}": v for k, v in pair(x, y).items()})
        cons = (A[d] != "") & (A[d] == B[d])
        r["consensus_n"] = int(cons.sum())
        r["LLM_acc_on_consensus"] = round((L[d][cons] == A[d][cons]).mean(), 3) if cons.sum() else None
        rows.append(r)
        for i in A.index[cons & (L[d] != A[d])]:
            dis.append({"item": L.at[i, "item"], "hash": i, "dimension": d, "human": A.at[i, d], "llm": L.at[i, d],
                        "llm_evidence": L.at[i, f"{d}_evidence"]})
    res = pd.DataFrame(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    res.to_csv(args.output_dir / "spot_check_results.csv", index=False)
    pd.DataFrame(dis, columns=["item", "hash", "dimension", "human", "llm", "llm_evidence"]).to_csv(
        args.output_dir / "disagreements_with_llm.csv", index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
