"""Step 3: keyword-rule cross-check of the four factual dimensions against the LLM labels.

Dimensions: group_work, participation, recording, writing.
The rules are deliberately simple, high-precision regular expressions (L3 text processing). They are a
check on the LLM labels, not a replacement: a rule that does not fire means "no keyword", not "absent".

Per dimension the patterns are tried in the listed order and the first label whose pattern matches wins;
negative forms ("no group project") are listed before positive ones ("group project").

Usage: python src/rule_check.py
Writes
  cleaned/rule_labels.csv                     rule label and matched snippet per review
  cleaned/review/rule_disagreements.csv       reviews where rule and LLM both label but disagree (regenerated)
  cleaned/review/rule_check_summary.csv
and prints agreement, Cohen's kappa and coverage per dimension.

Manual adjudication of each disagreement is kept in cleaned/review/rule_adjudication.csv (key: hash +
dimension; verdict = rule_wrong | both_defensible | llm_wrong_fixed). This script only reads that file and
never overwrites it. LLM errors are fixed through cleaned/review/overrides_rulecheck.json, not here.
"""

import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parent.parent
TEXT_COLS = ["comment_content", "comment_teaching", "comment_grading", "comment_workload"]

P = lambda *xs: re.compile("|".join(xs), re.IGNORECASE)  # noqa: E731

RULES = {
    "group_work": [
        ("none", P(r"\bno (group|team) ?(project|work|assignment|presentation)s?\b", r"\ball (assessments? |work |tasks? )?(are |is )?individual",
                   r"\bindividual (project|work|assignment)s? only\b", r"没有小组", r"冇group", r"沒有小組", r"\bno groupwork\b")),
        ("optional", P(r"\b(individually|alone) or (in )?(a )?(group|team)s?\b", r"\b(group|team)s? or (individually|alone)\b",
                       r"\boptional (group|team)", r"\b(group|team) ?(project|work)s? (is|are) optional\b",
                       r"\b(can|may) (choose to )?(work|do it|be done) (in|with) (a )?(group|team|friends)")),
        ("required", P(r"\b(group|team) ?(project|presentation|assignment|report|work|essay|video|pre)s?\b",
                       r"\bgroup ?mates?\b", r"\bteammates?\b", r"\bin groups of\b", r"\bform (a )?groups?\b",
                       r"小组", r"小組", r"分组", r"組員", r"组员")),
    ],
    "participation": [
        ("none", P(r"\bno (class )?participation (mark|marks|grade|score|requirement)", r"\bno need to (speak|talk|answer questions)",
                   r"\bjust (sit|listen) (and|there)", r"不用发言", r"唔使發言", r"唔洗發言", r"\bno participation\b")),
        ("voluntary", P(r"\b(optional|voluntary) (discussion|participation|questions)", r"\bnot (required|forced) to (speak|answer|talk)")),
        ("required_or_graded", P(r"\b(class |in-class |classroom )?participation (mark|marks|grade|score|points|counts)",
                                 r"\b(class |in-class )?participation\W{0,3}\(?\d{1,2} ?%", r"\d{1,2} ?% (for )?(class )?participation",
                                 r"\bcold[- ]call", r"\bcalls? on (random )?(students|people|you)\b", r"\brandomly (pick|pick|choose|select)s? (students|people|someone)",
                                 r"\bdebates?\b", r"\b(graded|mandatory) discussions?\b", r"課堂發言", r"课堂发言", r"发言.{0,6}分", r"參與分", r"参与分")),
    ],
    "recording": [
        ("no", P(r"\bno (lecture |class |video )?recordings?\b", r"\bnot (been )?recorded\b", r"\brecordings? (are |is |were |was )?not (available|provided|uploaded)",
                 r"\b(does|do|did|will) ?n[o']t (provide |upload |post )?(any )?record", r"\bwithout (lecture )?recordings?\b",
                 r"没有recording", r"冇recording", r"冇錄影", r"没有录播", r"沒有錄影", r"不錄影", r"不录")),
        ("partial", P(r"\bsome (of the )?(lectures|lessons|classes) (are |were )?recorded", r"\bnot all .{0,25}recorded",
                      r"\brecordings? .{0,25}(sometimes|occasionally|partially|not always)", r"\b(poor|bad) (quality |audio )?recordings?")),
        ("yes", P(r"\b(lectures?|lessons?|classes?) (are|is|were|was|will be|get|got) (all )?recorded", r"\brecordings? (are |is |were |will be )?(available|provided|uploaded)",
                  r"\blecture (recordings?|videos?)\b", r"\bpanopto\b", r"\brecorded (lectures?|videos?)\b", r"\bwatch(ed|ing)? (the )?recordings?\b",
                  r"\bzoom recordings?\b", r"\b(has|have|there are|there is|with) (lecture )?recordings?\b", r"有recording", r"有錄影", r"有录播", r"会录", r"有回放")),
    ],
    "writing": [
        ("low", P(r"\bno (essays?|writing|written (assignments?|work)|reports?)\b", r"\b(just|only|all) (mcq?s?|multiple[- ]choice)\b", r"没有essay", r"冇essay", r"唔使寫essay")),
        ("high", P(r"\b(several|many|lots of|a lot of|multiple|\d+|two|three|four|five) (long )?(essays|reports|papers|reflections)\b",
                   r"\ba lot of writing\b", r"\b(heavy|lots of) writing\b", r"\b([2-9],?\d{3}|\d{2},?\d{3})[- ]?words?\b")),
        ("medium", P(r"\b(an|one|1|a) (short |final |term |mid-term |midterm )?(essay|report|paper|reflection)\b", r"\b\d{3}[- ]?words?\b",
                     r"\b1,?\d{3}[- ]?words?\b")),
    ],
}
ORDINAL = {"writing": ["low", "medium", "high"]}


def apply_rules(text: str, dim: str):
    for label, pat in RULES[dim]:
        m = pat.search(text)
        if m:
            a, b = max(0, m.start() - 60), min(len(text), m.end() + 60)
            return label, text[a:b]
    return "unknown", ""


def main() -> None:
    df = pd.read_csv(ROOT / "cleaned" / "reviews_clean.csv", keep_default_na=False).set_index("hash")
    llm = pd.read_csv(ROOT / "cleaned" / "review_labels.csv", keep_default_na=False).set_index("hash")
    text = df[TEXT_COLS].apply(lambda r: " ".join(" ".join(str(x).split()) for x in r), axis=1)

    rule = pd.DataFrame(index=df.index)
    for d in RULES:
        res = text.map(lambda t: apply_rules(t, d))
        rule[d] = res.str[0]
        rule[f"{d}_match"] = res.str[1]
    rule.to_csv(ROOT / "cleaned" / "rule_labels.csv")

    rows, dis = [], []
    for d in RULES:
        r, l = rule[d], llm.loc[rule.index, d]
        both = (r != "unknown") & (l != "unknown")
        agree = (r[both] == l[both]).mean()
        kappa = cohen_kappa_score(r[both], l[both]) if both.sum() else float("nan")
        rows.append({"dimension": d, "rule_labeled": int((r != "unknown").sum()), "llm_labeled": int((l != "unknown").sum()),
                     "both_labeled": int(both.sum()), "agreement": round(agree, 3), "cohen_kappa": round(kappa, 3),
                     "rule_only": int(((r != "unknown") & (l == "unknown")).sum()),
                     "llm_only": int(((r == "unknown") & (l != "unknown")).sum())})
        for h in r[both & (r != l)].index:
            dis.append({"hash": h, "course": df.at[h, "course"], "dimension": d, "llm": l[h], "rule": r[h],
                        "llm_evidence": llm.at[h, f"{d}_evidence"], "rule_match": rule.at[h, f"{d}_match"]})
    summary = pd.DataFrame(rows)
    dis = pd.DataFrame(dis)
    adj_path = ROOT / "cleaned" / "review" / "rule_adjudication.csv"
    if adj_path.exists() and len(dis):
        adj = pd.read_csv(adj_path, keep_default_na=False)
        dis = dis.merge(adj[["hash", "dimension", "verdict", "note"]], on=["hash", "dimension"], how="left").fillna({"verdict": "not_adjudicated"})
        print("adjudication of all disagreements (including LLM errors already fixed):")
        print(adj.groupby(["dimension", "verdict"]).size().unstack(fill_value=0).to_string())
    dis.to_csv(ROOT / "cleaned" / "review" / "rule_disagreements.csv", index=False)
    summary.to_csv(ROOT / "cleaned" / "review" / "rule_check_summary.csv", index=False)
    print(summary.to_string(index=False))
    print(f"open disagreements: {len(dis)}; not adjudicated: {int((dis.get('verdict', pd.Series(dtype=str)) == 'not_adjudicated').sum())}")


if __name__ == "__main__":
    main()
