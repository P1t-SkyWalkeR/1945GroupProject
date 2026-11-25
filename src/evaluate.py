"""Prepare blind assessment sheets, select on development, and score the frozen test."""

import argparse
import csv
import hashlib
import json
import statistics
from collections import Counter
from html import escape
from pathlib import Path

from build_recommendation_pool import CLEANED, read_csv
from recommender import ANSWERS, ASSESSMENTS, TOPIC_LABELS, metrics, rank, select_version, validate_profile, version_weights


RANKING_CODE = Path(__file__).with_name("recommender.py")
REVIEW_FIELDS = {
    "comment_content": "Content", "comment_teaching": "Teaching",
    "comment_grading": "Grading", "comment_workload": "Workload",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_profiles(data):
    groups = json.loads(data)
    if set(groups) != {"development", "test"} or not all(groups.values()):
        raise ValueError("Supply nonempty and separate development and test profile sets.")
    profiles = [p for group in groups.values() for p in group]
    ids = [p["id"] for p in profiles]
    if any(not name for name in ids) or len(ids) != len(set(ids)):
        raise ValueError("Profiles need distinct IDs across both sets.")
    for p in profiles:
        validate_profile(p)
    return groups


def load_selection(path, pool_bytes, profile_bytes=None):
    selection = json.loads(path.read_bytes())
    if selection["version"] not in {"A", "B", "C"} or not isinstance(selection["include_teaching"], bool):
        raise ValueError("Invalid selected method.")
    if selection["pool_sha256"] != digest(pool_bytes):
        raise ValueError("Selection was made for a different pool.")
    if selection["ranking_sha256"] != digest(RANKING_CODE.read_bytes()):
        raise ValueError("Ranking code changed after method selection.")
    if profile_bytes is not None and selection["profiles_sha256"] != digest(profile_bytes):
        raise ValueError("Profiles changed after method selection.")
    return selection


def verify_protocol(data, pool_bytes, profile_bytes):
    protocol = json.loads(data)
    expected = {
        "pool_sha256": digest(pool_bytes),
        "profiles_sha256": digest(profile_bytes),
        "ranking_sha256": digest(RANKING_CODE.read_bytes()),
        "reviews_sha256": digest((CLEANED / "reviews_clean.csv").read_bytes()),
    }
    for key, value in expected.items():
        if protocol[key] != value:
            raise ValueError(f"Study input changed after freezing: {key}.")
    include_teaching = protocol["include_teaching"]
    if not isinstance(include_teaching, bool) or protocol["weights"] != version_weights(include_teaching):
        raise ValueError("Study weights differ from the ranking implementation.")
    return protocol


def prepare(pool, profiles, path):
    courses = sorted(pool["courses"], key=lambda c: c["course_code"])
    originals = {row["hash"]: row for row in read_csv("reviews_clean.csv")}
    missing = {h for course in courses for h in course["review_ids"]} - originals.keys()
    if missing:
        raise ValueError(f"{len(missing)} original reviews are missing from the evidence snapshot.")
    path.mkdir(parents=True, exist_ok=True)
    fields = ["profile_id", "course_code", "hard_status", "fit", "notes"]
    existing = [name for name in ("evidence.md", "judgments_a.csv", "judgments_b.csv", "judgments_adjudicated.csv") if (path / name).exists()]
    if existing:
        raise ValueError(f"Use a new packet directory to preserve existing files: {', '.join(existing)}")
    for suffix in ("a", "b", "adjudicated"):
        destination = path / f"judgments_{suffix}.csv"
        with destination.open("x", encoding="utf-8-sig", newline="") as out:
            writer = csv.writer(out)
            writer.writerow(fields)
            for profile in profiles:
                writer.writerows([profile["id"], c["course_code"], "", "", ""] for c in courses)
    lines = [
        f'# Blind assessment · {pool["term_name"]} / {pool["cohort"]}',
        "",
        "Judge every course against each profile independently. Complete A and B before reading the other sheet.",
        "Use the sources and unscored original reviews below. The third reviewer resolves disagreements in the adjudicated sheet before rankings are revealed.",
        "",
        "- hard_status is pass, fail or unresolved. Use pass if no required constraint applies.",
        "- fit is 2 for evidence supporting all stated soft preferences with all required conditions met; 1 for some; 0 for none or a confirmed hard failure.",
        "- Use unresolved when missing or conflicting evidence prevents the fit judgment. Require notes for unresolved judgments and adjudication disagreements.",
        "- A checkbox or a review's silence alone does not establish the absence of an assessment.",
        "- For workload, explicitly compare the source evidence with the profile's maximum. For interests, read the description and judge whether it covers a selected topic.",
        "",
        "## Preference profiles",
    ]
    for p in profiles:
        lines.extend([f'### {p["id"]}', p.get("description", "")])
        lines.extend(f"- {ASSESSMENTS[k]} · {ANSWERS[v]}" for k, v in p.get("assessment", {}).items() if v != "any")
        if p.get("workload", "any") != "any":
            lines.append(f'- Maximum preferred workload · {p["workload"]}')
        if p.get("topics"):
            lines.append("- Topics · " + ", ".join(TOPIC_LABELS[k] for k in p["topics"]))
    lines.extend(["", "## Course evidence"])
    for c in courses:
        lines.extend([
            "", f'### {c["course_code"]} · {c["title"]}', "",
            f'{c["instructor"]} · {c["review_count"]} same-term matched reviews', "",
            c["description"], "",
            f'[Official CC schedule]({c["official_url"]}) · [USTSPACE reviews]({c["review_url"]})', "",
        ])
        for field in dict.fromkeys(item["source"] for item in c["assessment"].values() if item["verified"]):
            lines.append(f'- [Official assessment outline]({field})')
        for h in c["review_ids"]:
            lines.extend(["", f'#### Review {h}'])
            for field, label in REVIEW_FIELDS.items():
                comment = originals[h][field].strip()
                if comment:
                    lines.append(f'> **{label}** · {escape(" ".join(comment.split()))}')
                    lines.append(">")
    with (path / "evidence.md").open("x", encoding="utf-8") as out:
        out.write("\n".join(lines) + "\n")


def load_judgments(path, profiles, pool):
    expected = {(p["id"], c["course_code"]) for p in profiles for c in pool}
    profiles_by_id = {p["id"]: p for p in profiles}
    judgments = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            key = (row["profile_id"], row["course_code"])
            fit, hard = row["fit"].strip().lower(), row["hard_status"].strip().lower()
            if key not in expected or key in judgments:
                raise ValueError(f"Unexpected or duplicate judgment: {key}")
            if fit not in {"0", "1", "2", "unresolved"} or hard not in {"pass", "fail", "unresolved"}:
                raise ValueError(f"Incomplete or invalid judgment: {key}")
            profile = profiles_by_id[key[0]]
            has_required = any(value.startswith("require_") for value in profile.get("assessment", {}).values())
            if not has_required and hard != "pass":
                raise ValueError(f"Profile has no hard condition: {key}")
            if (hard == "fail" and fit != "0") or (hard == "unresolved" and fit != "unresolved"):
                raise ValueError(f"Fit conflicts with hard-condition judgment: {key}")
            if fit == "unresolved" and not row["notes"].strip():
                raise ValueError(f"An unresolved judgment needs a note: {key}")
            judgments[key] = {"fit": fit, "hard_status": hard}
    if absent := expected - judgments.keys():
        raise ValueError(f"Missing {len(absent)} judgments. First: {min(absent)}")
    return judgments


def agreement(a, b):
    cats = {"0", "1", "2", "unresolved"}
    ca = Counter(row["fit"] for row in a.values())
    cb = Counter(row["fit"] for row in b.values())
    n = len(a)
    observed = sum(a[key]["fit"] == b[key]["fit"] for key in a) / n
    expected = sum(ca[v] * cb[v] for v in cats) / n**2
    return {"n": n, "fit_agreement": observed, "fit_kappa": (observed - expected) / (1 - expected) if expected < 1 else None}


def summarize(results):
    recalls = [r["recall_at_3"] for r in results if r["recall_at_3"] is not None]
    return {
        "mean_precision_at_3": statistics.mean(r["precision_at_3"] for r in results),
        "mean_recall_at_3": statistics.mean(recalls) if recalls else None,
        "profiles_with_recall": len(recalls),
        "total_hard_violations": sum(r["hard_violations"] for r in results),
        "mean_returned": statistics.mean(len(r["recommended"]) for r in results),
    }


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as out:
        out.write(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, required=True)
    parser.add_argument("--protocol", type=Path, help="Check the frozen study inputs and method weights.")
    steps = parser.add_subparsers(dest="step", required=True)
    packet = steps.add_parser("prepare")
    packet.add_argument("--split", choices=("development", "test"), required=True)
    packet.add_argument("--output", type=Path, required=True)
    for step in ("develop", "test"):
        score = steps.add_parser(step)
        score.add_argument("--judgments", type=Path, required=True, help="Adjudicated full-pool CSV")
        score.add_argument("--rater-a", type=Path, required=True)
        score.add_argument("--rater-b", type=Path, required=True)
        score.add_argument("--output", type=Path, required=True)
        score.add_argument("--selection", type=Path, required=True)
        if step == "develop":
            score.add_argument("--include-teaching", action=argparse.BooleanOptionalAction, default=None)
    args = parser.parse_args()
    pb, prb = args.pool.read_bytes(), args.profiles.read_bytes()
    protocol_bytes = args.protocol.read_bytes() if args.protocol else None
    protocol = verify_protocol(protocol_bytes, pb, prb) if protocol_bytes is not None else None
    pool = json.loads(pb)
    groups = read_profiles(prb)
    courses = pool["courses"]
    if not courses or len({c["course_code"] for c in courses}) != len(courses):
        parser.error("Pool must contain at least one course and unique full course codes.")
    if args.step == "prepare":
        prepare(pool, groups[args.split], args.output)
        return
    selected = None
    if args.step == "test":
        selected = load_selection(args.selection, pb, prb)
        if selected.get("protocol_sha256") != (digest(protocol_bytes) if protocol_bytes is not None else None):
            parser.error("Use the same study protocol as development.")
    elif args.selection.exists():
        parser.error("The selection file already exists. Preserve it and use a new path for a new experiment.")
    if args.output.exists():
        parser.error("The results file already exists.")
    split = "development" if args.step == "develop" else "test"
    profiles = groups[split]
    judgments = load_judgments(args.judgments, profiles, courses)
    raters = [load_judgments(path, profiles, courses) for path in (args.rater_a, args.rater_b)]
    if selected:
        include_teaching = selected["include_teaching"]
    elif protocol:
        include_teaching = protocol["include_teaching"]
        if args.include_teaching is not None and args.include_teaching != include_teaching:
            parser.error("The requested teaching setting differs from the frozen study.")
    else:
        include_teaching = args.include_teaching if args.include_teaching is not None else True
    results = {}
    for version in "ABC":
        rows = []
        for profile in profiles:
            labels = {c["course_code"]: judgments[(profile["id"], c["course_code"])] for c in courses}
            rows.append({"profile_id": profile["id"], **metrics(rank(courses, profile, version, include_teaching), labels)})
        results[version] = rows
    if selected is None:
        selected = {
            "version": select_version(results), "include_teaching": include_teaching,
            "pool_sha256": digest(pb), "profiles_sha256": digest(prb),
            "ranking_sha256": digest(RANKING_CODE.read_bytes()),
            "protocol_sha256": digest(protocol_bytes) if protocol_bytes is not None else None,
            "development_profile_ids": [p["id"] for p in groups["development"]],
        }
        write_json(args.selection, selected)
    write_json(args.output, {
        "split": split, "pool_size": len(courses), "selected_on_development": selected["version"],
        "human_agreement_before_adjudication": agreement(*raters),
        "versions": {version: {"profiles": rows, "summary": summarize(rows)} for version, rows in results.items()},
    })
    print(f"{split} results written to {args.output}")


if __name__ == "__main__":
    main()
