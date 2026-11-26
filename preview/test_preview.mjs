import {rankPreview} from "./ranking.mjs";
export {rankPreview};


function text(tag, value, className = "") {
  const item = document.createElement(tag);
  item.textContent = value;
  if (className) item.className = className;
  return item;
}


function addOptions(select, choices) {
  for (const [value, label] of Object.entries(choices)) {
    select.add(new Option(label, value));
  }
}


function evidenceLink(label, href) {
  const anchor = text("a", label);
  if (href.startsWith("https://")) {
    anchor.href = href;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
  }
  return anchor;
}


function list(items) {
  const ul = document.createElement("ul");
  ul.append(...items.map(item => text("li", item)));
  return ul;
}


function renderCard(row, data) {
  const course = row.course;
  const card = document.createElement("article");
  card.className = "panel card";
  card.dataset.courseCode = course.course_code;
  card.append(text("h3", `${course.course_code} · ${course.title}`));
  const reviewWord = course.review_count === 1 ? "review" : "reviews";
  card.append(text("p", `${course.instructor} · ${course.review_count} same-term ${reviewWord} · Match score ${row.score.toFixed(3)}`, "muted card-meta"));
  const reasons = [...row.reasons];
  if (row.missing.length) reasons.push(`Evidence unavailable or disputed: ${row.missing.join(", ")}.`);
  if (reasons.length) card.append(list(reasons));
  const details = document.createElement("details");
  details.append(text("summary", "Course evidence"), text("p", course.description));
  const sources = document.createElement("ul");
  for (const [key, detail] of Object.entries(course.assessment)) {
    const item = text("li", `${data.assessments[key]}: ${detail.note} `);
    if (detail.source) item.append(evidenceLink("Syllabus", detail.source));
    sources.append(item);
  }
  details.append(sources);
  const links = document.createElement("p");
  links.append(evidenceLink("Official CC schedule", course.official_url), " · ", evidenceLink("USTSPACE reviews", course.review_url));
  details.append(links);
  card.append(details);
  return card;
}


function boot(data) {
  const form = document.getElementById("preferences");
  const results = document.getElementById("results");
  const title = document.getElementById("results-status");
  const feedback = document.getElementById("feedback");
  const feedbackStatus = document.getElementById("feedback-status");
  const consider = document.getElementById("consider");
  const examples = {
    light: {workload: "low", topics: ["computing_programming", "physical_sciences"]},
    group: {assessment: {group_project: "require_yes"}},
    noFinal: {assessment: {final: "require_no"}},
  };
  let current = null;
  let example = null;
  document.getElementById("scope").textContent =
    `${data.term} · ${data.cohort} · ${data.courses.length} courses · ${data.selected ? "Selected method" : "Preview method"} ${data.version}`;

  for (const [key, wording] of Object.entries(data.assessments)) {
    const label = text("label", wording);
    const select = document.createElement("select");
    select.name = key;
    addOptions(select, data.answers);
    label.append(select);
    document.getElementById("assessment-fields").append(label);
  }
  const workload = {any: "No preference", low: "Low", medium: "Medium", high: "High"};
  addOptions(form.elements.workload, workload);
  for (const [key, wording] of Object.entries(data.topics)) {
    const item = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "topic";
    input.value = key;
    item.append(input, text("span", wording));
    document.getElementById("topics").append(item);
  }

  function clear(message) {
    current = null;
    title.textContent = "Your matches";
    results.replaceChildren(text("p", message, "panel muted"));
    feedback.hidden = true;
    feedback.reset();
    feedbackStatus.textContent = "";
  }

  function showMatches() {
    const values = new FormData(form);
    const profile = {
      assessment: Object.fromEntries(Object.keys(data.assessments).map(key => [key, values.get(key)])),
      workload: values.get("workload"),
      topics: values.getAll("topic"),
    };
    const ranking = rankPreview(data, profile);
    const picked = ranking.recommendations;
    title.textContent = `${picked.length} ${picked.length === 1 ? "match" : "matches"}`;
    results.replaceChildren();
    if (!picked.length) {
      results.append(text("p", "No course in this pool meets your required conditions with verified evidence. You can change a requirement and try again.", "panel"));
    } else {
      results.append(...picked.map(row => renderCard(row, data)));
    }
    if (ranking.excluded.length) {
      const details = document.createElement("details");
      details.className = "panel";
      details.append(text("summary", `Why ${ranking.excluded.length} courses were excluded`));
      details.append(list(ranking.excluded.map(row =>
        `${row.course_code} · ${row.conditions.map(c =>
          `${data.assessments[c.field]}: ${c.reason === "unverified" ? "needs verified evidence" : "does not meet the requirement"}`
        ).join(" · ")}`)));
      results.append(details);
    }
    current = {scenario: example, profile, recommendations: picked.map(row => row.course.course_code)};
    feedback.reset();
    consider.replaceChildren(new Option("None or unsure", ""));
    for (const {course} of picked) {
      consider.add(new Option(`${course.course_code} · ${course.title}`, course.course_code));
    }
    feedbackStatus.textContent = "";
    feedback.hidden = false;
    title.focus();
  }

  form.addEventListener("submit", event => {
    event.preventDefault();
    showMatches();
  });
  form.addEventListener("reset", () => {
    example = null;
    clear("Choose an example or set your own preferences.");
  });
  form.addEventListener("change", () => {
    example = null;
    if (current) clear("Preferences changed. Find matches to see the new results.");
  });
  for (const button of document.querySelectorAll("[data-example]")) {
    button.addEventListener("click", () => {
      form.reset();
      example = button.dataset.example;
      const scenario = examples[example];
      for (const [key, value] of Object.entries(scenario.assessment || {})) form.elements[key].value = value;
      if (scenario.workload) form.elements.workload.value = scenario.workload;
      for (const input of form.querySelectorAll('[name="topic"]')) {
        input.checked = (scenario.topics || []).includes(input.value);
      }
      showMatches();
    });
  }
  feedback.addEventListener("submit", event => {
    event.preventDefault();
    if (!current) return;
    const values = new FormData(feedback);
    const now = new Date();
    const record = {
      schema: "vibe-match-usability-v1", term: data.term, cohort: data.cohort, method: data.version,
      completed_at: now.toISOString(), ...current, usefulness: Number(values.get("usefulness")),
      would_consider: values.get("consider") || null, notes: values.get("notes").trim(),
    };
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2) + "\n"], {type: "application/json"}));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `vibe-match-feedback-${now.getTime()}.json`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    feedbackStatus.textContent = "Feedback file saved. Send it back to the project team.";
  });
}


if (typeof document !== "undefined") {
  boot(JSON.parse(document.getElementById("preview-data").textContent));
}
