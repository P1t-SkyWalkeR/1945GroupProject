"""Run the UST Course Vibe Match questionnaire on localhost."""

import argparse
import json
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from recommender import ANSWERS, ASSESSMENTS, LEVELS, TOPIC_LABELS, rank, validate_profile


STYLE = """
:root{color-scheme:light;--ink:#1a2c2d;--green:#155d52;--line:#d4e1dd}
*{box-sizing:border-box}body{margin:0;background:#f1f6f3;color:var(--ink);
font:16px/1.5 system-ui,sans-serif}main{width:min(100% - 2rem,820px);margin:3rem auto}
h1{font-size:clamp(2rem,7vw,3.4rem);line-height:1;margin:.4em 0}h2{margin-top:1.5rem}
form,article,details.audit{background:white;border:1px solid var(--line);border-radius:14px;padding:1.25rem;margin:1rem 0}
.fields,.topics{display:grid;grid-template-columns:repeat(auto-fit,minmax(175px,1fr));gap:.8rem}
label{display:block}select{margin-top:.25rem;width:100%}select,button{font:inherit;border-radius:7px;padding:.45rem}
fieldset{margin:1rem 0;border:1px solid var(--line)}button{background:var(--green);color:white;border:0;
padding:.5rem 1rem;cursor:pointer}a{color:var(--green)}summary{cursor:pointer}.muted{color:#435d5a}
ul{padding-left:1.4rem}blockquote{margin:.6rem 0;padding-left:.8rem;border-left:2px solid var(--line)}
"""


def options(values, selected):
    return "".join(f'<option value="{key}"{" selected" if key == selected else ""}>{label}</option>'
                   for key, label in values.items())


def source_link(url, label):
    if not url.startswith("https://"):
        return escape(label)
    return f'<a href="{escape(url, quote=True)}">{escape(label)}</a>'


def course_card(row):
    c = row["course"]
    reasons = "".join(f"<li>{escape(item)}</li>" for item in row["reasons"])
    if row["missing"]:
        reasons += f'<li>Evidence unavailable or disputed: {escape(", ".join(row["missing"]))}.</li>'
    sources = []
    for key, label in ASSESSMENTS.items():
        evidence = c["assessment"][key]
        url = evidence["source"]
        cite = f' {source_link(url, "Assessment source")}' if url else ""
        ids = f' Review IDs: {escape(", ".join(evidence["review_ids"]))}.' if evidence["review_ids"] else ""
        sources.append(f'<li>{label}: {escape(evidence["note"])}{cite}{ids}</li>')
    quotes = "".join(f'<blockquote>{escape(x["quote"])} <small>({escape(x["review_id"])})</small></blockquote>'
                     for k in ("workload", "teaching") for x in c[k]["examples"])
    return (
        f'<article><h3>{escape(c["course_code"])} · {escape(c["title"])}</h3>'
        f'<p class="muted">{escape(c["instructor"])} · {c["review_count"]} same-term matched reviews'
        f' · Ranking score {row["score"]:.3f}</p>'
        f'{"<ul>" + reasons + "</ul>" if reasons else ""}'
        f'<p>{source_link(c["official_url"], "Official CC schedule")} · '
        f'{source_link(c["review_url"], "USTSPACE course reviews")}</p>'
        f'<details><summary>Evidence and gaps</summary><p>{escape(c["description"])}</p>'
        f'<ul>{"".join(sources)}</ul>{quotes}</details></article>'
    )


def render(pool, profile, version, result=None, error=""):
    assessment = profile.get("assessment", {})
    selects = "".join(
        f'<label>{label}<select name="{key}">{options(ANSWERS, assessment.get(key, "any"))}</select></label>'
        for key, label in ASSESSMENTS.items()
    )
    work = options({"any": "No preference", **{x: x.title() for x in LEVELS}}, profile.get("workload", "any"))
    topics = "".join(
        f'<label><input type="checkbox" name="topic" value="{key}"'
        f'{" checked" if key in profile.get("topics", []) else ""}> {label}</label>'
        for key, label in TOPIC_LABELS.items()
    )
    results = ""
    if result is not None:
        picked = result["recommendations"]
        count = len(picked)
        summary = f"{count} course{'s' if count != 1 else ''} recommended"
        if count < 3:
            summary += f" · {len(result['ranked'])} met all required conditions"
        cards = "".join(course_card(row) for row in picked)
        blocked = "".join(
            f'<li>{escape(row["course_code"])} · ' + "; ".join(
                f'{ASSESSMENTS[condition["field"]]}: {condition["reason"]}'
                for condition in row["conditions"]
            ) + "</li>" for row in result["excluded"]
        )
        audit = (f'<details class="audit"><summary>Why {len(result["excluded"])} courses were excluded</summary>'
                 f'<ul>{blocked}</ul></details>') if blocked else ""
        results = f'<section id="results"><h2>{summary}</h2>{cards}{audit}</section>'
    alert = f'<p role="alert">{escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>UST Course Vibe Match</title><style>{STYLE}</style></head>
<body><main><h1>UST Course Vibe Match</h1>
<p class="muted">{escape(pool["term_name"])} · {escape(pool["cohort"])}
· {len(pool["courses"])} courses in this demo · Method {escape(version)}</p>
<p>Tell us what fits you. Required conditions need verified evidence for the displayed offering.</p>
<form method="post" action="/">{alert}<div class="fields">{selects}
<label>Maximum preferred workload<select name="workload">{work}</select></label></div>
<fieldset><legend>Topics you are interested in</legend><div class="topics">{topics}</div></fieldset>
<button type="submit">Find courses</button></form>{results}</main></body></html>"""


def serve(pool, version, include_teaching, port):
    class Handler(BaseHTTPRequestHandler):
        def respond(self, html, status=200):
            data = html.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            self.respond(render(pool, {}, version))

        def do_POST(self):
            if self.path != "/":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", 0))
                if not 0 < size <= 4096:
                    raise ValueError("Invalid form size.")
                values = parse_qs(self.rfile.read(size).decode("utf-8"), max_num_fields=32)
                profile = {
                    "assessment": {field: values.get(field, ["any"])[0] for field in ASSESSMENTS},
                    "workload": values.get("workload", ["any"])[0],
                    "topics": values.get("topic", []),
                }
                validate_profile(profile)
            except ValueError:
                self.respond(render(pool, {}, version, error="Please choose a listed preference."), 400)
                return
            self.respond(render(pool, profile, version, rank(pool["courses"], profile, version, include_teaching)))

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(f"Open http://127.0.0.1:{server.server_port}", flush=True)
        server.serve_forever()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pool", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8000)
    model = parser.add_mutually_exclusive_group(required=True)
    model.add_argument("--version", choices="ABC", help="Preview an explicit method.")
    model.add_argument("--selection", type=Path, help="Use the method frozen by evaluation.")
    parser.add_argument("--include-teaching", action="store_true", help="For previews using the teaching variant.")
    args = parser.parse_args()
    pool_bytes = args.pool.read_bytes()
    version, include_teaching = args.version, args.include_teaching
    if args.selection:
        from evaluate import load_selection

        selection = load_selection(args.selection, pool_bytes)
        version, include_teaching = selection["version"], selection["include_teaching"]
    serve(json.loads(pool_bytes), version, include_teaching, args.port)


if __name__ == "__main__":
    main()
