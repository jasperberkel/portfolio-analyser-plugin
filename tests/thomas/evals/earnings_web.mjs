// Run with an explicit output directory. The paid model never sees fixture documents until it opens them.
import { decide, validate } from "./earnings_decide.mjs";
import { mkdir, readFile, writeFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { grade } from "./earnings_grade.mjs";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";
import { cases, schedule, identity, searchFixture } from "./earnings_cases.mjs";
const [plugin, output, ...requested] = process.argv.slice(2);
if (!plugin || !output) throw Error("Usage: node earnings_web.mjs PLUGIN_PACKAGE OUTPUT_DIR [case...]");
const { researchInstructions, researchTask } = await import(
  pathToFileURL(resolve(plugin, "scripts/earnings_research.mjs")).href
);
const schemas = JSON.parse(await readFile(join(plugin, "references/research/earnings-schemas.json"), "utf8"));

await mkdir(output, { recursive: true });
const ids = requested.length ? requested : Object.keys(cases);
const existing = new Set(await readdir(output));
for (const id of ids) {
  if (!Object.hasOwn(cases, id)) throw Error("Unknown earnings case: " + id);
  if (existing.has(id + ".json")) throw Error("Case trace already exists: " + id);
}
async function run(id, knownSchedule) {
  const c = cases[id],
    now = () => c.stamp + "T18:00:00Z";
  let response,
    requests = 0;
  const meta = {
    model: process.env.EARNINGS_EVAL_MODEL || "gpt-6.1-sol",
    wheel_sha256: process.env.EARNINGS_EVAL_WHEEL_SHA256,
  };
  const actions = [];
  try {
    response = await researchTask({
      task: {
        phase: c.phase,
        result_schema: schemas[c.phase],
        identity,
        known_events: knownSchedule ? [{ phase: "open", schedule: knownSchedule }] : [],
        research_cutoff: now(),
        schedule: c.phase === "calendar" ? undefined : schedule,
        candidate: c.candidate ? [{ url: c.candidate.url, title: c.candidate.title }] : [],
        history: c.history || [],
        held: false,
      },
      instructions: await researchInstructions(plugin, c.phase),
      decide: async (prompt, input) => {
        if (++requests > Number(process.env.EARNINGS_EVAL_MAX_REQUESTS || 12))
          throw Error("Model request budget exhausted");
        return decide(prompt, input);
      },
      validate,
      now,
      search: async (query) => {
        actions.push({ search: query });
        return searchFixture(c.docs, query);
      },
      open: async (url) => {
        actions.push({ open: url });
        const doc = c.docs.find((d) => d.url === url);
        if (!doc) throw Error("no page");
        return doc;
      },
    });
    grade(id, c, response.result, response.web_trace);
    await writeFile(
      join(output, id + ".json"),
      JSON.stringify({ id, ...meta, requests, pass: true, actions, ...response }, null, 2),
    );
    console.log(id, "PASS");
    return response.result;
  } catch (err) {
    await writeFile(
      join(output, id + ".json"),
      JSON.stringify(
        { id, ...meta, requests, pass: false, actions, error: String(err), ...response },
        null,
        2,
      ),
    );
    console.log(id, "FAIL", String(err).slice(-350));
    process.exitCode = 1;
  }
}
const calendarIds = ["nov", "dec", "jan"].filter((id) => ids.includes(id));
const jobs = ids.filter((id) => !calendarIds.includes(id)).map((id) => () => run(id));
if (calendarIds.length)
  jobs.unshift(async () => {
    let knownSchedule;
    for (const id of calendarIds) knownSchedule = (await run(id, knownSchedule))?.schedule || knownSchedule;
  });
await Promise.all(
  Array.from({ length: Math.min(3, jobs.length) }, async () => {
    while (jobs.length) await jobs.shift()();
  }),
);
