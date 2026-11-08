"""Real model selection in a synthetic authenticated dashboard with no existing grant."""
import argparse
import json
from pathlib import Path

from codex_model import completion


def execute(model, output):
    root = Path(__file__).resolve().parents[3] / "plugins/portfolio-analyser"
    instructions = (root / "skills/portfolio-analyser-setup/SKILL.md").read_text()
    tools = []
    for name, description, properties in [
        ("bind_personal_wake", "Bind an installed package to this authenticated personal inbox.",
         {"package": {"type": "string", "enum": ["library-reminders", "portfolio-analyser"]}}),
        ("portfolio_analyser__connect", "Request sign-in to the personal service in this private dashboard.", {}),
        ("schedule", "Create a recurring general task.", {"prompt": {"type":"string"}}),
    ]:
        tools.append({"type":"function","function":{"name":name,"description":description,
            "parameters":{"type":"object","properties":properties,"required":list(properties),"additionalProperties":False}}})
    messages = [{"role":"system","content":"Authenticated private Thomas dashboard. Use the installed setup skill:\n"+instructions},
                {"role":"user","content":"Richte das Trading-Paket ein."}]
    calls = []
    for _ in range(4):
        data = completion({"model": model,"messages":messages,"tools":tools},model=model,timeout=90,token_cap=3500)
        delta = json.loads(data.splitlines()[0][6:])["choices"][0]["delta"]
        actions = delta.get("tool_calls", [])
        messages.append({"role":"assistant","content":delta.get("content",""),"tool_calls":[
            {k:v for k,v in action.items() if k!="index"} for action in actions]})
        if not actions: break
        for action in actions:
            fn = action["function"]; name = fn["name"]; args = json.loads(fn["arguments"])
            calls.append([name,args])
            if [name,args] == ["bind_personal_wake",{"package":"portfolio-analyser"}]: result = "Personal wake bound."
            elif [name,args] == ["portfolio_analyser__connect",{}]: result = "Open https://example.invalid/synthetic-consent"
            else: raise ValueError("Unexpected side effect or wrong package")
            messages.append({"role":"tool","tool_call_id":action["id"],"content":result})
    final = messages[-1].get("content","")
    proof = {"model":model,"input":messages[1]["content"],"transport":"real Codex model, synthetic tool results",
             "calls":calls,"response":final}
    output.write_text(json.dumps(proof,indent=2,ensure_ascii=False)+"\n")
    assert calls == [["bind_personal_wake",{"package":"portfolio-analyser"}],["portfolio_analyser__connect",{}]], calls
    assert messages[-1]["role"] == "assistant" and "https://example.invalid/synthetic-consent" in final
    print("PASS real model selected package, requested personal consent and returned its URL")


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path); parser.add_argument("--model",default="gpt-6.1-sol")
    args=parser.parse_args(); execute(args.model,args.output)
