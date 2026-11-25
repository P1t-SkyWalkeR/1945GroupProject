"""Resolve review and evidence names against the corresponding course offering."""

import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd


UNKNOWN = "Unknown instructor"
TEACHER_DIMS = ("teaching_clarity", "grading_leniency", "participation", "recording")
TITLES = ("prof", "professor", "dr", "doctor", "mr", "mister", "ms", "mrs", "teacher")
OTHER_TEACHERS = re.compile(r"\b(?:the\s+)?other\s+(?:two|lecturers?|teachers?|professors?|instructors?)\b", re.I)


def course_key(value):
    return "".join(value.split()).upper()


def words(value):
    plain = "".join(
        ch for ch in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(ch)
    )
    return tuple(re.findall(r"[^\W\d_]+", plain))


def canonicalize(name, variants):
    return variants.get(words(name), name.strip())


def split_names(value):
    return {name.strip() for name in value.split(";") if name.strip() and name.strip() != UNKNOWN}


def alias_patterns(candidates, confirmed):
    """Use whole names, title-prefixed surnames, and manually confirmed aliases."""
    patterns = defaultdict(set)
    for name in candidates:
        surname, comma, given = name.partition(",")
        forms = {words(name)}
        if comma:
            forms.add(words(given) + words(surname))
            # A short name on its own is relevant only with an instructor title.
            short = {words(surname), words(given)} | {(w,) for w in words(given) if len(w) >= 3}
            for title in TITLES:
                for span in short:
                    if span:
                        patterns[(title,) + span].add(name)
        for span in forms:
            if len(span) > 1:
                patterns[span].add(name)
                for title in TITLES:
                    patterns[(title,) + span].add(name)
    for alias, targets in confirmed.items():
        relevant = set(targets) & candidates
        if alias and relevant:
            patterns[alias].update(relevant)
            for title in TITLES:
                patterns[(title,) + alias].update(relevant)
    return patterns


def named_instructors(evidence, patterns):
    """Find names as complete words, preferring a full name over an overlapping short form."""
    tokens = words(evidence)
    widths = sorted({len(key) for key in patterns}, reverse=True)
    matches = set()
    start = 0
    while start < len(tokens):
        for width in widths:
            if found := patterns.get(tokens[start:start + width]):
                matches.update(found)
                start += width
                break
        else:
            start += 1
    return matches


def review_teacher(registered, confirmed_in_text, lecturers, roster_complete):
    """Return a unique review owner where the evidence supports one."""
    if len(confirmed_in_text) == 1:
        return next(iter(confirmed_in_text)), "identified_in_review"
    if len(registered) == 1:
        return next(iter(registered)), "registered_instructor"
    if len(lecturers) == 1 and roster_complete and not registered and not confirmed_in_text:
        return next(iter(lecturers)), "sole_semester_lecturer"
    return None, ""


def resolve_reviews(reviews, labels, cleaned: Path):
    """Resolve known owners and flag evidence whose individual owner remains unclear."""
    instructor_map = pd.read_csv(cleaned / "review_instructor_map.csv", keep_default_na=False)
    references = cleaned / "review"
    archive = json.loads((references / "semester_instructors.json").read_text(encoding="utf-8"))
    rosters = {(r["course"], r["semester"]): r for r in archive["rosters"]}
    variants = {}
    for name in [
        *(n for r in archive["rosters"] for n in r["lecturers"]),
        *(n for n in instructor_map.instructor if n != UNKNOWN),
    ]:
        variants.setdefault(words(name), name)
    name_variants = references / "instructor_name_variants.csv"
    if name_variants.exists():
        for r in pd.read_csv(name_variants, keep_default_na=False).itertuples():
            variants[words(r.canonical)] = r.canonical
            variants[words(r.variant)] = r.canonical

    aliases = defaultdict(lambda: defaultdict(set))
    for r in pd.read_csv(references / "instructor_fill.csv", keep_default_na=False).itertuples():
        for name in split_names(r.resolved_instructor):
            aliases[r.course][words(r.instructor_in_text)].add(canonicalize(name, variants))
    registered = defaultdict(set)
    for r in instructor_map.itertuples():
        if r.instructor and r.instructor != UNKNOWN:
            registered[r.hash].add(canonicalize(r.instructor, variants))

    resolutions = {}
    label_map = labels.set_index("hash")
    for review in reviews.itertuples():
        label = label_map.loc[review.hash]
        course = course_key(review.course)
        roster = rosters.get((course, review.semester), {})
        lecturers = {canonicalize(name, variants) for name in roster.get("lecturers", [])}
        enrolled = registered[review.hash]
        known_names = lecturers | enrolled
        text_alias = aliases[course].get(words(label.instructor_in_text), set())
        patterns = alias_patterns(known_names | text_alias, aliases[course])
        identified = named_instructors(label.instructor_in_text, patterns)
        base, reason = review_teacher(
            enrolled, identified, lecturers, bool(lecturers) and roster["unnamed_sections"] == 0,
        )
        targets = {}
        for dimension in TEACHER_DIMS:
            if label[dimension] == "unknown":
                continue
            explicit = named_instructors(label[f"{dimension}_evidence"], patterns)
            comparison = (label[dimension] == "mixed" and len(known_names) > 1
                          and OTHER_TEACHERS.search(label[f"{dimension}_evidence"]))
            if len(explicit) > 1 or comparison:
                targets[dimension] = (None, "ambiguous_evidence")
            elif len(explicit) == 1:
                targets[dimension] = (next(iter(explicit)), "evidence_name")
            else:
                targets[dimension] = (base, reason)
        resolutions[review.hash] = {
            "owner": base, "reason": reason,
            "semester_lecturers": sorted(lecturers), "enrolled_instructors": sorted(enrolled),
            "targets": targets,
        }
    return resolutions
