import os
import unittest

from praetor.security.sandbox import run_python_sandboxed


class SandboxTests(unittest.TestCase):
    def test_simple_execution(self):
        result = run_python_sandboxed("print(2 + 2)")
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "4")

    def test_environment_is_scrubbed(self):
        os.environ["PRAETOR_TEST_SENTINEL"] = "leak"
        try:
            result = run_python_sandboxed(
                """
import os
print(os.environ.get('PRAETOR_TEST_SENTINEL', 'clean'))
"""
            )
        finally:
            del os.environ["PRAETOR_TEST_SENTINEL"]
        self.assertTrue(result.ok)
        self.assertEqual(result.stdout.strip(), "clean")

    def test_wall_clock_timeout_kills_runaway_process(self):
        result = run_python_sandboxed(
            """
import time
time.sleep(30)
""",
            timeout_s=1.0,
        )
        self.assertTrue(result.timed_out)
        self.assertFalse(result.ok)

    def test_output_is_bounded(self):
        result = run_python_sandboxed("print('x' * 100000)")
        self.assertLessEqual(len(result.stdout), 8192)

    def test_errors_are_reported(self):
        result = run_python_sandboxed("raise ValueError('boom')")
        self.assertFalse(result.ok)
        self.assertIn("boom", result.stderr)

    def test_oversized_source_is_rejected(self):
        with self.assertRaises(ValueError):
            run_python_sandboxed("#" + ("x" * 100000))


if __name__ == "__main__":
    unittest.main()
