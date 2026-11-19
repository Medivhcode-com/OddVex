"""A rehearsal of the dump and restore path of ops.sh against a real PostgreSQL server.

Nothing can be rehearsed on the server itself, so this test starts a private PostgreSQL in a
temporary directory and lets the stub docker run the words after `compose exec -T db` as local
commands. pg_dump, pg_restore and psql are then the real programs, with the exact arguments
ops.sh gives them. It is skipped where no PostgreSQL server programs are installed (in CI that is a failure).
"""

from __future__ import annotations

import glob
import os
import pwd
import shutil
import socket
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import OpsCase, cannot_run

UP = r" up -d --no-build .*--wait"
PREVIOUS = "aaa1111"


def server_programs() -> str | None:
    """The directory that holds initdb and pg_ctl."""
    found = shutil.which("initdb")
    if found:
        return str(Path(found).parent)
    candidates = sorted(glob.glob("/usr/lib/postgresql/*/bin/initdb"))
    return str(Path(candidates[-1]).parent) if candidates else None


class RealPostgres(OpsCase):
    def setUp(self) -> None:
        super().setUp()
        self.bindir = server_programs()
        if self.bindir is None or shutil.which("psql") is None:
            raise cannot_run("PostgreSQL server programs (initdb, pg_ctl) are not installed")
        self.as_user: list[str] = []
        if os.geteuid() == 0:
            # PostgreSQL refuses to run as root.
            try:
                pwd.getpwnam("postgres")
            except KeyError:
                raise cannot_run("running as root and there is no postgres user to run the server as")
            if shutil.which("runuser") is None:
                raise cannot_run("running as root and runuser is not installed")
            self.as_user = ["runuser", "-u", "postgres", "--"]
        self.pg = Path(tempfile.mkdtemp(prefix="oddvex-pg-", dir="/tmp"))
        self.addCleanup(shutil.rmtree, self.pg, ignore_errors=True)
        self.pg.chmod(0o755)
        if self.as_user:
            shutil.chown(self.pg, "postgres")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = str(probe.getsockname()[1])
        data = self.pg / "data"
        self.server("initdb", "-U", "oddvex", "-A", "trust", "-E", "UTF8", "-D", str(data))
        options = f"-c listen_addresses='' -c unix_socket_directories='{self.pg}' -p {self.port}"
        self.server("pg_ctl", "-D", str(data), "-l", str(self.pg / "server.log"), "-w", "-o", options, "start")
        self.addCleanup(self.server, "pg_ctl", "-D", str(data), "-m", "immediate", "-w", "stop")
        self.pg_env = {"PGHOST": str(self.pg), "PGPORT": self.port}
        self.sql("postgres", "CREATE DATABASE oddvex OWNER oddvex")
        self.sql("oddvex", "CREATE TABLE alembic_version (version_num varchar(32) PRIMARY KEY)")
        self.sql("oddvex", "INSERT INTO alembic_version VALUES ('0005')")
        self.sql("oddvex", "CREATE TABLE users (id serial PRIMARY KEY, email text UNIQUE NOT NULL)")
        self.sql("oddvex", "INSERT INTO users (email) VALUES ('first@example.test'), ('second@example.test')")

    def server(self, program: str, *args: str) -> None:
        result = subprocess.run([*self.as_user, f"{self.bindir}/{program}", *args], capture_output=True, text=True, cwd="/tmp")
        if result.returncode != 0:
            self.fail(f"{program} failed:\n{result.stdout}\n{result.stderr}")

    def sql(self, database: str, statement: str) -> str:
        result = subprocess.run(
            ["psql", "-U", "oddvex", "-d", database, "-v", "ON_ERROR_STOP=1", "-qAtc", statement],
            capture_output=True, text=True, env={**os.environ, **self.pg_env},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def emails(self, database: str = "oddvex") -> list[str]:
        return self.sql(database, "SELECT email FROM users ORDER BY id").split()

    def columns(self, database: str = "oddvex") -> list[str]:
        return self.sql(database, "SELECT column_name FROM information_schema.columns WHERE table_name = 'users' ORDER BY 1").split()

    def answers(self) -> None:
        self.rules = []
        self.rule(r"exec -T db ", local=True)
        self.answer_builder()
        self.answer_running(PREVIOUS)
        self.answer_healthy()
        self.rule(r"^ps -q .*label=com\.docker\.compose\.service=oddvex-api$", stdout="apicontainer\n")

    def test_a_failed_deploy_with_a_migration_can_be_undone_with_the_dump_it_names(self) -> None:
        self.write_env(ODDVEX_CONTACT_EMAIL="support@oddvex.com")
        psql = ["psql", "-U", "oddvex", "-d", "oddvex", "-v", "ON_ERROR_STOP=1", "-q"]

        # 1. A deploy whose release applies a migration and then does not become healthy.
        self.answers()
        self.rule(r" run --rm -T migrate$", command=[*psql, "-c", "ALTER TABLE users ADD COLUMN nickname text",
                                                    "-c", "UPDATE alembic_version SET version_num = '0006'"])
        self.rules.insert(0, {"match": UP, "release": self.release, "exit": 1})
        result = self.ops("deploy", **self.pg_env)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("A MIGRATION WAS APPLIED BY THIS DEPLOY AND WAS NOT UNDONE: the database is at revision 0006, it was at 0005.", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK", result.stdout)
        dumps = sorted(self.backups.glob("predeploy-*.dump"))
        self.assertEqual(len(dumps), 1)
        dump = dumps[0].name
        self.assertIn(f"DUMP={dump}", result.stdout)
        self.assertTrue(dumps[0].read_bytes().startswith(b"PGDMP"), "a real custom-format dump was written")
        self.assertIn("nickname", self.columns())

        # 2. Somebody signs up after the dump was taken.
        self.sql("oddvex", "INSERT INTO users (email) VALUES ('late@example.test')")

        # 3. Without CONFIRM nothing happens.
        self.answers()
        result = self.ops("restore", DUMP=dump, **self.pg_env)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.sql("oddvex", "SELECT version_num FROM alembic_version"), "0006")
        self.assertEqual(len(self.emails()), 3)

        # 4. The restore the failed deploy printed.
        result = self.ops("restore", DUMP=dump, CONFIRM=dump, **self.pg_env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(f"RESTORED: the live database is now the content of {dump} (revision 0005; it was at 0006).", result.stdout)
        self.assertEqual(self.sql("oddvex", "SELECT version_num FROM alembic_version"), "0005")
        self.assertEqual(self.emails(), ["first@example.test", "second@example.test"])
        self.assertNotIn("nickname", self.columns(), "the schema is the one from before the migration")
        self.assertEqual(self.sql("oddvex", "INSERT INTO users (email) VALUES ('new@example.test') RETURNING id"), "3",
                         "sequences are restored too")

        # 5. The database that was replaced is kept, and so is a dump of it.
        kept = self.sql("postgres", "SELECT datname FROM pg_database WHERE datname LIKE 'oddvex\\_replaced\\_%'").split()
        self.assertEqual(len(kept), 1)
        self.assertEqual(self.emails(kept[0]), ["first@example.test", "second@example.test", "late@example.test"])
        self.assertEqual(self.sql("postgres", "SELECT count(*) FROM pg_database WHERE datname = 'oddvex_restore'"), "0")
        safety = sorted(self.backups.glob("prerestore-*.dump"))
        self.assertEqual(len(safety), 1)
        self.assertIn(f"DUMP={safety[0].name} with CONFIRM={safety[0].name}", result.stdout)

        # 6. Status reads the same server.
        self.answers()
        result = self.ops("status", **self.pg_env)
        self.assertIn("database revision: 0005", result.stdout)
        self.assertIn(f"databases kept by earlier restores: {kept[0]}", result.stdout)

        # 7. The restore can itself be undone with the dump taken just before it.
        self.answers()
        result = self.ops("restore", DUMP=safety[0].name, CONFIRM=safety[0].name, **self.pg_env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.sql("oddvex", "SELECT version_num FROM alembic_version"), "0006")
        self.assertEqual(self.emails(), ["first@example.test", "second@example.test", "late@example.test"])
        self.assertIn("nickname", self.columns())

    def test_a_restore_goes_through_while_a_client_is_still_connected(self) -> None:
        self.write_env()
        self.answers()
        result = self.ops("deploy", **self.pg_env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        dump = sorted(self.backups.glob("predeploy-*.dump"))[0].name
        # A session that stays connected, as a container that was not stopped would.
        idle = subprocess.Popen(["psql", "-U", "oddvex", "-d", "oddvex", "-qAtc", "SELECT pg_sleep(120)"],
                                env={**os.environ, **self.pg_env}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.addCleanup(idle.kill)
        for _ in range(50):
            if self.sql("postgres", "SELECT count(*) FROM pg_stat_activity WHERE datname = 'oddvex' AND query LIKE '%pg_sleep%'") == "1":
                break
            subprocess.run(["sleep", "0.1"])
        self.answers()
        result = self.ops("restore", DUMP=dump, CONFIRM=dump, **self.pg_env)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESTORED:", result.stdout)

    def test_a_file_that_is_not_a_dump_changes_nothing(self) -> None:
        self.write_env()
        self.add_dump("oddvex-20260101T000000Z.dump", b"this is not a dump")
        self.answers()
        result = self.ops("restore", DUMP="oddvex-20260101T000000Z.dump", CONFIRM="oddvex-20260101T000000Z.dump", **self.pg_env)
        self.assertEqual(result.returncode, 2)
        self.assertIn("pg_restore cannot read oddvex-20260101T000000Z.dump. Nothing was changed.", result.stdout)
        self.assertEqual(self.emails(), ["first@example.test", "second@example.test"])
        self.assertEqual(self.sql("postgres", "SELECT count(*) FROM pg_database WHERE datname LIKE 'oddvex\\_re%'"), "0")


if __name__ == "__main__":
    unittest.main()
