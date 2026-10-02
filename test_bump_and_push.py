"""The date that `bump_and_push.sh` writes in CHANGELOG.md.

`## [X] — YYYY-MM-DD <!-- the date is written when the tag is made -->` was a
promise nobody kept: the 0.1.2 was tagged and its line still said YYYY-MM-DD.
These tests run the real script on a throwaway repository (with a bare one as
its origin, so `git push` has somewhere to go) and read the CHANGELOG back.

Standard library only, like the rest of the suite. Skipped where the script is
not (the sdist does not ship it) or where there is no git or bash.

    python3 -m unittest test_bump_and_push
"""

import datetime
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SCRIPT = HERE / "bump_and_push.sh"

CHANGELOG = """\
# Changelog

## [0.2.0] — YYYY-MM-DD <!-- the date is written when the tag is made -->

Not tagged, not being tagged: keeps its placeholder.

## [0.1.3] — YYYY-MM-DD <!-- the date is written when the tag is made -->

The one being tagged.

## [0.1.2] — YYYY-MM-DD <!-- the date is written when the tag is made -->

Tagged on 2026-09-30 and never dated.

## [0.1.1] — 2026-09-16

Already dated: untouched.
"""


def _git(cwd, *args, env=None):
    return subprocess.run(["git", *args], cwd=cwd, check=True, env=env,
                          capture_output=True, text=True).stdout.strip()


@unittest.skipUnless(SCRIPT.exists() and shutil.which("git") and shutil.which("bash"),
                     "bump_and_push.sh, git and bash are needed")
class ChangelogDate(unittest.TestCase):

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp(prefix="dtc-bump-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        origin = self.tmp / "origin.git"
        self.repo = self.tmp / "work"
        _git(self.tmp, "init", "-q", "--bare", str(origin))
        _git(self.tmp, "init", "-q", "-b", "main", str(self.repo))
        for k, v in (("user.name", "Test"), ("user.email", "test@example.org"),
                     ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
            _git(self.repo, "config", k, v)
        _git(self.repo, "remote", "add", "origin", str(origin))
        shutil.copy(SCRIPT, self.repo / "bump_and_push.sh")
        (self.repo / "pyproject.toml").write_text('[project]\nname = "dtcstamp"\nversion = "0.1.2"\n')
        (self.repo / "dtcstamp.py").write_text('__version__ = "0.1.2"\n')
        (self.repo / ".bumpversion.cfg").write_text("[bumpversion]\ncurrent_version = 0.1.2\n")
        (self.repo / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")
        _git(self.repo, "add", "-A")
        old = dict(os.environ, GIT_COMMITTER_DATE="2026-09-30T12:00:00+0000",
                   GIT_AUTHOR_DATE="2026-09-30T12:00:00+0000")
        _git(self.repo, "commit", "-q", "-m", "0.1.2", env=old)
        _git(self.repo, "tag", "-a", "v0.1.2", "-m", "v0.1.2", env=old)
        _git(self.repo, "push", "-q", "-u", "origin", "main", "--tags")
        self.today = datetime.date.today().isoformat()

    def run_script(self, *args):
        return subprocess.run(["bash", "./bump_and_push.sh", *args], cwd=self.repo,
                              capture_output=True, text=True, stdin=subprocess.DEVNULL)

    def heading(self, text, version):
        return next(l for l in text.splitlines() if l.startswith(f"## [{version}]"))

    def assert_dated(self, text):
        self.assertEqual(self.heading(text, "0.1.3"), f"## [0.1.3] — {self.today}")
        self.assertEqual(self.heading(text, "0.1.2"), "## [0.1.2] — 2026-09-30")
        self.assertEqual(self.heading(text, "0.1.1"), "## [0.1.1] — 2026-09-16")
        # THE COUNTEREXAMPLE: a version neither tagged nor being tagged is not dated
        self.assertEqual(self.heading(text, "0.2.0"),
                         "## [0.2.0] — YYYY-MM-DD <!-- the date is written when the tag is made -->")

    def test_date_changelog_writes_today_and_the_tags_date(self):
        r = self.run_script("--date-changelog", "0.1.3")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assert_dated((self.repo / "CHANGELOG.md").read_text(encoding="utf-8"))
        # and commits nothing
        self.assertEqual(_git(self.repo, "rev-list", "--count", "HEAD"), "1")

    def test_set_puts_the_date_INSIDE_the_commit_the_tag_names(self):
        r = self.run_script("--set", "0.1.3")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        tagged = _git(self.repo, "show", "v0.1.3:CHANGELOG.md")
        self.assert_dated(tagged)
        self.assertEqual(_git(self.repo, "status", "--porcelain"), "")
        self.assertIn("Bump version: 0.1.2 → 0.1.3", _git(self.repo, "log", "-1", "--format=%s", "v0.1.3"))

    def test_tag_only_commits_the_date_before_it_tags(self):
        for f, old, new in (("pyproject.toml", 'version = "0.1.2"', 'version = "0.1.3"'),
                            ("dtcstamp.py", '"0.1.2"', '"0.1.3"')):
            p = self.repo / f
            p.write_text(p.read_text().replace(old, new))
        _git(self.repo, "commit", "-q", "-am", "0.1.3 by hand")
        r = self.run_script("--tag-only")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        self.assert_dated(_git(self.repo, "show", "v0.1.3:CHANGELOG.md"))
        self.assertEqual(_git(self.repo, "log", "-1", "--format=%s", "v0.1.3"),
                         "Date the changelog for v0.1.3")


if __name__ == "__main__":
    unittest.main()
