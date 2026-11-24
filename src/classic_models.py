"""Step 4: how well do the classic course models reproduce the LLM labels?

Representations : BoW (binary counts, L3/L5) and averaged pretrained GloVe vectors (L6)
Classifiers     : Perceptron (L5), KNN (L7), MLP (L10), plus a majority-class baseline
Split           : GroupKFold by course (5 folds), so no course appears in both train and test
Tasks           : full  = predict the LLM label including `unknown` (detection + level)
                  level = predict the level only, on reviews the LLM labeled (non-unknown)
Metrics         : macro-F1 and accuracy on pooled out-of-fold predictions; std of fold macro-F1

Important: the target is the LLM label, so this measures agreement with the LLM, not with the truth.
All fitted preprocessing (vocabulary, scaling) is fitted on the training fold only.

Requires the GloVe file at ~/gensim-data/glove-wiki-gigaword-100/glove-wiki-gigaword-100.gz
(gensim-data release "glove-wiki-gigaword-100"; downloaded with curl because gensim's index fetch failed).

Usage: python src/classic_models.py
Writes cleaned/experiments/classic_results.csv, classic_folds.csv, oof_predictions.csv
"""

import re
import time
from pathlib import Path

import numpy as np
import pandas as pd
from gensim.models import KeyedVectors
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.linear_model import Perceptron
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import GroupKFold
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler

from build_labels import DIMS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "cleaned" / "experiments"
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]
GLOVE = Path.home() / "gensim-data" / "glove-wiki-gigaword-100" / "glove-wiki-gigaword-100.gz"
N_FOLDS = 5
SEED = 0

TOKEN = re.compile(r"[a-z]+(?:'[a-z]+)?|\d+|[一-鿿]")


def tokenize(text: str) -> list[str]:
    """Lowercase, n't -> not, keep negations and all words, one token per Chinese character (step 1)."""
    text = text.lower().replace("n't", " not").replace("n’t", " not")
    return TOKEN.findall(text)


def classifiers(rep: str) -> dict:
    return {
        "majority": DummyClassifier(strategy="most_frequent"),
        "perceptron": Perceptron(max_iter=1000, class_weight="balanced", random_state=SEED),
        "knn": KNeighborsClassifier(n_neighbors=15, metric="cosine" if rep == "bow" else "minkowski", weights="distance"),
        "mlp": MLPClassifier(hidden_layer_sizes=(64,), early_stopping=True, max_iter=200, random_state=SEED),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False).set_index("hash")
    labels = pd.read_csv(ROOT / "cleaned" / "review_labels.csv", keep_default_na=False).set_index("hash").loc[df.index]
    tokens = df[TEXT_COLS].apply(lambda r: tokenize(" ".join(r)), axis=1).tolist()
    groups = df.course.to_numpy()

    print("loading GloVe ...", flush=True)
    kv = KeyedVectors.load_word2vec_format(str(GLOVE), binary=False)
    glove = np.vstack([np.mean([kv[t] for t in ts if t in kv] or [np.zeros(kv.vector_size)], axis=0) for ts in tokens])
    oov = np.mean([sum(t not in kv for t in ts) / max(len(ts), 1) for ts in tokens])
    print(f"GloVe: {kv.vector_size}d, mean OOV token share {oov:.1%}", flush=True)

    folds = list(GroupKFold(n_splits=N_FOLDS).split(tokens, groups=groups))
    feats = []  # per fold: {rep: (Xtr, Xte)}
    for tr, te in folds:
        vec = CountVectorizer(analyzer=lambda x: x, min_df=2, binary=True).fit([tokens[i] for i in tr])
        sc = StandardScaler().fit(glove[tr])
        feats.append({"bow": (vec.transform([tokens[i] for i in tr]), vec.transform([tokens[i] for i in te])),
                      "glove": (sc.transform(glove[tr]), sc.transform(glove[te]))})

    results, fold_rows, oof_rows = [], [], []
    for d in DIMS:
        y_all = labels[d].to_numpy()
        for task in ["full", "level"]:
            keep = np.ones(len(y_all), bool) if task == "full" else (y_all != "unknown")
            for rep in ["bow", "glove"]:
                for name in classifiers(rep):
                    if name == "majority" and rep == "glove":
                        continue  # baseline does not depend on the representation
                    t0, pred, true, idx, fold_f1 = time.time(), [], [], [], []
                    for k, (tr, te) in enumerate(folds):
                        mtr, mte = keep[tr], keep[te]
                        if mte.sum() == 0 or len(set(y_all[tr][mtr])) < 2:
                            continue
                        Xtr, Xte = feats[k][rep]
                        clf = classifiers(rep)[name].fit(Xtr[mtr], y_all[tr][mtr])
                        p = clf.predict(Xte[mte])
                        pred += list(p); true += list(y_all[te][mte]); idx += list(te[mte])
                        fold_f1.append(f1_score(y_all[te][mte], p, average="macro", zero_division=0))
                        fold_rows.append({"dimension": d, "task": task, "representation": rep, "model": name,
                                          "fold": k, "n_test": int(mte.sum()), "macro_f1": fold_f1[-1]})
                    model = name if name == "majority" else f"{rep}+{name}"
                    results.append({"dimension": d, "task": task, "model": model, "n": len(true),
                                    "n_classes": len(set(true)),
                                    "macro_f1": round(f1_score(true, pred, average="macro", zero_division=0), 3),
                                    "macro_f1_fold_std": round(float(np.std(fold_f1)), 3),
                                    "accuracy": round(accuracy_score(true, pred), 3)})
                    oof_rows += [{"hash": df.index[i], "dimension": d, "task": task, "model": model, "true": t, "pred": p}
                                 for i, t, p in zip(idx, true, pred)]
                    print(f"{d:22s} {task:5s} {model:16s} macroF1={results[-1]['macro_f1']:.3f} "
                          f"acc={results[-1]['accuracy']:.3f} ({time.time() - t0:.0f}s)", flush=True)

    pd.DataFrame(results).to_csv(OUT / "classic_results.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(OUT / "classic_folds.csv", index=False)
    pd.DataFrame(oof_rows).to_csv(OUT / "oof_predictions.csv", index=False)
    res = pd.DataFrame(results)
    for task in ["full", "level"]:
        print(f"\nmacro-F1, task={task}")
        print(res[res.task == task].pivot(index="dimension", columns="model", values="macro_f1").to_string())


if __name__ == "__main__":
    main()
