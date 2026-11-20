import assert from "node:assert/strict";
import { test } from "node:test";
import { wake, renderDelivery } from "../plugins/portfolio-analyser/scripts/earnings_wake.mjs";
import { dispatchInvestment } from "../plugins/portfolio-analyser/scripts/earnings_wake.mjs";
import { researchTask } from "../plugins/portfolio-analyser/scripts/earnings_research.mjs";
test("prepare and acknowledge the exact finished preview in the personal destination", async () => {
  const item = {id:"doc", identity:{name:"Issuer"}, fiscal_period:"FY", kind:"preview",
    body:{assessment:"Erwartungen steigen.", gaps:["Konsens fehlt."]}};
  const calls = [];
  const more = await wake({destination:"private", firstWake:true,
    call: async (name, args) => {
      calls.push([name,args]);
      if (name === "get_investment_monitoring") return {enabled:false};
      if (name === "check_due_investment_events") return {ready:false};
      if (name === "check_due_earnings") return {ready:true};
      if (name === "claim_due_earnings") return {phase:"delivery",delivery:item};
    },
    deliver: async (id, message, authorization) => {
      assert.equal(id,"doc");
      assert.equal(message,"Issuer · FY\n\nVorabbericht\nErwartungen steigen.\nKonsens fehlt.");
      assert.deepEqual(authorization,{name:"prepare_earnings_delivery",args:{delivery_id:id,destination:"private"}});
      return "native-receipt";
    }});
  assert.equal(more,true);
  assert.deepEqual(calls.map(x=>x[0]),["get_investment_monitoring","sync_earnings_tracking","check_due_earnings","claim_due_earnings","ack_earnings_delivery","check_due_investment_events"]);
  assert.deepEqual(calls.at(-2)[1],{delivery_id:"doc",destination:"private",receipt:"native-receipt"});
});
test("changed holdings refresh personal wording", () => {
  const item={identity:{name:"Issuer"}, fiscal_period:"FY",body:{scenarios:{positive:"p",neutral:"n",negative:"m"},portfolio_basis:{held:true},portfolio_context:"Old holding"},current_portfolio_basis:{held:false}};
  const message=renderDelivery(item);
  assert.ok(message.includes("Aktuell nur beobachtet") && !message.includes("Old holding"));
});

test("investment delivery failure preserves its ID and is not acknowledged", async () => {
  const calls=[];
  const input={destination:"private",call:async (name,args)=>{
    calls.push([name,args]);
    if(name==="check_due_investment_events") return {ready:true};
    if(name==="claim_due_investment_events") return {phase:"delivery",delivery:{id:"event",body:{instrument:{name:"Issuer"},title:"Guidance",observation:"Reduced",thesis_effect:"Weakened",review_reason:"Valuation",source:{url:"https://issuer.example/",title:"IR"}}}};
  },deliver:async(id,message,authorization)=>{
    assert.equal(id,"event");
    assert.equal(authorization.name,"prepare_investment_delivery");
    assert.ok(message.indexOf("Valuation") < message.indexOf("Reduced"));
    assert.ok(message.includes("Weakened") && message.includes("https://issuer.example/"));
    throw Error("Uncertain delivery");
  }};
  await assert.rejects(dispatchInvestment(input),/Uncertain/);
  assert.ok(!calls.some(([name])=>name==="ack_investment_delivery"));
  input.deliver=async()=>"receipt";
  await dispatchInvestment(input);
  assert.deepEqual(calls.at(-1),["ack_investment_delivery",{delivery_id:"event",receipt:"receipt",destination:"private"}]);
});

test("earnings message preserves the condition and leaves scenario details in the saved review", () => {
  const basis = { snapshot_id: "A", plan_version: 1, held: true };
  const review = { portfolio_basis: basis, portfolio_context: "Halten, solange die Marge stabil bleibt.",
    outlook: "Die Marge blieb stabil.", uncertainty: "Der Ausblick hängt vom Absatz ab.",
    scenarios: {negative: "Detailed downside scenario"}, baseline_gap: "Konsens fehlt." };
  const item = { identity: {name: "Issuer"}, fiscal_period: "FY", kind: "review",
    body: review, current_portfolio_basis: basis, actual: {source: {url: "https://issuer.example/report"}} };
  const first = renderDelivery(item);
  assert.ok(first.includes(review.portfolio_context) && first.includes(review.uncertainty));
  assert.ok(first.includes(item.actual.source.url) && !first.includes(review.scenarios.negative));
  assert.equal(review.scenarios.negative, "Detailed downside scenario");
  item.current_portfolio_basis = { ...basis, snapshot_id: "B" };
  assert.ok(!renderDelivery(item).includes(review.portfolio_context));
  item.current_portfolio_basis = basis;
  review.portfolio_context = "Zukaufen ".repeat(65) + "nur unter der genannten Bedingung.";
  assert.ok(!renderDelivery(item).includes("Zukaufen"));
  review.portfolio_context = "Jetzt erhöhen.";
  review.uncertainty = "Eine notwendige Bedingung. ".repeat(15);
  assert.ok(!renderDelivery(item).includes("Jetzt erhöhen."));
  review.outlook = "Ausführlicher Bericht. ".repeat(18);
  item.actual.facts = [{metric: "Umsatz", value_kind: "actual", value: "85", currency: "EUR",
    unit: "Millionen", period: "Q2", basis: "IFRS", source: item.actual.source}];
  assert.match(renderDelivery(item), /Umsatz.*Q2.*IFRS.*85 Millionen EUR/);
});

test("empty and unavailable searches stay explicit investment coverage gaps", async () => {
  for (const unavailable of [false, true]) {
    const response = await researchTask({
      task: {phase: "investment", identity: {instruments: [{instrument_id: "stock-A"}]}},
      instructions: "", decide: async () => ({queries: ["Synthetic issuer"], urls: []}),
      search: async () => { if (unavailable) throw Error("offline"); return []; },
      open: async () => assert.fail("no source to open"),
    });
    assert.deepEqual(response.result.events, []);
    assert.deepEqual(response.result.researched, ["stock-A"]);
    assert.equal(response.result.gaps.length, 1);
    assert.equal(Boolean(response.web_trace.gaps.length), unavailable);
    assert.match(response.result.gaps[0], unavailable ? /unvollständig/ : /keinen überprüften Beleg/);
  }
});

test("investment-only enrollment does not enroll earnings", async () => {
  const calls=[];
  const more=await wake({firstWake:true,destination:"private",call:async(name)=>{
    calls.push(name);
    if(name==="get_investment_monitoring") return {enabled:true};
    return {ready:false};
  }});
  assert.equal(more,false);
  assert.ok(!calls.includes("sync_earnings_tracking"));
});
