"""Bundle the frozen pool, page, and ranking logic into a single offline HTML file."""

import argparse
import json
from pathlib import Path

from evaluate import load_selection
from recommender import ANSWERS, ASSESSMENTS, LEVELS, TEACHING, TOPIC_LABELS, version_weights


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "preview"
POOL = ROOT / "recommendation" / "pool.json"


def page_data(pool, version, include_teaching, selected):
    courses = []
    for course in pool["courses"]:
        # Readers can find the original reviews through the source links. The
        # standalone preview needs the labels and counts, not review IDs or prose.
        fields = ("course_code", "title", "instructor", "review_count", "topics", "description", "official_url", "review_url")
        exported = {key: course[key] for key in fields}
        exported["assessment"] = {
            name: {key: detail[key] for key in ("value", "verified", "note", "source")}
            for name, detail in course["assessment"].items()
        }
        for signal in ("workload", "teaching"):
            exported[signal] = {key: course[signal][key] for key in ("value", "n")}
        courses.append(exported)
    return {
        "term": pool["term_name"], "cohort": pool["cohort"], "version": version, "selected": selected,
        "weights": version_weights(include_teaching)[version],
        "assessments": ASSESSMENTS, "answers": ANSWERS, "levels": LEVELS, "teaching": TEACHING,
        "topics": TOPIC_LABELS, "courses": courses,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--version", choices="ABC")
    mode.add_argument("--selection", type=Path, help="Use the version selected on the development profiles.")
    args = parser.parse_args()
    pool_bytes = POOL.read_bytes()
    version, include_teaching = args.version or "C", True
    if args.selection:
        selection = load_selection(args.selection, pool_bytes)
        version, include_teaching = selection["version"], selection["include_teaching"]
    data = page_data(json.loads(pool_bytes), version, include_teaching, args.selection is not None)
    # Keep source strings inside the JSON script's text node.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    template = (FRONTEND / "test_preview.html").read_text(encoding="utf-8")
    script = (FRONTEND / "test_preview.mjs").read_text(encoding="utf-8")
    rendered = template.replace("<!-- PREVIEW_SCRIPT -->", script).replace("<!-- PREVIEW_DATA -->", payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
