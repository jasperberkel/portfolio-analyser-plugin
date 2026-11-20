import { fileURLToPath } from "node:url";
import { researchInstructions, researchTask } from "./earnings_research.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));

export async function wake({ call, deliver, destination, web, complete, validate, firstWake }) {
  if (firstWake) {
    const investments = await call("get_investment_monitoring", {});
    if (!investments.enabled) await call("sync_earnings_tracking", { destination });
  }
  const research = async (task) => researchTask({
    task, instructions: await researchInstructions(root, task.phase),
    ...web, validate,
    decide: async (prompt, input) => JSON.parse((await complete(prompt, JSON.stringify(input))).trim().replace(/^```(?:json)?\s*|\s*```$/g, "")),
  });
  const earnings = await dispatch({ call, deliver, destination, research, render: renderDelivery });
  // Check both independent queues; one busy earnings issuer must not starve material events.
  const investments = await dispatchInvestment({ call, deliver, destination, research });
  return earnings !== "idle" || investments !== "idle";
}

/** One replay-safe work batch in a single authenticated account. */
export async function dispatch({ call, research, deliver, render, destination }) {
  const due = await call("check_due_earnings", { destination });
  if (!due.ready) return "idle";
  const task = await call("claim_due_earnings", { destination });
  if (task.phase === "idle") return "idle";
  if (task.phase === "delivery") {
    const item = task.delivery;
    const receipt = await deliver(item.id, render(item), {
      name: "prepare_earnings_delivery", args: { delivery_id: item.id, destination },
    });
    await call("ack_earnings_delivery", { delivery_id: item.id, receipt, destination });
    return "delivery";
  }
  const response = await research(task);
  const { result, web_trace } = response.web_trace ? response : { result: response };
  await call("complete_earnings_check", {
    phase: task.phase,
    claim: task.claim,
    result,
    ...(web_trace && { web_trace }),
  });
  return task.phase;
}

// Older stored reviews can contain whole reports in a single field. Keep a
// qualified conclusion intact or defer it in full to the saved explanation.
function shortField(value, fallback) {
  const line = value?.trim().replace(/\s+/g, " ");
  return line && line.length <= 280 ? line : fallback;
}

function reportedFact(facts) {
  const labels = {actual: "Gemeldet", guidance: "Unternehmensausblick", consensus: "Analystenkonsens"};
  const fact = facts?.find(f => labels[f.value_kind] && f.source?.url && f.value != null);
  if (!fact) return null;
  const measure = [...new Set([fact.unit, fact.currency].filter(Boolean))].join(" ");
  const text = shortField(`${fact.metric} (${fact.period}, ${fact.basis}) · ${labels[fact.value_kind]} ${fact.value} ${measure}.`, null);
  return text ? {text, source: fact.source} : null;
}

export function renderDelivery(item) {
  const doc = item.body;
  const preview = item.kind === "preview";
  const lines = [item.identity.name + " · " + item.fiscal_period, "",
    preview ? "Vorabbericht" : "Quartalszahlen"];
  let source;
  if (preview) {
    const fact = reportedFact(doc.facts);
    lines.push(shortField(doc.assessment, fact?.text || "Die Einschätzung vor den Zahlen liegt vor."));
    if (doc.gaps?.length) lines.push(shortField(doc.gaps[0], "Die Erwartungen sind nur teilweise belegt."));
    source = fact?.source;
  } else {
    const basis = doc.portfolio_basis;
    const current = item.current_portfolio_basis;
    if (current && basis?.snapshot_id !== undefined && current.snapshot_id === basis.snapshot_id &&
        current.plan_version === basis.plan_version && current.held === basis.held) {
      const personal = shortField(doc.uncertainty, null) ? shortField(doc.portfolio_context, null) : null;
      lines.push(personal || "Die Bedingungen für einen konkreten Schritt sind im Bericht erläutert.");
    } else if (current?.held === false) {
      lines.push("Aktuell nur beobachtet. Für einen Einstieg zählt, ob sich die Annahmen bestätigen.");
    } else if (current || basis) {
      lines.push("Für einen konkreten Schritt muss der aktuelle Depotstand neu bewertet werden.");
    }
    lines.push(shortField(doc.outlook, reportedFact(item.actual?.facts)?.text || "Die Einschätzung zu den veröffentlichten Zahlen liegt vor."));
    if (doc.uncertainty) lines.push(shortField(doc.uncertainty, "Die Einschätzung hängt von mehreren offenen Annahmen ab."));
    if (doc.baseline_gap) lines.push(shortField(doc.baseline_gap, "Der Vergleich mit den Erwartungen ist eingeschränkt."));
    source = item.actual?.source;
  }
  if (source?.url) lines.push(source.url);
  return lines.join("\n");
}

export async function dispatchInvestment({ call, research, deliver, destination }) {
  const due = await call("check_due_investment_events", { destination });
  if (!due.ready) return "idle";
  const task = await call("claim_due_investment_events", { destination });
  if (task.phase === "idle") return "idle";
  if (task.phase === "delivery") {
    const { id, body } = task.delivery;
    const receipt = await deliver(id, renderInvestment(body), {
      name: "prepare_investment_delivery", args: { delivery_id: id, destination },
    });
    await call("ack_investment_delivery", { delivery_id: id, receipt, destination });
    return "delivery";
  }
  const { result, web_trace } = await research(task);
  await call("complete_investment_check", { claim: task.claim, result, web_trace });
  return task.phase;
}

export function renderInvestment(body) {
  return [body.instrument.name + " · " + body.title, "",
    shortField(body.review_reason, "Prüfe die bisherige Einschätzung zu diesem Titel."),
    shortField(body.observation, "Eine neue Veröffentlichung liegt vor."),
    shortField(body.thesis_effect, "Die Bedeutung hängt von den Annahmen im Bericht ab."),
    body.source.url].join("\n");
}
