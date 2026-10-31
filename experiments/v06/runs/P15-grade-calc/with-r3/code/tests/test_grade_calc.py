import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest

import grade_calc as gc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(d, name, text):
    p = os.path.join(d, name)
    with open(p, "w") as fh:
        fh.write(text)
    return p


def run_main(*args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = gc.main(list(args))
    return code, out.getvalue(), err.getvalue()


class GradeCalcTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.addCleanup(self.tmp.cleanup)
        self.weights = write(self.d, "weights.csv", "assessment,weight\nhw,30\nmid,30\nfinal,20\n")
        self.scores = write(self.d, "scores.csv", "student,hw,mid,final\nAnn,90,80,70\n")

    def test_weights_normalized_to_100(self):
        n = gc.normalize(gc.read_weights(self.weights))
        self.assertAlmostEqual(sum(n.values()), 100.0)
        self.assertAlmostEqual(n["hw"], 37.5)
        self.assertAlmostEqual(n["final"], 25.0)
        self.assertAlmostEqual(sum(gc.normalize({"a": 1, "b": 3}).values()), 100.0)

    def test_weighted_final_grade(self):
        n = gc.normalize(gc.read_weights(self.weights))
        students = gc.read_scores(self.scores, n)
        self.assertAlmostEqual(gc.final_grade(students[0][1], n), 81.25)

    def test_letter_and_gpa_boundaries(self):
        cases = [(95, "A", 4.0), (90, "A", 4.0), (89.99, "B", 3.0), (80, "B", 3.0),
                 (70, "C", 2.0), (60, "D", 1.0), (59.99, "F", 0.0), (0, "F", 0.0)]
        for g, letter, gpa in cases:
            self.assertEqual(gc.letter_gpa(g), (letter, gpa), g)

    def test_class_statistics(self):
        s = gc.class_stats([60, 70, 80, 90])
        self.assertAlmostEqual(s["mean"], 75)
        self.assertAlmostEqual(s["median"], 75)
        self.assertAlmostEqual(s["stddev"], 11.1803, places=3)
        self.assertEqual((s["highest"], s["lowest"]), (90, 60))
        self.assertEqual(gc.class_stats([50, 90, 60])["median"], 60)

    def test_invalid_input_exits_2(self):
        bad_scores = [
            "student,hw,mid\nAnn,90,80\n",                     # final missing
            "student,hw,mid,final,extra\nAnn,1,2,3,4\n",       # extra column, no weight
            "name,hw,mid,final\nAnn,90,80,70\n",               # bad header
            "student,hw,mid,final\nAnn,90,,70\n",              # blank
            "student,hw,mid,final\nAnn,90,abc,70\n",           # non numeric
            "student,hw,mid,final\nAnn,90,101,70\n",           # out of range
            "student,hw,mid,final\nAnn,90,80\n",               # short row
            "student,hw,mid,final\n",                          # no students
        ]
        for i, text in enumerate(bad_scores):
            p = write(self.d, f"bad{i}.csv", text)
            code, out, err = run_main(p, self.weights)
            self.assertEqual(code, 2, text)
            self.assertEqual(out, "")
            self.assertTrue(err.startswith("error:"), text)
        for i, text in enumerate(["assessment,weight\nhw,0\n", "assessment,weight\nhw,-5\n",
                                  "assessment,weight\n", "a,b\nhw,5\n",
                                  "assessment,weight\nhw,x\n"]):
            w = write(self.d, f"badweights{i}.csv", text)
            self.assertEqual(run_main(self.scores, w)[0], 2, text)
        self.assertEqual(run_main(os.path.join(self.d, "nope.csv"), self.weights)[0], 2)
        self.assertEqual(run_main(self.scores)[0], 2)

    def test_cli_end_to_end(self):
        s = write(self.d, "class.csv",
                  "student,hw,mid,final\nAnn,90,80,70\nBob,100,100,100\nCy,50,40,30\n")
        r = subprocess.run([sys.executable, os.path.join(ROOT, "grade_calc.py"), s, self.weights],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Ann: final 81.25 grade B GPA 3.0", r.stdout)
        self.assertIn("Bob: final 100.00 grade A GPA 4.0", r.stdout)
        self.assertIn("Cy: final 41.25 grade F GPA 0.0", r.stdout)
        for key in ("mean", "median", "stddev", "highest", "lowest"):
            self.assertIn(key, r.stdout)


if __name__ == "__main__":
    unittest.main()
