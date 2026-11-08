import assert from "node:assert/strict";
export function grade(id, c, result, trace) {
  const view = result.sentiment,
    x = result.actual;
  const outside = view?.perspectives.filter((p) => p.kind !== "management") || [];
  const text = JSON.stringify(result);
  const millions = (f) => Number(f.value) / (/mill|mio|mn|^m$/i.test(f.unit) ? 1 : 1000000);

  const opened = new Set(trace.opened.map((d) => d.url));
  const checkSources = (value) => {
    if (!value || typeof value !== "object") return;
    if (value.url && value.locator) assert(opened.has(value.url), "uncaptured source " + value.url);
    if (value.published_at)
      assert(Date.parse(value.published_at) <= Date.parse(c.stamp + "T18:00:00Z"), "future evidence");
    Object.values(value).forEach(checkSources);
  };
  checkSources(result);
  assert(opened.size > 0);
  assert(trace.queries.length > 0 || c.phase === "actual");
  if (c.precision) {
    const s = result.schedule;
    assert.equal(s.precision, c.precision);
    assert.match(s.period, /2029/);
    assert.match(s.period, /Q4|4Q|quarter.?4/i);
    assert.equal(s.report_type, "quarter");
    assert.match(s.source.url, /\/calendar$/);
    if (id === "jan") {
      assert.equal(s.day, "2030-01-25");
      assert.match(s.local_time, /^08:00/);
    } else {
      assert(!s.day);
      assert.equal(s.window_start, id === "nov" ? "2030-01-01" : "2030-01-21");
      assert.equal(s.window_end, "2030-01-31");
    }
  }
  if (id === "preview") {
    assert(
      result.facts.some(
        (f) =>
          millions(f) === 102 &&
          f.period === "FY2029-Q4" &&
          f.currency === "GBP" &&
          f.source.url.endsWith("/survey") &&
          f.aggregation === "median" &&
          f.analyst_count === 5,
      ),
    );
    assert(["found", "conflicting"].includes(view.status));
    assert(outside.length >= 2);
    assert(!text.includes("777"));
    assert(outside.every((p) => p.source.url.endsWith("/survey") && p.source.published_at));
    assert.match(text, /Roy|Alder/);
    assert.match(text, /Yen|Birch/);
  }
  if (id === "actual" || id === "correction") {
    assert.equal(x.release, id === "actual" ? "full" : "correction");
    assert(
      x.facts.some(
        (f) =>
          f.period === "FY2029-Q4" &&
          f.currency === "GBP" &&
          f.source.url === x.source.url &&
          millions(f) === (id === "actual" ? 105 : 103),
      ),
    );
    assert(!result.review);
    assert.match(x.source.url, id === "actual" ? /\/results$/ : /\/correction$/);
  }
  if (id === "review") {
    assert(["found", "conflicting"].includes(view.status));
    assert(outside.length >= 2);
    assert(outside.every((p) => p.source.url.endsWith("/responses")));
    assert(result.scenarios.positive && result.scenarios.negative && result.scenarios.neutral);
    if (result.market_reaction) {
      assert(result.reaction_source.url.endsWith("/price") && result.reaction_window);
    }
  }
  if (id === "price_only") {
    assert.equal(view.status, "unavailable");
    assert(!outside.length);
    assert(view.limitations.length);
    assert(result.market_reaction, "missing documented close-to-close return");
    if (result.market_reaction) {
      assert(result.reaction_source.url.endsWith("/price"));
      assert(result.reaction_window);
    }
  }
  if (["review", "preview", "price_only", "sparse"].includes(id))
    assert(
      trace.queries.some((q) =>
        /analy|market|markt|sell.side|consens|konsens|broker|investor|stimm|reaction|meinung/i.test(q),
      ),
      "no participant research",
    );
  if (id === "sparse") {
    assert.equal(view.status, "unavailable");
    assert(view.limitations.length);
    assert(!result.facts.some((f) => f.value_kind === "consensus"));
    assert(!text.includes("777"));
  }
}
