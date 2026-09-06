"""Host-independent workflow state tests, using only temporary files and stdlib."""

import copy
import importlib.util
import json
import subprocess
import tempfile
import unittest
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import tomllib

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "portfolio-analyser"


def load_script(name):
    spec = importlib.util.spec_from_file_location(
        name, PLUGIN / "scripts" / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


workflow = load_script("workflow")
profiles = load_script("install_agent_profiles")
mcp_call = load_script("mcp_call")


def step(skill, *, stage="research", requires=None, produces=None):
    return {
        "contract_version": 1,
        "skill": skill,
        "stage": stage,
        "requires": requires if requires is not None else [],
        "produces": produces or f"report.{skill}",
    }


def flow():
    return {
        "contract_version": 1,
        "steps": [
            step("positions", requires=["current_portfolio", "previous_report"]),
            step("market", requires=["previous_report"]),
            step("strategy", stage="strategy", requires=["strategy_context"]),
        ],
    }


def app_context():
    return {
        "contract_version": 1,
        "source_fingerprint": "a" * 64,
        "workflow_fingerprint": "b" * 64,
        "research_cutoff": datetime.now(timezone.utc).isoformat(),
        "existing_run": None,
        "dashboard": {
            "snapshot": {"id": str(uuid.uuid4()), "cash_value": "400"},
            "positions": [
                {
                    "isin": "IE00BK5BQT80",
                    "name": "Secret holding",
                    "symbol": "VWCE",
                    "asset_type": "ETF",
                    "currency": "EUR",
                }
            ],
            "plan": {"version": 1, "content_markdown": "Sensitive allocation plan"},
            "previous_briefing": {"content_markdown": "Sensitive strategy"},
            "previous_portfolio": {"positions": [{"name": "Secret former holding"}]},
            "reports": [{"content_markdown": "Unrelated portfolio evidence"}],
        },
        "previous_reports": {
            "report.positions": {"content_markdown": "Position research baseline"},
            "report.market": {"content_markdown": "Public market baseline"},
        },
        "report_settings": [],
    }


def result_for(task):
    portfolio = task.get("current_portfolio")
    selected = (
        [workflow.position_key(p) for p in portfolio["positions"]]
        if portfolio
        else ["markets"]
    )
    return {
        "contract_version": 1,
        "id": task["report_id"],
        "run_id": task["run_id"],
        "skill": task["skill"],
        "analysis_type": task["analysis_type"],
        "content_markdown": "# Research\n\nSourced evidence.",
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": portfolio["snapshot"]["id"] if portfolio else None,
        "status": "complete",
        "coverage": {
            "selected": selected,
            "researched": selected.copy(),
            "uncovered": [],
        },
        "gaps": ["Long-term forecast uncertain."],
    }


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.folder = Path(self.temporary.name) / "run"
        self.context = app_context()
        self.state = workflow.initialize(self.folder, self.context, flow())

    def complete(self, skill, *, content=None):
        task = workflow.start(self.folder, skill)
        result = result_for(task)
        if content:
            result["content_markdown"] = content
        workflow.write(self.folder / skill / "result.json", result)
        state = workflow.collect(self.folder, skill)
        self.assertEqual(state["tasks"][skill]["status"], "complete")
        return result

    def prepare(self):
        value = {
            "source_fingerprint": self.context["source_fingerprint"],
            "evidence_fingerprint": "c" * 64,
            "dashboard": copy.deepcopy(self.context["dashboard"]),
        }
        value["dashboard"]["reports"] = workflow.draft(self.folder)["research"]
        return workflow.prepared(self.folder, value)

    def final_strategy(self):
        task = workflow.read(self.folder / "strategy" / "input.json")
        return {
            "contract_version": 1,
            "run_id": self.state["run_id"],
            "evidence_fingerprint": task["strategy_context"]["evidence_fingerprint"],
            "status": "complete",
            "expected_plan_version": 1,
            "strategy": {
                "title": "Portfolio strategy",
                "content_markdown": "Hold the plan.",
            },
        }

    def all_research(self):
        for name in self.state["tasks"]:
            self.complete(name)

    def test_generation_notes_validate_and_survive_publication(self):
        self.all_research()
        self.prepare()
        for notes in ("", " \n ", "a" * 20_001, 7, []):
            with self.subTest(notes=repr(notes)[:40]):
                result = self.final_strategy()
                result["strategy"]["generation_notes_markdown"] = notes
                with self.assertRaisesRegex(ValueError, "generation notes"):
                    workflow.accept_strategy(self.folder, result)
        result = self.final_strategy()
        result["strategy"]["generation_notes_markdown"] = "a" * 20_000
        workflow.accept_strategy(self.folder, result)
        self.assertEqual(workflow.publication(self.folder)["strategy"], result["strategy"])

    def test_null_generation_notes_are_accepted(self):
        self.all_research()
        self.prepare()
        result = self.final_strategy()
        result["strategy"]["generation_notes_markdown"] = None
        workflow.accept_strategy(self.folder, result)
        self.assertEqual(workflow.publication(self.folder)["strategy"], result["strategy"])

    def test_input_partition_does_not_leak_portfolio_into_market_worker(self):
        market = workflow.read(self.folder / "market" / "input.json")
        positions = workflow.read(self.folder / "positions" / "input.json")
        self.assertEqual(
            market["previous_report"]["content_markdown"], "Public market baseline"
        )
        for forbidden in (
            "current_portfolio",
            "plan",
            "previous_strategy",
            "dashboard",
            "reports",
        ):
            self.assertNotIn(forbidden, market)
        self.assertNotIn("Secret", json.dumps(market))
        self.assertNotIn("Sensitive", json.dumps(market))
        self.assertEqual(
            positions["current_portfolio"]["positions"],
            self.context["dashboard"]["positions"],
        )
        self.assertNotIn("plan", positions)
        self.assertNotIn("previous_strategy", positions)
        self.assertNotEqual(market["report_id"], positions["report_id"])
        self.assertEqual(market["run_id"], positions["run_id"])

    def test_only_requested_plan_and_previous_strategy_are_projected(self):
        task = workflow.make_input(
            step("special", requires=["plan", "previous_strategy"]),
            self.context,
            self.state["run_id"],
        )
        self.assertEqual(task["plan"], self.context["dashboard"]["plan"])
        self.assertEqual(
            task["previous_strategy"]["previous_portfolio"],
            self.context["dashboard"]["previous_portfolio"],
        )
        self.assertNotIn("current_portfolio", task)
        self.assertNotIn("previous_report", task)

    def test_cash_only_snapshot_can_run_with_empty_position_coverage(self):
        folder = Path(self.temporary.name) / "cash-run"
        context = app_context()
        context["dashboard"]["positions"] = []
        workflow.initialize(folder, context, flow())
        task = workflow.start(folder, "positions")
        result = result_for(task)
        self.assertEqual(result["coverage"]["selected"], [])
        workflow.write(folder / "positions" / "result.json", result)
        self.assertEqual(
            workflow.collect(folder, "positions")["tasks"]["positions"]["status"],
            "complete",
        )

    def test_existing_daily_receipt_and_absent_portfolio_stop_initialization(self):
        context = app_context()
        context["existing_run"] = {"run_id": str(uuid.uuid4())}
        folder = Path(self.temporary.name) / "new"
        with self.assertRaises(ValueError):
            workflow.initialize(folder, context, flow())
        self.assertFalse(folder.exists())
        context["existing_run"] = None
        context["dashboard"]["snapshot"] = None
        with self.assertRaises(ValueError):
            workflow.initialize(folder, context, flow())
        self.assertFalse(folder.exists())

    def test_existing_run_folder_is_not_overwritten(self):
        before = (self.folder / "state.json").read_bytes()
        with self.assertRaises(ValueError):
            workflow.initialize(self.folder, self.context, flow())
        self.assertEqual((self.folder / "state.json").read_bytes(), before)

    def test_independent_tasks_can_run_concurrently_and_strategy_waits_for_all(self):
        tasks = {
            skill: workflow.start(self.folder, skill) for skill in self.state["tasks"]
        }
        self.assertTrue(
            all(
                t["status"] == "running"
                for t in workflow.read_state(self.folder)["tasks"].values()
            )
        )
        with self.assertRaises(ValueError):
            workflow.draft(self.folder)
        workflow.write(
            self.folder / "positions" / "result.json", result_for(tasks["positions"])
        )
        workflow.collect(self.folder, "positions")
        with self.assertRaises(ValueError):
            self.prepare()
        workflow.write(
            self.folder / "market" / "result.json", result_for(tasks["market"])
        )
        workflow.collect(self.folder, "market")
        self.assertEqual(len(workflow.draft(self.folder)["research"]), 2)
        self.assertEqual(self.prepare()["followup_round"], 0)

    def test_failed_task_gets_exactly_one_retry_and_preserves_ids(self):
        first = workflow.start(self.folder, "positions")
        failed = workflow.collect(self.folder, "positions", failed=True)
        self.assertFalse(failed["stopped"])
        self.assertEqual(failed["tasks"]["positions"]["attempts"], 1)
        self.assertEqual(workflow.start(self.folder, "positions"), first)
        failed = workflow.collect(self.folder, "positions", failed=True)
        self.assertTrue(failed["stopped"])
        self.assertEqual(failed["tasks"]["positions"]["attempts"], 2)
        with self.assertRaises(ValueError):
            workflow.start(self.folder, "positions")
        with self.assertRaises(ValueError):
            workflow.start(self.folder, "market")
        with self.assertRaises(ValueError):
            workflow.draft(self.folder)
        self.assertFalse((self.folder / "publication.json").exists())

    def test_invalid_result_can_be_corrected_on_one_retry(self):
        task = workflow.start(self.folder, "positions")
        invalid = result_for(task)
        invalid["coverage"] = {"selected": [], "researched": [], "uncovered": []}
        workflow.write(self.folder / "positions" / "result.json", invalid)
        self.assertEqual(
            workflow.collect(self.folder, "positions")["tasks"]["positions"]["status"],
            "failed",
        )
        self.assertFalse((self.folder / "positions" / "accepted.json").exists())
        self.complete("positions")
        self.assertEqual(
            workflow.read_state(self.folder)["tasks"]["positions"]["attempts"], 2
        )

    def test_malformed_timestamp_is_failed_attempt_not_unhandled_exception(self):
        task = workflow.start(self.folder, "positions")
        result = result_for(task)
        result["researched_at"] = None
        workflow.write(self.folder / "positions" / "result.json", result)
        state = workflow.collect(self.folder, "positions")
        self.assertEqual(state["tasks"]["positions"]["status"], "failed")
        self.assertFalse(state["stopped"])

    def test_ids_snapshot_and_coverage_are_validated(self):
        task = workflow.read(self.folder / "positions" / "input.json")
        original = result_for(task)
        mutations = [
            {"id": str(uuid.uuid4())},
            {"run_id": str(uuid.uuid4())},
            {"skill": "other"},
            {"analysis_type": "other.type"},
            {"snapshot_id": str(uuid.uuid4())},
            {"status": "partial"},
            {"content_markdown": "  \n "},
            {
                "coverage": {
                    "selected": ["other"],
                    "researched": ["other"],
                    "uncovered": [],
                }
            },
            {
                "coverage": {
                    "selected": ["IE00BK5BQT80"],
                    "researched": [],
                    "uncovered": ["IE00BK5BQT80"],
                }
            },
            {"extra": "unexpected"},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                workflow.validate_result({**original, **mutation}, task)
        market = workflow.read(self.folder / "market" / "input.json")
        result = result_for(market)
        result["snapshot_id"] = self.context["dashboard"]["snapshot"]["id"]
        with self.assertRaises(ValueError):
            workflow.validate_result(result, market)

    def test_one_followup_round_then_final_strategy_freezes_publication(self):
        self.all_research()
        old_market = workflow.read(self.folder / "market" / "accepted.json")
        self.prepare()
        request = {
            "contract_version": 1,
            "run_id": self.state["run_id"],
            "evidence_fingerprint": "c" * 64,
            "status": "needs_research",
            "requests": [
                {"skill": "positions", "questions": ["Verify valuation evidence."]}
            ],
        }
        state = workflow.accept_strategy(self.folder, request)
        self.assertEqual(state["followup_round"], 1)
        self.assertEqual(state["tasks"]["positions"]["attempts"], 0)
        self.assertEqual(state["tasks"]["market"]["status"], "complete")
        inputs = workflow.read(self.folder / "positions" / "input.json")
        self.assertEqual(inputs["followup_round"], 1)
        self.assertIn("current_draft", inputs)
        with self.assertRaises(ValueError):
            workflow.draft(self.folder)
        self.complete(
            "positions", content="# Research\n\nUpdated complete valuation evidence."
        )
        self.assertEqual(
            workflow.read(self.folder / "market" / "accepted.json"), old_market
        )
        self.assertEqual(self.prepare()["followup_round"], 1)
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, request)
        workflow.accept_strategy(self.folder, self.final_strategy())
        frozen = workflow.publication(self.folder)
        before = (self.folder / "publication.json").read_bytes()
        self.assertEqual(workflow.publication(self.folder), frozen)
        self.assertEqual((self.folder / "publication.json").read_bytes(), before)
        self.assertNotIn("plan_update", frozen)
        self.assertEqual(frozen["run_id"], self.state["run_id"])
        self.assertIn(
            "Updated complete",
            next(
                r["content_markdown"]
                for r in frozen["research"]
                if r["skill"] == "positions"
            ),
        )
        accepted = workflow.read(self.folder / "strategy" / "accepted.json")
        accepted["strategy"]["content_markdown"] = "Unexpected modification"
        workflow.write(self.folder / "strategy" / "accepted.json", accepted)
        with self.assertRaises(ValueError):
            workflow.publication(self.folder)
        self.assertEqual((self.folder / "publication.json").read_bytes(), before)

    def test_invalid_followup_batch_changes_no_task(self):
        self.all_research()
        self.prepare()
        before = workflow.read_state(self.folder)
        inputs = (self.folder / "positions" / "input.json").read_bytes()
        request = {
            "contract_version": 1,
            "run_id": self.state["run_id"],
            "evidence_fingerprint": "c" * 64,
            "status": "needs_research",
            "requests": [
                {"skill": "positions", "questions": ["Valid question"]},
                {"skill": "unknown", "questions": ["Invalid routing"]},
            ],
        }
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, request)
        self.assertEqual(workflow.read_state(self.folder), before)
        self.assertEqual(
            (self.folder / "positions" / "input.json").read_bytes(), inputs
        )

    def test_excluded_research_cannot_receive_strategy_followup(self):
        self.all_research()
        value = self.prepare()["strategy_context"]
        value["dashboard"]["reports"] = [
            r
            for r in value["dashboard"]["reports"]
            if r["analysis_type"] != "report.positions"
        ]
        workflow.prepared(self.folder, value)
        before = workflow.read_state(self.folder)
        inputs = (self.folder / "positions" / "input.json").read_bytes()
        request = {
            "contract_version": 1,
            "run_id": self.state["run_id"],
            "evidence_fingerprint": "c" * 64,
            "status": "needs_research",
            "requests": [{"skill": "positions", "questions": ["Should we rebalance?"]}],
        }
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, request)
        self.assertEqual(workflow.read_state(self.folder), before)
        self.assertEqual(
            (self.folder / "positions" / "input.json").read_bytes(), inputs
        )

    def test_changed_research_after_prepare_and_wrong_evidence_stop_strategy(self):
        self.all_research()
        self.prepare()
        strategy = self.final_strategy()
        strategy["evidence_fingerprint"] = "d" * 64
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, strategy)
        accepted = workflow.read(self.folder / "positions" / "accepted.json")
        accepted["content_markdown"] += " Changed after prepare"
        workflow.write(self.folder / "positions" / "accepted.json", accepted)
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, self.final_strategy())

    def test_first_strategy_requires_plan_and_checks_expected_version(self):
        self.all_research()
        prepared = {
            "source_fingerprint": self.context["source_fingerprint"],
            "evidence_fingerprint": "c" * 64,
            "dashboard": {"plan": None},
        }
        workflow.prepared(self.folder, prepared)
        strategy = self.final_strategy()
        strategy["expected_plan_version"] = 0
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, strategy)
        strategy["plan_update"] = {
            "content_markdown": "# Long-term plan",
            "change_reason": "First plan",
        }
        strategy["expected_plan_version"] = 1
        with self.assertRaises(ValueError):
            workflow.accept_strategy(self.folder, strategy)
        strategy["expected_plan_version"] = 0
        workflow.accept_strategy(self.folder, strategy)
        self.assertEqual(
            workflow.publication(self.folder)["plan_update"], strategy["plan_update"]
        )

    def test_transport_limit_prevents_publication_file_creation(self):
        self.all_research()
        self.prepare()
        workflow.accept_strategy(self.folder, self.final_strategy())
        with patch.object(workflow, "MAX_BYTES", 100), self.assertRaises(ValueError):
            workflow.publication(self.folder)
        self.assertFalse((self.folder / "publication.json").exists())


class DiscoveryAndProfileTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        for item in flow()["steps"]:
            self.add_skill(item)

    def add_skill(self, item):
        folder = self.root / "skills" / item["skill"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "SKILL.md").write_text("# Test skill\n")
        workflow.write(folder / "workflow.json", item)

    def test_additional_research_discovered_without_registry_edit(self):
        self.add_skill(step("commodities", produces="commodities.outlook"))
        discovered = workflow.discover(self.root)
        self.assertEqual(len(discovered["steps"]), 4)
        self.assertIn("commodities", {s["skill"] for s in discovered["steps"]})
        (self.root / "skills" / "irrelevant-research").mkdir()
        self.assertEqual(workflow.discover(self.root), discovered)

    def test_installed_plugin_contracts_discover(self):
        discovered = workflow.discover(PLUGIN)
        self.assertEqual(sum(s["stage"] == "strategy" for s in discovered["steps"]), 1)
        self.assertEqual(sum(s["stage"] == "research" for s in discovered["steps"]), 5)
        self.assertIn("portfolio-strategy", {s["skill"] for s in discovered["steps"]})

    def test_unknown_versions_inputs_duplicate_types_and_cycles_rejected(self):
        original = step("market", requires=["previous_report"])
        changes = [
            {"contract_version": 2},
            {"requires": ["unknown"]},
            {"requires": ["previous_report", "previous_report"]},
            {"requires": ["strategy_context"]},
            {"stage": "unknown"},
            {"produces": "report.positions"},
            {"unknown": True},
            {"skill": "different-folder"},
        ]
        for change in changes:
            with self.subTest(change=change):
                workflow.write(
                    self.root / "skills" / "market" / "workflow.json",
                    {**original, **change},
                )
                with self.assertRaises(ValueError):
                    workflow.discover(self.root)
        workflow.write(self.root / "skills" / "market" / "workflow.json", original)
        (self.root / "skills" / "market" / "SKILL.md").unlink()
        with self.assertRaises(ValueError):
            workflow.discover(self.root)

    def test_overlong_identifiers_rejected_before_mcp(self):
        for extra in [step("a" * 65), step("commodity", produces="a" * 161)]:
            with self.subTest(extra=extra):
                self.add_skill(extra)
                with self.assertRaises(ValueError):
                    workflow.discover(self.root)
                path = self.root / "skills" / extra["skill"]
                (path / "workflow.json").unlink()

    def test_symlink_escape_is_rejected(self):
        outside = self.root / "outside.json"
        workflow.write(outside, step("escape"))
        plugin_root = self.root / "plugin"
        for item in flow()["steps"]:
            path = plugin_root / "skills" / item["skill"]
            path.mkdir(parents=True)
            workflow.write(path / "workflow.json", item)
            (path / "SKILL.md").write_text("# Skill")
        target = plugin_root / "skills" / "escape"
        target.mkdir()
        (target / "workflow.json").symlink_to(outside)
        (target / "SKILL.md").write_text("# Escape")
        with self.assertRaises(ValueError):
            workflow.discover(plugin_root)

    def test_unmanaged_collision_leaves_every_profile_unchanged(self):
        directory = self.root / ".codex" / "agents"
        directory.mkdir(parents=True)
        managed = directory / "portfolio-research-agent.toml"
        unmanaged = directory / "portfolio-strategy-agent.toml"
        managed.write_text(profiles.MARKER + 'name = "old-managed"\n')
        unmanaged.write_text('name = "user-owned"\n')
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        with self.assertRaises(ValueError):
            profiles.install(self.root)
        self.assertEqual({p.name: p.read_bytes() for p in directory.iterdir()}, before)

    def test_profiles_install_idempotently_and_leave_other_configuration(self):
        self.root.joinpath(".codex").mkdir()
        settings = self.root / ".codex" / "config.toml"
        settings.write_text('model = "user-choice"\n')
        installed = profiles.install(self.root)
        before = {p: Path(p).read_bytes() for p in installed}
        self.assertEqual(profiles.install(self.root), installed)
        self.assertEqual({p: Path(p).read_bytes() for p in installed}, before)
        self.assertEqual(settings.read_text(), 'model = "user-choice"\n')
        self.assertEqual(len(installed), 2)
        for name in installed:
            value = tomllib.loads(Path(name).read_text())
            self.assertIn("developer_instructions", value)
            self.assertNotIn("model", value)
            self.assertNotIn("model_reasoning_effort", value)
            self.assertNotIn(str(PLUGIN), value["developer_instructions"])


class MCPClientTests(unittest.TestCase):
    @staticmethod
    def process(*responses):
        return subprocess.CompletedProcess(
            args=["mock-bridge", "mcp"],
            returncode=0,
            stdout="\n".join(json.dumps(r) for r in responses) + "\n",
            stderr="",
        )

    def invoke(self, result, tool="get_analysis_context", arguments=None):
        process = self.process(
            {"jsonrpc": "2.0", "id": 1, "result": {"protocolVersion": "2025-06-18"}},
            {"jsonrpc": "2.0", "id": 2, "result": result},
        )
        with patch.object(mcp_call.subprocess, "run", return_value=process) as run:
            value = mcp_call.call(
                tool, arguments or {}, bridge="/mock/bridge", timeout=7
            )
        run.assert_called_once()
        return value, run.call_args.kwargs

    def test_tools_list_and_handshake_wire(self):
        result = {"tools": [{"name": "publish_analysis_run"}]}
        value, kwargs = self.invoke(result, tool="list")
        self.assertEqual(value, result)
        messages = [json.loads(line) for line in kwargs["input"].splitlines()]
        self.assertEqual(
            [m["method"] for m in messages],
            ["initialize", "notifications/initialized", "tools/list"],
        )
        self.assertEqual(messages[-1]["params"], {})
        self.assertEqual(kwargs["timeout"], 7)
        self.assertTrue(kwargs["capture_output"])
        self.assertFalse(kwargs["check"])

    def test_direct_and_result_wrapped_structured_content(self):
        expected = {"run_id": str(uuid.uuid4()), "created": True}
        for payload in [expected, {"result": expected}]:
            with self.subTest(payload=payload):
                value, kwargs = self.invoke(
                    {"structuredContent": payload},
                    tool="publish_analysis_run",
                    arguments={"publication": {"run_id": expected["run_id"]}},
                )
                self.assertEqual(value, expected)
                request = json.loads(kwargs["input"].splitlines()[-1])
                self.assertEqual(request["method"], "tools/call")
                self.assertEqual(request["params"]["name"], "publish_analysis_run")
                self.assertEqual(
                    request["params"]["arguments"],
                    {"publication": {"run_id": expected["run_id"]}},
                )
        structured = {"result": expected, "metadata": "preserved"}
        self.assertEqual(self.invoke({"structuredContent": structured})[0], structured)

    def test_json_text_result(self):
        expected = {"content_markdown": "Vollständiger Bericht mit Umlauten: Größe."}
        value, _ = self.invoke(
            {"content": [{"type": "text", "text": json.dumps(expected)}]}
        )
        self.assertEqual(value, expected)

    def test_initialization_failure_never_retries(self):
        failures = [
            {"id": 1, "error": {"message": "not paired"}},
            {"id": 9, "result": {}},
            {"id": 1},
        ]
        for response in failures:
            with self.subTest(response=response):
                with (
                    patch.object(
                        mcp_call.subprocess, "run", return_value=self.process(response)
                    ) as run,
                    self.assertRaises(RuntimeError),
                ):
                    mcp_call.call("get_analysis_context", {})
                run.assert_called_once()

    def test_tool_errors_and_json_rpc_error_propagate_without_retry(self):
        errors = [
            {
                "id": 2,
                "result": {
                    "isError": True,
                    "content": [{"type": "text", "text": "context changed"}],
                },
            },
            {"id": 2, "error": {"message": "context changed"}},
        ]
        for error in errors:
            with self.subTest(error=error):
                response = self.process({"id": 1, "result": {}}, error)
                with (
                    patch.object(
                        mcp_call.subprocess, "run", return_value=response
                    ) as run,
                    self.assertRaisesRegex(RuntimeError, "context changed"),
                ):
                    mcp_call.call(
                        "publish_analysis_run", {"publication": {"run_id": "fixed"}}
                    )
                run.assert_called_once()

    def test_missing_tool_response_marks_uncertain_outcome_without_retry(self):
        response = self.process({"id": 1, "result": {}})
        with (
            patch.object(mcp_call.subprocess, "run", return_value=response) as run,
            self.assertRaisesRegex(RuntimeError, "uncertain"),
        ):
            mcp_call.call("publish_analysis_run", {})
        run.assert_called_once()

    def test_bridge_timeout_is_not_automatically_retried(self):
        with (
            patch.object(
                mcp_call.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("bridge", 7),
            ) as run,
            self.assertRaises(subprocess.TimeoutExpired),
        ):
            mcp_call.call("publish_analysis_run", {}, timeout=7)
        run.assert_called_once()

    def test_disallowed_calls_do_not_launch_bridge(self):
        for tool in [
            "publish_analysis",
            "publish_portfolio_snapshot_and_analysis",
            "unknown",
        ]:
            with (
                self.subTest(tool=tool),
                patch.object(mcp_call.subprocess, "run") as run,
            ):
                with self.assertRaises(ValueError):
                    mcp_call.call(tool, {})
                run.assert_not_called()

    def test_ambiguous_text_result_is_rejected(self):
        for result in [
            {"content": []},
            {"content": [{"type": "text", "text": "{}"}] * 2},
        ]:
            with self.subTest(result=result), self.assertRaises(RuntimeError):
                self.invoke(result)


if __name__ == "__main__":
    unittest.main()
