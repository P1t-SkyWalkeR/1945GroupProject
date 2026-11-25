"""Extract lecturers for the exact course and semester pairs in the review corpus."""

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REVISION = "d35538fc2358b0460ed90c8c196049b328857689"
ARCHIVE_URL = f"https://huggingface.co/datasets/ust-archive/schedule/resolve/{REVISION}/canonical/class_records.parquet"
ARCHIVE_SHA256 = "f3b51394177aacea52e8c9f6ecf8c8c86124a825236b2db79816c54f53bc7157"
PLACEHOLDERS = {"", "tba", "tbc", "tbd", "to be announced", "to be confirmed", "staff", "instructor", "unknown instructor"}
LECTURE_SECTION = re.compile(r"L[0-9]+[A-Z]?$", re.I)


def extract_rosters(parquet, pairs):
    import duckdb

    db = duckdb.connect()
    db.read_parquet(str(parquet)).create_view("archive_classes")
    db.execute("CREATE TABLE review_terms(course VARCHAR, semester VARCHAR)")
    db.executemany("INSERT INTO review_terms VALUES (?, ?)", sorted(pairs))
    classes = db.execute("""
        SELECT term_code, term_name, course, section, type, schedules
        FROM (
            SELECT a.*, r.course, row_number() OVER (
                PARTITION BY term_code, r.course, section, number
                ORDER BY timestamp DESC NULLS LAST, source_order DESC NULLS LAST,
                         CASE WHEN version = 'api' THEN 0 ELSE 1 END, status ASC
            ) AS event_rank
            FROM archive_classes a
            JOIN review_terms r ON a.term_name = r.semester AND a.prefix || a.course_number = r.course
        )
        WHERE event_rank = 1 AND status = 'ACTIVE'
    """).fetchall()
    by_term = defaultdict(list)
    for term, semester, course, section, kind, schedules in classes:
        if kind == "LEC" or (not kind and LECTURE_SECTION.fullmatch(section or "")):
            people = {
                n.strip() for event in (schedules or []) for n in (event["instructors"] or [])
                if n and n.strip().casefold() not in PLACEHOLDERS
            }
            by_term[course, semester].append((term, people))
    rosters = []
    for course, semester in sorted(pairs):
        lectures = by_term[course, semester]
        names = sorted({name for _, group in lectures for name in group}, key=str.casefold)
        rosters.append({
            "course": course, "semester": semester, "term_code": lectures[0][0] if lectures else "",
            "lecturers": names, "lecture_sections": len(lectures),
            "unnamed_sections": sum(not group for _, group in lectures),
        })
    return rosters


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("parquet", type=Path, help=ARCHIVE_URL)
    parser.add_argument("--output", type=Path, default=ROOT / "cleaned/review/semester_instructors.json")
    args = parser.parse_args()
    checksum = hashlib.sha256(args.parquet.read_bytes()).hexdigest()
    if checksum != ARCHIVE_SHA256:
        parser.error("The Parquet checksum differs from the pinned archive.")
    with (ROOT / "cleaned/reviews_clean.csv").open(encoding="utf-8-sig", newline="") as stream:
        pairs = {("".join(r["course"].split()).upper(), r["semester"]) for r in csv.DictReader(stream)}
    rosters = extract_rosters(args.parquet, pairs)
    args.output.write_text(json.dumps({
        "source_archive": ARCHIVE_URL, "source_sha256": checksum, "rosters": rosters,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{sum(bool(r['lecturers']) for r in rosters)}/{len(rosters)} course-semester pairs have named lecturers.")


if __name__ == "__main__":
    main()
