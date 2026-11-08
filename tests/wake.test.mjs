import assert from "node:assert/strict";
import { test } from "node:test";
import { wake, renderDelivery } from "../plugins/portfolio-analyser/scripts/earnings_wake.mjs";
test("prepare and acknowledge the exact finished preview in the personal destination", async () => {
  const item = {id:"doc", identity:{name:"Issuer"}, fiscal_period:"FY", kind:"preview",
    body:{assessment:"Erwartungen steigen.", gaps:["Konsens fehlt."]}};
  const calls = [];
  const more = await wake({destination:"private", firstWake:true,
    call: async (name, args) => {
      calls.push([name,args]);
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
  assert.deepEqual(calls.map(x=>x[0]),["sync_earnings_tracking","check_due_earnings","claim_due_earnings","ack_earnings_delivery"]);
  assert.deepEqual(calls.at(-1)[1],{delivery_id:"doc",destination:"private",receipt:"native-receipt"});
});
test("changed holdings refresh personal wording", () => {
  const item={identity:{name:"Issuer"}, fiscal_period:"FY",body:{scenarios:{positive:"p",neutral:"n",negative:"m"},portfolio_basis:{held:true},portfolio_context:"Old holding"},current_portfolio_basis:{held:false}};
  const message=renderDelivery(item);
  assert.ok(message.includes("Aktuell nur beobachtet") && !message.includes("Old holding"));
});
