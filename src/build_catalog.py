"""Build the full, term-specific CC catalog from the collected schedule snapshot."""

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

from build_recommendation_pool import (
    assessment_signal,
    categorical_signal,
    code_key,
    instructor_key,
    offered_instructors,
    read_csv,
    read_verified,
)
from recommender import LEVELS, TEACHING, TOPIC_LABELS


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "recommendation" / "catalog.json"
VERIFIED = ROOT / "recommendation" / "verified_assessments.json"
MIDTERM_VERIFIED = ROOT / "recommendation" / "catalog_verified_midterms.json"
WORKSPACE_ASSESSMENTS = {
    "midterm": "Midterm exam",
    "final": "Final exam",
    "presentation": "Graded presentation",
    "group_project": "Group work",
}


def build_catalog(archive_bytes, verified, instructor_rows, topic_rows):
    archive = json.loads(archive_bytes)
    metadata = archive["metadata"]
    term_codes = {name: code for code, name in metadata["term_names"].items()}
    reviews = defaultdict(dict)
    for row in instructor_rows:
        term = term_codes.get(row["semester"])
        if term and row["attribution_scope"] == "instructor":
            key = (code_key(row["course"]), term, instructor_key(row["instructor"]))
            reviews[key][row["hash"]] = row

    topics = {
        code_key(row["course"]): sorted(set(row["topic_categories"].split("; ")) & TOPIC_LABELS.keys())
        for row in topic_rows
    }
    coverage = {row["term_code"]: row for row in metadata["coverage"]}
    cohorts_by_term = defaultdict(set)
    courses = {}
    for code, course in sorted(archive["courses"].items()):
        offerings = {}
        for term, offering in sorted(course["terms"].items()):
            schedule = offering["schedule"]
            provenance = offering["provenance"]
            cohorts = {
                cohort: sorted({attribute["area"] for attribute in attributes})
                for cohort, attributes in sorted(offering["cc_by_cohort"].items())
            }
            cohorts_by_term[term].update(cohorts)
            scheduled = {
                key: name for key, name in offered_instructors(offering).items()
                if key and key != "tba"
            }
            profiles = []
            for instructor, name in (scheduled or {"": "Instructor unlisted"}).items():
                key = (code, term, instructor)
                rows = list(reviews[key].values())
                evidence = verified.get(key, {})
                assessment = {}
                for field in WORKSPACE_ASSESSMENTS:
                    detail = assessment_signal(rows, field, evidence.get(field))
                    assessment[field] = {key: detail[key] for key in ("value", "verified", "note", "source")}
                signals = {
                    name: categorical_signal(rows, field, allowed)
                    for name, field, allowed in (
                        ("workload", "workload", LEVELS), ("teaching", "teaching_clarity", TEACHING),
                    )
                }
                profiles.append({
                    "instructor": name,
                    "review_count": len(rows),
                    "assessment": assessment,
                    **{name: {key: signal[key] for key in ("value", "n")} for name, signal in signals.items()},
                })
            profiles.sort(key=lambda profile: (-profile["review_count"], profile["instructor"]))
            offerings[term] = {
                "title": schedule["title"],
                "description": schedule["description"],
                "credits": schedule["credits"],
                "cohorts": cohorts,
                "official_url": provenance["official_subject_url"],
                "section_count": offering["derived"]["section_count"],
                "rankings_url": provenance["rankings_detail_url"],
                "ratings": {
                    criterion: {key: row[key] for key in ("rating", "bayesian", "samples", "evidence_status")}
                    for criterion, row in sorted(offering["ratings"].items())
                },
                "instructors": profiles,
            }
        courses[code] = {
            "topics": topics.get(code, []),
            "review_url": f"https://ust.space/review/{code}",
            "offerings": offerings,
        }

    return {
        "archive_date_hkt": metadata["collected_date_hkt"],
        "archive_sha256": hashlib.sha256(archive_bytes).hexdigest(),
        "schedule_archive_url": archive["sources"]["schedule_courses"]["url"],
        "terms": [
            {
                "code": term,
                "name": metadata["term_names"][term],
                "cohorts": sorted(cohorts_by_term[term]),
                "official_schedule_verified": coverage[term]["live_official_course_list_match"],
            }
            for term in metadata["term_codes"]
        ],
        "courses": courses,
        "assessments": WORKSPACE_ASSESSMENTS,
        "rating_criteria": archive["criteria"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True, help="Collected cc_courses_merged.json snapshot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    verified = read_verified(VERIFIED)
    for key, assignments in read_verified(MIDTERM_VERIFIED, {"midterm"}).items():
        verified.setdefault(key, {}).update(assignments)
    catalog = build_catalog(
        args.archive.read_bytes(),
        verified,
        read_csv("review_instructor_labels.csv"),
        read_csv("course_topics.csv"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(catalog, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n",
                           encoding="utf-8")
    print(f"{args.output}: {len(catalog['courses'])} courses, "
          f"{sum(len(course['offerings']) for course in catalog['courses'].values())} course-term records.")


if __name__ == "__main__":
    main()
