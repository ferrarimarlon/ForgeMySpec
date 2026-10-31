from __future__ import annotations

import inspect
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import KERNEL_BUNDLE, make_project, make_valid_spec_data

from forgemyspec import gate, hooks, kernel, linting, project, risk
from forgemyspec.dafny_runner import find_dafny


class KernelTests(unittest.TestCase):
    def test_decisions_come_from_translated_kernel(self) -> None:
        # 1. The translated kernel answers like the proven contract.
        self.assertEqual(kernel.classify_obligation("boundary", 0, 0, True, False), ("fragile", "boundary"))
        self.assertEqual(kernel.requirement_status("locked", "current", ["proven", "leaking"]), ("leaking", "obligation", 1))
        self.assertEqual(kernel.decide_edit("BundleImpl", True, "draft", False, False), (False, "RImplWithoutLock"))
        self.assertEqual(kernel.coverage(["h1"], ["a"], [[]], [["a"]]), (["h1"], []))

        # 2. Gate, box, lint and guards follow the kernel: swapping it for a sentinel changes their output.
        ev = gate._Evidence({"formal": {"obligations": [{"id": "o", "kind": "dafny"}]}})
        with patch.object(kernel, "classify_obligation", return_value=("proven", "sentinel")):
            self.assertEqual(ev.finish()["o"]["reason"], "sentinel")

        spec = make_valid_spec_data()
        spec["formal"] = {"module": "X", "obligations": [{"id": "o", "kind": "boundary", "statement": "s", "hypotheses": ["h1", "h2"],
                                                           "must_include": ["parser cli", "argument parsing"], "test": "t.T.t"}]}
        with patch.object(kernel, "coverage", return_value=(["h-sentinel"], [])):
            messages = [i.message for i in linting.lint_spec(spec, require_formal=True).issues]
        self.assertTrue(any("h-sentinel" in m for m in messages))

        with tempfile.TemporaryDirectory() as tmp:
            root = make_project(Path(tmp)).resolve()
            config = project.load_config(root)
            bundles = project.discover_bundles(root, config)
            with patch.object(kernel, "decide_edit", return_value=(False, "RProtected")):
                allow, message = hooks.decide_path(root, config, bundles, root / "README.md")
            self.assertFalse(allow)
            self.assertIn("protected", message)
            budget = next(b for b in bundles if b.name == "budget-core")
            with patch.object(kernel, "requirement_status", return_value=("proven", "no-gate", None)):
                requirements = risk._bundle_requirements(budget, project.gate_status(budget, config))
            self.assertTrue(all(r.status == "proven" for r in requirements))

        # 3. None of the four rules is reimplemented in Python outside the bridge.
        for owner, name in ((gate._Evidence, "finish"), (risk, "_bundle_requirements"), (hooks, "decide_path")):
            self.assertIn("kernel.", inspect.getsource(getattr(owner, name)))

    @unittest.skipUnless(find_dafny(), "dafny is not installed; CI installs it and runs this")
    def test_translated_kernel_matches_a_fresh_translation(self) -> None:
        self.assertEqual(kernel.check(KERNEL_BUNDLE), [])


if __name__ == "__main__":
    unittest.main()
