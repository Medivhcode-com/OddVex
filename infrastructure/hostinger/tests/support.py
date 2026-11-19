"""Shared helpers for the infrastructure tests.

The tests run ops.sh for real, in a temporary directory that stands in for /opt/oddvex, with a
stub `docker` first on PATH (tests/stubs/docker). No Docker daemon is needed. `docker compose
config`, which needs no daemon either, is used to read the compose files the way Compose does.

Environment switches:
  OPS_TEST_SHELL  the shell that runs ops.sh (default "sh"; CI also uses "busybox sh")
  OPS_SH          another ops.sh to test (used once to see the tests fail on the old script)
  COMPOSE_YAML    another compose.yaml to test
  OPS_TESTS_REQUIRE_ALL  "1": a test that cannot run here (no docker CLI, no PostgreSQL server
                  programs, API not importable) fails instead of being skipped. CI sets it.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOSTINGER = HERE.parent
REPO_ROOT = HOSTINGER.parent.parent
OPS_SH = Path(os.environ.get("OPS_SH", HOSTINGER / "ops.sh"))
COMPOSE_YAML = Path(os.environ.get("COMPOSE_YAML", HOSTINGER / "compose.yaml"))
OPS_COMPOSE_YAML = HOSTINGER / "ops.compose.yaml"
SHELL = shlex.split(os.environ.get("OPS_TEST_SHELL", "sh"))
REAL_DOCKER = shutil.which("docker")

# Two made-up values that stand in for the generated ones in /opt/oddvex/.env. No test output may
# ever contain them.
HIDDEN_A = "first-value-that-must-never-be-shown"
HIDDEN_B = "second-value-that-must-never-be-shown"


def placeholder_env() -> dict[str, str]:
    """The settings of .env.example, with a made-up value where the example leaves a required one empty."""
    pairs: dict[str, str] = {}
    for line in (HOSTINGER / ".env.example").read_text().splitlines():
        name, separator, value = line.partition("=")
        if separator and name.startswith("ODDVEX_"):
            pairs[name] = value
    for name, value in pairs.items():
        if not value and name != "ODDVEX_ADMIN_EMAILS":
            pairs[name] = "x" * 40
    pairs["ODDVEX_PUBLIC_URL"] = "https://preview.example.test"
    pairs["ODDVEX_CONTACT_EMAIL"] = "contact@example.test"
    return pairs


PLACEHOLDER_ENV = placeholder_env()

# What makes a container of an old service name disappear in the stub: `docker rm -f <id>`.
LEGACY_GONE = r"^rm -f {}$"


def cannot_run(reason: str) -> Exception:
    """The exception to raise when something a test needs is not installed: a skip, or a failure in CI."""
    if os.environ.get("OPS_TESTS_REQUIRE_ALL") == "1":
        return AssertionError(f"{reason} (OPS_TESTS_REQUIRE_ALL=1, so a test that cannot run is a failure)")
    return unittest.SkipTest(reason)


def compose_config(path: Path, env: dict[str, str] | None = None, process_env: dict[str, str] | None = None) -> dict:
    """The compose file as Compose resolves it. Skips (or fails, see cannot_run) without the docker CLI."""
    if REAL_DOCKER is None:
        raise cannot_run("the docker CLI is not installed, so `docker compose config` cannot run")
    with tempfile.TemporaryDirectory() as tmp:
        env_file = Path(tmp) / "env"
        env_file.write_text("".join(f"{k}={v}\n" for k, v in (PLACEHOLDER_ENV if env is None else env).items()))
        clean = {k: v for k, v in os.environ.items() if not k.startswith("ODDVEX_")}
        clean.update(process_env or {})
        result = subprocess.run(
            [REAL_DOCKER, "compose", "-f", str(path), "--env-file", str(env_file), "config", "--format", "json"],
            capture_output=True,
            text=True,
            env=clean,
        )
    if result.returncode != 0:
        raise AssertionError(f"docker compose config failed for {path}:\n{result.stderr}")
    return json.loads(result.stdout)


def unescape(text: str) -> str:
    """`docker compose config` prints a literal dollar sign as two."""
    return text.replace("$$", "$")


def write_executable(path: Path, text: str) -> None:
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class OpsCase(unittest.TestCase):
    """Runs ops.sh against a temporary /opt/oddvex and a stub docker."""

    maxDiff = None

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="oddvex-ops-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.root = self.tmp / "opt-oddvex"
        self.repo = self.root / "repo"
        self.backups = self.root / "backups"
        self.stub_dir = self.tmp / "docker-stub"
        self.bin = self.tmp / "bin"
        for folder in (self.root, self.stub_dir, self.bin):
            folder.mkdir(parents=True)
        shutil.copy(HERE / "stubs" / "docker", self.bin / "docker")
        (self.bin / "docker").chmod(0o755)
        self.meminfo = self.tmp / "meminfo"
        self.meminfo.write_text("MemTotal:        8000000 kB\nMemAvailable:    4700000 kB\n")
        self.rules: list[dict] = []
        self.release = self.make_repo()

    # --- the stand-in for /opt/oddvex ---------------------------------------------------

    def git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(self.repo), "-c", "user.name=test", "-c", "user.email=test@example.test",
             "-c", "commit.gpgsign=false", *args],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()

    def make_repo(self) -> str:
        """A small git repository where the server keeps its clone. Returns the short commit id."""
        target = self.repo / "infrastructure" / "hostinger"
        target.mkdir(parents=True)
        shutil.copy(COMPOSE_YAML, target / "compose.yaml")
        (self.repo / "services" / "api").mkdir(parents=True)
        (self.repo / "services" / "api" / "Dockerfile").write_text("FROM scratch\n")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "first release")
        return self.git("rev-parse", "--short", "HEAD")

    def commit(self, message: str) -> str:
        """Another commit in the clone, as a newer release. Returns its short id."""
        (self.repo / "CHANGES").write_text(message + "\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "--short", "HEAD")

    def write_env(self, **values: str) -> None:
        lines = {
            "ODDVEX_DB_PASSWORD": HIDDEN_A,
            "ODDVEX_JWT_SECRET": HIDDEN_B,
            "ODDVEX_PUBLIC_URL": "https://preview.oddvex.com",
            "ODDVEX_CONTACT_EMAIL": "",
            "ODDVEX_ADMIN_EMAILS": "",
        }
        lines.update(values)
        (self.root / ".env").write_text("".join(f"{k}={v}\n" for k, v in lines.items() if v is not None))
        (self.root / ".env").chmod(0o600)

    def env_file(self) -> dict[str, str]:
        pairs = {}
        for line in (self.root / ".env").read_text().splitlines():
            key, _, value = line.partition("=")
            pairs[key] = value
        return pairs

    def add_dump(self, name: str, content: bytes = b"PGDMP-test", age_hours: float = 0) -> Path:
        self.backups.mkdir(exist_ok=True)
        path = self.backups / name
        path.write_bytes(content)
        if age_hours:
            import time

            then = time.time() - age_hours * 3600
            os.utime(path, (then, then))
        return path

    # --- the stub docker ----------------------------------------------------------------

    def rule(self, match: str, **answer) -> None:
        """Add an answer for the stub docker. Earlier rules win."""
        self.rules.append({"match": match, **answer})

    def calls(self, pattern: str | None = None) -> list[dict]:
        log = self.stub_dir / "calls.jsonl"
        if not log.exists():
            return []
        entries = [json.loads(line) for line in log.read_text().splitlines()]
        if pattern is None:
            return entries
        import re

        return [entry for entry in entries if re.search(pattern, entry["line"])]

    def lines(self, pattern: str | None = None) -> list[str]:
        return [entry["line"] for entry in self.calls(pattern)]

    def index_of(self, pattern: str) -> int:
        """Position of the first docker call that matches, for checking the order of steps."""
        import re

        for position, entry in enumerate(self.calls()):
            if re.search(pattern, entry["line"]):
                return position
        self.fail(f"no docker call matches {pattern!r}. Calls were:\n" + "\n".join(self.lines()))

    # --- running ops.sh -----------------------------------------------------------------

    def ops(self, action: str, **env: str) -> subprocess.CompletedProcess:
        (self.stub_dir / "rules.json").write_text(json.dumps(self.rules))
        environment = {
            "PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
            "HOME": str(self.tmp),
            "ACTION": action,
            "DOCKER_STUB_DIR": str(self.stub_dir),
            "ODDVEX_ROOT": str(self.root),
            "ODDVEX_MEMINFO": str(self.meminfo),
            "ODDVEX_PROBE_WAIT": "0",
            "ODDVEX_PROBE_TRIES": "2",
        }
        environment.update(env)
        return subprocess.run(
            [*SHELL, str(OPS_SH)], capture_output=True, text=True, env=environment, stdin=subprocess.DEVNULL, timeout=120
        )

    def setenv(self, name: str, value: str) -> subprocess.CompletedProcess:
        return self.ops("setenv", KEY=name, VALUE=value)

    def assert_nothing_hidden_is_shown(self, result: subprocess.CompletedProcess) -> None:
        output = result.stdout + result.stderr
        self.assertNotIn(HIDDEN_A, output)
        self.assertNotIn(HIDDEN_B, output)

    def assert_ok(self, result: subprocess.CompletedProcess) -> None:
        self.assertEqual(result.returncode, 0, f"ops.sh failed:\n{result.stdout}\n{result.stderr}")

    # --- canned answers that describe a server --------------------------------------------

    def answer_healthy(self) -> None:
        """Both containers answer through the shared network."""
        self.rule(r"^run --rm --network \S+ \S+ .*oddvex-api:8000/health", stdout="200")
        self.rule(r"^run --rm --network \S+ \S+ .*oddvex-web:3000/", stdout="200")

    def answer_builder(self, memory_mb: int = 2048, quota: int = 100000, shares: int = 128) -> None:
        """The build runs on cgroup v2 and the builder container carries the wanted ceiling."""
        self.rule(r"^info --format", stdout="2 [name=apparmor name=seccomp,profile=builtin name=cgroupns]\n")
        self.rule(r"^ps -aq --filter name=buildx_buildkit_", stdout="builder123\n")
        self.rule(r"^inspect --format \S*HostConfig\.Memory.* builder123$", stdout=f"{memory_mb * 1048576} {quota} {shares}\n")

    def answer_database(self, revision: str | None = "0005", after: str | None = None) -> None:
        """The database answers; `after` is the revision once the migration step has run."""
        self.rule(r"exec -T db psql .*to_regclass", stdout="t\n" if revision else "f\n", times=1)
        if revision:
            self.rule(r"exec -T db psql .*SELECT version_num", stdout=f"{revision}\n", times=1)
        self.rule(r"exec -T db psql .*to_regclass", stdout="t\n")
        self.rule(r"exec -T db psql .*SELECT version_num", stdout=f"{after or revision or '0005'}\n")
        self.rule(r"exec -T db pg_dump ", stdout="PGDMP-canned-dump-bytes")

    def answer_running(self, release: str, legacy: bool = False) -> None:
        """Containers of an earlier release are running, under the old or the new service names."""
        api, web = ("api", "web") if legacy else ("oddvex-api", "oddvex-web")
        # A container of an old service name is listed until the call that removes it has worked.
        for service, container in ((api, "apicontainer"), (web, "webcontainer")):
            gone = {"until": LEGACY_GONE.format(container)} if legacy else {}
            self.rule(rf"^ps -aq .*label=com\.docker\.compose\.service={service}$", stdout=f"{container}\n", **gone)
        self.rule(r"^inspect --format \S*Config\.Image\S* apicontainer$", stdout=f"oddvex-api:{release}\n")
        self.rule(r"^inspect --format \S*Config\.Image\S* webcontainer$", stdout=f"oddvex-web:{release}\n")
