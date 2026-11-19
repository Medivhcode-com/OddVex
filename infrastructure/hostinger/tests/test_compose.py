"""The two compose files, read the way Compose reads them (`docker compose config`)."""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

from support import (
    COMPOSE_YAML,
    HOSTINGER,
    OPS_COMPOSE_YAML,
    OPS_SH,
    PLACEHOLDER_ENV,
    SHELL,
    compose_config,
    unescape,
    write_executable,
)


def settable_keys() -> list[str]:
    match = re.search(r'^SETTABLE="([^"]*)"', OPS_SH.read_text(), re.MULTILINE)
    assert match, "ops.sh has no SETTABLE list"
    return match.group(1).split()


class SharedNetworkNames(unittest.TestCase):
    """deploy-ops#3: Compose registers a service name on every network the service joins."""

    def setUp(self) -> None:
        self.services = compose_config(COMPOSE_YAML)["services"]

    def test_every_service_on_the_shared_network_has_a_name_that_starts_with_oddvex(self) -> None:
        on_edge = [name for name, service in self.services.items() if "edge" in (service.get("networks") or {})]
        self.assertEqual(sorted(on_edge), ["oddvex-api", "oddvex-web"])
        for name in on_edge:
            aliases = (self.services[name]["networks"]["edge"] or {}).get("aliases", [])
            for registered in [name, *aliases]:
                self.assertTrue(registered.startswith("oddvex-"), f"{registered!r} would be registered on the shared network")

    def test_no_service_has_a_generic_name(self) -> None:
        self.assertNotIn("api", self.services)
        self.assertNotIn("web", self.services)

    def test_database_worker_and_backup_stay_off_the_shared_network(self) -> None:
        for name in ("db", "worker", "backup"):
            self.assertEqual(list(self.services[name]["networks"]), ["default"], name)

    def test_dependencies_point_at_the_renamed_api(self) -> None:
        self.assertIn("oddvex-api", self.services["worker"]["depends_on"])
        self.assertIn("oddvex-api", self.services["oddvex-web"]["depends_on"])
        self.assertEqual(self.services["oddvex-web"]["environment"]["ODDVEX_API_URL"], "http://oddvex-api:8000")


class ApiCommandAndMigrations(unittest.TestCase):
    """deploy-ops#2 and compliance#6: the API container neither migrates nor writes uvicorn's access log."""

    def test_api_command_serves_only_and_has_no_access_log(self) -> None:
        command = compose_config(COMPOSE_YAML)["services"]["oddvex-api"]["command"]
        self.assertEqual(command[:2], ["uvicorn", "oddvex_api.main:app"])
        self.assertIn("--no-access-log", command)
        self.assertNotIn("alembic", " ".join(command))

    def test_migrate_is_a_one_shot_service_that_up_does_not_start(self) -> None:
        self.assertNotIn("migrate", compose_config(COMPOSE_YAML)["services"])
        with_profile = compose_config(COMPOSE_YAML, process_env={"COMPOSE_PROFILES": "ops"})["services"]
        migrate = with_profile["migrate"]
        self.assertEqual(migrate["command"], ["alembic", "upgrade", "head"])
        self.assertEqual(list(migrate["networks"]), ["default"], "the migration container must not join the shared network")
        self.assertEqual(migrate["image"], with_profile["oddvex-api"]["image"])
        self.assertEqual(migrate["environment"]["DATABASE_URL"], with_profile["oddvex-api"]["environment"]["DATABASE_URL"])
        self.assertEqual(migrate["restart"], "no")


class SettingsReachTheContainers(unittest.TestCase):
    def test_contact_address_is_a_build_argument_of_the_web_image(self) -> None:
        env = dict(PLACEHOLDER_ENV, ODDVEX_CONTACT_EMAIL="support@oddvex.com")
        args = compose_config(COMPOSE_YAML, env)["services"]["oddvex-web"]["build"]["args"]
        self.assertEqual(args["NEXT_PUBLIC_CONTACT_EMAIL"], "support@oddvex.com")

    def test_web_dockerfile_compiles_the_argument_into_the_build(self) -> None:
        text = (HOSTINGER.parent.parent / "apps" / "web" / "Dockerfile").read_text()
        arg = text.index("ARG NEXT_PUBLIC_CONTACT_EMAIL")
        env = text.index("NEXT_PUBLIC_CONTACT_EMAIL=$NEXT_PUBLIC_CONTACT_EMAIL")
        build = text.index("RUN pnpm --filter @oddvex/web build")
        self.assertLess(arg, env)
        self.assertLess(env, build, "the value must be in the environment before `next build` runs")

    def test_every_key_setenv_may_write_is_read_by_the_compose_file(self) -> None:
        text = COMPOSE_YAML.read_text()
        for key in settable_keys():
            self.assertIn("${" + key, text, f"setenv accepts {key} but compose.yaml never reads it")

    def test_settings_are_passed_to_the_api_and_the_backup_loop(self) -> None:
        env = dict(
            PLACEHOLDER_ENV,
            ODDVEX_ADMIN_EMAILS="owner@example.test",
            ODDVEX_PASSWORD_HASH_CONCURRENCY="4",
            ODDVEX_PASSWORD_HASH_WAIT_SECONDS="2.5",
            ODDVEX_BACKUP_KEEP_DAYS="30",
        )
        services = compose_config(COMPOSE_YAML, env)["services"]
        api = services["oddvex-api"]["environment"]
        self.assertEqual(api["ODDVEX_ADMIN_EMAILS"], "owner@example.test")
        self.assertEqual(api["ODDVEX_PASSWORD_HASH_CONCURRENCY"], "4")
        self.assertEqual(api["ODDVEX_PASSWORD_HASH_WAIT_SECONDS"], "2.5")
        self.assertEqual(services["worker"]["environment"]["ODDVEX_ADMIN_EMAILS"], "owner@example.test")
        self.assertEqual(services["backup"]["environment"]["KEEP_DAYS"], "30")

    def test_defaults_match_the_api_defaults(self) -> None:
        api = compose_config(COMPOSE_YAML)["services"]["oddvex-api"]["environment"]
        self.assertEqual(api["ODDVEX_PASSWORD_HASH_CONCURRENCY"], "2")
        self.assertEqual(api["ODDVEX_PASSWORD_HASH_WAIT_SECONDS"], "1.0")

    def test_a_rollback_can_build_from_another_directory(self) -> None:
        services = compose_config(COMPOSE_YAML, process_env={"ODDVEX_BUILD_ROOT": "/opt/oddvex/rollback-source"})["services"]
        self.assertEqual(services["oddvex-api"]["build"]["context"], "/opt/oddvex/rollback-source/services/api")
        self.assertEqual(services["oddvex-web"]["build"]["context"], "/opt/oddvex/rollback-source")


class OpsComposeFile(unittest.TestCase):
    def config(self, **env: str) -> dict:
        return compose_config(OPS_COMPOSE_YAML, env)

    def test_it_parses_with_no_variables_and_idles_on_status(self) -> None:
        environment = self.config()["services"]["ops"]["environment"]
        self.assertEqual(environment["ACTION"], "status")
        self.assertEqual(environment["REF"], "", "a rollback must be told where to go, so REF has no default here")
        self.assertEqual(environment["KEY"], "")

    def test_the_variables_of_the_new_actions_reach_the_container(self) -> None:
        environment = self.config(
            ACTION="setenv", KEY="ODDVEX_ADMIN_EMAILS", VALUE="a@example.test,b@example.test",
            EMAIL="a@example.test", DUMP="predeploy-x.dump", CONFIRM="predeploy-x.dump", ODDVEX_BUILD_LIMITS="off",
        )["services"]["ops"]["environment"]
        self.assertEqual(environment["KEY"], "ODDVEX_ADMIN_EMAILS")
        self.assertEqual(environment["VALUE"], "a@example.test,b@example.test")
        self.assertEqual(environment["EMAIL"], "a@example.test")
        self.assertEqual(environment["DUMP"], "predeploy-x.dump")
        self.assertEqual(environment["CONFIRM"], "predeploy-x.dump")
        self.assertEqual(environment["ODDVEX_BUILD_LIMITS"], "off")

    # What the two files looked like before the services were renamed (commit 9a2a9bc), cut down
    # to the lines that matter here.
    OLD_COMPOSE = "name: oddvex\nservices:\n  db:\n    image: postgres:17-alpine\n  api:\n    networks:\n      edge: { aliases: [oddvex-api] }\n  web:\n    image: x\n"
    OLD_OPS = '#!/bin/sh\nset -eu\necho "[oddvex] the old script ran with ACTION=$ACTION"\ncase "${ACTION:-status}" in\n  status) ;;\n  deploy) ;;\n  caddy) ;;\n  stop) ;;\nesac\n'

    def boot(self, *, old_files: bool = False, old_compose: bool | None = None, old_ops: bool | None = None,
             **env: str) -> tuple[subprocess.CompletedProcess, list[str]]:
        """Runs the boot script with stub `apk`, `git` and `docker`. The checkout holds the real
        ops.sh and compose.yaml, or the two old stand-ins. Returns the result and the git calls."""
        script = unescape(self.config()["configs"]["boot"]["content"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "bin").mkdir()
            write_executable(root / "bin" / "apk", "#!/bin/sh\nexit 0\n")
            write_executable(root / "bin" / "git", f'#!/bin/sh\necho "$*" >> "{root}/git.log"\nexit 0\n')
            # Every docker call fails, so the real ops.sh stops at its first question to Docker.
            write_executable(root / "bin" / "docker", f'#!/bin/sh\necho "$*" >> "{root}/docker.log"\nexit 1\n')
            target = root / "opt" / "repo" / "infrastructure" / "hostinger"
            target.mkdir(parents=True)
            old_ops = old_files if old_ops is None else old_ops
            old_compose = old_files if old_compose is None else old_compose
            (target / "ops.sh").write_text(self.OLD_OPS if old_ops else OPS_SH.read_text())
            (target / "compose.yaml").write_text(self.OLD_COMPOSE if old_compose else COMPOSE_YAML.read_text())
            (root / "boot.sh").write_text(script)
            environment = {"PATH": f"{root / 'bin'}{os.pathsep}{os.environ['PATH']}", "ODDVEX_ROOT": str(root / "opt"),
                           "ACTION": "status", "REF": "", "OPS_REF": "main", **env}
            result = subprocess.run([*SHELL, str(root / "boot.sh")], capture_output=True, text=True, env=environment)
            log = root / "git.log"
            return result, (log.read_text().splitlines() if log.exists() else [])

    def test_without_a_ref_the_files_of_main_are_used(self) -> None:
        result, calls = self.boot(ACTION="status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("[oddvex] nothing is deployed here yet", result.stdout, "ops.sh ran")
        self.assertTrue(any(call.endswith("fetch -q origin main") for call in calls), calls)

    def test_a_deploy_runs_the_files_of_the_ref_it_deploys(self) -> None:
        result, calls = self.boot(ACTION="deploy", REF="release-branch")
        self.assertTrue(any(call.endswith("fetch -q origin release-branch") for call in calls), calls)
        self.assertNotIn("[boot] STOP", result.stdout)
        self.assertIn("[oddvex] STOP: network medivh-automation_default not found", result.stdout,
                      "the real ops.sh of this commit was started (and stopped at the stub docker)")

    def test_a_rollback_runs_the_current_ops_script_not_the_earlier_one(self) -> None:
        result, calls = self.boot(ACTION="rollback", REF="abc1234", OPS_REF="main")
        self.assertTrue(any(call.endswith("fetch -q origin main") for call in calls), calls)
        self.assertFalse(any("abc1234" in call for call in calls), "the earlier commit's ops.sh may not know the rollback action")
        self.assertIn("[oddvex]", result.stdout, "ops.sh ran")

    def test_a_deploy_of_a_commit_from_before_the_rename_is_refused(self) -> None:
        """deploy-ops#2 replayed after the rename: that commit's own ops.sh would start `api` and
        `web` next to the running `oddvex-api` and `oddvex-web`, with no orphan removal."""
        result, calls = self.boot(old_files=True, ACTION="deploy", REF="9a2a9bc")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertTrue(any(call.endswith("fetch -q origin 9a2a9bc") for call in calls), calls)
        self.assertNotIn("the old script ran", result.stdout, "the old ops.sh must not be started")
        self.assertIn("[boot] STOP", result.stdout)
        self.assertIn("ACTION=rollback", result.stdout)
        self.assertIn("REF=9a2a9bc", result.stdout)
        self.assertIn("Nothing was changed", result.stdout)

    def test_the_old_files_are_refused_for_a_deploy_without_a_ref_too(self) -> None:
        result, _ = self.boot(old_files=True, ACTION="deploy")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("the old script ran", result.stdout)

    def test_either_old_file_alone_is_enough_to_refuse(self) -> None:
        for flags in ({"old_compose": True}, {"old_ops": True}):
            result, _ = self.boot(ACTION="deploy", REF="some-commit", **flags)
            self.assertEqual(result.returncode, 2, flags)
            self.assertIn("[boot] STOP", result.stdout, flags)
            self.assertNotIn("[oddvex]", result.stdout, flags)

    def test_the_two_checks_match_the_current_files_and_not_the_old_ones(self) -> None:
        script = unescape(self.config()["configs"]["boot"]["content"])
        self.assertIn("compose.yaml", script)
        self.assertIn("ops.sh", script)
        for pattern in re.findall(r"grep -q '([^']+)'", script):
            if "oddvex-api" in pattern:
                self.assertRegex(COMPOSE_YAML.read_text(), re.compile(pattern, re.MULTILINE))
                self.assertNotRegex(self.OLD_COMPOSE, re.compile(pattern, re.MULTILINE))
            else:
                self.assertRegex(OPS_SH.read_text(), re.compile(pattern, re.MULTILINE))
                self.assertNotRegex(self.OLD_OPS, re.compile(pattern, re.MULTILINE))

    def test_actions_that_change_nothing_still_run_from_an_old_commit(self) -> None:
        result, _ = self.boot(old_files=True, ACTION="status", REF="9a2a9bc")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("the old script ran with ACTION=status", result.stdout)


if __name__ == "__main__":
    unittest.main()
