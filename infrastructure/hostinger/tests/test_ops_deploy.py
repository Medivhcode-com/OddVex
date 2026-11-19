"""ACTION=deploy of ops.sh, run for real against a temporary /opt/oddvex and a stub docker."""

from __future__ import annotations

import unittest

from support import OpsCase

UP = r" up -d --no-build .*--wait"
PREVIOUS = "aaa1111"


class DeployCase(OpsCase):
    def server(self, *, running: str | None = PREVIOUS, legacy: bool = False, revision: str | None = "0005",
               after: str | None = None, contact: str = "support@oddvex.com") -> None:
        """A server with a release running and a database at one revision."""
        self.write_env(ODDVEX_CONTACT_EMAIL=contact)
        self.answer_builder()
        self.answer_database(revision, after)
        if running:
            self.answer_running(running, legacy)
        self.answer_healthy()

    def predeploy_dumps(self) -> list[str]:
        return sorted(path.name for path in self.backups.glob("predeploy-*.dump")) if self.backups.exists() else []


class RenamedServices(DeployCase):
    """deploy-ops#3"""

    def test_the_containers_of_the_old_service_names_are_removed_in_the_same_run(self) -> None:
        self.server(legacy=True)
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertEqual(self.lines(r"^rm -f"), ["rm -f apicontainer", "rm -f webcontainer"])
        self.assertIn("removed container apicontainer of the old service name 'api'", result.stdout)
        self.assertLess(self.index_of(r"^rm -f apicontainer"), self.index_of(UP), "old containers go before the new ones start")

    def test_only_containers_carrying_this_projects_labels_are_looked_up(self) -> None:
        self.server(legacy=True)
        self.assert_ok(self.ops("deploy"))
        for line in self.lines(r"^ps "):
            if "name=buildx_buildkit_" in line or "network=" in line:
                continue
            self.assertIn("label=com.docker.compose.project=oddvex", line)

    def test_up_also_removes_orphans_and_builds_and_logs_use_the_new_names(self) -> None:
        self.server(legacy=True)
        self.assert_ok(self.ops("deploy"))
        self.assertIn("--remove-orphans", self.lines(UP)[0])
        builds = self.lines(r"compose\.yaml build ")
        self.assertEqual([line.split()[-1] for line in builds], ["oddvex-api", "oddvex-web"])

    def test_the_put_back_release_runs_under_the_new_names_too(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.server(legacy=True)
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.lines(r"^rm -f"), ["rm -f apicontainer", "rm -f webcontainer"])
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK", result.stdout)

    BUSY = "Error response from daemon: removal of container webcontainer is already in progress\n"

    def test_a_failed_removal_of_an_old_container_does_not_end_the_deploy_without_a_word(self) -> None:
        """The first deploy after the rename: a migration is applied, then `docker rm -f` of the old web container fails."""
        self.rule(r"^rm -f webcontainer$", exit=1, stderr=self.BUSY)
        self.rule(UP, release=self.release, exit=1)
        self.server(legacy=True, after="0006")
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("WARNING: container webcontainer of the old service name 'web' could not be removed", result.stdout)
        self.assertEqual([call["release"] for call in self.calls(UP)], [self.release, PREVIOUS], "the start and the put-back still ran")
        self.assertIn(f"DEPLOY FAILED: release {self.release} did not become healthy.", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK and answers.", result.stdout)
        self.assertIn("A MIGRATION WAS APPLIED BY THIS DEPLOY AND WAS NOT UNDONE: the database is at revision 0006, it was at 0005.", result.stdout)
        dump = self.predeploy_dumps()[0]
        self.assertIn(f"DUMP={dump}", result.stdout)
        self.assertIn(f"CONFIRM={dump}", result.stdout)
        self.assertIn("A CONTAINER OF AN OLD SERVICE NAME IS STILL THERE: webcontainer", result.stdout)
        self.assertRegex((self.root / "ops.log").read_text(), rf"deploy release={self.release} previous={PREVIOUS} revision=0005->0006 dump={dump} result=failed")

    def test_an_old_container_the_first_removal_missed_is_removed_by_a_second_try(self) -> None:
        self.rule(r"^rm -f webcontainer$", exit=1, times=1, stderr=self.BUSY)
        self.server(legacy=True)
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertEqual(self.lines(r"^rm -f"), ["rm -f apicontainer", "rm -f webcontainer", "rm -f webcontainer"])
        self.assertLess(self.index_of(UP), len(self.calls()) - 1)
        self.assertIn("WARNING: container webcontainer of the old service name 'web' could not be removed", result.stdout)
        self.assertIn("removed container webcontainer of the old service name 'web'", result.stdout)
        self.assertNotIn("IS STILL THERE", result.stdout)
        self.assertRegex((self.root / "ops.log").read_text(), r"result=ok")

    def test_an_old_container_that_cannot_be_removed_is_not_reported_as_success(self) -> None:
        self.rule(r"^rm -f webcontainer$", exit=1, stderr=self.BUSY)
        self.server(legacy=True, after="0006")
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("DEPLOY NOT COMPLETE", result.stdout)
        self.assertIn("A CONTAINER OF AN OLD SERVICE NAME IS STILL THERE: webcontainer", result.stdout)
        self.assertIn(f"Release {self.release} is running and answers", result.stdout)
        self.assertIn("MIGRATION APPLIED: the database went from revision 0005 to 0006", result.stdout)
        self.assertEqual([call["release"] for call in self.calls(UP)], [self.release], "the new release is healthy, so nothing is put back")
        self.assertEqual((self.root / "release.healthy").read_text().strip(), self.release)
        self.assertRegex((self.root / "ops.log").read_text(), r"result=old-container-left")
        self.assertNotRegex((self.root / "ops.log").read_text(), r"result=ok")

    def test_stop_also_removes_containers_of_the_old_names(self) -> None:
        self.write_env()
        self.assert_ok(self.ops("stop"))
        self.assertIn("--remove-orphans", self.lines(r" down")[0])


class BuildCeiling(DeployCase):
    """deploy-ops#4"""

    def test_both_images_are_built_by_the_limited_builder_and_up_never_builds(self) -> None:
        self.server()
        result = self.ops("deploy")
        self.assert_ok(result)
        builds = self.lines(r"compose\.yaml build ")
        self.assertEqual(len(builds), 2)
        for line in builds:
            self.assertIn("build --builder oddvex-builder", line)
        for line in self.lines(r" up -d"):
            if not line.endswith(" db"):
                self.assertIn("--no-build", line)
        self.assertIn("at most 2048 MB of memory", result.stdout)
        self.assertIn("confirmed with docker inspect", result.stdout)

    def test_a_missing_builder_is_created_with_a_memory_and_cpu_ceiling(self) -> None:
        self.rule(r"^buildx inspect oddvex-builder$", exit=1, times=1)
        self.server()
        self.assert_ok(self.ops("deploy"))
        create = self.lines(r"^buildx create")
        self.assertEqual(len(create), 1)
        for option in ("--driver docker-container", "memory=2048m", "memory-swap=2048m", "cpu-period=100000",
                       "cpu-quota=100000", "cpu-shares=128", "default-load=true"):
            self.assertIn(option, create[0])
        self.assertLess(self.index_of(r"^buildx create"), self.index_of(r"compose\.yaml build "))

    def test_a_builder_without_the_ceiling_is_made_again_and_checked_before_any_build(self) -> None:
        self.rule(r"^inspect --format \S*HostConfig\.Memory.* builder123$", stdout="0 0 0\n", times=1)
        self.server()
        self.assert_ok(self.ops("deploy"))
        self.assertEqual(len(self.lines(r"^buildx rm -f oddvex-builder")), 1)
        self.assertEqual(len(self.lines(r"^buildx create")), 1)
        self.assertLess(self.index_of(r"^buildx create"), self.index_of(r"compose\.yaml build "))

    def test_nothing_is_built_when_the_ceiling_cannot_be_confirmed(self) -> None:
        self.rule(r"^inspect --format \S*HostConfig\.Memory.* builder123$", stdout="0 0 0\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not carry the memory and CPU ceiling", result.stdout)
        self.assertEqual(self.lines(r"compose\.yaml build "), [])
        self.assertEqual(self.lines(UP), [])

    def test_nothing_is_built_on_a_server_without_cgroup_v2(self) -> None:
        self.rule(r"^info --format", stdout="1 [name=apparmor name=seccomp,profile=builtin]\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("cgroup version '1'", result.stdout)
        self.assertEqual(self.lines(r"compose\.yaml build "), [])

    def test_nothing_is_built_when_containers_share_the_hosts_cgroup_namespace(self) -> None:
        self.rule(r"^info --format", stdout="2 [name=apparmor name=seccomp,profile=builtin]\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("does not give containers their own cgroup namespace", result.stdout)
        self.assertEqual(self.lines(r"compose\.yaml build "), [])
        self.assertEqual(self.lines(UP), [])

    def test_the_deploy_stops_when_an_image_is_not_in_the_image_store_after_the_build(self) -> None:
        self.rule(rf"^image inspect oddvex-web:{self.release}$", exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"image oddvex-web:{self.release} is not in Docker's image store", result.stdout)
        self.assertEqual(self.lines(UP), [])
        self.assertEqual(self.lines(r" run --rm -T migrate"), [])

    def test_a_failed_build_touches_no_container(self) -> None:
        self.rule(r"compose\.yaml build .* oddvex-web$", exit=1, stderr="Killed\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("The running containers were not touched", result.stdout)
        self.assertEqual(self.lines(UP), [])
        self.assertEqual(self.lines(r"^rm -f"), [])
        self.assertLess(self.index_of(r"compose\.yaml build .* oddvex-web$"), self.index_of(r"^buildx stop oddvex-builder$"),
                        "the build container is stopped after a failed build too")

    def test_the_memory_check_still_refuses_a_build_on_a_full_server(self) -> None:
        self.meminfo.write_text("MemAvailable:    1200000 kB\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("only 1200000 kB memory available", result.stdout)
        self.assertEqual(self.lines(r"compose\.yaml build "), [])

    def test_the_ceiling_can_be_switched_off_and_the_output_says_so(self) -> None:
        self.server()
        result = self.ops("deploy", ODDVEX_BUILD_LIMITS="off")
        self.assert_ok(result)
        self.assertIn("NO memory or CPU ceiling", result.stdout)
        self.assertEqual(self.lines(r"^buildx"), [])
        for line in self.lines(r"compose\.yaml build "):
            self.assertNotIn("--builder", line)

    def test_no_step_claims_a_priority_that_nice_cannot_give(self) -> None:
        self.server()
        result = self.ops("deploy")
        self.assertNotIn("low priority", result.stdout)


class DumpMigrateReplace(DeployCase):
    """deploy-ops#2 and the pre-deploy dump of deploy-ops#6"""

    def test_the_order_is_build_dump_migrate_replace(self) -> None:
        self.server()
        self.assert_ok(self.ops("deploy"))
        build = self.index_of(r"compose\.yaml build ")
        dump = self.index_of(r"exec -T db pg_dump ")
        migrate = self.index_of(r" run --rm -T migrate$")
        up = self.index_of(UP)
        self.assertLess(build, dump)
        self.assertLess(dump, migrate)
        self.assertLess(migrate, up)

    def test_a_dump_named_after_both_releases_is_written_before_migrations(self) -> None:
        self.server()
        result = self.ops("deploy")
        self.assert_ok(result)
        dumps = self.predeploy_dumps()
        self.assertEqual(len(dumps), 1)
        self.assertRegex(dumps[0], rf"^predeploy-\d{{8}}T\d{{6}}Z-{PREVIOUS}-to-{self.release}\.dump$")
        self.assertEqual((self.backups / dumps[0]).read_bytes(), b"PGDMP-canned-dump-bytes")
        self.assertEqual((self.backups / dumps[0]).stat().st_mode & 0o077, 0)
        self.assertIn(f"pre-deploy dump written: {self.backups / dumps[0]}", result.stdout)

    def test_the_image_tags_that_were_running_are_recorded_first(self) -> None:
        self.server()
        result = self.ops("deploy")
        self.assert_ok(result)
        recorded = (self.root / "release.previous").read_text()
        self.assertIn(f"api=oddvex-api:{PREVIOUS}", recorded)
        self.assertIn(f"web=oddvex-web:{PREVIOUS}", recorded)
        self.assertIn(f"put_back={PREVIOUS}", recorded)
        self.assertIn(f"running before this change: oddvex-api:{PREVIOUS} and oddvex-web:{PREVIOUS}", result.stdout)

    def test_a_healthy_deploy_is_recorded(self) -> None:
        self.server(after="0006")
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertEqual((self.root / "release.healthy").read_text().strip(), self.release)
        self.assertIn("MIGRATION APPLIED: the database went from revision 0005 to 0006", result.stdout)
        self.assertIn(f"release {self.release} is running and answers", result.stdout)
        log = (self.root / "ops.log").read_text()
        self.assertRegex(log, rf"deploy release={self.release} previous={PREVIOUS} revision=0005->0006 dump=predeploy-\S+ result=ok")

    def test_when_the_dump_fails_no_migration_runs_and_no_container_is_replaced(self) -> None:
        self.rule(r"exec -T db pg_dump ", exit=1, stderr="pg_dump: error: connection failed\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("the pre-deploy dump failed. Migrations were not run and no container was replaced", result.stdout)
        self.assertEqual(self.lines(r" run --rm -T migrate"), [])
        self.assertEqual(self.lines(UP), [])
        self.assertEqual([path.name for path in self.backups.iterdir()], [], "a failed dump leaves no file behind")

    def test_an_empty_dump_is_a_failed_dump(self) -> None:
        self.rule(r"exec -T db pg_dump ", stdout="")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.lines(r" run --rm -T migrate"), [])

    def test_a_dump_that_cannot_be_read_back_is_a_failed_dump(self) -> None:
        self.rule(r"exec -T db pg_restore -l", exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.lines(UP), [])

    def test_older_pre_deploy_dumps_are_pruned_only_after_a_new_one_exists(self) -> None:
        for number in range(1, 8):
            self.add_dump(f"predeploy-2026010{number}T000000Z-x-to-y.dump", age_hours=24 * (10 - number))
        self.add_dump("oddvex-20260101T000000Z.dump", age_hours=24 * 30)
        self.server()
        self.assert_ok(self.ops("deploy"))
        self.assertEqual(len(self.predeploy_dumps()), 5)
        self.assertNotIn("predeploy-20260101T000000Z-x-to-y.dump", self.predeploy_dumps())
        self.assertTrue((self.backups / "oddvex-20260101T000000Z.dump").exists(), "daily dumps belong to the backup loop")

    def test_a_failed_dump_prunes_nothing(self) -> None:
        for number in range(1, 8):
            self.add_dump(f"predeploy-2026010{number}T000000Z-x-to-y.dump", age_hours=24 * (10 - number))
        self.rule(r"exec -T db pg_dump ", exit=1)
        self.server()
        self.assertEqual(self.ops("deploy").returncode, 2)
        self.assertEqual(len(self.predeploy_dumps()), 7)

    def test_a_failed_migration_replaces_nothing_and_says_so(self) -> None:
        self.rule(r" run --rm -T migrate$", exit=1, stderr="alembic failed\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("DEPLOY FAILED: the migration step failed. No container was replaced", result.stdout)
        self.assertIn("The database revision is still 0005", result.stdout)
        self.assertIn("ACTION=rollback", result.stdout, "an earlier release is started with rollback, not deploy")
        self.assertEqual(self.lines(UP), [])
        self.assertEqual(self.lines(r"^rm -f"), [])

    def test_a_migration_table_without_a_revision_is_dumped_too(self) -> None:
        self.rule(r"exec -T db psql .*SELECT version_num", stdout="\n", times=1)
        self.server(after="0006")
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertNotIn("nothing to dump", result.stdout)
        self.assertEqual(len(self.predeploy_dumps()), 1)
        self.assertLess(self.index_of(r"exec -T db pg_dump "), self.index_of(r" run --rm -T migrate$"))

    def unreadable_after_migration(self) -> None:
        """The revision is 0005 before the migration step and cannot be read after it."""
        self.write_env(ODDVEX_CONTACT_EMAIL="support@oddvex.com")
        self.answer_builder()
        self.rule(r"exec -T db psql .*to_regclass", stdout="t\n", times=1)
        self.rule(r"exec -T db psql .*SELECT version_num", stdout="0005\n", times=1)
        self.rule(r"exec -T db psql ", exit=1, stderr="psql: error: connection refused\n")
        self.rule(r"exec -T db pg_dump ", stdout="PGDMP-canned-dump-bytes")
        self.answer_running(PREVIOUS)
        self.answer_healthy()

    def test_a_revision_that_cannot_be_read_afterwards_is_not_reported_as_a_migration(self) -> None:
        self.unreadable_after_migration()
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertNotIn("MIGRATION APPLIED", result.stdout)
        self.assertNotIn("to unknown", result.stdout)
        self.assertIn("the database revision could not be read after the migration step", result.stdout)
        self.assertIn("it was 0005 before", result.stdout)

    def test_a_failed_release_with_an_unreadable_revision_names_the_dump_without_claiming_a_migration(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.unreadable_after_migration()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("A MIGRATION WAS APPLIED", result.stdout)
        self.assertIn("IT IS NOT KNOWN WHETHER THIS DEPLOY APPLIED A MIGRATION", result.stdout)
        self.assertIn(f"DUMP={self.predeploy_dumps()[0]}", result.stdout)

    def test_the_first_deploy_has_no_schema_to_dump(self) -> None:
        self.answer_builder()
        self.answer_database(None, after="0005")
        self.answer_healthy()
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertIn("nothing to dump", result.stdout)
        self.assertEqual(self.lines(r"pg_dump"), [])
        self.assertEqual(len(self.lines(r" run --rm -T migrate$")), 1)


class FailedDeploy(DeployCase):
    """deploy-ops#2: a release that does not become healthy"""

    def test_the_previous_images_are_started_again_and_the_output_says_so(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        ups = self.calls(UP)
        self.assertEqual([call["release"] for call in ups], [self.release, PREVIOUS])
        self.assertIn(f"DEPLOY FAILED: release {self.release} did not become healthy.", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK and answers.", result.stdout)
        self.assertEqual((self.root / "release.healthy").read_text().strip(), PREVIOUS)
        self.assertRegex((self.root / "ops.log").read_text(), rf"deploy release={self.release} previous={PREVIOUS} .* result=failed")

    def test_without_a_migration_it_says_the_database_is_as_before(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertIn("No migration was applied by this deploy: the database is at revision 0005, as before.", result.stdout)
        self.assertNotIn("ACTION=restore", result.stdout)

    def test_with_a_migration_applied_it_names_the_dump_and_the_exact_restore_command(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.server(after="0006")
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        dump = self.predeploy_dumps()[0]
        self.assertIn("A MIGRATION WAS APPLIED BY THIS DEPLOY AND WAS NOT UNDONE: the database is at revision 0006, it was at 0005.", result.stdout)
        self.assertIn("ACTION=restore", result.stdout)
        self.assertIn(f"DUMP={dump}", result.stdout)
        self.assertIn(f"CONFIRM={dump}", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK", result.stdout)

    def test_the_previous_release_is_started_without_running_migrations_again(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.server(after="0006")
        self.ops("deploy")
        self.assertEqual(len(self.lines(r" run --rm -T migrate")), 1, "only the new release's migration step ran")
        self.assertEqual(self.lines(r"pg_restore -U"), [], "a deploy never restores a dump by itself")

    def test_containers_that_start_but_do_not_answer_count_as_unhealthy(self) -> None:
        self.rule(r"^run --rm --network \S+ \S+ .*oddvex-api:8000/health", release=self.release, stdout="503", exit=22)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("the API health check answered '503'", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {PREVIOUS} WAS PUT BACK", result.stdout)

    def test_it_says_loudly_when_putting_back_fails_too(self) -> None:
        self.rule(UP, exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"PUTTING BACK RELEASE {PREVIOUS} FAILED TOO. OddVex is not answering.", result.stdout)

    def test_it_says_so_when_there_is_nothing_to_put_back(self) -> None:
        self.rule(UP, exit=1)
        self.server(running=None)
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("NOTHING WAS PUT BACK: no earlier release was running", result.stdout)
        self.assertEqual(len(self.lines(UP)), 1)

    def test_it_says_so_when_the_previous_images_are_gone(self) -> None:
        self.rule(UP, release=self.release, exit=1)
        self.rule(rf"^image inspect oddvex-api:{PREVIOUS}$", exit=1)
        self.server()
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"NOTHING WAS PUT BACK: the images of the previous release {PREVIOUS} are no longer on this server.", result.stdout)

    def test_the_last_healthy_release_is_used_when_the_running_tags_disagree(self) -> None:
        (self.root / "release.healthy").write_text("good999\n")
        self.rule(UP, release=self.release, exit=1)
        self.rule(r"^inspect --format \S*Config\.Image\S* webcontainer$", stdout="oddvex-web:other22\n")
        self.server()
        result = self.ops("deploy")
        self.assertEqual([call["release"] for call in self.calls(UP)], [self.release, "good999"])
        self.assertIn("THE PREVIOUS RELEASE good999 WAS PUT BACK", result.stdout)


class EnvFile(DeployCase):
    """The contact address and the first-run file"""

    def test_an_empty_contact_address_is_filled_in_and_nothing_else_changes(self) -> None:
        self.server(contact="")
        before = self.env_file()
        result = self.ops("deploy")
        self.assert_ok(result)
        after = self.env_file()
        self.assertEqual(after["ODDVEX_CONTACT_EMAIL"], "support@oddvex.com")
        self.assertEqual({k: v for k, v in after.items() if k != "ODDVEX_CONTACT_EMAIL"},
                         {k: v for k, v in before.items() if k != "ODDVEX_CONTACT_EMAIL"})
        self.assertIn("ODDVEX_CONTACT_EMAIL was missing or empty", result.stdout)
        self.assertLess(result.stdout.index("ODDVEX_CONTACT_EMAIL was missing"), result.stdout.index("building oddvex-web"),
                        "the address must be in the file before the web image is built")

    def test_a_missing_contact_key_is_added(self) -> None:
        self.server()
        self.write_env(ODDVEX_CONTACT_EMAIL=None)
        self.assertNotIn("ODDVEX_CONTACT_EMAIL", self.env_file())
        self.assert_ok(self.ops("deploy"))
        self.assertEqual(self.env_file()["ODDVEX_CONTACT_EMAIL"], "support@oddvex.com")

    def test_an_existing_contact_address_is_left_alone(self) -> None:
        self.server(contact="hello@example.test")
        text = (self.root / ".env").read_text()
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertEqual((self.root / ".env").read_text(), text)
        self.assertIn("the contact page of this build will show: hello@example.test", result.stdout)

    def test_the_file_stays_private_and_secrets_are_never_printed(self) -> None:
        self.server(contact="")
        result = self.ops("deploy")
        self.assertEqual((self.root / ".env").stat().st_mode & 0o777, 0o600)
        self.assert_nothing_hidden_is_shown(result)

    def test_the_first_deploy_creates_the_file_with_the_contact_address(self) -> None:
        self.answer_builder()
        self.answer_database(None, after="0005")
        self.answer_healthy()
        result = self.ops("deploy")
        self.assert_ok(result)
        env = self.env_file()
        self.assertEqual(env["ODDVEX_CONTACT_EMAIL"], "support@oddvex.com")
        self.assertEqual(env["ODDVEX_ADMIN_EMAILS"], "")
        self.assertEqual(len(env["ODDVEX_JWT_SECRET"]), 64)
        self.assertNotIn(env["ODDVEX_JWT_SECRET"], result.stdout)
        self.assertNotIn(env["ODDVEX_DB_PASSWORD"], result.stdout)
        self.assertEqual((self.root / ".env").stat().st_mode & 0o777, 0o600)


class AdministratorList(DeployCase):
    """docs-truth#1: the documented way to the first administrator is only safe on a release that has the new rule."""

    def test_a_commit_without_the_script_is_not_deployed_while_an_address_is_listed(self) -> None:
        self.server()
        self.write_env(ODDVEX_CONTACT_EMAIL="support@oddvex.com", ODDVEX_ADMIN_EMAILS="owner@example.test")
        result = self.ops("deploy")
        self.assertEqual(result.returncode, 2)
        self.assertIn("has no services/api/scripts/bootstrap_admin.py", result.stdout)
        self.assertIn("Nothing was changed", result.stdout)
        self.assertEqual(self.calls(r"compose\.yaml (build|up|run)"), [])
        self.assertEqual(self.lines(r"^rm -f"), [])

    def test_a_commit_with_the_script_is_deployed(self) -> None:
        script = self.repo / "services" / "api" / "scripts" / "bootstrap_admin.py"
        script.parent.mkdir(parents=True)
        script.write_text("# stand-in\n")
        release = self.commit("the administrator script")
        self.server()
        self.write_env(ODDVEX_CONTACT_EMAIL="support@oddvex.com", ODDVEX_ADMIN_EMAILS="owner@example.test")
        result = self.ops("deploy")
        self.assert_ok(result)
        self.assertIn(f"release {release} is running and answers", result.stdout)

    def test_an_empty_list_needs_no_script(self) -> None:
        self.server()
        self.assert_ok(self.ops("deploy"))


class RunTwice(DeployCase):
    def test_a_second_deploy_of_the_same_release_succeeds(self) -> None:
        self.server()
        self.assert_ok(self.ops("deploy"))
        first = (self.root / ".env").read_text()
        self.assert_ok(self.ops("deploy"))
        self.assertEqual((self.root / ".env").read_text(), first)
        # Two dumps were taken. The file name has a resolution of one second, so on a fast machine
        # the second can replace the first; the docker calls are what is counted.
        self.assertEqual(len(self.lines(r"exec -T db pg_dump ")), 2)
        self.assertIn(len(self.predeploy_dumps()), (1, 2))


if __name__ == "__main__":
    unittest.main()
