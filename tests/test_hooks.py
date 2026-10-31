from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import make_project

from forgemyspec import hooks, project, risk


def _denied(answer) -> bool:
    return answer.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


class _Project(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self._tmp.name)).resolve()
        self._env = patch.dict(os.environ, {"CLAUDE_PROJECT_DIR": str(self.root)})
        self._env.start()

    def tearDown(self) -> None:
        self._env.stop()
        self._tmp.cleanup()

    def tool(self, name: str, **data):
        return hooks.pre_tool_use({"tool_name": name, "cwd": str(self.root), "session_id": "s", "tool_input": data})


class FileGuardTests(_Project):
    def test_decision_table(self) -> None:
        r = self.root
        spec = (r / "budget-core" / "spec.yaml").read_text(encoding="utf-8")
        denied = {
            "outside every spec": ("Write", {"file_path": str(r / "lib" / "x.py"), "content": "x"}),
            "locked contract": ("Edit", {"file_path": str(r / "budget-core" / "contract.dfy"), "old_string": "a", "new_string": "b"}),
            "locked tests": ("Write", {"file_path": str(r / "budget-core" / "tests.dfy"), "content": "x"}),
            "locked planted error": ("Write", {"file_path": str(r / "budget-core" / "planted" / "new.dfy"), "content": "x"}),
            "locked formal section": ("Edit", {"file_path": str(r / "budget-core" / "spec.yaml"),
                                               "old_string": "module: BudgetCore", "new_string": "module: Other"}),
            "locked version": ("Edit", {"file_path": str(r / "budget-core" / "spec.yaml"),
                                        "old_string": 'version: "0.1"', "new_string": 'version: "0.2"'}),
            "lock file": ("Write", {"file_path": str(r / "budget-core" / "contract.lock"), "content": "x"}),
            "generated": ("Write", {"file_path": str(r / "budget-core" / "generated" / "x.py"), "content": "x"}),
            "harness state": ("Write", {"file_path": str(r / ".forgemyspec" / "state" / "x.json"), "content": "x"}),
            "config": ("Write", {"file_path": str(r / ".forgemyspec" / "config.yaml"), "content": "x"}),
            "settings": ("Write", {"file_path": str(r / ".claude" / "settings.json"), "content": "{}"}),
            "scope not approved": ("Write", {"file_path": str(r / "draft" / "x.py"), "content": "x"}),
            "approved spec-only spec": ("Edit", {"file_path": str(r / "app-spec" / "spec.yaml"), "old_string": "a", "new_string": "b"}),
        }
        allowed = {
            "implementation with lock": ("Edit", {"file_path": str(r / "budget-core" / "impl.dfy"), "old_string": "a", "new_string": "b"}),
            "shell with lock": ("Write", {"file_path": str(r / "budget-core" / "shell" / "new.py"), "content": "x"}),
            "formal spec outside the formal section": ("Edit", {"file_path": str(r / "budget-core" / "spec.yaml"),
                                                                "old_string": spec.split("\n")[1], "new_string": 'title: "Another title"'}),
            "allow_paths": ("Edit", {"file_path": str(r / "README.md"), "old_string": "a", "new_string": "b"}),
            "approved scope": ("Write", {"file_path": str(r / "app" / "new.py"), "content": "x"}),
            "outside the project": ("Write", {"file_path": "/tmp/forgemyspec-outside.py", "content": "x"}),
            "new spec": ("Write", {"file_path": str(r / "new-bundle" / "spec.yaml"), "content": "x: 1"}),
        }
        for case, (name, data) in denied.items():
            with self.subTest(case=case):
                answer = self.tool(name, **data)
                self.assertTrue(_denied(answer), answer)
                self.assertIn("ForgeMySpec", answer["hookSpecificOutput"]["permissionDecisionReason"])
        for case, (name, data) in allowed.items():
            with self.subTest(case=case):
                self.assertEqual(self.tool(name, **data), {})

    def test_reasons_name_the_next_step(self) -> None:
        answer = self.tool("Write", file_path=str(self.root / "lib" / "x.py"), content="x")
        self.assertIn("Next step", answer["hookSpecificOutput"]["permissionDecisionReason"])

    def test_crashing_guard_blocks(self) -> None:
        out = io.StringIO()
        self.assertEqual(hooks.main("pre-tool-use", stdin=io.StringIO("{not json"), stdout=out), 2)
        with patch.object(hooks, "decide_path", side_effect=RuntimeError("broke")):
            event = json.dumps({"tool_name": "Write", "cwd": str(self.root), "tool_input": {"file_path": str(self.root / "README.md")}})
            self.assertEqual(hooks.main("pre-tool-use", stdin=io.StringIO(event), stdout=out), 2)


class BashGuardTests(_Project):
    def test_decision_table(self) -> None:
        denied = [
            "PYTHONPATH=src python3 -m forgemyspec lock budget-core",
            "python3 -m forgemyspec approve app-spec",
            "python3 -m forgemyspec unlock budget-core",
            "python3 -m forgemyspec init .",
            "git commit --no-verify -m x",
            "git commit -nm x",
            "git -c core.hooksPath=/dev/null commit -m x",
            "git config --unset core.hooksPath",
            "cd budget-core && echo x > contract.lock",
            "echo x > budget-core/contract.lock",
            "sed -i '' 's/a/b/' budget-core/contract.dfy",
            "echo x | tee lib/new.py",
            "cp /tmp/x budget-core/generated/x.py",
            "python3 - <<'EOF'\nopen('lib/new.py', 'w').write('x')\nEOF",
            "python3 -c \"open('lib/y.py','w').write('x')\"",
        ]
        allowed = [
            "ls -la",
            "cat budget-core/contract.dfy",
            "grep -n ensures budget-core/contract.dfy",
            "PYTHONPATH=src python3 -m forgemyspec lock budget-core --check",
            "PYTHONPATH=src python3 -m forgemyspec gate budget-core",
            "echo x > /tmp/forgemyspec-out.txt",
            "python3 - <<'EOF'\nif 3 > 2: print(open('budget-core/impl.dfy').read()[:5])\nEOF",
            "git commit -m 'normal message'",
            "echo x > app/new.py",
            # false blocks fixed: a version literal, a sed expression, a cd, reading hooksPath
            "python3 - <<'EOF'\nv = \"0.5\"\nPath('/tmp/fms-out.txt').write_text(v)\nEOF",
            "sed -i '' 's/print/echo/' app/main.py",
            "cd /tmp && echo x > fms-relative.txt",
            "git config --get core.hooksPath",
        ]
        for command in denied:
            with self.subTest(command=command):
                self.assertTrue(_denied(self.tool("Bash", command=command)), command)
        for command in allowed:
            with self.subTest(command=command):
                self.assertEqual(self.tool("Bash", command=command), {}, command)


class StopHookTests(_Project):
    def stop(self, active: bool = False):
        return hooks.stop({"cwd": str(self.root), "session_id": "s", "stop_hook_active": active})

    def test_gate_states(self) -> None:
        config = project.load_config(self.root)
        bundles = {b.name: b for b in project.discover_bundles(self.root, config)}
        # Pending, passed, changed and repeated: the Stop hook never blocks and writes nothing in the chat.
        self.assertEqual(self.stop(), {})
        for name in ("budget-core", "app-spec"):
            project.write_gate_cache(bundles[name], config, {"passed": True, "stages": [], "evidence": {}})
        self.assertEqual(self.stop(), {})
        impl = self.root / "budget-core" / "impl.dfy"
        impl.write_text(impl.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        for _ in range(5):
            self.assertEqual(self.stop(active=True), {})
        ends = [e for e in project.read_ledger(self.root) if e.get("event") == "turn-end"]
        self.assertEqual(ends[-1]["pending"], ["budget-core"])


class RiskBoxTests(_Project):
    def _cache(self, evidence, strength=None) -> None:
        config = project.load_config(self.root)
        for b in project.discover_bundles(self.root, config):
            if b.name in {"budget-core", "app-spec"}:
                ev = evidence if b.name == "budget-core" else {
                    "o1": {"kind": "boundary", "status": "fragile", "reason": "boundary", "fails": [], "survivors": [],
                           "must_include": ["parser cli", "argument parsing"]}}
                project.write_gate_cache(b, config, {"passed": True, "stages": [], "evidence": ev, "strength": strength or {}})

    def _evidence(self, status="proven", reason="proof", fails=(), survivors=()):
        import yaml
        spec = yaml.safe_load((self.root / "budget-core" / "spec.yaml").read_text(encoding="utf-8"))
        ev = {}
        for o in spec["formal"]["obligations"]:
            boundary = o["kind"] == "boundary"
            ev[o["id"]] = {"kind": o["kind"], "statement": o["statement"], "must_include": o.get("must_include", []),
                           "status": "fragile" if boundary else "proven", "reason": "boundary" if boundary else "proof",
                           "fails": [], "survivors": []}
        ev["replay"].update(status=status, reason=reason, fails=list(fails), survivors=list(survivors))
        return ev

    def box(self) -> str:
        return risk.render(risk.build(self.root))

    def test_box_states(self) -> None:
        self._cache(self._evidence(), {"mutants": [14, 14], "planted": [4, 4]})
        box = self.box()
        self.assertIn("🟢 ledger replay", box)
        self.assertIn("strength: mutants 14/14 · planted errors 4/4", box)
        self.assertTrue(all(len(line) <= 60 for line in box.splitlines()), box)

        self._cache(self._evidence("fragile", "mutant", survivors=[{"place": "impl.dfy:42", "original": "+", "replacement": "-"}]))
        box = self.box()
        self.assertIn("🟡 ledger replay", box)
        self.assertIn("1 mutant(s) survived", box)
        self.assertIn("budget-core/impl.dfy:42", box)

        self._cache(self._evidence("leaking", "failed", fails=[{"stage": "verify", "place": "contract.dfy:60"}]))
        box = self.box()
        self.assertIn("🔴 ledger replay", box)
        self.assertIn("LEAKING: verification (dafny verify) failed", box)
        self.assertIn("WHERE IT LEAKS", box)
        self.assertIn("WHAT ONLY YOU GUARANTEE", box)
        self.assertTrue(all(len(line) <= 60 for line in box.splitlines()), box)

    def test_tokens_from_transcript(self) -> None:
        transcript = Path(self._tmp.name) / "t.jsonl"
        lines = [
            {"type": "user", "message": {"content": "before"}},
            {"type": "assistant", "message": {"id": "m0", "usage": {"input_tokens": 999, "output_tokens": 999}}},
            {"type": "user", "message": {"content": [{"type": "text", "text": "request"}]}},
            {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "cache_read_input_tokens": 1000,
                                                                   "cache_creation_input_tokens": 0, "output_tokens": 50}}},
            {"type": "assistant", "message": {"id": "m1", "usage": {"input_tokens": 10, "cache_read_input_tokens": 1000,
                                                                   "cache_creation_input_tokens": 0, "output_tokens": 50}}},
            {"type": "user", "message": {"content": [{"type": "tool_result", "content": "ok"}]}},
            {"type": "assistant", "message": {"id": "m2", "usage": {"input_tokens": 5, "cache_read_input_tokens": 2000,
                                                                   "cache_creation_input_tokens": 100, "output_tokens": 20}}},
        ]
        transcript.write_text("\n".join(json.dumps(line) for line in lines), encoding="utf-8")
        self.assertEqual(risk.turn_tokens(str(transcript)), (3115, 3000, 70))
        self.assertIsNone(risk.turn_tokens(str(Path(self._tmp.name) / "missing.jsonl")))


class StateTests(_Project):
    def test_summary(self) -> None:
        context = hooks.session_start({"cwd": str(self.root)})["hookSpecificOutput"]["additionalContext"]
        self.assertIn("budget-core [Dafny contract]: approved", context)
        self.assertIn("draft-spec [spec-only]: draft spec", context)
        self.assertIn("approve draft-spec", context)
        self.assertIn("Rules:", context)
        answer = hooks.user_prompt_submit({"cwd": str(self.root), "session_id": "s"})
        self.assertEqual(answer["hookSpecificOutput"]["hookEventName"], "UserPromptSubmit")


if __name__ == "__main__":
    unittest.main()
