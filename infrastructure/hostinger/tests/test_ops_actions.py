"""The other actions of ops.sh: setenv, admin, status, rollback, restore."""

from __future__ import annotations

import shutil
import unittest

from support import OpsCase

UP = r" up -d --no-build .*--wait"
RUNNING = "bbb2222"


class Setenv(OpsCase):
    def test_it_replaces_one_key_and_leaves_every_other_line_alone(self) -> None:
        self.write_env()
        before = self.env_file()
        result = self.setenv("ODDVEX_ADMIN_EMAILS", "owner@example.test")
        self.assert_ok(result)
        after = self.env_file()
        self.assertEqual(after["ODDVEX_ADMIN_EMAILS"], "owner@example.test")
        del before["ODDVEX_ADMIN_EMAILS"], after["ODDVEX_ADMIN_EMAILS"]
        self.assertEqual(after, before)
        self.assertEqual((self.root / ".env").stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.calls(), [], "setenv does not touch Docker")

    def test_it_adds_a_key_that_is_not_in_the_file(self) -> None:
        self.write_env()
        self.assert_ok(self.setenv("ODDVEX_PASSWORD_HASH_CONCURRENCY", "4"))
        self.assertEqual(self.env_file()["ODDVEX_PASSWORD_HASH_CONCURRENCY"], "4")
        self.assertEqual(len((self.root / ".env").read_text().splitlines()), 6)

    def test_it_never_prints_another_value_from_the_file(self) -> None:
        self.write_env()
        result = self.setenv("ODDVEX_CONTACT_EMAIL", "hello@example.test")
        self.assert_ok(result)
        self.assert_nothing_hidden_is_shown(result)
        self.assertNotIn("preview.oddvex.com", result.stdout + result.stderr)

    def test_it_says_that_a_deploy_is_needed(self) -> None:
        self.write_env()
        result = self.setenv("ODDVEX_CONTACT_EMAIL", "hello@example.test")
        self.assertIn("A deploy is needed for the change to take effect", result.stdout)

    def test_secrets_and_unknown_keys_are_refused(self) -> None:
        for key in ("ODDVEX_JWT_SECRET", "ODDVEX_DB_PASSWORD", "ODDVEX_PUBLIC_URL", "PATH", "ODDVEX_ADMIN_EMAILS EXTRA",
                    # Two names that are next to each other in the list: a substring test would let this through
                    # and the line it writes makes Compose reject the whole file.
                    "ODDVEX_CONTACT_EMAIL ODDVEX_ADMIN_EMAILS", "ODDVEX_ADMIN_EMAILS ODDVEX_PASSWORD_HASH_CONCURRENCY",
                    " ODDVEX_ADMIN_EMAILS", "ODDVEX_ADMIN_EMAILS ", "ODDVEX_ADMIN_EMAILS\nODDVEX_JWT_SECRET",
                    "oddvex_admin_emails", "ODDVEX_ADMIN_EMAILS=x", "*"):
            self.write_env()
            text = (self.root / ".env").read_text()
            result = self.setenv(key, "x@example.test")
            self.assertEqual(result.returncode, 2, key)
            self.assertIn("cannot be set with this action", result.stdout)
            self.assertEqual((self.root / ".env").read_text(), text, key)
            self.assert_nothing_hidden_is_shown(result)

    def test_values_that_could_break_the_file_are_refused(self) -> None:
        for value in ("a@example.test\nODDVEX_PUBLIC_URL=x", "a@example.test #x", "$ODDVEX_PUBLIC_URL@example.test", "a b@example.test", "'a@example.test'"):
            self.write_env()
            text = (self.root / ".env").read_text()
            result = self.setenv("ODDVEX_ADMIN_EMAILS", value)
            self.assertEqual(result.returncode, 2, value)
            self.assertEqual((self.root / ".env").read_text(), text, value)

    def test_each_key_checks_its_value(self) -> None:
        bad = {
            "ODDVEX_CONTACT_EMAIL": ["", "not-an-address", "a@example.test,b@example.test"],
            "ODDVEX_ADMIN_EMAILS": ["not-an-address", "a@example.test,nope"],
            "ODDVEX_PASSWORD_HASH_CONCURRENCY": ["0", "9", "32", "two", ""],
            "ODDVEX_PASSWORD_HASH_WAIT_SECONDS": ["31", "30.5", "-1", "soon", "", "1.", ".5", "1.234", "100"],
            "ODDVEX_BACKUP_KEEP_DAYS": ["0", "100", "all", ""],
        }
        for key, values in bad.items():
            for value in values:
                self.write_env()
                result = self.setenv(key, value)
                self.assertEqual(result.returncode, 2, f"{key}={value!r}")
                self.assertIn("nothing was changed", result.stdout)
        good = {
            "ODDVEX_ADMIN_EMAILS": ["", "a@example.test,b.c+d@example.test"],
            "ODDVEX_PASSWORD_HASH_CONCURRENCY": ["1", "8"],
            "ODDVEX_PASSWORD_HASH_WAIT_SECONDS": ["0", "1.0", "0.25", "10.5", "29.75", "30", "30.0"],
            "ODDVEX_BACKUP_KEEP_DAYS": ["1", "30"],
        }
        for key, values in good.items():
            for value in values:
                self.write_env()
                self.assert_ok(self.setenv(key, value))
                self.assertEqual(self.env_file()[key], value)

    def test_running_it_twice_changes_nothing_the_second_time(self) -> None:
        self.write_env()
        self.assert_ok(self.setenv("ODDVEX_ADMIN_EMAILS", "owner@example.test"))
        text = (self.root / ".env").read_text()
        result = self.setenv("ODDVEX_ADMIN_EMAILS", "owner@example.test")
        self.assert_ok(result)
        self.assertIn("nothing was changed", result.stdout)
        self.assertEqual((self.root / ".env").read_text(), text)

    def test_listing_an_administrator_explains_the_real_rule(self) -> None:
        self.write_env()
        result = self.setenv("ODDVEX_ADMIN_EMAILS", "owner@example.test")
        self.assertIn("Listing an address gives nobody the administrator role by itself", result.stdout)
        self.assertIn("ACTION=admin", result.stdout)
        self.assertNotIn("WARNING", result.stdout)

    def test_it_advises_against_the_public_contact_address_as_administrator(self) -> None:
        self.write_env(ODDVEX_CONTACT_EMAIL="hello@example.test")
        for address in ("support@oddvex.com", "Hello@example.test"):
            result = self.setenv("ODDVEX_ADMIN_EMAILS", address)
            self.assert_ok(result)
            self.assertIn(f"WARNING: {address} is the public contact address", result.stdout)

    def test_without_an_env_file_it_changes_nothing(self) -> None:
        result = self.setenv("ODDVEX_ADMIN_EMAILS", "owner@example.test")
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.root / ".env").exists())


class Admin(OpsCase):
    def test_it_runs_the_script_in_the_api_container_and_prints_its_output(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="other@example.test,Owner@example.test")
        self.rule(r"exec -T oddvex-api python scripts/bootstrap_admin\.py", stdout="Administrator owner@example.test\nNew password: canned-password\n")
        result = self.ops("admin", EMAIL="owner@example.test")
        self.assert_ok(result)
        call = self.calls(r"bootstrap_admin")[0]
        self.assertEqual(call["args"][-7:-5], ["exec", "-T"])
        self.assertEqual(call["args"][-5:], ["oddvex-api", "python", "scripts/bootstrap_admin.py", "--email", "owner@example.test"])
        self.assertIn("New password: canned-password", result.stdout)
        self.assertIn("not shown again", result.stdout)

    def test_an_address_that_is_not_listed_is_refused_before_anything_runs(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="owner@example.test")
        result = self.ops("admin", EMAIL="stranger@example.test")
        self.assertEqual(result.returncode, 2)
        self.assertIn("is not listed in ODDVEX_ADMIN_EMAILS", result.stdout)
        self.assertEqual(self.calls(), [])

    def test_a_missing_or_malformed_address_is_refused(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="owner@example.test")
        for email in ("", "owner", "owner@example.test; rm -rf /", "--help"):
            result = self.ops("admin", EMAIL=email)
            self.assertEqual(result.returncode, 2, email)
            self.assertEqual(self.calls(), [], email)

    def test_a_failing_script_fails_the_action_with_a_hint(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="owner@example.test")
        self.rule(r"bootstrap_admin\.py", exit=1, stderr="owner@example.test is not in ODDVEX_ADMIN_EMAILS\n")
        result = self.ops("admin", EMAIL="owner@example.test")
        self.assertEqual(result.returncode, 2)
        self.assertIn("deploy first", result.stdout)
        self.assertIn("is not in ODDVEX_ADMIN_EMAILS", result.stderr)

    def test_no_secret_from_the_env_file_is_printed(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="owner@example.test")
        result = self.ops("admin", EMAIL="owner@example.test")
        self.assert_nothing_hidden_is_shown(result)


class Status(OpsCase):
    EDGE_PS = r"^ps -q .*--filter network=medivh-automation_default$"

    def container(self, identifier: str, name: str, address: str, names: str) -> None:
        self.rule(rf"^inspect --format \S*\.Name\S* .* {identifier}$", stdout=f"/{name} {address} {names} \n")

    def lookup(self, name: str, answer: str) -> None:
        self.rule(rf"--entrypoint sh \S+ -c .* lookup {name}$", stdout=answer)

    def test_it_shows_that_api_and_web_do_not_resolve_to_an_oddvex_container(self) -> None:
        self.write_env()
        self.rule(self.EDGE_PS, stdout="c1\nc2\n")
        self.container("c1", "oddvex-oddvex-api-1", "172.18.0.5", "oddvex-oddvex-api-1 oddvex-api 0123abcd")
        self.container("c2", "oddvex-oddvex-web-1", "172.18.0.6", "oddvex-oddvex-web-1 oddvex-web 4567cdef")
        self.lookup("api", "Server:\t\t127.0.0.11\nAddress:\t127.0.0.11:53\n\n** server can't find api: NXDOMAIN\n\nlookup-done\n")
        self.lookup("web", "Server:\t\t127.0.0.11\nAddress:\t127.0.0.11:53\n\nNon-authoritative answer:\nName:\tweb\nAddress: 172.18.0.9\n\nlookup-done\n")
        result = self.ops("status")
        self.assert_ok(result)
        self.assertIn("oddvex-oddvex-api-1 (172.18.0.5): oddvex-oddvex-api-1 oddvex-api 0123abcd", result.stdout)
        self.assertIn("the name 'api' does not resolve on the shared network", result.stdout)
        self.assertIn("the name 'web' resolves to 172.18.0.9, which is not an OddVex container", result.stdout)
        self.assertIn("OK: no OddVex container answers to 'api' or 'web' on the shared network", result.stdout)
        self.assertNotIn("WARNING: an OddVex container", result.stdout)

    def test_it_warns_while_a_container_of_an_old_service_name_is_still_there(self) -> None:
        self.write_env()
        self.rule(self.EDGE_PS, stdout="c1\n")
        self.container("c1", "oddvex-api-1", "172.18.0.5", "oddvex-api-1 api oddvex-api 0123abcd")
        self.lookup("api", "Name:\tapi\nAddress: 172.18.0.5\nlookup-done\n")
        self.lookup("web", "** server can't find web: NXDOMAIN\nlookup-done\n")
        result = self.ops("status")
        self.assert_ok(result)
        self.assertIn("the name 'api' resolves to 172.18.0.5, which IS AN OddVex CONTAINER", result.stdout)
        self.assertIn("WARNING: an OddVex container still answers to 'api' or 'web'", result.stdout)
        self.assertNotIn("OK: no OddVex container", result.stdout)

    def test_a_registered_generic_alias_is_a_warning_even_when_the_lookup_cannot_run(self) -> None:
        self.write_env()
        self.rule(self.EDGE_PS, stdout="c1\n")
        self.container("c1", "oddvex-web-1", "172.18.0.6", "oddvex-web-1 web oddvex-web")
        self.lookup("api", "lookup-unavailable\n")
        self.lookup("web", "lookup-unavailable\n")
        result = self.ops("status")
        self.assertIn("could not be looked up", result.stdout)
        self.assertIn("WARNING: an OddVex container still answers", result.stdout)

    def test_it_shows_the_age_and_size_of_the_newest_dump(self) -> None:
        self.write_env()
        self.add_dump("oddvex-20260101T000000Z.dump", b"x" * 10, age_hours=50)
        self.add_dump("oddvex-20260102T000000Z.dump", b"x" * 1234, age_hours=3)
        self.add_dump("predeploy-20260102T100000Z-aaa-to-bbb.dump", b"x" * 99, age_hours=5)
        result = self.ops("status")
        self.assert_ok(result)
        self.assertIn("daily dumps in", result.stdout)
        self.assertIn(": 2; newest oddvex-20260102T000000Z.dump, 1234 bytes, written 3 h ago", result.stdout)
        self.assertIn("newest pre-deploy dump: predeploy-20260102T100000Z-aaa-to-bbb.dump, 99 bytes, written 5 h ago", result.stdout)
        self.assertNotIn("more than 26 hours old", result.stdout)

    def test_it_warns_when_the_newest_daily_dump_is_old_and_shows_the_backup_log(self) -> None:
        self.write_env()
        self.add_dump("oddvex-20260101T000000Z.dump", age_hours=72)
        self.rule(r" logs --no-log-prefix --tail 4 backup$", stdout="BACKUP FAILED at 2026-01-03T00:00:00Z (3 in a row)\n")
        result = self.ops("status")
        self.assertIn("written 3 d ago", result.stdout)
        self.assertIn("WARNING: the newest daily dump is more than 26 hours old", result.stdout)
        self.assertIn("BACKUP FAILED at 2026-01-03T00:00:00Z (3 in a row)", result.stdout)

    def test_it_says_when_there_is_no_dump_at_all(self) -> None:
        self.write_env()
        result = self.ops("status")
        self.assertIn("daily dumps in", result.stdout)
        self.assertIn(": none", result.stdout)

    def test_it_changes_nothing(self) -> None:
        self.write_env()
        self.add_dump("oddvex-20260101T000000Z.dump")
        before = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if ".git" not in path.parts)
        text = (self.root / ".env").read_text()
        self.assert_ok(self.ops("status"))
        after = sorted(str(path.relative_to(self.root)) for path in self.root.rglob("*") if ".git" not in path.parts)
        self.assertEqual(after, before)
        self.assertEqual((self.root / ".env").read_text(), text)
        for line in self.lines():
            self.assertNotRegex(line, r"( up | down| rm | stop | start | build | restart |pg_restore|pg_dump|ALTER|DROP|CREATE)")

    def test_it_prints_no_secret(self) -> None:
        self.write_env(ODDVEX_ADMIN_EMAILS="owner@example.test")
        result = self.ops("status")
        self.assert_nothing_hidden_is_shown(result)
        self.assertIn("administrator addresses listed: owner@example.test", result.stdout)

    def test_it_does_not_fail_on_a_server_with_nothing_deployed(self) -> None:
        result = self.ops("status")
        self.assert_ok(result)
        self.assertIn("nothing is deployed here yet", result.stdout)

    def test_an_unknown_action_is_refused(self) -> None:
        self.write_env()
        result = self.ops("destroy")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])


class Rollback(OpsCase):
    def server(self, *, revision: str = "0005", history: str = "0004 -> 0005 (head), five\n0003 -> 0004, four\n<base> -> 0001, one\n") -> str:
        """Release RUNNING is live. The clone holds an earlier commit; returns its short id."""
        earlier = self.release
        self.commit("second release")
        self.write_env()
        self.answer_builder()
        self.rule(r" run --rm -T migrate alembic history$", stdout=history)
        self.answer_database(revision)
        self.answer_running(RUNNING)
        self.answer_healthy()
        self.rule(rf"^image inspect oddvex-(api|web):({RUNNING}|{earlier})$", exit=0)
        self.rule(r"^image inspect ", exit=1)
        self.rule(r"^image ls --format \S+ oddvex-api$", stdout=f"{earlier}\n{RUNNING}\n")
        return earlier

    def test_an_earlier_release_is_started_from_its_images_without_a_build(self) -> None:
        earlier = self.server()
        result = self.ops("rollback", REF=earlier)
        self.assert_ok(result)
        self.assertEqual([call["release"] for call in self.calls(UP)], [earlier])
        self.assertEqual(self.lines(r"compose\.yaml build "), [])
        self.assertEqual(self.lines(r"^buildx"), [])
        self.assertIn(f"release {earlier} is running and answers", result.stdout)
        self.assertEqual((self.root / "release.healthy").read_text().strip(), earlier)

    def test_a_full_commit_id_finds_the_release_that_was_built_from_it(self) -> None:
        earlier = self.server()
        full = self.git("rev-parse", earlier)
        result = self.ops("rollback", REF=full)
        self.assert_ok(result)
        self.assertEqual([call["release"] for call in self.calls(UP)], [earlier])

    def test_it_never_runs_migrations_and_never_restores(self) -> None:
        earlier = self.server()
        self.assert_ok(self.ops("rollback", REF=earlier))
        self.assertEqual(self.lines(r" run --rm -T migrate$"), [])
        self.assertEqual(self.lines(r"alembic (upgrade|downgrade)"), [])
        self.assertEqual(self.lines(r"pg_restore -U"), [])

    def test_no_memory_check_stands_in_the_way_when_nothing_is_built(self) -> None:
        earlier = self.server()
        self.meminfo.write_text("MemAvailable:    300000 kB\n")
        self.assert_ok(self.ops("rollback", REF=earlier))

    def test_a_database_newer_than_the_release_is_said_loudly_with_the_dump_to_restore(self) -> None:
        earlier = self.server(revision="0006")
        self.add_dump(f"predeploy-20260101T000000Z-zzz-to-{earlier}.dump", age_hours=30)
        dump = self.add_dump(f"predeploy-20260102T000000Z-{earlier}-to-{RUNNING}.dump", age_hours=4)
        result = self.ops("rollback", REF=earlier)
        self.assert_ok(result)
        self.assertIn("THE DATABASE IS NEWER THAN THIS RELEASE: it is at revision 0006; the newest migration "
                      f"release {earlier} knows is 0005.", result.stdout)
        self.assertIn("Nothing was undone in the database.", result.stdout)
        self.assertIn(f"DUMP={dump.name}", result.stdout)
        self.assertIn(f"CONFIRM={dump.name}", result.stdout)
        self.assertEqual([call["release"] for call in self.calls(UP)], [earlier], "the release is started all the same")

    def test_it_says_so_when_no_matching_dump_exists(self) -> None:
        earlier = self.server(revision="0006")
        result = self.ops("rollback", REF=earlier)
        self.assert_ok(result)
        self.assertIn(f"No pre-deploy dump taken while release {earlier} was running", result.stdout)

    def test_a_matching_database_needs_no_warning(self) -> None:
        earlier = self.server()
        result = self.ops("rollback", REF=earlier)
        self.assertIn(f"the database is at revision 0005, the newest one release {earlier} knows", result.stdout)
        self.assertNotIn("THE DATABASE IS NEWER", result.stdout)

    def test_a_release_that_needs_a_newer_database_is_refused(self) -> None:
        earlier = self.server(revision="0004")
        result = self.ops("rollback", REF=earlier)
        self.assertEqual(result.returncode, 2)
        self.assertIn("A rollback never applies migrations", result.stdout)
        self.assertEqual(self.lines(UP), [])

    def test_missing_images_are_built_again_from_that_commit_under_the_ceiling(self) -> None:
        earlier = self.server()
        # Asked twice before the build (is REF a release tag, are its images here), then after it.
        self.rules.insert(0, {"match": rf"^image inspect oddvex-(api|web):{earlier}$", "exit": 1, "times": 2})
        self.rules.insert(0, {"match": r"^image ls --format \S+ oddvex-api$", "stdout": f"{RUNNING}\n"})
        result = self.ops("rollback", REF=earlier)
        self.assert_ok(result)
        builds = self.calls(r"compose\.yaml build ")
        self.assertEqual(len(builds), 2)
        for call in builds:
            self.assertIn("--builder oddvex-builder", call["line"])
            self.assertEqual(call["release"], earlier)
            self.assertEqual(call["build_root"], str(self.root / "rollback-source"))
        self.assertFalse((self.root / "rollback-source").exists(), "the exported commit is removed after the build")
        self.assertIn("building them from commit", result.stdout)

    def test_a_failed_rollback_puts_the_running_release_back(self) -> None:
        earlier = self.server()
        self.rules.insert(0, {"match": UP, "release": earlier, "exit": 1})
        result = self.ops("rollback", REF=earlier)
        self.assertEqual(result.returncode, 2)
        self.assertEqual([call["release"] for call in self.calls(UP)], [earlier, RUNNING])
        self.assertIn(f"ROLLBACK FAILED: release {earlier} did not become healthy.", result.stdout)
        self.assertIn(f"THE PREVIOUS RELEASE {RUNNING} WAS PUT BACK", result.stdout)

    def test_a_failed_build_stops_the_builder_and_leaves_no_exported_commit_behind(self) -> None:
        earlier = self.server()
        self.rules.insert(0, {"match": rf"^image inspect oddvex-(api|web):{earlier}$", "exit": 1})
        self.rules.insert(0, {"match": r"^image ls --format \S+ oddvex-api$", "stdout": f"{RUNNING}\n"})
        self.rules.insert(0, {"match": r"compose\.yaml build .* oddvex-api$", "exit": 1, "stderr": "Killed\n"})
        result = self.ops("rollback", REF=earlier)
        self.assertEqual(result.returncode, 2)
        self.assertIn("The running containers were not touched", result.stdout)
        self.assertFalse((self.root / "rollback-source").exists(), "the exported commit is removed after a failed build too")
        self.assertEqual(len(self.lines(r"^buildx stop oddvex-builder$")), 1)
        self.assertEqual(self.lines(UP), [])

    def test_a_commit_that_cannot_be_exported_stops_with_a_message(self) -> None:
        earlier = self.server()
        self.rules.insert(0, {"match": rf"^image inspect oddvex-(api|web):{earlier}$", "exit": 1})
        self.rules.insert(0, {"match": r"^image ls --format \S+ oddvex-api$", "stdout": f"{RUNNING}\n"})
        # `git archive` fails, so tar gets no archive. (A stand-in for git, not for tar: a BusyBox
        # shell may run its own tar whatever is on PATH.)
        real_git = shutil.which("git")
        (self.bin / "git").write_text(f'#!/bin/sh\ncase " $* " in *" archive "*) exit 1 ;; esac\nexec "{real_git}" "$@"\n')
        (self.bin / "git").chmod(0o755)
        result = self.ops("rollback", REF=earlier)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("could not export commit", result.stdout)
        self.assertIn("Nothing was changed", result.stdout)
        self.assertEqual(self.lines(r"compose\.yaml build "), [])
        self.assertEqual(self.lines(UP), [])
        self.assertFalse((self.root / "rollback-source").exists())

    def test_an_old_container_that_cannot_be_removed_is_not_reported_as_success(self) -> None:
        earlier = self.server()
        self.rules.insert(0, {"match": r"^ps -aq .*label=com\.docker\.compose\.service=web$", "stdout": "oldweb\n", "until": r"^rm -f oldweb$"})
        self.rules.insert(0, {"match": r"^rm -f oldweb$", "exit": 1, "stderr": "Error response from daemon: device or resource busy\n"})
        result = self.ops("rollback", REF=earlier)
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("ROLLBACK NOT COMPLETE", result.stdout)
        self.assertIn("A CONTAINER OF AN OLD SERVICE NAME IS STILL THERE: oldweb", result.stdout)
        self.assertEqual([call["release"] for call in self.calls(UP)], [earlier])
        self.assertRegex((self.root / "ops.log").read_text(), r"rollback .* result=old-container-left")

    def test_rolling_back_to_the_running_release_changes_nothing(self) -> None:
        self.server()
        result = self.ops("rollback", REF=RUNNING)
        self.assert_ok(result)
        self.assertIn(f"release {RUNNING} is already running and answers; nothing was changed", result.stdout)
        self.assertEqual(self.lines(UP), [])

    def test_an_unknown_ref_changes_nothing(self) -> None:
        self.server()
        result = self.ops("rollback", REF="no-such-ref")
        self.assertEqual(result.returncode, 2)
        self.assertIn("is neither a release with images on this server nor a commit", result.stdout)
        self.assertEqual(self.lines(UP), [])

    def test_a_ref_that_looks_like_an_option_is_refused(self) -> None:
        self.server()
        for ref in ("", "--upload-pack=x", "a b", "$(reboot)"):
            result = self.ops("rollback", REF=ref)
            self.assertEqual(result.returncode, 2, ref)
            self.assertEqual(self.lines(UP), [], ref)


class Restore(OpsCase):
    DUMP = "predeploy-20260102T000000Z-aaa1111-to-bbb2222.dump"
    SWAP = r"exec -T db psql .*ALTER DATABASE oddvex RENAME TO oddvex_replaced_\d{8}_\d{6} -c ALTER DATABASE oddvex_restore RENAME TO oddvex$"

    def server(self) -> None:
        self.write_env()
        self.add_dump(self.DUMP, b"PGDMP-the-dump-to-restore", age_hours=2)
        self.answer_database("0006", after="0005")
        self.answer_healthy()
        self.answer_running(RUNNING)
        self.rule(r"^ps -q .*label=com\.docker\.compose\.service=oddvex-api$", stdout="apicontainer\n")
        self.rule(r"^ps -q .*label=com\.docker\.compose\.service=oddvex-web$", stdout="webcontainer\n")
        self.rule(r"^ps -q .*label=com\.docker\.compose\.service=worker$", stdout="workercontainer\n")
        self.rule(r"exec -T db pg_restore -U oddvex -d oddvex_restore", stdin=True)

    def test_without_confirm_it_describes_the_dump_and_changes_nothing(self) -> None:
        self.server()
        result = self.ops("restore", DUMP=self.DUMP)
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"dump {self.DUMP}: 25 bytes, written 2 h ago", result.stdout)
        self.assertIn("REPLACES the whole OddVex database", result.stdout)
        self.assertIn(f"not confirmed, so nothing was changed. To go ahead, run it again with CONFIRM={self.DUMP}", result.stdout)
        self.assertEqual(self.calls(), [], "nothing is asked of Docker before the confirmation")

    def test_a_confirm_that_names_another_file_changes_nothing(self) -> None:
        self.server()
        for confirm in ("yes", "true", self.DUMP.upper(), self.DUMP + "x"):
            result = self.ops("restore", DUMP=self.DUMP, CONFIRM=confirm)
            self.assertEqual(result.returncode, 2, confirm)
            self.assertEqual(self.calls(), [], confirm)

    def test_without_a_dump_name_it_lists_the_dumps_and_changes_nothing(self) -> None:
        self.server()
        result = self.ops("restore")
        self.assertEqual(result.returncode, 2)
        self.assertIn(self.DUMP, result.stdout)
        self.assertEqual(self.calls(), [])

    def test_a_name_with_a_path_or_a_missing_or_empty_file_is_refused(self) -> None:
        self.server()
        self.add_dump("empty.dump", b"")
        for name in ("../.env", "/etc/hostname", "nothing-here.dump", "empty.dump", ".hidden"):
            result = self.ops("restore", DUMP=name, CONFIRM=name)
            self.assertEqual(result.returncode, 2, name)
            self.assertEqual(self.calls(), [], name)

    def test_a_confirmed_restore_dumps_the_live_database_first_then_loads_then_swaps(self) -> None:
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assert_ok(result)
        safety = self.index_of(r"exec -T db pg_dump ")
        create = self.index_of(r"CREATE DATABASE oddvex_restore OWNER oddvex")
        load = self.index_of(r"exec -T db pg_restore -U oddvex -d oddvex_restore --no-owner --exit-on-error$")
        stop = self.index_of(r"^stop apicontainer$")
        swap = self.index_of(self.SWAP)
        start = self.index_of(r"^start apicontainer$")
        self.assertLess(safety, create)
        self.assertLess(create, load)
        self.assertLess(load, stop, "the live database and the containers are untouched until the dump has loaded")
        self.assertLess(stop, swap)
        self.assertLess(swap, start)
        self.assertEqual(self.calls(r"pg_restore -U oddvex -d oddvex_restore")[0]["stdin_bytes"], 25)
        self.assertEqual(sorted(self.lines(r"^stop ")), ["stop apicontainer", "stop webcontainer", "stop workercontainer"])
        self.assertEqual(sorted(self.lines(r"^start ")), ["start apicontainer", "start webcontainer", "start workercontainer"])
        safety_dumps = list(self.backups.glob("prerestore-*.dump"))
        self.assertEqual(len(safety_dumps), 1)
        self.assertIn(f"RESTORED: the live database is now the content of {self.DUMP} (revision 0005; it was at 0006).", result.stdout)
        self.assertIn("The database it replaced was not deleted", result.stdout)
        self.assertIn(f"DUMP={safety_dumps[0].name} with CONFIRM={safety_dumps[0].name}", result.stdout)
        self.assertRegex((self.root / "ops.log").read_text(), rf"restore dump={self.DUMP} revision=0006->0005 kept=oddvex_replaced_\S+ safety=prerestore-\S+ result=ok")

    def test_the_replaced_database_is_never_dropped(self) -> None:
        self.server()
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP))
        for line in self.lines(r"DROP DATABASE"):
            self.assertRegex(line, r"DROP DATABASE IF EXISTS oddvex_restore$")

    def test_a_dump_that_pg_restore_cannot_read_changes_nothing(self) -> None:
        self.rule(r"exec -T db pg_restore -l$", exit=1)
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"pg_restore cannot read {self.DUMP}. Nothing was changed.", result.stdout)
        self.assertEqual(self.lines(r"CREATE DATABASE|ALTER DATABASE|^stop "), [])

    def test_a_dump_that_does_not_load_leaves_the_live_database_and_the_containers_alone(self) -> None:
        self.rule(r"exec -T db pg_restore -U oddvex -d oddvex_restore", exit=1, stderr="pg_restore: error\n")
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assertEqual(result.returncode, 2)
        self.assertIn("the dump did not load cleanly. The live database was not touched.", result.stdout)
        self.assertEqual(self.lines(r"ALTER DATABASE|^stop |^start "), [])

    def test_when_the_swap_fails_the_containers_are_started_again_and_it_says_so(self) -> None:
        self.rule(self.SWAP, exit=1, stderr="ERROR: database is being accessed by other users\n")
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assertEqual(result.returncode, 2)
        self.assertIn("RESTORE FAILED: the databases could not be swapped. The live database is unchanged", result.stdout)
        self.assertEqual(len(self.lines(r"^start ")), 3)
        self.assertNotIn("RESTORED:", result.stdout)

    def test_running_the_same_restore_again_changes_nothing(self) -> None:
        """Docker Manager can start the ops project again with the environment it was last sent."""
        self.server()
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP))
        calls = len(self.calls())
        log = (self.root / "ops.log").read_text()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assertEqual(result.returncode, 2)
        self.assertIn(f"{self.DUMP} is the dump the last restore on this server loaded", result.stdout)
        self.assertIn(f"CONFIRM={self.DUMP}:restore-2", result.stdout)
        self.assertIn("nothing was changed", result.stdout)
        self.assertEqual(len(self.calls()), calls, "nothing is asked of Docker")
        self.assertEqual((self.root / "ops.log").read_text(), log)
        self.assertEqual(len(list(self.backups.glob("prerestore-*.dump"))), 1)

    def test_a_repeated_restore_needs_a_confirmation_that_works_once(self) -> None:
        self.server()
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP))
        again = f"{self.DUMP}:restore-2"
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=again))
        self.assertEqual(len(self.lines(self.SWAP)), 2)
        calls = len(self.calls())
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=again)
        self.assertEqual(result.returncode, 2, "the same environment sent a third time must not swap again")
        self.assertIn(f"CONFIRM={self.DUMP}:restore-3", result.stdout)
        self.assertEqual(len(self.calls()), calls)

    def test_the_repeat_confirmation_is_not_accepted_for_a_first_restore(self) -> None:
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=f"{self.DUMP}:restore-1")
        self.assertEqual(result.returncode, 2)
        self.assertEqual(self.calls(), [])

    def test_another_dump_can_be_restored_after_a_restore(self) -> None:
        self.server()
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP))
        safety = next(self.backups.glob("prerestore-*.dump")).name
        self.assert_ok(self.ops("restore", DUMP=safety, CONFIRM=safety))
        self.assert_ok(self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP))

    def test_it_points_at_deploy_or_rollback_when_the_revision_changed(self) -> None:
        self.server()
        result = self.ops("restore", DUMP=self.DUMP, CONFIRM=self.DUMP)
        self.assertIn(f"Release {RUNNING} was running on revision 0006 and the database is now at 0005.", result.stdout)
        self.assertIn("ACTION=rollback", result.stdout)


if __name__ == "__main__":
    unittest.main()
