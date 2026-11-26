"""Bundle the frozen pool or full catalog into a single offline HTML file."""

import argparse
import json
from base64 import b64encode
from html import escape
from pathlib import Path

from evaluate import load_selection
from recommender import ANSWERS, ASSESSMENTS, LEVELS, TEACHING, TOPIC_LABELS, version_weights


ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "preview"
POOL = ROOT / "recommendation" / "pool.json"
RANK_IMPORT = 'import {rankPreview} from "./ranking.mjs";\n'
CATALOG_DESIGNS = {
    "orbit": ("catalog.html", "<!-- HERO_ART -->", "course-orbit.jpg"),
    "workspace": ("workspace.html", "<!-- WORKSPACE_ART -->", "workspace-sheets.png"),
}
TOPIC_SYMBOLS = {
    "arts_music_film": "✦",
    "business_finance": "↗",
    "computing_programming": "⌘",
    "economics": "∿",
    "engineering_technology": "⊞",
    "environment_sustainability": "❧",
    "history_culture": "◷",
    "language_literature_writing": "Aa",
    "life_sciences_health": "+",
    "management_entrepreneurship": "◈",
    "mathematics_statistics": "∑",
    "philosophy_religion": "◇",
    "physical_sciences": "⊙",
    "social_sciences": "∴",
}


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


def picker_markup(name, label, options, control_id=None):
    options = list(options)
    control_id = control_id or name
    choices = "".join(
        f'<label><input type="radio" name="{escape(name)}" value="{escape(value)}"'
        f'{" checked" if index == 0 else ""}>{escape(text)}</label>'
        for index, (value, text) in enumerate(options)
    )
    selected = options[0][1]
    return (f'<fieldset class="field"><legend>{escape(label)}</legend>'
            f'<details class="picker" id="{escape(control_id)}"><summary aria-label="{escape(f"{label}: {selected}")}">'
            f'{escape(selected)}</summary>'
            f'<div class="picker-options">{choices}</div></details></fieldset>')


def workload_markup():
    options = [("any", "Any"), *((level, level.title()) for level in LEVELS)]
    choices = "".join(
        f'<label><input class="sr-only" type="radio" name="workload" value="{level}"'
        f'{" checked" if level == "any" else ""}><span class="workload-option">'
        f'<span class="load-bars" data-level="{level}" aria-hidden="true">'
        f'<span></span><span></span><span></span></span>{label}</span></label>'
        for level, label in options
    )
    return ('<fieldset class="workload-field" id="workload"><legend>Maximum workload</legend>'
            f'<div class="workload-grid">{choices}</div></fieldset>')


def catalog_controls(template, data):
    terms = list(reversed(data["catalog"]["terms"]))
    preferences = "".join(
        picker_markup(field, label, data["answers"].items())
        for field, label in data["assessments"].items()
    )
    topics = "".join(
        f'<label><span class="topic-symbol" aria-hidden="true">{TOPIC_SYMBOLS.get(topic, "◇")}</span>'
        f'<span>{escape(label)}</span><input type="checkbox" name="topic" value="{escape(topic)}"></label>'
        for topic, label in data["topics"].items()
    )
    cohorts = [("all", "All curricula"), *((value, value) for value in terms[0]["cohorts"])]
    term_field = picker_markup("term", "Academic term", ((term["code"], term["display_name"]) for term in terms),
                               "catalog-term")
    term_range = f'{terms[-1]["display_name"]}–{terms[0]["display_name"]}'
    return (template.replace("<!-- TERM_FIELD -->", term_field)
            .replace("<!-- COHORT_FIELD -->", picker_markup("cohort", "Common Core curriculum", cohorts, "catalog-cohort"))
            .replace("<!-- AREA_FIELD -->", picker_markup("area", "Common Core area", [("all", "All areas")], "catalog-area"))
            .replace("<!-- TERM_RANGE -->", escape(term_range))
            .replace("<!-- WORKLOAD_FIELD -->", workload_markup())
            .replace("<!-- PREFERENCE_FIELDS -->", preferences)
            .replace("<!-- TOPIC_FIELDS -->", topics))


def calendar_term_name(name):
    academic_year, season = name.split(" ", 1)
    first_year = int(academic_year.split("-")[0])
    calendar_year = first_year + (season == "Spring")
    return f"{calendar_year} {season}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, help="Use an all-term catalog from build_catalog.py.")
    parser.add_argument("--catalog-design", choices=CATALOG_DESIGNS, default="orbit", help="Template for the full catalog.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--version", choices="ABC")
    mode.add_argument("--selection", type=Path, help="Use the version selected on the development profiles.")
    args = parser.parse_args()
    version, include_teaching = args.version or "C", True
    if args.catalog and args.selection:
        parser.error("--selection applies to the frozen study pool only.")
    if not args.catalog and args.catalog_design != "orbit":
        parser.error("--catalog-design requires --catalog.")
    if args.selection:
        selection = load_selection(args.selection, POOL.read_bytes())
        version, include_teaching = selection["version"], selection["include_teaching"]
    if args.catalog:
        catalog = json.loads(args.catalog.read_bytes())
        for term in catalog["terms"]:
            term["display_name"] = calendar_term_name(term["name"])
        assessments = catalog.get("assessments", ASSESSMENTS) if args.catalog_design == "workspace" else ASSESSMENTS
        data = {
            "catalog": catalog,
            "version": version, "weights": version_weights(include_teaching)[version],
            "assessments": assessments, "answers": ANSWERS, "levels": LEVELS, "teaching": TEACHING,
            "topics": TOPIC_LABELS,
        }
        template_name, asset_marker, asset_name = CATALOG_DESIGNS[args.catalog_design]
        template = catalog_controls((FRONTEND / template_name).read_text(encoding="utf-8"), data)
        asset = b64encode((FRONTEND / asset_name).read_bytes()).decode("ascii")
        template = template.replace(asset_marker, asset)
        frontend = (FRONTEND / "catalog.mjs").read_text(encoding="utf-8").removeprefix(RANK_IMPORT)
    else:
        data = page_data(json.loads(POOL.read_bytes()), version, include_teaching, args.selection is not None)
        template = (FRONTEND / "test_preview.html").read_text(encoding="utf-8")
        frontend = (FRONTEND / "test_preview.mjs").read_text(encoding="utf-8").removeprefix(RANK_IMPORT)
        frontend = frontend.removeprefix("export {rankPreview};\n")
    ranking = (FRONTEND / "ranking.mjs").read_text(encoding="utf-8")
    script = ranking + "\n" + frontend
    if args.catalog:
        # An inline classic script can start directly from file://, with no module loading.
        script = script.replace("export function ", "function ")
    # Keep source strings inside the JSON script's text node.
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    rendered = template.replace("<!-- PREVIEW_SCRIPT -->", script).replace("<!-- PREVIEW_DATA -->", payload)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
