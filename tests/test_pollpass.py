from __future__ import annotations
import unittest
from hyrulefast.pollpass import add_polls, validate_interval


class PollPassTests(unittest.TestCase):
    SAMPLE = """void f_80000000(Ctx *c) {
L_80000000:;
    work();
    if (again) goto L_80000000;
    goto L_80000020;
L_80000020:;
    return;
}
"""

    def test_interval_one_matches_upstream_rewrite(self):
        output, count = add_polls(self.SAMPLE, 1)
        self.assertEqual(count, 1)
        self.assertIn("{ A64_POLL(c); goto L_80000000; }", output)
        self.assertNotIn("hyrule_poll_budget", output)

    def test_interval_four_adds_function_local_countdown(self):
        output, count = add_polls(self.SAMPLE, 4)
        self.assertEqual(count, 1)
        self.assertIn("unsigned int hyrule_poll_budget = 4u;", output)
        self.assertIn("if (__builtin_expect(--hyrule_poll_budget == 0u, 0))", output)
        self.assertIn("hyrule_poll_budget = 4u; A64_POLL(c);", output)

    def test_unknown_and_forward_targets_are_not_instrumented(self):
        source = "void f(Ctx *c) { goto L_00000010; goto L_missing; L_00000010:; return; }"
        output, count = add_polls(source, 8)
        self.assertEqual(count, 0)
        self.assertEqual(output, source)

    def test_each_backward_edge_is_counted(self):
        source = "void f(Ctx *c) {\nL_00000001:;\n if (a) goto L_00000001; if (b) goto L_00000001;\n}"
        output, count = add_polls(source, 2)
        self.assertEqual(count, 2)
        self.assertEqual(output.count("if (__builtin_expect(--hyrule_poll_budget == 0u, 0))"), 2)

    def test_interval_validation(self):
        for valid in (1, 2, 4, 8, 16):
            self.assertEqual(validate_interval(valid), valid)
        for invalid in (0, 3, 32, True, "4"):
            with self.assertRaises((TypeError, ValueError)):
                validate_interval(invalid)

    def test_no_loop_is_unchanged(self):
        source = "void f(Ctx *c) { work(); return; }"
        output, count = add_polls(source, 4)
        self.assertEqual((output, count), (source, 0))


if __name__ == "__main__":
    unittest.main()
