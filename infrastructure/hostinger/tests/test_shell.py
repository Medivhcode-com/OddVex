"""ops.sh as a shell script: it parses, and it avoids what the CI shellcheck step rejects.

shellcheck itself runs in CI (job "Infrastructure"), at warning severity. These tests pin the
one pattern of that severity that was found by review, so it cannot come back unnoticed on a
machine without shellcheck.
"""

from __future__ import annotations

import re
import subprocess
import unittest

from support import OPS_SH, SHELL

OPS = OPS_SH.read_text()


class ShellScript(unittest.TestCase):
    def test_it_parses(self) -> None:
        result = subprocess.run([*SHELL, "-n", str(OPS_SH)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_ls_is_never_piped_into_grep(self) -> None:
        """SC2010 (warning): list files with a glob instead."""
        for number, line in enumerate(OPS.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            self.assertNotRegex(line, r"\bls\b[^|]*\|\s*grep\b", f"ops.sh line {number}")

    def test_every_ls_in_a_pipeline_or_substitution_carries_the_directive_for_it(self) -> None:
        """SC2012 (info) is switched off on purpose where the newest file is wanted (`ls -t`)."""
        lines = OPS.splitlines()
        for index, line in enumerate(lines):
            if line.lstrip().startswith("#") or not re.search(r"(^|[\s(])ls -?\w* ?\"\$BACKUPS\"", line):
                continue
            self.assertRegex(lines[index - 1], r"# shellcheck disable=.*SC2012", f"ops.sh line {index + 1}")

    def test_case_patterns_do_not_expand_unquoted_variables(self) -> None:
        """SC2254 (warning): an unquoted expansion in a case pattern is matched as a glob."""
        for number, line in enumerate(OPS.splitlines(), 1):
            match = re.match(r"^\s*([^\s#][^)]*)\)(\s|$)", line)
            if not match or "(" in match.group(1) or not line.rstrip().endswith((";;", ")")):
                continue
            pattern = re.sub(r'"[^"]*"', "", match.group(1))
            self.assertNotIn("$", pattern, f"ops.sh line {number}: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
