"""compliance#6: the API container must not write uvicorn's access log.

uvicorn's access log repeats every request with its full query string, so an administrator's
search by email address would land in the container log. The application writes its own request
line with the path only. The second class starts the real application with the exact uvicorn
arguments of the image and of the server's compose file and reads what it writes.
"""

from __future__ import annotations

import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

from support import COMPOSE_YAML, REPO_ROOT, cannot_run, compose_config

API = REPO_ROOT / "services" / "api"
DOCKERFILE = API / "Dockerfile"


def dockerfile_command() -> str:
    """The shell command the API image starts with."""
    lines = [line for line in DOCKERFILE.read_text().splitlines() if line.startswith("CMD ")]
    command = json.loads(lines[-1][4:])
    assert command[:2] == ["sh", "-c"], command
    return command[2]


def dockerfile_uvicorn_arguments() -> list[str]:
    words = shlex.split(dockerfile_command().split("exec ", 1)[1])
    assert words[0] == "uvicorn", words
    return words[1:]


def compose_uvicorn_arguments() -> list[str]:
    command = compose_config(COMPOSE_YAML)["services"]["oddvex-api"]["command"]
    assert command[0] == "uvicorn", command
    return command[1:]


def api_python() -> str | None:
    """A Python that can import the API and uvicorn: the project's virtualenv, or this one."""
    candidates = [API / ".venv" / "bin" / "python", Path(os.environ.get("ODDVEX_API_PYTHON", "/nonexistent")), Path(shutil.which("python3") or "/nonexistent")]
    for candidate in candidates:
        if candidate.exists() and subprocess.run([str(candidate), "-c", "import oddvex_api, uvicorn"], capture_output=True).returncode == 0:
            return str(candidate)
    return None


class StartCommands(unittest.TestCase):
    def test_the_image_starts_uvicorn_without_its_access_log(self) -> None:
        self.assertIn("--no-access-log", dockerfile_uvicorn_arguments())

    def test_the_image_still_applies_migrations_before_it_serves(self) -> None:
        self.assertTrue(dockerfile_command().startswith("alembic upgrade head && exec uvicorn "))

    def test_the_server_starts_uvicorn_without_its_access_log(self) -> None:
        self.assertIn("--no-access-log", compose_uvicorn_arguments())


class WhatTheContainerWrites(unittest.TestCase):
    QUERY = "q=jane.doe%40example.test&note=find-this-marker"

    def output_of(self, arguments: list[str]) -> str:
        python = api_python()
        if python is None:
            raise cannot_run("no Python here can import oddvex_api and uvicorn (install services/api to run this)")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        arguments = list(arguments)
        arguments[arguments.index("--host") + 1] = "127.0.0.1"
        arguments[arguments.index("--port") + 1] = str(port)
        with tempfile.TemporaryDirectory() as tmp:
            env = {k: v for k, v in os.environ.items() if not k.startswith("ODDVEX_") and k != "DATABASE_URL"}
            env.update({"DATABASE_URL": f"sqlite:///{tmp}/log-test.db", "ODDVEX_ENV": "development", "PYTHONUNBUFFERED": "1"})
            log = open(Path(tmp) / "output.log", "w+")
            self.addCleanup(log.close)
            process = subprocess.Popen([python, "-m", "uvicorn", *arguments], cwd=tmp, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                deadline = time.time() + 60
                while True:
                    try:
                        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health?{self.QUERY}", timeout=2) as response:
                            self.assertEqual(response.status, 200)
                        break
                    except OSError:
                        if process.poll() is not None or time.time() > deadline:
                            log.seek(0)
                            self.fail("the API did not start:\n" + log.read())
                        time.sleep(0.3)
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/v1/meta?{self.QUERY}", timeout=5) as response:
                    self.assertEqual(response.status, 200)
            finally:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
            log.seek(0)
            return log.read()

    def check(self, arguments: list[str]) -> None:
        output = self.output_of(arguments)
        self.assertNotIn("jane.doe", output, "a query string reached the container log")
        self.assertNotIn("find-this-marker", output)
        self.assertNotIn("?", "".join(line for line in output.splitlines() if "/v1/meta" in line))
        requests = [json.loads(line) for line in output.splitlines() if line.startswith("{") and '"request"' in line]
        paths = [entry["path"] for entry in requests if entry.get("message") == "request"]
        self.assertIn("/health", paths, "the application's own request line is still written")
        self.assertIn("/v1/meta", paths)
        for entry in requests:
            self.assertNotIn("?", entry["path"])
            self.assertFalse({"query", "query_string", "url"} & set(entry), entry)

    def test_with_the_image_command_no_query_string_is_logged(self) -> None:
        self.check(dockerfile_uvicorn_arguments())

    def test_with_the_server_command_no_query_string_is_logged(self) -> None:
        self.check(compose_uvicorn_arguments())


if __name__ == "__main__":
    unittest.main()
