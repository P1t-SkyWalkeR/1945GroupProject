import {rankPreview} from "./ranking.mjs";

export function coursesInScope(catalog, term, cohort) {
  const courses = [];
  for (const [code, course] of Object.entries(catalog.courses)) {
    const offering = course.offerings[term.code];
    if (!offering || (cohort !== "all" && !Object.prototype.hasOwnProperty.call(offering.cohorts, cohort))) continue;
    const areas = cohort === "all" ? Object.values(offering.cohorts).flat() : offering.cohorts[cohort];
    courses.push({
      ...offering,
      course_code: code,
      topics: course.topics,
      review_url: course.review_url,
      areas: [...new Set(areas)].sort(),
      offered_terms: catalog.terms.filter(item => Object.prototype.hasOwnProperty.call(course.offerings, item.code))
        .map(item => item.display_name || item.name),
      schedule_label: term.official_schedule_verified ? "Official schedule" : "Archived schedule data",
      official_url: term.official_schedule_verified ? offering.official_url : catalog.schedule_archive_url,
    });
  }
  return courses;
}


export function rankCatalog(data, profile) {
  const offers = rankPreview(data, profile);
  const byCourse = new Map();
  for (const row of offers.ranked) {
    if (!byCourse.has(row.course.course_code)) byCourse.set(row.course.course_code, row);
  }
  const rejected = new Map();
  for (const row of offers.excluded) {
    if (byCourse.has(row.course_code)) continue;
    if (!rejected.has(row.course_code)) rejected.set(row.course_code, new Map());
    for (const condition of row.conditions) {
      rejected.get(row.course_code).set(`${condition.field}/${condition.reason}`, condition);
    }
  }
  const ranked = [...byCourse.values()];
  const excluded = [...rejected].map(([course_code, conditions]) => ({
    course_code, conditions: [...conditions.values()],
  }));
  return {ranked, recommendations: ranked.slice(0, 3), excluded};
}


function offeringProfile(course, instructor) {
  const {course_code, title, description, official_url, schedule_label, topics, review_url, cohorts} = course;
  return {course_code, title, description, official_url, schedule_label, topics, review_url, cohorts, ...instructor};
}


function node(tag, value = "", className = "") {
  const element = document.createElement(tag);
  element.textContent = value;
  if (className) element.className = className;
  return element;
}


function sourceLink(label, url) {
  const link = node("a", label);
  if (url && url.startsWith("https://")) {
    link.href = url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
  }
  return link;
}


function sourceLinks(course) {
  const links = node("p", "", "links");
  links.append(sourceLink(course.schedule_label, course.official_url), sourceLink("USTSPACE reviews", course.review_url));
  return links;
}


function clearAndAppend(element, children) {
  element.textContent = "";
  element.append(...children);
}


function selectedChoice(picker) {
  return picker.querySelector("input:checked");
}


function showChoice(picker) {
  const summary = picker.querySelector("summary");
  const label = picker.parentElement.querySelector("legend").textContent;
  const value = selectedChoice(picker).parentElement.textContent;
  summary.textContent = value;
  summary.setAttribute("aria-label", `${label}: ${value}`);
}


function replaceChoices(picker, name, choices, value) {
  const selected = choices.some(([key]) => key === value) ? value : choices[0][0];
  const options = choices.map(([key, label]) => {
    const option = node("label");
    const input = node("input");
    input.type = "radio";
    input.name = name;
    input.value = key;
    input.checked = key === selected;
    option.append(input, label);
    return option;
  });
  clearAndAppend(picker.querySelector(".picker-options"), options);
  showChoice(picker);
}


function instructorSignals(instructor, data) {
  const signals = node("ul", "", "reason-list");
  signals.append(
    node("li", `Workload: ${instructor.workload.value} (${instructor.workload.n} labeled reviews)`),
    node("li", `Teaching clarity: ${instructor.teaching.value} (${instructor.teaching.n} labeled reviews)`),
  );
  for (const [field, label] of Object.entries(data.assessments)) {
    const detail = instructor.assessment[field];
    const item = node("li", `${label}: ${detail.note} `);
    if (detail.source) item.append(sourceLink("Syllabus", detail.source));
    signals.append(item);
  }
  return signals;
}


function catalogEntry(course, data) {
  const entry = node("details", "", "catalog-entry");
  entry.dataset.courseCode = course.course_code;
  const summary = node("summary");
  summary.append(node("span", course.course_code, "course-code"),
    node("span", course.title, "catalog-name"), node("span", course.areas.join(" · "), "catalog-area"));
  entry.append(summary);
  entry.addEventListener("toggle", () => {
    if (!entry.open || entry.childElementCount > 1) return;
    const eligible = Object.entries(course.cohorts).map(([cohort, areas]) => `${cohort} ${areas.join(", ")}`);
    const sections = course.section_count === 1 ? "section" : "sections";
    entry.append(node("p", course.description),
      node("p", `${course.credits} credits · ${course.section_count} ${sections} · ${eligible.join(" / ")}`, "meta"));
    for (const instructor of course.instructors) {
      const details = node("details");
      details.append(node("summary", `${instructor.instructor} · ${instructor.review_count} matched reviews`),
        instructorSignals(instructor, data));
      entry.append(details);
    }
    const ratings = node("details");
    const scores = node("ul", "", "reason-list");
    for (const [criterion, row] of Object.entries(course.ratings)) {
      const evidence = row.evidence_status === "population_prior_only" ? "prior only" : `${row.samples} term samples`;
      scores.append(node("li", `${data.catalog.rating_criteria[criterion]}: ${row.rating.toFixed(3)} · ${evidence}`));
    }
    ratings.append(node("summary", "USTRankings scores"),
      node("p", "Standardized course-level scores for this term. Negative values are possible.", "meta"),
      scores, sourceLink("USTRankings course page", course.rankings_url));
    entry.append(ratings, node("p", `Archived terms: ${course.offered_terms.join(" · ")}`, "meta"), sourceLinks(course));
  });
  return entry;
}


function matchMetrics(course) {
  const metrics = node("dl", "", "metric-grid");
  const workload = course.workload.value;
  const teaching = course.teaching.value;
  const bars = node("span", "", "load-bars");
  bars.dataset.level = workload;
  bars.setAttribute("aria-hidden", "true");
  bars.append(node("span"), node("span"), node("span"));
  for (const [label, value, icon] of [
    ["Workload", workload, bars],
    ["Teaching clarity", teaching],
    ["Same-term reviews", String(course.review_count)],
  ]) {
    const metric = node("div", "", "metric");
    metric.dataset.value = value;
    const detail = node("dd");
    if (icon) detail.append(icon);
    detail.append(value[0].toUpperCase() + value.slice(1));
    metric.append(node("dt", label), detail);
    metrics.append(metric);
  }
  return metrics;
}


function matchCard(row, data, cohort, profile) {
  const course = row.course;
  const card = node("article", "", "panel course-card");
  card.dataset.courseCode = course.course_code;
  card.append(node("span", course.course_code, "course-code"), node("h3", course.title),
    node("p", course.instructor, "meta"), matchMetrics(course));
  if (cohort === "all") {
    card.append(node("p", `Eligible curricula: ${Object.keys(course.cohorts).join(", ")}`, "meta"));
  }
  const sharedTopics = "topic" in data.weights ? course.topics.filter(topic => profile.topics.includes(topic)) : [];
  if (sharedTopics.length) {
    const matches = node("div", "", "topic-matches");
    matches.setAttribute("role", "list");
    matches.setAttribute("aria-label", "Matching interests");
    for (const topic of sharedTopics) {
      const match = node("span", data.topics[topic], "topic-match");
      match.setAttribute("role", "listitem");
      matches.append(match);
    }
    card.append(matches);
  }
  if (Object.values(profile.assessment).some(answer => answer.startsWith("require_"))) {
    card.append(node("span", "Requirements verified", "verified-tag"));
  }
  if (!row.reasons.length) {
    card.append(node("p", "Limited evidence for these preferences.", "meta"));
  }
  const evidence = node("details", "", "evidence");
  evidence.append(node("summary", "Match details & sources"));
  if (row.reasons.length) {
    const reasons = node("ul", "", "reason-list");
    reasons.append(...row.reasons.map(reason => node("li", reason)));
    evidence.append(reasons);
  }
  if (row.missing.length) {
    evidence.append(node("p", `Evidence unavailable: ${row.missing.join(", ")}`, "meta"));
  }
  evidence.append(node("p", course.description), instructorSignals(course, data), sourceLinks(course));
  card.append(evidence);
  return card;
}


function exclusionDetails(excluded, data) {
  const section = node("details", "", "panel blocked");
  section.append(node("summary", `Why ${excluded.length} courses were excluded`));
  section.addEventListener("toggle", () => {
    if (!section.open || section.childElementCount > 1) return;
    const list = node("ul", "", "reason-list");
    for (const row of excluded) {
      const reasons = row.conditions.map(condition => {
        const reason = condition.reason === "unverified" ? "needs verified evidence" : "does not meet the requirement";
        return `${data.assessments[condition.field]} ${reason}`;
      });
      list.append(node("li", `${row.course_code} · ${reasons.join("; ")}`));
    }
    section.append(list);
  });
  return section;
}


function noMatchesMessage(data, profile, scope) {
  const missing = Object.entries(profile.assessment)
    .filter(([field, answer]) => answer.startsWith("require_") &&
      !data.courses.some(course => course.assessment[field].verified))
    .map(([field]) => data.assessments[field]);
  if (missing.length) {
    return `${scope} has no verified assessment evidence for ${missing.join(", ")}. Hard requirements need a syllabus for the same term and instructor.`;
  }
  return `No course in ${scope} has verified evidence for all selected requirements. Expand the exclusions below to see why.`;
}


function bootCatalog(data) {
  const byId = id => document.getElementById(id);
  const form = byId("preferences");
  const interestPicker = byId("interest-picker");
  const topicInputs = [...form.querySelectorAll('input[name="topic"]')];
  const selectAllTopics = byId("select-all-topics");
  const termPicker = byId("catalog-term");
  const cohortPicker = byId("catalog-cohort");
  const search = byId("catalog-search");
  const areaPicker = byId("catalog-area");
  const matchView = byId("match-view");
  const catalogView = byId("catalog-view");
  const matchNav = byId("open-matches");
  const catalogNav = byId("open-catalog");
  const pageIntro = byId("page-intro");
  const finderIntro = pageIntro.textContent;
  const initialMatches = byId("initial-matches");
  const terms = new Map(data.catalog.terms.map(term => [term.code, term]));
  let courses = [];

  function renderMatches() {
    const values = new FormData(form);
    const profile = {
      assessment: Object.fromEntries(Object.keys(data.assessments).map(field => [field, values.get(field)])),
      workload: values.get("workload"),
      topics: values.getAll("topic"),
    };
    byId("topics-summary").textContent = profile.topics.length ? `Interests (${profile.topics.length})` : "Interests";
    const allSelected = profile.topics.length === topicInputs.length;
    selectAllTopics.textContent = allSelected ? "Clear all" : "Select all";
    selectAllTopics.setAttribute("aria-label", allSelected ? "Clear all interests" : "Select all interests");
    const hasPreference = Object.prototype.hasOwnProperty.call(data.levels, profile.workload) ||
      profile.topics.length > 0 || Object.values(profile.assessment).some(answer => answer && answer !== "any");
    if (initialMatches && !hasPreference) {
      const emptyView = initialMatches.content.cloneNode(true);
      emptyView.querySelector(".browse-button").addEventListener("click", () => {
        showView(true);
        catalogNav.focus();
      });
      byId("results-count").textContent = "";
      clearAndAppend(byId("results"), [emptyView]);
      return;
    }
    const ranking = rankCatalog(data, profile);
    const cohort = selectedChoice(cohortPicker).value;
    const children = ranking.recommendations.map(row => matchCard(row, data, cohort, profile));
    const count = ranking.recommendations.length;
    byId("results-count").textContent = `${count} of ${courses.length} courses shown`;
    if (!count) {
      const term = terms.get(selectedChoice(termPicker).value);
      const scope = `${term.display_name || term.name} · ${cohort === "all" ? "All curricula" : cohort}`;
      children.push(node("p", noMatchesMessage(data, profile, scope), "panel empty"));
    }
    if (ranking.excluded.length) children.push(exclusionDetails(ranking.excluded, data));
    clearAndAppend(byId("results"), children);
  }

  function renderCatalog() {
    const query = search.value.trim().toLowerCase();
    const codeQuery = query.replace(/\s/g, "");
    const area = selectedChoice(areaPicker).value;
    const visible = courses.filter(course => {
      const matchesSearch = course.course_code.toLowerCase().includes(codeQuery) || course.title.toLowerCase().includes(query);
      return matchesSearch && (area === "all" || course.areas.includes(area));
    });
    byId("catalog-count").textContent = `${visible.length} of ${courses.length} courses`;
    const entries = visible.map(course => catalogEntry(course, data));
    if (!visible.length) entries.push(node("p", "No courses match this search.", "muted"));
    clearAndAppend(byId("catalog-courses"), entries);
  }

  function updateScope() {
    const term = terms.get(selectedChoice(termPicker).value);
    courses = coursesInScope(data.catalog, term, selectedChoice(cohortPicker).value);
    data.courses = courses.flatMap(course => course.instructors.map(instructor => offeringProfile(course, instructor)));
    const matched = courses.filter(course => course.instructors.some(instructor => instructor.review_count)).length;
    const coverage = byId("coverage");
    const reviewLabel = coverage.dataset.reviewLabel || "with matching reviews";
    coverage.textContent = `${courses.length} courses · ${matched} ${reviewLabel}`;
    byId("snapshot").textContent = `Data through ${data.catalog.archive_date_hkt}${term.official_schedule_verified ? "" : " · Historical schedule archive"}`;
    const areas = [...new Set(courses.flatMap(course => course.areas))].sort();
    replaceChoices(areaPicker, "area", [["all", "All areas"], ...areas.map(value => [value, value])], selectedChoice(areaPicker).value);
    renderMatches();
    renderCatalog();
  }

  function updateTerm() {
    const term = terms.get(selectedChoice(termPicker).value);
    replaceChoices(cohortPicker, "cohort", [["all", "All curricula"], ...term.cohorts.map(value => [value, value])],
      selectedChoice(cohortPicker).value);
    updateScope();
  }

  function showView(isCatalog) {
    matchView.hidden = isCatalog;
    catalogView.hidden = !isCatalog;
    matchNav.setAttribute("aria-pressed", String(!isCatalog));
    catalogNav.setAttribute("aria-pressed", String(isCatalog));
    const commonCore = node("span", "Common Core", "hero-subject");
    clearAndAppend(byId("page-heading"), isCatalog ? [commonCore, " catalog"] : ["Find your ", commonCore]);
    pageIntro.textContent = isCatalog ? "Look up courses, teaching staff, and term-specific ratings." : finderIntro;
  }

  updateTerm();
  termPicker.addEventListener("change", updateTerm);
  cohortPicker.addEventListener("change", updateScope);
  form.addEventListener("change", renderMatches);
  selectAllTopics.addEventListener("click", () => {
    const select = topicInputs.some(input => !input.checked);
    topicInputs.forEach(input => { input.checked = select; });
    if (select) interestPicker.open = true;
    renderMatches();
  });
  form.addEventListener("reset", () => setTimeout(() => {
    form.querySelectorAll(".picker").forEach(showChoice);
    renderMatches();
  }, 0));
  form.addEventListener("submit", event => event.preventDefault());
  search.addEventListener("input", renderCatalog);
  areaPicker.addEventListener("change", renderCatalog);
  matchNav.addEventListener("click", () => showView(false));
  catalogNav.addEventListener("click", () => showView(true));
  document.addEventListener("change", event => {
    const picker = event.target.closest(".picker");
    if (picker) showChoice(picker);
  });
  document.addEventListener("click", event => {
    const picker = event.target.closest(".picker");
    document.querySelectorAll(".picker[open]").forEach(open => {
      if (open !== picker) open.open = false;
    });
    if (picker && event.target.type === "radio" && event.target.checked) {
      picker.open = false;
      picker.querySelector("summary").focus();
    }
  });
  document.addEventListener("keydown", event => {
    const picker = event.target.closest(".picker[open]");
    if (event.key === "Escape" && picker) {
      picker.open = false;
      picker.querySelector("summary").focus();
    }
  });
}


if (typeof document !== "undefined") {
  const notice = document.getElementById("startup-notice");
  try {
    bootCatalog(JSON.parse(document.getElementById("preview-data").textContent));
    notice.hidden = true;
  } catch (error) {
    notice.textContent = "The course app could not start. Save a fresh copy of the HTML and open it directly in Chrome or Safari.";
    console.error("Could not start UST Vibe Match", error);
  }
}
