import contextlib
import io
import os
import tempfile
import unittest

import grade_calc


def run(scores, weights):
    with tempfile.TemporaryDirectory() as d:
        paths = []
        for name, text in (("scores.csv", scores), ("weights.csv", weights)):
            p = os.path.join(d, name)
            if text is not None:
                with open(p, "w") as f:
                    f.write(text)
            paths.append(p)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = grade_calc.main(paths)
    return code, out.getvalue(), err.getvalue()


class GradeCalcTests(unittest.TestCase):
    def test_weights_normalized_and_weighted(self):
        data = "student,a,b\nAna,100,50\nBo,80,90\n"
        c1, o1, _ = run(data, "assessment,weight\na,1\nb,1\n")
        c2, o2, _ = run(data, "assessment,weight\na,50\nb,50\n")
        self.assertEqual((c1, c2), (0, 0))
        self.assertEqual(o1, o2)
        self.assertIn("75.00", o1)
        n = {"a": 0.75, "b": 0.25}
        self.assertEqual(grade_calc.final_grade({"a": 100, "b": 60}, n), 90.0)

    def test_letter_and_gpa_boundaries(self):
        cases = [(90, "A", 4), (89.99, "B", 3), (80, "B", 3), (70, "C", 2),
                 (60, "D", 1), (59.99, "F", 0)]
        for g, letter, gpa in cases:
            self.assertEqual(grade_calc.letter_and_gpa(g), (letter, gpa), g)
        # 89.996 rounds to 90.00 before the letter is chosen
        self.assertEqual(grade_calc.letter_and_gpa(grade_calc.final_grade({"a": 89.996}, {"a": 1.0})), ("A", 4.0))

    def test_class_statistics_output(self):
        data = "student,a\nX,70\nY,80\nZ,90\n"
        code, out, _ = run(data, "assessment,weight\na,1\n")
        self.assertEqual(code, 0)
        for line in ("mean     80.00", "median   80.00", "stddev   8.16",
                     "highest  90.00", "lowest   70.00"):
            self.assertIn(line, out)

    def test_cli_report(self):
        data = "student,a,b,notes\nAna,90,90,x\nBo,50,60,y\n"
        code, out, err = run(data, "assessment,weight\na,1\nb,3\n")
        self.assertEqual(code, 0)
        self.assertEqual(err, "")
        lines = out.splitlines()
        self.assertRegex(lines[1], r"Ana\s+90\.00\s+A\s+4\.0")
        self.assertRegex(lines[2], r"Bo\s+57\.50\s+F\s+0\.0")

    def test_invalid_input_exits_2(self):
        w = "assessment,weight\na,1\n"
        bad = [
            ("student,a\nX,\n", w), ("student,a\nX,abc\n", w),
            ("student,a\nX,101\n", w), ("student,a\nX,-1\n", w),
            ("student,a\nX,50\n", "assessment,weight\na,-1\n"),
            ("student,a\nX,50\n", "assessment,weight\na,0\n"),
            ("student,b\nX,50\n", w), ("student,a\n", w),
            ("student,a\nX,50\n", None), (None, w),
            ("student,a\nX,50\n", "name,weight\na,1\n"),
        ]
        for scores, weights in bad:
            code, out, err = run(scores, weights)
            self.assertEqual(code, 2, (scores, weights))
            self.assertTrue(err.startswith("error:"), (scores, weights))
        code, _, err = run("student,a\nX,50\nY,zz\n", w)
        self.assertIn("line 3", err)


if __name__ == "__main__":
    unittest.main()
