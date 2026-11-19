"""The documents next to the scripts must say what the scripts do (docs-truth#1 and decision 9)."""

from __future__ import annotations

import re
import unittest

from support import COMPOSE_YAML, HOSTINGER, OPS_COMPOSE_YAML, OPS_SH, compose_config

README = (HOSTINGER / "README.md").read_text()
ENV_EXAMPLE = (HOSTINGER / ".env.example").read_text()
OPS = OPS_SH.read_text()
COMPOSE_TEXT = COMPOSE_YAML.read_text()
OPS_COMPOSE_TEXT = OPS_COMPOSE_YAML.read_text()


def default(name: str) -> str:
    match = re.search(rf"^{name}=\$\{{\w+:-([^}}]*)\}}", OPS, re.MULTILINE)
    assert match, name
    return match.group(1)


def actions() -> list[str]:
    block = OPS[OPS.index('case "${ACTION:-status}" in') :]
    return re.findall(r"^  (\w+)\)", block, re.MULTILINE)


class AdministratorRule(unittest.TestCase):
    """docs-truth#1: the old comment said listed addresses get the role when they sign up."""

    def test_no_document_says_a_listed_address_gets_the_role_by_signing_up(self) -> None:
        for name, text in (("README.md", README), (".env.example", ENV_EXAMPLE), ("ops.sh", OPS), ("compose.yaml", COMPOSE_TEXT)):
            self.assertNotRegex(text, r"get the admin role when they sign up", name)
            self.assertNotRegex(text, r"(?i)gets? the (admin|administrator) role (when|as soon as|once) (they|it) (sign|register)", name)

    def test_the_env_example_and_the_readme_state_the_real_rule(self) -> None:
        for name, text in ((".env.example", ENV_EXAMPLE), ("README.md", README)):
            flat = " ".join(line.lstrip("# ") for line in text.splitlines())
            self.assertIn("Listing an address gives nobody the role by itself", flat, name)
            self.assertRegex(flat, r"only to an account whose email address is verified", name)
            self.assertIn("ACTION=admin", flat, name)
            self.assertRegex(flat, r"sets a new random password", name)

    def test_both_advise_against_a_published_address_as_administrator(self) -> None:
        self.assertRegex(" ".join(README.split()), r"Do not list `support@oddvex\.com` or any other address that is published")
        flat = " ".join(line.lstrip("# ") for line in ENV_EXAMPLE.splitlines())
        self.assertIn("Do not list the contact address above or any other published address", flat)

    def test_the_example_lists_no_administrator(self) -> None:
        self.assertRegex(ENV_EXAMPLE, r"(?m)^ODDVEX_ADMIN_EMAILS=$")


class ClaimsMatchTheFiles(unittest.TestCase):
    def test_every_action_is_in_the_readme_the_script_header_and_the_ops_compose_header(self) -> None:
        found = actions()
        self.assertEqual(sorted(found), sorted(["status", "deploy", "rollback", "restore", "setenv", "admin", "caddy", "stop"]))
        header = OPS[: OPS.index("set -eu")]
        for action in found:
            self.assertRegex(README, rf"(?m)^\| `{action}` \|", f"README table lacks {action}")
            self.assertRegex(header, rf"(?m)^#   ACTION={action}\b", f"ops.sh header lacks {action}")
            self.assertRegex(OPS_COMPOSE_TEXT.split("name: oddvex-ops")[0], rf"\b{action}\b", f"ops.compose.yaml header lacks {action}")
        listed = re.findall(r"(?m)^\| `([a-z]+)` \|", README.split("## What a deploy does")[0])
        self.assertEqual(sorted(listed), sorted(found), "the README table and the script disagree about the actions")

    def test_the_memory_figures_are_the_ones_in_the_compose_file(self) -> None:
        services = compose_config(COMPOSE_YAML, process_env={"COMPOSE_PROFILES": "ops"})["services"]
        megabytes = {name: int(service["mem_limit"]) // 1048576 for name, service in services.items()}
        running = sum(value for name, value in megabytes.items() if name != "migrate")
        self.assertEqual(running, 2176)
        self.assertIn("about 2.2 GB of memory in total", README)
        self.assertIn(
            f"database {megabytes['db']} MB, API {megabytes['oddvex-api']} MB, web {megabytes['oddvex-web']} MB, "
            f"worker\n  {megabytes['worker']} MB, backup {megabytes['backup']} MB",
            README,
        )
        self.assertIn(f"migration container may use up to {megabytes['migrate']} MB more", README)
        self.assertNotIn("1.8 GB", README)

    def test_the_build_ceiling_in_the_readme_is_the_one_in_the_script(self) -> None:
        self.assertEqual(default("BUILD_MEMORY_MB"), "2048")
        self.assertEqual(default("BUILD_CPU_QUOTA"), "100000")
        self.assertEqual(default("BUILD_CPU_SHARES"), "128")
        self.assertEqual(default("MIN_FREE_KB"), "2500000")
        flat = " ".join(README.split())
        self.assertIn("limited to 2 GB of memory, one of the two CPUs, and a low CPU weight (128, against 1024", flat)
        self.assertIn("less than about 2.5 GB of memory available", flat)

    def test_nothing_claims_a_low_priority_build(self) -> None:
        for name, text in (("README.md", README), ("ops.sh", OPS), ("compose.yaml", COMPOSE_TEXT)):
            self.assertNotIn("low priority", text, name)
        self.assertNotRegex(OPS, r"(?m)^\s*nice ", "nice only lowers the docker client, not the build")

    def test_retention_figures(self) -> None:
        self.assertEqual(default("KEEP_PREDEPLOY"), "5")
        self.assertIn("newest five pre-deploy dumps are kept", " ".join(README.split()))
        self.assertIn("${ODDVEX_BACKUP_KEEP_DAYS:-14}", COMPOSE_TEXT)
        self.assertIn("keeps 14 days", README)
        self.assertIn("-gt 93600", OPS)
        self.assertIn("more than 26 hours old", README)

    def test_the_contact_default_is_the_address_of_decision_d017(self) -> None:
        self.assertEqual(default("DEFAULT_CONTACT_EMAIL"), "support@oddvex.com")
        self.assertRegex(ENV_EXAMPLE, r"(?m)^ODDVEX_CONTACT_EMAIL=support@oddvex\.com$")

    def test_the_readme_lists_exactly_the_keys_setenv_accepts(self) -> None:
        settable = re.search(r'^SETTABLE="([^"]*)"', OPS, re.MULTILINE).group(1).split()
        section = README[README.index("## Settings") : README.index("## The first administrator")]
        self.assertEqual(sorted(re.findall(r"(?m)^\| `(ODDVEX_\w+)` \|", section)), sorted(settable))
        for key in settable:
            self.assertRegex(ENV_EXAMPLE, rf"(?m)^{key}=", f".env.example lacks {key}")

    def test_every_key_in_the_env_example_is_read_by_the_compose_file(self) -> None:
        for key in re.findall(r"(?m)^(ODDVEX_\w+)=", ENV_EXAMPLE):
            self.assertIn("${" + key, COMPOSE_TEXT, key)

    def test_the_compose_header_shows_the_command_the_script_runs(self) -> None:
        self.assertIn("up -d --no-build --remove-orphans --wait", COMPOSE_TEXT.split("name: oddvex")[0])
        self.assertIn("compose up -d --no-build --remove-orphans --wait", OPS)

    def test_the_readme_says_what_happens_to_a_deploy_of_a_commit_from_before_the_rename(self) -> None:
        flat = " ".join(README.split())
        self.assertIn("The ops container therefore refuses to deploy such a commit", flat)
        self.assertIn("prints `[boot] STOP`. Use `ACTION=rollback` with that `REF`", flat)
        self.assertIn('echo "[boot] STOP: ', OPS_COMPOSE_TEXT)
        self.assertIn("send ACTION=rollback with REF=", OPS_COMPOSE_TEXT)

    def test_the_readme_does_not_present_the_build_ceiling_as_observed(self) -> None:
        flat = " ".join(README.split())
        self.assertIn("Not yet seen: this build container on the server", flat)
        self.assertIn("not observed", flat)

    def test_the_readme_gives_the_repeat_confirmation_the_script_asks_for(self) -> None:
        self.assertIn("`<file name>:restore-<number>`", README)
        self.assertIn("wanted=$dump:restore-$((done_before + 1))", OPS)

    def test_the_readme_mentions_the_outage_of_the_first_deploy_with_the_new_names(self) -> None:
        flat = " ".join(README.split())
        self.assertIn("That first deploy takes the preview away for a short time", flat)
        self.assertIn("This has not been timed on the server", flat)

    def test_the_check_on_the_administrator_list_is_documented_where_the_script_makes_it(self) -> None:
        self.assertIn('[ ! -f "$REPO/services/api/scripts/bootstrap_admin.py" ]', OPS)
        flat = " ".join(README.split())
        self.assertIn("A deploy therefore refuses, before it builds, to deploy a commit without that file while the list holds an address", flat)
        self.assertIn("A rollback does not check this", flat)

    def test_the_copy_rules(self) -> None:
        banned = re.compile(r"(?i)\b(lock|locks|guaranteed|can't lose|risk-free|sure thing|win either way)\b")
        for name, text in (("README.md", README), (".env.example", ENV_EXAMPLE), ("ops.sh", OPS), ("compose.yaml", COMPOSE_TEXT), ("ops.compose.yaml", OPS_COMPOSE_TEXT)):
            self.assertIsNone(banned.search(text), name)


if __name__ == "__main__":
    unittest.main()
