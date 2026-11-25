"""Shared eligibility rules and ranking for the local demo and evaluation."""

import math
from fractions import Fraction


ASSESSMENTS = {
    "final": "Final exam or final test",
    "presentation": "Required graded presentation",
    "group_project": "Required group work",
}
ANSWERS = {
    "any": "No preference",
    "prefer_no": "Prefer to avoid",
    "prefer_yes": "Prefer to have",
    "require_no": "Must not have",
    "require_yes": "Must have",
}
LEVELS = {"low": 0.0, "medium": 0.5, "high": 1.0}
TEACHING = {"unclear": 0.0, "mixed": 0.5, "clear": 1.0}
TOPIC_LABELS = {
    "arts_music_film": "Arts, music and film",
    "business_finance": "Business and finance",
    "computing_programming": "Computing and programming",
    "economics": "Economics",
    "engineering_technology": "Engineering and technology",
    "environment_sustainability": "Environment and sustainability",
    "history_culture": "History and culture",
    "language_literature_writing": "Language, literature and writing",
    "life_sciences_health": "Life sciences and health",
    "management_entrepreneurship": "Management and entrepreneurship",
    "mathematics_statistics": "Mathematics and statistics",
    "philosophy_religion": "Philosophy and religion",
    "physical_sciences": "Physical sciences",
    "social_sciences": "Social sciences",
}


def version_weights(include_teaching=True):
    if include_teaching:
        return {
            "A": {"assessment": 1},
            "B": {"assessment": 0.60, "workload": 0.30, "teaching": 0.10},
            "C": {"assessment": 0.45, "workload": 0.225, "teaching": 0.075, "topic": 0.25},
        }
    return {
        "A": {"assessment": 1},
        "B": {"assessment": 0.60, "workload": 0.40},
        "C": {"assessment": 0.45, "workload": 0.30, "topic": 0.25},
    }


def validate_profile(profile):
    if not isinstance(profile, dict):
        raise ValueError("A preference profile must be an object.")
    assessment = profile.get("assessment", {})
    if not isinstance(assessment, dict) or set(assessment) - ASSESSMENTS.keys():
        raise ValueError("Invalid assessment preference field.")
    if any(v not in ANSWERS for v in assessment.values()):
        raise ValueError("Invalid assessment preference value.")
    if profile.get("workload", "any") not in {"any", *LEVELS}:
        raise ValueError("Invalid preferred workload.")
    topics = profile.get("topics", [])
    if not isinstance(topics, list) or set(topics) - TOPIC_LABELS.keys():
        raise ValueError("Invalid topic preference.")


def hard_filter(course, profile):
    failures = []
    for field, answer in profile.get("assessment", {}).items():
        if not answer.startswith("require_"):
            continue
        expected = answer.removeprefix("require_")
        evidence = course["assessment"][field]
        if not evidence["verified"] or evidence["value"] == "unknown":
            failures.append({"field": field, "reason": "unverified", "expected": expected})
        elif evidence["value"] != expected:
            failures.append({"field": field, "reason": "mismatch", "expected": expected})
    return failures


def rank(pool, profile, version, include_teaching=True):
    """Return full eligible ranking and audited exclusions for one version."""
    validate_profile(profile)
    weights = version_weights(include_teaching)[version]
    ranked, excluded = [], []
    for course in pool:
        failures = hard_filter(course, profile)
        if failures:
            excluded.append({"course_code": course["course_code"], "conditions": failures})
            continue
        assessment_scores = []
        unknown = []
        reasons = []
        for field, answer in profile.get("assessment", {}).items():
            if not answer.startswith(("prefer_", "require_")):
                continue
            value = course["assessment"][field]["value"]
            if answer.startswith("require_"):
                reasons.append(f"{ASSESSMENTS[field]}: required condition verified.")
                continue
            if value == "unknown":
                assessment_scores.append(0.5)
                unknown.append(ASSESSMENTS[field])
                continue
            match = value == answer.removeprefix("prefer_")
            assessment_scores.append(float(match))
            source = "verified" if course["assessment"][field]["verified"] else "review evidence"
            reasons.append(f"{ASSESSMENTS[field]}: {'matches' if match else 'differs from'} your preference ({source}).")
        scores = {"assessment": sum(assessment_scores) / len(assessment_scores) if assessment_scores else 0.5}
        if "workload" in weights:
            preferred = profile.get("workload", "any")
            observed = course["workload"]["value"]
            scores["workload"] = 0.5
            if preferred in LEVELS:
                if observed in LEVELS:
                    scores["workload"] = 1 - max(0, LEVELS[observed] - LEVELS[preferred])
                    reasons.append(f"Workload: {observed}, based on {course['workload']['n']} labeled reviews.")
                else:
                    unknown.append("Workload")
        if "teaching" in weights:
            observed = course["teaching"]["value"]
            scores["teaching"] = TEACHING.get(observed, 0.5)
            if observed in TEACHING:
                reasons.append(f"Teaching clarity: {observed}, based on {course['teaching']['n']} labeled reviews.")
            else:
                unknown.append("Teaching clarity")
        if "topic" in weights:
            interests = set(profile.get("topics", []))
            course_topics = set(course["topics"])
            scores["topic"] = 0.5
            if interests:
                if course_topics:
                    shared = interests & course_topics
                    scores["topic"] = len(shared) / math.sqrt(len(interests) * len(course_topics))
                    if shared:
                        reasons.append("Interest match: " + ", ".join(TOPIC_LABELS[tag] for tag in sorted(shared)) + ".")
                    else:
                        reasons.append("No overlap with your selected topics.")
                else:
                    unknown.append("Topics")
        score = round(sum(weights[k] * v for k, v in scores.items()), 12)
        ranked.append({"course": course, "score": score, "components": scores, "missing": unknown, "reasons": reasons})
    ranked.sort(key=lambda row: (-row["score"], len(row["missing"]), row["course"]["course_code"]))
    return {"ranked": ranked, "recommendations": ranked[:3], "excluded": excluded}


def metrics(ranking, judgments):
    """Use a complete adjudicated pool keyed by full course code."""
    eligible = {r["course"]["course_code"] for r in ranking["ranked"]}
    excluded = {r["course_code"]: r["conditions"] for r in ranking["excluded"]}
    if set(judgments) != eligible | excluded.keys():
        raise ValueError("Judgments must cover exactly the entire frozen candidate pool.")
    recommended = [r["course"]["course_code"] for r in ranking["recommendations"]]
    suitable = {code for code, row in judgments.items() if row["fit"] == "2"}
    hits = suitable.intersection(recommended)
    return {
        "precision_at_3": len(hits) / 3,
        "recall_at_3": len(hits) / len(suitable) if suitable else None,
        "recommended": recommended,
        "suitable_returned": len(hits),
        "suitable_in_pool": len(suitable),
        "unresolved_in_pool": sum(r["fit"] == "unresolved" for r in judgments.values()),
        "unresolved_recommendations": sum(judgments[c]["fit"] == "unresolved" for c in recommended),
        "hard_violations": sum(judgments[c]["hard_status"] == "fail" for c in recommended),
        "missed_suitable": [
            {"course_code": code, "stage": "filter" if code in excluded else "rank", "conditions": excluded.get(code, [])}
            for code in sorted(suitable - hits)
        ],
        "lower_fit_recommendations": [code for code in recommended if judgments[code]["fit"] in {"0", "1"}],
    }


def select_version(development_results):
    """Choose on development judgments only, with exact tie handling."""
    candidates = [
        (Fraction(sum(row["suitable_returned"] for row in rows), 3 * len(rows)), version)
        for version, rows in development_results.items() if rows and all(row["hard_violations"] == 0 for row in rows)
    ]
    if not candidates:
        raise ValueError("No version passed the development hard-condition check.")
    return sorted(candidates, key=lambda item: (-item[0], item[1]))[0][1]
