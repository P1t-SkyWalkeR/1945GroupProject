export function rankPreview(data, profile) {
  const ranked = [];
  const excluded = [];
  const wantedTopics = new Set(profile.topics);

  for (const course of data.courses) {
    const conditions = [];
    const assessment = [];
    const reasons = [];
    const missing = [];
    for (const [key, answer] of Object.entries(profile.assessment)) {
      const detail = course.assessment[key];
      const label = data.assessments[key];
      if (answer.startsWith("require_")) {
        const expected = answer.slice(8);
        if (!detail.verified || detail.value === "unknown") {
          conditions.push({field: key, reason: "unverified", expected});
        } else if (detail.value !== expected) {
          conditions.push({field: key, reason: "mismatch", expected});
        } else {
          reasons.push(`${label}: required condition verified.`);
        }
      } else if (answer.startsWith("prefer_")) {
        if (detail.value === "unknown") {
          assessment.push(0.5);
          missing.push(label);
        } else {
          const matches = detail.value === answer.slice(7);
          assessment.push(Number(matches));
          const source = detail.verified ? "verified" : "review evidence";
          reasons.push(`${label}: ${matches ? "matches" : "differs from"} your preference (${source}).`);
        }
      }
    }
    if (conditions.length) {
      excluded.push({course_code: course.course_code, conditions});
      continue;
    }
    const scores = {
      assessment: assessment.length ? assessment.reduce((sum, value) => sum + value, 0) / assessment.length : 0.5,
    };
    if (Object.prototype.hasOwnProperty.call(data.weights, "workload")) {
      const preferred = data.levels[profile.workload];
      const observed = data.levels[course.workload.value];
      scores.workload = 0.5;
      if (preferred !== undefined) {
        if (observed === undefined) {
          missing.push("Workload");
        } else {
          scores.workload = 1 - Math.max(0, observed - preferred);
          reasons.push(`Workload: ${course.workload.value}, based on ${course.workload.n} labeled ${course.workload.n === 1 ? "review" : "reviews"}.`);
        }
      }
    }
    if (Object.prototype.hasOwnProperty.call(data.weights, "teaching")) {
      const observed = data.teaching[course.teaching.value];
      scores.teaching = observed === undefined ? 0.5 : observed;
      if (observed === undefined) {
        missing.push("Teaching clarity");
      } else {
        reasons.push(`Teaching clarity: ${course.teaching.value}, based on ${course.teaching.n} labeled ${course.teaching.n === 1 ? "review" : "reviews"}.`);
      }
    }
    if (Object.prototype.hasOwnProperty.call(data.weights, "topic")) {
      scores.topic = 0.5;
      if (wantedTopics.size) {
        const courseTopics = new Set(course.topics);
        if (courseTopics.size) {
          const shared = [...wantedTopics].filter(tag => courseTopics.has(tag)).sort();
          scores.topic = shared.length / Math.sqrt(wantedTopics.size * courseTopics.size);
          reasons.push(shared.length
            ? `Interest match: ${shared.map(tag => data.topics[tag]).join(", ")}.`
            : "No overlap with your selected topics.");
        } else {
          missing.push("Topics");
        }
      }
    }
    const total = Object.entries(scores).reduce((sum, [key, value]) => sum + value * data.weights[key], 0);
    ranked.push({course, score: Math.round(total * 1e12) / 1e12, reasons, missing, components: scores});
  }

  ranked.sort((a, b) => b.score - a.score || a.missing.length - b.missing.length
    || (a.course.course_code < b.course.course_code ? -1 : a.course.course_code > b.course.course_code ? 1 : 0));
  return {ranked, recommendations: ranked.slice(0, 3), excluded};
}
