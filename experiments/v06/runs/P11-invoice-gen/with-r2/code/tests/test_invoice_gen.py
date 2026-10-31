import ast
import contextlib
import io
import json
import os
import tempfile
import unittest
from decimal import Decimal

import invoice_gen as ig


def good(**kw):
    inv = {"customer": {"name": "Acme"},
           "items": [{"description": "Widget", "quantity": 3, "unit_price": 0.125}],
           "tax_rate": 8.25}
    inv.update(kw)
    return ig.load_json(json.dumps(inv))


class ValidationTests(unittest.TestCase):
    def test_all_errors_reported_together(self):
        inv = ig.load_json(json.dumps({
            "customer": {"name": " "},
            "items": [{"description": "x", "quantity": 0, "unit_price": -1}],
            "tax_rate": 150,
            "discount": {"type": "percent", "value": 120}}))
        errs = ig.validate(inv)
        for f in ("customer.name", "items[0].quantity", "items[0].unit_price",
                  "tax_rate", "discount.value"):
            self.assertTrue(any(e.startswith(f) for e in errs), (f, errs))
        self.assertEqual(len(errs), 5)

    def test_valid(self):
        self.assertEqual(ig.validate(good()), [])


class ComputeTests(unittest.TestCase):
    def test_half_cent_rounding_and_grand_total(self):
        r = ig.compute(good())
        self.assertEqual(r["items"][0]["line_total"], Decimal("0.38"))
        inv = ig.load_json(json.dumps({
            "customer": {"name": "A"},
            "items": [{"description": "x", "quantity": 1, "unit_price": 10.10}],
            "tax_rate": 8.25}))
        r = ig.compute(inv)
        self.assertEqual(r["tax"], Decimal("0.83"))
        self.assertEqual(r["total"], Decimal("10.93"))
        inv = ig.load_json(json.dumps({
            "customer": {"name": "A"},
            "items": [{"description": "x", "quantity": 2, "unit_price": 10.05}],
            "tax_rate": 10, "discount": {"type": "percent", "value": 15}}))
        r = ig.compute(inv)
        self.assertEqual((r["subtotal"], r["discount"], r["tax"], r["total"]),
                         (Decimal("20.10"), Decimal("3.02"), Decimal("1.71"),
                          Decimal("18.79")))
        self.assertEqual(r["total"], r["subtotal"] - r["discount"] + r["tax"])

    def test_fixed_discount(self):
        r = ig.compute(good(discount={"type": "fixed", "value": 0.1}))
        self.assertEqual(r["discount"], Decimal("0.10"))


class FormatTests(unittest.TestCase):
    def test_text_invoice_layout(self):
        t = ig.format_text(ig.compute(good()))
        for s in ("Acme", "Widget", "0.125", "0.38", "Subtotal:", "Discount:",
                  "Tax (8.25%):", "TOTAL:"):
            self.assertIn(s, t)

    def test_json_export_matches_computation(self):
        r = ig.compute(good())
        d = json.loads(ig.to_json(r))
        self.assertEqual(d["subtotal"], "0.38")
        self.assertEqual(d["total"], str(r["total"]))
        self.assertEqual(d["items"][0]["line_total"], "0.38")


class CliTests(unittest.TestCase):
    def run_cli(self, content, *extra):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "i.json")
            if content is not None:
                with open(p, "w") as f:
                    f.write(content)
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = ig.main([p, *extra])
            return code, out.getvalue(), err.getvalue()

    def test_exit_codes(self):
        code, out, _ = self.run_cli(json.dumps(
            {"customer": {"name": "A"}, "items": [
                {"description": "x", "quantity": 1, "unit_price": 1}], "tax_rate": 0}))
        self.assertEqual(code, 0)
        self.assertIn("TOTAL:", out)
        code, out, _ = self.run_cli(json.dumps(
            {"customer": {"name": "A"}, "items": [
                {"description": "x", "quantity": 1, "unit_price": 1}], "tax_rate": 0}),
            "--format", "json")
        self.assertEqual(json.loads(out)["total"], "1.00")
        code, _, err = self.run_cli(json.dumps({"customer": {}, "items": [], "tax_rate": -1}))
        self.assertEqual(code, 2)
        self.assertGreaterEqual(err.count("\n  - "), 3)
        self.assertEqual(self.run_cli("{bad")[0], 2)
        self.assertEqual(self.run_cli(None)[0], 2)


class ConstraintTests(unittest.TestCase):
    def test_stdlib_only_single_file(self):
        import sys
        tree = ast.parse(open(ig.__file__).read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module.split(".")[0])
        std = getattr(sys, "stdlib_module_names", None) or {
            "argparse", "json", "sys", "decimal"}
        self.assertTrue(mods <= set(std), mods)


if __name__ == "__main__":
    unittest.main()
