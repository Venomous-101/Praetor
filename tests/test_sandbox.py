import os
import sys
import unittest
from unittest import mock

from praetor.security import sandbox
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


class SandboxEnvTests(unittest.TestCase):
    def test_windows_env_keeps_system_vars_and_rebuilds_path(self):
        # clear=True isolates the test from the host environment so the
        # assertions hold identically on Linux CI and on a Windows laptop.
        with mock.patch.object(
            sandbox.os, "name", "nt"
        ), mock.patch.dict(
            sandbox.os.environ,
            {"SYSTEMROOT": "C:/Windows", "COMSPEC": "C:/Windows/System32/cmd.exe"},
            clear=True,
        ):
            env = sandbox._build_env("workdir")
        self.assertEqual(env["SYSTEMROOT"], "C:/Windows")
        self.assertEqual(env["COMSPEC"], "C:/Windows/System32/cmd.exe")
        self.assertNotIn("SYSTEMDRIVE", env)  # absent from the host env: stays scrubbed
        self.assertIn(os.path.dirname(sys.executable), env["PATH"])
        self.assertNotIn("/usr/local/bin:/usr/bin:/bin", env["PATH"])
        self.assertNotIn("SYSTEMDRIVE", env["PATH"].split(os.pathsep))

    def test_posix_env_stays_scrubbed_and_static(self):
        with mock.patch.object(sandbox.os, "name", "posix"), mock.patch.dict(
            sandbox.os.environ, {"SYSTEMROOT": "C:/Windows"}
        ):
            env = sandbox._build_env("workdir")
        self.assertNotIn("SYSTEMROOT", env)
        self.assertEqual(env["PATH"], "/usr/local/bin:/usr/bin:/bin")
        self.assertEqual(env["HOME"], "workdir")
        self.assertEqual(env["PYTHONHASHSEED"], "0")


if __name__ == "__main__":
    unittest.main()
