# OddVex on the Hostinger VPS (private preview)

Founder decision D-016 (2026-11-17): host on the Hostinger VPS with the `oddvex.com` domain, starting with a
password-protected preview at `preview.oddvex.com`. This replaces Vercel + Neon in `../DEPLOYMENT_PLAN.md` for the
preview. See `docs/product/BUILD_STATUS.md` for what is currently running.

## What the server looks like (read through the Hostinger API on 2026-11-17)

- `srv2032315`, KVM 2: 2 CPUs, 8 GB memory, 100 GB disk, Ubuntu 26.04, IP `179.236.240.236`.
- It is shared. About ten other Docker projects run on it, several of them live products with their own databases.
- One Caddy container (project `medivh-automation`) owns ports 80 and 443 for the whole server. OddVex must be
  added to that Caddy's configuration; it cannot bring its own proxy on those ports.
- The server has no swap. About 4.7 GB of memory was available when checked.
- A Traefik container (`traefik-zxwy`) is in a restart loop. It is not ours and is left alone.
- `oddvex.com` and `www` currently point to `2.57.91.91`, not to this server. They are not changed for the preview.
- The mailbox `support@oddvex.com` was created on 2026-11-19 (decision D-017; seen active through the Hostinger API
  that day). It is the address a deploy puts on the contact page.

## How it is operated

Nobody has a shell on the server. OddVex is operated through a one-shot "ops" container sent to Hostinger's Docker
Manager (`ops.compose.yaml`) with an environment such as `ACTION=deploy` and `REF=<git ref>`. It fetches this public
repository to `/opt/oddvex/repo` at `REF` (`main` when none is sent) and runs `ops.sh` from that commit; a rollback is
the one exception and is described under "Going back". Every action prints what it did and what it found.

The project can be started again from the Docker Manager page. Whether that page keeps the environment that was
last sent has not been checked; if it does, starting the project repeats that action. So every action is written to
be run twice: a second `deploy` or `rollback` of the same release ends with the same release running, a second
`setenv`, `caddy` or `stop` changes nothing, and a second `restore` of the same dump is refused (see "Going back").
The one action that does something new each time is `admin`: every run sets and prints another new password. After
`restore`, `admin` or `stop`, send `ACTION=status`, so that what a restart would repeat is an action that changes
nothing.

| `ACTION` | Other variables | What it does |
|---|---|---|
| `status` | | Changes nothing. Lists the containers, checks that the API and web answer, and shows the running image tags, the database revision, the newest dumps with their age and size, the last lines of the backup container, the names OddVex registers on the shared network, and the last operations |
| `deploy` | `REF` (default `main`) | Builds `REF` and replaces the running containers. The steps are in "What a deploy does" below |
| `rollback` | `REF` (the earlier commit, tag or release; it has no default), `OPS_REF` (default `main`) | Starts an earlier release again. See "Going back" |
| `restore` | `DUMP`, `CONFIRM` | Replaces the database with one dump from `/opt/oddvex/backups`. Does nothing unless `CONFIRM` holds the same file name as `DUMP`, and nothing when the same request arrives a second time. See "Going back" |
| `setenv` | `KEY`, `VALUE` | Sets one setting in `/opt/oddvex/.env`. See "Settings" |
| `admin` | `EMAIL` | Sets a new random password for an administrator address and prints it once. See "The first administrator" |
| `caddy` | | Appends one marked block for `preview.oddvex.com` and `api-preview.oddvex.com` to the shared Caddyfile. It validates the whole new file first, keeps a backup under `/opt/oddvex/`, appends in place and reloads; if the reload fails it restores the backup. It prints the preview user and password once |
| `stop` | | Stops the stack. The database volume and the dumps are kept |

The containers publish no ports. The services `oddvex-web` and `oddvex-api` join the shared proxy network
`medivh-automation_default`; the database, the worker and the backup container are only on the project's own network.
Compose registers a service's name on every network the service joins, which is why the two services are not called
`web` and `api`: those names would also answer lookups made by the other projects on that network. They were called
that before. The first deploy with the new names removes the two old containers, and `status` shows, for the shared
network, every name an OddVex container registers and what `api` and `web` resolve to there.

That first deploy takes the preview away for a short time. The old containers also answer to the names the proxy
uses, so they are removed before the new ones start, and the new web container starts only after the new API has
passed its first health check, which the image runs every 30 seconds. Expect `preview.oddvex.com` to be unavailable
for about a minute, and `api-preview.oddvex.com` until the new API container listens. If the release fails, add the
wait of up to 180 seconds and the time to start the previous images. This has not been timed on the server. Later
deploys replace one container at a time.

`api-preview.oddvex.com` has no password prompt because the mobile app signs in with its own token.

DNS: `A` records `preview` and `api-preview` → `179.236.240.236`.

## What a deploy does

1. Creates `/opt/oddvex/.env` with generated secrets on the first run. If `ODDVEX_CONTACT_EMAIL` is missing or empty
   it is set to `support@oddvex.com`; no other line is changed. The address is compiled into the contact page when the
   web image is built, so a change to it shows after a deploy, not before.
2. Writes the image tags that are running to `/opt/oddvex/release.previous`.
3. Refuses to build with less than about 2.5 GB of memory available.
4. Builds the two images, one after the other, in a separate build container (`oddvex-builder`) that is limited to
   2 GB of memory, one of the two CPUs, and a low CPU weight (128, against 1024 for other containers) when the server
   is busy. The script reads the limits back from Docker before it builds, and stops if they are not there or if the
   server does not use cgroup v2 with private cgroup namespaces (without those, build steps could run outside the
   build container's limits). A build that needs more than 2 GB is killed inside the build container and the deploy
   stops there. Up to this point the running containers have not been touched. Measured on 2026-11-19 outside
   Docker: the web build of commit 9a2a9bc on one CPU peaked at about 0.8 GB. Not yet seen: this build container on
   the server. No deploy has run with it, so that the limits hold a build step there is expected from how Docker
   and cgroup v2 work, not observed. The first deploy prints the limits Docker reports for the container.
5. Takes a dump of the database (`predeploy-<time>-<old release>-to-<new release>.dump` in `/opt/oddvex/backups`),
   checks that it is not empty and that `pg_restore` can read it, and stops if that fails. The newest five pre-deploy
   dumps are kept.
6. Applies migrations in a one-shot container (`alembic upgrade head`) while the old release keeps serving. If that
   fails, nothing is replaced.
7. Removes containers of the old service names, starts the new release and waits until Docker reports it healthy and
   the API health check and the web home page answer through the shared network. A removal that fails is reported
   and tried again after the start.
8. If the new release does not get there, it starts the previous images again and says so in capital letters. If a
   migration was applied in step 6 it also prints the name of the dump from step 5 and the three lines to send to
   restore it; if the revision could not be read after step 6 it says that instead and prints the same lines. The
   action ends with status 2.
9. If the new release answers but a container of an old service name could still not be removed, the action says
   `DEPLOY NOT COMPLETE`, names the container and ends with status 2. The new release stays: the previous one would
   run next to that container in the same way. Sending the deploy again tries the removal again.

A deploy refuses to start, before it builds, when `ODDVEX_ADMIN_EMAILS` lists an address and the commit has no
`services/api/scripts/bootstrap_admin.py` (see "The first administrator").

`ODDVEX_BUILD_LIMITS=off` builds without the ceiling of step 4 and says so. It is there in case the build container
cannot be started on the server; it is not the normal way.

## Going back

What is automatic:

- A deploy whose release does not become healthy puts the previous images back (step 8).
- The API container on this server never applies migrations when it starts (the compose file overrides the image's
  command), so an earlier image starts even when the database already holds a newer revision.
- Every deploy that finds a schema takes a dump first.

What is not automatic:

- **No migration is ever undone and no dump is ever restored by a deploy or a rollback.** After a failed deploy that
  applied a migration, the previous release runs on the newer schema. That works only while migrations are additive
  (new tables and columns). Restoring the dump is a decision, because it discards everything written after the dump
  was taken.
- A release that becomes healthy and turns out to be wrong later is not noticed by anything here.

`ACTION=rollback` with `REF=<earlier commit, tag or release>` starts that release again. It runs the `ops.sh` and
compose file of `OPS_REF` (default `main`), because the earlier commit's own files may not know the action. It uses
the images of that release if they are still on the server (`status` lists them) and builds nothing; otherwise it
builds that commit again under the same ceiling. It never applies or undoes a migration. If the database is newer
than the release, it starts the release all the same, says so, and prints the newest dump that was taken while that
release was running with the lines to restore it. If the database is older than the release needs, it refuses: use
`deploy`. If the rolled-back release does not become healthy, the release that was running is put back. A compose
file from `main` runs the earlier image, so a setting the earlier code needs must still be in that file.

`ACTION=deploy` with an earlier `REF` is not a way back. It runs that commit's own `ops.sh` and compose file, and its
migration step fails when the database is ahead of it. For a commit from before the services were renamed it would
be worse: that commit's script starts containers named `api` and `web` next to the running `oddvex-api` and
`oddvex-web` and removes nothing, so two releases would answer. The ops container therefore refuses to deploy such a
commit, before that commit's script runs, and prints `[boot] STOP`. Use `ACTION=rollback` with that `REF`. `OPS_REF`
must then name a commit that has the rollback action; `main` has it once this change is merged.

`ACTION=restore` with `DUMP=<file name>` and `CONFIRM=<the same file name>`:

1. Without a matching `CONFIRM` it prints the size and age of the dump and changes nothing. Without `DUMP` it lists
   the dumps.
2. It dumps the live database first (`prerestore-<time>.dump`). If that dump fails it says so and goes on: the live
   database is kept anyway (step 5), but then only inside the database server.
3. It loads the dump into a new database. If that fails, the live database and the containers are untouched.
4. It stops the API, worker, backup and web containers, swaps the two databases by renaming them, and starts the
   same containers again. This is a short outage.
5. The database that was replaced is not deleted. It stays in the database server as `oddvex_replaced_<time>`;
   `status` lists these. No action removes them.
6. If the restored revision differs from the one the running release was using, it says so: run `deploy` (it applies
   the migrations again) or `rollback` to the release that matches.
7. The same request sent a second time changes nothing. When the last restore recorded in `/opt/oddvex/ops.log`
   loaded the same dump, `CONFIRM` must be `<file name>:restore-<number>`; the action prints the value to send. The
   number goes up with every restore, so no value works twice.

A restore is undone by restoring the `prerestore-` dump it printed.

Rehearsed: the dump, restore and undo steps run in the tests against a real PostgreSQL 16 server
(`tests/test_restore_postgres.py`), with the same commands the script uses. Not rehearsed: any of this on the server
itself, against PostgreSQL 17 in the `db` container, or with Docker; the tests use a stand-in for the `docker`
command.

## Settings

`/opt/oddvex/.env` (mode 600) holds the two generated secrets and the settings in `.env.example`. `ACTION=setenv`
with `KEY` and `VALUE` sets one of these and nothing else:

| `KEY` | Value |
|---|---|
| `ODDVEX_CONTACT_EMAIL` | One email address. Shown on the contact page |
| `ODDVEX_ADMIN_EMAILS` | Comma-separated email addresses, or empty. See the next section |
| `ODDVEX_PASSWORD_HASH_CONCURRENCY` | 1 to 8. Password hashes computed at once; each holds about 64 MiB in the 768 MB API container |
| `ODDVEX_PASSWORD_HASH_WAIT_SECONDS` | 0 to 30, with at most two decimals. How long a sign-in waits for a free slot before it gets 429 |
| `ODDVEX_BACKUP_KEEP_DAYS` | 1 to 99. Days a daily dump is kept |

It refuses every other key, including the two secrets, and never prints another value from the file. The running
containers keep the old value until the next `deploy`.

## The first administrator

`ODDVEX_ADMIN_EMAILS` lists the addresses that may hold the administrator role. Listing an address gives nobody the
role by itself: the API gives it only to an account whose email address is verified, and takes it away when the
address leaves the list. In production nothing sends a verification email yet, and the API hostname is open to the
internet, so anyone can have registered any address first. The way to get an administrator is therefore:

1. `ACTION=setenv`, `KEY=ODDVEX_ADMIN_EMAILS`, `VALUE=<address>`.
2. `ACTION=deploy`, so the API runs with the new list.
3. `ACTION=admin`, `EMAIL=<address>`. It runs `python scripts/bootstrap_admin.py --email <address>` in the API
   container. The script creates the account for a listed address, or takes it over if it exists, sets a new random
   password and prints it once. Whoever registered that address earlier no longer has a password that works.
4. Sign in with the printed password and change it. The password is in the output of that ops run, which Docker
   keeps until the ops container is replaced by the next run or removed.

Do not list `support@oddvex.com` or any other address that is published. This repository is public and names that
address, so it is the first one a stranger would register. Use a personal address that only the administrator reads.
`setenv` prints a warning when the list holds the contact address.

The rule above and the script arrive in the API in the same change as this page. A release from before that change
has no `services/api/scripts/bootstrap_admin.py`, and its API gave the role to whoever used an account with a listed
address, verified or not. A deploy therefore refuses, before it builds, to deploy a commit without that file while
the list holds an address: deploy a commit that has it, or empty the list first. A rollback does not check this.

## Limits of this setup

- Running containers are capped at about 2.2 GB of memory in total (database 512 MB, API 768 MB, web 512 MB, worker
  256 MB, backup 128 MB). During a deploy the migration container may use up to 256 MB more and the build container
  up to 2 GB more. The caps keep OddVex from taking more than that; they do not reserve it.
- The build runs on the server. It is limited as described above, but it still takes one CPU and up to 2 GB for some
  minutes while the other sites are serving.
- A `backup` container writes one database dump a day to `/opt/oddvex/backups` and keeps 14 days. It deletes old
  dumps only after a new dump has been written and read back, so the directory is never emptied while dumps are
  failing. A failed dump is written to that container's log and tried again after an hour; `status` shows the last
  lines of that log and warns when the newest daily dump is more than 26 hours old. Nothing sends an alert. The dumps
  are on the same disk as the database, so they do not protect against losing the server.
- Images of earlier releases, the build container's cache and the dumps named `prerestore-` are never deleted by
  these scripts. They use disk, and nothing here watches how much.
- Every dump, and every database a restore keeps (`oddvex_replaced_<time>`), is a full copy of the database with
  the accounts as they were then. An account deleted later is still in those copies: for 14 days in a daily dump,
  until five newer deploys in a pre-deploy dump, and with no end date in a `prerestore-` dump or a kept database.
- `ACTION=admin` prints the new password into the output of the ops container, which Docker and the Hostinger panel
  keep until the next run replaces that container.
- A `worker` container evaluates alert rules and grades community picks every two minutes. Delivery is in-app only.
- The API container does not write uvicorn's access log. The application writes one line per request (time, method,
  path, status, duration, client address) and no query string. The API container that ran before this change did
  write uvicorn's access log, with query strings; the deploy that removes that container removes its log with it
  when Docker uses its default log driver, which has not been checked on this server. The shared Caddy keeps its own
  logs, which this project does not control. Container logs have no size limit or retention rule here.
- Email stays in the outbox table; nothing is sent.
- Going public (`oddvex.com` itself, no password) is a separate Founder decision.

## Taking the preview away

`ACTION=stop` stops OddVex and keeps its database volume and the dumps. To take the address away, remove the block
between the `# >>> oddvex preview` and `# <<< oddvex preview` markers from the shared Caddyfile (a backup of the file
from before the block was added is in `/opt/oddvex/`), reload Caddy, and delete the two DNS records. No action does
that part.

## Tests

`python3 -m unittest discover -s infrastructure/hostinger/tests -v` runs `ops.sh` against a temporary directory and a
stand-in for the `docker` command, runs the backup loop taken from `compose.yaml`, reads both compose files with
`docker compose config`, starts the API with the image's start command to read what it logs, and rehearses dump and
restore against a private PostgreSQL server. No Docker daemon is needed. A test whose tools are missing is skipped;
with `OPS_TESTS_REQUIRE_ALL=1` it fails instead. CI runs them that way in the job "Infrastructure (ops script,
compose files)", which also runs shellcheck on `ops.sh` when the runner has it.
