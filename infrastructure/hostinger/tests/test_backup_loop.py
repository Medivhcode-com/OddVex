"""deploy-ops#6: the daily backup loop of the `backup` service.

The loop is taken out of compose.yaml and run for real, with stub `pg_dump`, `pg_restore` and
`sleep` first on PATH and a temporary directory in place of /backups. The stub `sleep` records
how long the loop wanted to wait and then ends it.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from support import COMPOSE_YAML, SHELL, compose_config, unescape, write_executable

OLD = "oddvex-20260101T000000Z.dump"
OLDER = "oddvex-20251225T000000Z.dump"
RECENT = "oddvex-20260110T000000Z.dump"


class BackupLoop(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="oddvex-backup-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.backups = self.tmp / "backups"
        self.backups.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        command = compose_config(COMPOSE_YAML)["services"]["backup"]["command"]
        self.assertEqual(command[:2], ["sh", "-c"])
        # A BusyBox shell built to run its own applets first would ignore a `sleep` on PATH, so
        # the stand-in is also given to the loop as a shell function, which every shell prefers.
        self.script = f'sleep() {{ "{self.bin}/sleep" "$@"; }}\n' + unescape(command[2]).replace("/backups", str(self.backups))
        # Ends the loop after one pass. The real sleep that follows only gives the signal time to
        # arrive; its output is closed so the test does not wait for it.
        write_executable(
            self.bin / "sleep",
            f'#!/bin/sh\necho "$1" >> "{self.tmp}/sleeps"\nkill -TERM "$PPID"\n'
            "PATH=/usr/bin:/bin exec sleep 5 > /dev/null 2>&1 < /dev/null\n",
        )
        write_executable(self.bin / "pg_restore", "#!/bin/sh\nexit 0\n")
        for name, days in ((OLDER, 40), (OLD, 20), (RECENT, 3)):
            path = self.backups / name
            path.write_bytes(b"PGDMP-old")
            then = time.time() - days * 86400
            os.utime(path, (then, then))

    def pg_dump(self, body: str) -> None:
        # The loop calls: pg_dump -h oddvex-db -U oddvex -Fc -f FILE oddvex
        write_executable(self.bin / "pg_dump", '#!/bin/sh\nwhile [ "$1" != "-f" ]; do shift; done\nout=$2\n' + body + "\n")

    def run_once(self, keep_days: str | None = None) -> subprocess.CompletedProcess:
        env = {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"}
        if keep_days is not None:
            env["KEEP_DAYS"] = keep_days
        return subprocess.run([*SHELL, "-c", self.script], capture_output=True, text=True, env=env, timeout=60)

    def dumps(self) -> list[str]:
        return sorted(path.name for path in self.backups.iterdir())

    def slept(self) -> list[str]:
        return (self.tmp / "sleeps").read_text().split()

    def test_a_failed_dump_deletes_nothing_and_is_reported(self) -> None:
        self.pg_dump('echo "connection refused" >&2\nexit 1')
        result = self.run_once()
        self.assertEqual(self.dumps(), sorted([OLDER, OLD, RECENT]), "old dumps must survive while new dumps fail")
        self.assertIn("BACKUP FAILED", result.stderr)
        self.assertIn("1 in a row", result.stderr)
        self.assertIn("no old dump was deleted", result.stderr)
        self.assertIn(RECENT, result.stderr, "the report names the newest dump that exists")

    def test_a_failed_dump_is_tried_again_after_an_hour_not_a_day(self) -> None:
        self.pg_dump("exit 1")
        self.run_once()
        self.assertEqual(self.slept(), ["3600"])

    def test_an_empty_dump_counts_as_a_failure(self) -> None:
        self.pg_dump(': > "$out"\nexit 0')
        result = self.run_once()
        self.assertEqual(self.dumps(), sorted([OLDER, OLD, RECENT]))
        self.assertIn("BACKUP FAILED", result.stderr)

    def test_a_dump_that_cannot_be_read_back_counts_as_a_failure(self) -> None:
        self.pg_dump('echo broken > "$out"\nexit 0')
        write_executable(self.bin / "pg_restore", "#!/bin/sh\nexit 1\n")
        result = self.run_once()
        self.assertEqual(self.dumps(), sorted([OLDER, OLD, RECENT]))
        self.assertIn("BACKUP FAILED", result.stderr)

    def test_a_good_dump_is_kept_and_only_then_old_dumps_are_deleted(self) -> None:
        self.pg_dump('echo PGDMP-new > "$out"\nexit 0')
        result = self.run_once()
        names = self.dumps()
        self.assertEqual(len(names), 2, names)
        self.assertIn(RECENT, names)
        self.assertNotIn(OLD, names)
        self.assertNotIn(OLDER, names)
        self.assertFalse(any(name.endswith(".part") for name in names))
        self.assertIn("backup ok: wrote", result.stdout)
        self.assertEqual(self.slept(), ["86400"])

    def test_the_number_of_days_kept_can_be_set(self) -> None:
        self.pg_dump('echo PGDMP-new > "$out"\nexit 0')
        self.run_once(keep_days="30")
        names = self.dumps()
        self.assertIn(OLD, names, "a 20 day old dump is kept when 30 days are kept")
        self.assertNotIn(OLDER, names)

    def test_an_unfinished_file_from_a_stopped_pass_is_removed_and_other_files_are_not(self) -> None:
        (self.backups / "oddvex-20260105T000000Z.dump.part").write_bytes(b"half")
        (self.backups / "predeploy-20260105T000000Z-a-to-b.dump.part").write_bytes(b"being written by ops.sh")
        kept = self.backups / "predeploy-20250101T000000Z-a-to-b.dump"
        kept.write_bytes(b"PGDMP")
        os.utime(kept, (time.time() - 90 * 86400,) * 2)
        self.pg_dump('echo PGDMP-new > "$out"\nexit 0')
        self.run_once()
        names = self.dumps()
        self.assertNotIn("oddvex-20260105T000000Z.dump.part", names)
        self.assertIn("predeploy-20260105T000000Z-a-to-b.dump.part", names, "a dump ops.sh is writing is not the loop's to remove")
        self.assertIn(kept.name, names, "pre-deploy dumps are pruned by ops.sh, not by age here")

    def test_new_dumps_are_private(self) -> None:
        self.pg_dump('echo PGDMP-new > "$out"\nexit 0')
        self.run_once()
        new = [path for path in self.backups.iterdir() if path.name not in (OLD, OLDER, RECENT)]
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].stat().st_mode & 0o077, 0)


if __name__ == "__main__":
    unittest.main()
