"""Score the human spot check (see spot_check/README.md).

For every dimension: Cohen's kappa and raw agreement for A vs B, A vs LLM, B vs LLM, and for the items
where A and B agree, LLM accuracy against that consensus. Empty cells are treated as missing.

Usage: python src/score_spot_check.py
Writes spot_check/spot_check_results.csv and spot_check/disagreements_with_llm.csv
"""

from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

from build_labels import ALLOWED, DIMS

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "spot_check"


def load(name: str) -> pd.DataFrame:
    x = pd.read_csv(S / name, keep_default_na=False, encoding="utf-8-sig").set_index("item")
    for d in DIMS:
        x[d] = x[d].astype(str).str.strip().str.lower()
        bad = x[(x[d] != "") & ~x[d].isin(ALLOWED[d] | {"unknown"})]
        if len(bad):
            raise ValueError(f"{name} {d}: invalid values at items {list(bad.index)}: {sorted(set(bad[d]))}")
    return x


def pair(a: pd.Series, b: pd.Series) -> dict:
    m = (a != "") & (b != "")
    if m.sum() == 0:
        return {"n": 0, "agreement": None, "kappa": None}
    return {"n": int(m.sum()), "agreement": round((a[m] == b[m]).mean(), 3),
            "kappa": round(cohen_kappa_score(a[m], b[m]), 3) if len(set(a[m]) | set(b[m])) > 1 else None}


def main() -> None:
    A, B, L = load("sheet_annotator_A.csv"), load("sheet_annotator_B.csv"), load("llm_labels_HIDDEN.csv")
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
            dis.append({"item": i, "dimension": d, "human": A.at[i, d], "llm": L.at[i, d],
                        "llm_evidence": L.at[i, f"{d}_evidence"]})
    res = pd.DataFrame(rows)
    res.to_csv(S / "spot_check_results.csv", index=False)
    pd.DataFrame(dis).to_csv(S / "disagreements_with_llm.csv", index=False)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
