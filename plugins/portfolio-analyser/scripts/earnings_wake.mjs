import { fileURLToPath } from "node:url";
import { researchInstructions, researchTask } from "./earnings_research.mjs";
const root = fileURLToPath(new URL("../", import.meta.url));

export async function wake({ call, deliver, destination, web, complete, validate, firstWake }) {
  if (firstWake) await call("sync_earnings_tracking", { destination });
  const research = async (task) => researchTask({
    task, instructions: await researchInstructions(root, task.phase),
    ...web, validate,
    decide: async (prompt, input) => JSON.parse((await complete(prompt, JSON.stringify(input))).trim().replace(/^```(?:json)?\s*|\s*```$/g, "")),
  });
  return (await dispatch({ call, deliver, destination, research, render: renderDelivery })) !== "idle";
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

export function renderDelivery(item) {
  const doc = item.body;
  const facts = item.actual?.facts || doc.facts || [];
  const source = item.actual?.source;
  const basis = doc.portfolio_basis;
  const current = item.current_portfolio_basis;
  const basisMatches =
    !basis ||
    !current ||
    (basis.snapshot_id === current.snapshot_id &&
      basis.plan_version === current.plan_version &&
      basis.held === current.held);
  const personal = basisMatches
    ? doc.portfolio_context
    : current.held
      ? "Depot oder Plan wurden seit diesem Bericht aktualisiert. Die Einordnung der Position ist erneut zu prüfen."
      : "Aktuell nur beobachtet. Die Emittentenszenarien gelten für eine mögliche Erstposition.";
  const lines = [item.identity.name + " · " + item.fiscal_period, ""];
  if (item.kind === "preview") lines.push("Vorabbericht", doc.assessment, ...(doc.gaps || []));
  else
    lines.push(
      "Quartalszahlen",
      doc.outlook,
      personal,
      "Positives Szenario: " + doc.scenarios.positive,
      "Neutrales Szenario: " + doc.scenarios.neutral,
      "Negatives Szenario: " + doc.scenarios.negative,
      "Zeithorizont: " + doc.horizon,
      "Unsicherheit: " + doc.uncertainty,
    );
  for (const view of doc.sentiment?.perspectives || []) {
    lines.push(
      view.participant +
        " (" +
        view.kind +
        ", " +
        view.source.published_at +
        "): " +
        view.view +
        " " +
        view.rationale +
        " Unsicherheit: " +
        view.uncertainty +
        " " +
        view.source.url,
    );
  }
  for (const gap of doc.sentiment?.limitations || []) lines.push(gap);
  const labels = {
    consensus: "Analystenkonsens",
    guidance: "Unternehmensausblick",
    assumption: "Annahme",
    actual: "Ist",
  };
  for (const fact of facts) {
    const basis = [fact.basis, fact.period, fact.currency].filter(Boolean).join(", ");
    lines.push(
      `${labels[fact.value_kind]} · ${fact.metric}: ${fact.value} ${fact.unit} (${basis}). ${fact.source.url}`,
    );
  }
  for (const c of doc.comparisons || []) {
    lines.push(
      `${c.metric}: ${c.actual} gegenüber ${c.expected} ${c.unit} (${labels[c.comparison_kind]}), Abweichung ${c.difference} ${c.difference_unit}. Stand ${c.source.accessed_at}. ${c.source.url}`,
    );
  }
  if (basis?.as_of) lines.push("Depotstand des Berichts: " + basis.as_of + ".");
  for (const gap of item.preview?.gaps || []) lines.push(gap);
  if (doc.baseline_gap) lines.push(doc.baseline_gap);
  if (source)
    lines.push(
      "Veröffentlichung: " + (item.actual.published_at || item.actual.published_on) + " · " + source.url,
    );
  if (doc.market_reaction)
    lines.push(
      "Beobachtete Marktreaktion (" +
        doc.reaction_window +
        "): " +
        doc.market_reaction +
        " " +
        doc.reaction_source.url,
    );
  return lines.join("\n");
}
