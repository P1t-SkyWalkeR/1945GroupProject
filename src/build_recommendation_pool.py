"""Join one official term/cohort with matching USTSPACE course and instructor evidence."""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from recommender import ASSESSMENTS, LEVELS, TEACHING, TOPIC_LABELS


ROOT = Path(__file__).resolve().parent.parent
CLEANED = ROOT / "cleaned"
REVIEW_FIELDS = {"final": "has_final", "presentation": "has_presentation", "group_project": "group_work"}


def code_key(value):
    return "".join(value.upper().split())


def instructor_key(value):
    return "".join(c for c in value.casefold() if c.isalnum())


def read_csv(name):
    with (CLEANED / name).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def categorical_signal(rows, field, allowed):
    known = [row for row in rows if row[field] != "unknown"]
    counts = Counter(row[field] for row in known)
    votes = counts.most_common()
    value = "unknown"
    if votes and votes[0][0] in allowed and (len(votes) == 1 or votes[0][1] > votes[1][1]):
        value = votes[0][0]
    quotes = {}
    for row in known:
        if row[f"{field}_evidence"]:
            quotes.setdefault(row[field], {"review_id": row["hash"], "quote": row[f"{field}_evidence"]})
    return {"value": value, "n": len(known), "counts": dict(counts), "examples": list(quotes.values())}


def assessment_signal(rows, field, override):
    if override:
        return {"value": override["value"], "verified": True, "note": override["note"], "source": override["source"], "review_ids": []}
    source_field = REVIEW_FIELDS[field]
    if field == "group_project":
        positive = [row for row in rows if row[source_field] == "required"]
        negative = [row for row in rows if row[source_field] in {"none", "optional"}]
        if positive:
            note = "Student review labels report required group work."
        elif negative:
            note = "Student review labels report optional or individual work."
        else:
            note = "Evidence of required group work is missing."
    else:
        positive = [row for row in rows if row[source_field].casefold() == "true"]
        negative = [row for row in rows if row[source_field].casefold() == "false"]
        note = "Student review checkboxes report this assessment." if positive else "No positive review checkbox; absence is unverified."
    value = "unknown"
    if positive and negative:
        note = "Student reports vary; confirmation is needed."
    elif positive:
        value = "yes"
    elif field == "group_project" and negative:
        value = "no"
    return {
        "value": value,
        "verified": False,
        "note": note,
        "source": "",
        "review_ids": [row["hash"] for row in positive + negative],
    }


def offered_instructors(term_data):
    derived = term_data["derived"]
    names = derived["lecture_instructors"] or derived["all_instructors"]
    return {instructor_key(name): name for name in names}


def assemble(archive_bytes, term, cohort, min_reviews, limit, verified):
    archive = json.loads(archive_bytes)
    term_name = archive["metadata"]["term_names"].get(term)
    if not term_name:
        raise ValueError(f"Unknown academic term: {term}")
    topics = {code_key(row["course"]): row for row in read_csv("course_topics.csv")}
    reviews = defaultdict(lambda: defaultdict(dict))
    instructor_rows = read_csv("review_instructor_labels.csv")
    attributions = Counter(row["hash"] for row in instructor_rows)
    for row in instructor_rows:
        if row["semester"] != term_name or row["instructor"] == "Unknown instructor" or attributions[row["hash"]] != 1:
            continue
        reviews[code_key(row["course"])][instructor_key(row["instructor"])][row["hash"]] = row
    eligible_count, matched_count = 0, 0
    courses = []
    for code, info in archive["courses"].items():
        offering = info["terms"].get(term)
        if not offering or cohort not in offering["cc_by_cohort"]:
            continue
        eligible_count += 1
        scheduled = offered_instructors(offering)
        matches = {
            name: list(group.values())
            for name, group in reviews.get(code, {}).items() if name in scheduled
        }
        if not matches:
            continue
        matched_count += 1
        instructor, rows = min(matches.items(), key=lambda item: (-len(item[1]), item[0]))
        if len(rows) < min_reviews:
            continue
        evidence = verified.get((code, term, instructor), {})
        topic_row = topics.get(code, {})
        categories = sorted(set(topic_row.get("topic_categories", "").split("; ")) & TOPIC_LABELS.keys())
        urls = offering["provenance"]["official_cc_verified_urls"]
        official = next((url for url in urls if f"/{cohort}#" in url), offering["provenance"]["official_subject_url"])
        courses.append({
            "course_code": code, "title": offering["schedule"]["title"], "term_code": term,
            "instructor": scheduled[instructor], "cc_areas": [x["area"] for x in offering["cc_by_cohort"][cohort]],
            "description": offering["schedule"]["description"], "official_url": official,
            "review_url": f"https://ust.space/review/{code}",
            "review_count": len(rows), "review_ids": sorted(row["hash"] for row in rows),
            "assessment": {field: assessment_signal(rows, field, evidence.get(field)) for field in ASSESSMENTS},
            "workload": categorical_signal(rows, "workload", LEVELS),
            "teaching": categorical_signal(rows, "teaching_clarity", TEACHING),
            "topics": categories,
        })
    courses.sort(key=lambda c: (-c["review_count"], c["course_code"]))
    if limit:
        courses = courses[:limit]
    if not courses:
        raise ValueError("No eligible course has enough same-term, same-instructor reviews for this pool.")
    return {
        "term_code": term, "term_name": term_name, "cohort": cohort,
        "archive_date_hkt": archive["metadata"]["collected_date_hkt"],
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "eligible_course_count": eligible_count, "matched_instructor_course_count": matched_count,
        "minimum_reviews": min_reviews, "courses": sorted(courses, key=lambda c: c["course_code"]),
    }


def read_verified(path):
    if path is None:
        return {}
    verified = {}
    for row in json.loads(path.read_text(encoding="utf-8")):
        key = (code_key(row["course_code"]), row["term_code"], instructor_key(row["instructor"]))
        field = row["field"]
        if field not in ASSESSMENTS or row["value"] not in {"yes", "no"} or not row["note"].strip():
            raise ValueError(f"Invalid verified assessment: {key} / {field}")
        if not row["source"].startswith("https://"):
            raise ValueError(f"Missing HTTPS evidence source: {key} / {field}")
        fields = verified.setdefault(key, {})
        if field in fields:
            raise ValueError(f"Duplicate verified assessment: {key} / {field}")
        fields[field] = row
    return verified


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Seven-term cc_courses_merged.json snapshot")
    parser.add_argument("--term", required=True, help="Official term code, e.g. 2530")
    parser.add_argument("--cohort", required=True, help="Official CC cohort, e.g. CC25")
    parser.add_argument("--min-reviews", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of courses; zero keeps all matches")
    parser.add_argument("--verified", type=Path, help="Verified assessment overrides for specific course offerings")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.min_reviews < 1 or args.limit < 0:
        parser.error("Expected --min-reviews >= 1 and --limit >= 0.")
    try:
        data = assemble(args.archive.read_bytes(), args.term, args.cohort, args.min_reviews, args.limit, read_verified(args.verified))
    except ValueError as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(data['courses'])} selected of {data['eligible_course_count']} cohort CC courses; "
          f"{data['matched_instructor_course_count']} courses with matching reviews.")


if __name__ == "__main__":
    main()
