import ast
import io
import os
import sys
import tempfile
import unittest

import grade_calc


class GradeCalcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, name, text):
        p = os.path.join(self.tmp.name, name)
        with open(p, "w") as fh:
            fh.write(text)
        return p

    def run_cli(self, scores, weights):
        sp = self.write("s.csv", scores) if scores is not None else "/nonexistent/s.csv"
        wp = self.write("w.csv", weights) if weights is not None else "/nonexistent/w.csv"
        out, err = io.StringIO(), io.StringIO()
        code = grade_calc.main([sp, wp], out, err)
        return code, out.getvalue(), err.getvalue()

    def test_weights_normalized(self):
        n = grade_calc.normalize_weights({"a": 1.0, "b": 1.0})
        self.assertAlmostEqual(sum(n.values()), 100.0)
        self.assertAlmostEqual(n["a"], 50.0)
        scores = "student,a,b\nAnn,80,100\n"
        r1 = self.run_cli(scores, "assessment,weight\na,1\nb,1\n")
        r2 = self.run_cli(scores, "assessment,weight\na,50%\nb,50%\n")
        r3 = self.run_cli(scores, "assessment,weight\na,30\nb,30\n")
        self.assertEqual(r1, r2)
        self.assertEqual(r1, r3)
        self.assertIn("90.00", r1[1])

    def test_weighted_final_grade(self):
        code, out, _ = self.run_cli(
            "student,hw,exam\nAnn,100,50\nBob,0,100\n",
            "assessment,weight\nhw,25\nexam,75\n")
        self.assertEqual(code, 0)
        self.assertIn("62.50", out)  # Ann: 25 + 37.5
        self.assertIn("75.00", out)  # Bob

    def test_letter_and_gpa_boundaries(self):
        cases = [(90, "A", 4.0), (89.99, "B", 3.0), (80, "B", 3.0),
                 (70, "C", 2.0), (60, "D", 1.0), (59.99, "F", 0.0)]
        for g, letter, gpa in cases:
            self.assertEqual(grade_calc.letter_and_gpa(g), (letter, gpa), g)
        # unrounded grade decides: 89.999 displays as 90.00 but is a B
        code, out, _ = self.run_cli("student,a\nAnn,89.999\n", "assessment,weight\na,1\n")
        self.assertIn("90.00", out)
        self.assertIn(" B ", out)

    def test_class_statistics(self):
        odd = grade_calc.class_stats([60.0, 70.0, 100.0])
        self.assertAlmostEqual(odd["mean"], 230 / 3)
        self.assertEqual(odd["median"], 70.0)
        self.assertEqual(odd["highest"], 100.0)
        self.assertEqual(odd["lowest"], 60.0)
        even = grade_calc.class_stats([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        self.assertEqual(even["mean"], 5.0)
        self.assertEqual(even["median"], 4.5)
        self.assertAlmostEqual(even["std dev"], 2.0)  # population
        code, out, _ = self.run_cli(
            "student,a\nA,60\nB,70\nC,100\n", "assessment,weight\na,100\n")
        for label in ("mean", "median", "std dev", "highest", "lowest"):
            self.assertIn(label, out)
        self.assertIn("76.67", out)

    def test_invalid_input_exits_2(self):
        w = "assessment,weight\na,1\nb,1\n"
        cases = {
            "missing scores file": (None, w),
            "missing weights file": ("student,a,b\nA,1,2\n", None),
            "assessment without weight": ("student,a,c\nA,1,2\n", w),
            "weight without column": ("student,a\nA,1\n", w),
            "blank score": ("student,a,b\nA,1,\n", w),
            "non-numeric score": ("student,a,b\nA,1,x\n", w),
            "out of range score": ("student,a,b\nA,1,101\n", w),
            "zero weight": ("student,a,b\nA,1,2\n", "assessment,weight\na,0\nb,1\n"),
            "negative weight": ("student,a,b\nA,1,2\n", "assessment,weight\na,-1\nb,1\n"),
            "bad weight": ("student,a,b\nA,1,2\n", "assessment,weight\na,abc\nb,1\n"),
            "short row": ("student,a,b\nA,1\n", w),
            "no students": ("student,a,b\n", w),
        }
        for label, (s, wt) in cases.items():
            code, out, err = self.run_cli(s, wt)
            self.assertEqual(code, 2, label)
            self.assertTrue(err.startswith("error:"), label)
            self.assertEqual(out, "", label)
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(grade_calc.main([], out, err), 2)

    def test_stdlib_only(self):
        path = os.path.join(os.path.dirname(os.path.abspath(grade_calc.__file__)),
                            "grade_calc.py")
        with open(path) as fh:
            tree = ast.parse(fh.read())
        stdlib = set(getattr(sys, "stdlib_module_names", ())) or {"csv", "math", "sys"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = [node.module or ""]
            else:
                continue
            for m in mods:
                self.assertIn(m.split(".")[0], stdlib, m)
        self.assertTrue(os.path.isfile(path))


if __name__ == "__main__":
    unittest.main()
