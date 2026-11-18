"""Check that local credential files cannot enter a normal Git add."""

from pathlib import Path, PurePosixPath
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


class SecretExclusionTests(unittest.TestCase):
    def git(self, *args):
        return subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True, check=False
        )

    def test_private_paths_are_ignored(self):
        for path in (
            ".env",
            "vacation_planner/.env",
            "vacation_planner/.env.production",
            "vacation_planner/.streamlit/secrets.toml",
            "vacation_planner/report.md",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.git("check-ignore", "-q", path).returncode, 0)

    def test_no_environment_or_streamlit_secret_files_are_tracked(self):
        result = self.git("ls-files", "-z")
        self.assertEqual(result.returncode, 0)
        for path in filter(None, result.stdout.split("\0")):
            name = PurePosixPath(path).name
            private_env = (name == ".env" or name.startswith(".env.")) and name not in (
                ".env.example", ".env.template"
            )
            private_streamlit = path.endswith("/.streamlit/secrets.toml")
            self.assertFalse(private_env or private_streamlit, f"Private file tracked: {path}")

    def test_blank_environment_template_remains_trackable(self):
        self.assertEqual(
            self.git("check-ignore", "-q", "vacation_planner/.env.example").returncode, 1
        )


if __name__ == "__main__":
    unittest.main()
