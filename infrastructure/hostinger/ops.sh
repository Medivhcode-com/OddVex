#!/bin/sh
# OddVex operations on the shared Hostinger VPS. Runs inside a one-shot `docker:cli` container
# that has the Docker socket, /opt/oddvex and the shared Caddy directory mounted (see README).
# Nobody has a shell on the server: every operation is an action here, prints what it did and
# what it found, and can be run twice (a second admin run sets another new password; a second
# restore of the same dump is refused).
#
#   ACTION=status    show containers, health, release, database revision, dumps and the names
#                    OddVex registers on the shared network (changes nothing)
#   ACTION=deploy    build the images from /opt/oddvex/repo under a memory and CPU ceiling, dump
#                    the database, apply migrations, replace the containers. If the new release
#                    does not become healthy, the previous images are started again
#   ACTION=rollback  run an earlier release again (REF). Never applies or undoes a migration
#   ACTION=restore   replace the database with a dump from /opt/oddvex/backups (DUMP). Does
#                    nothing unless CONFIRM holds the same file name, and nothing when the last
#                    restore already loaded that dump (it then prints the CONFIRM value to send)
#   ACTION=setenv    set one allow-listed, non-secret KEY to VALUE in /opt/oddvex/.env
#   ACTION=admin     set a new random password for the administrator address EMAIL and print it
#   ACTION=caddy     add the OddVex site blocks to the shared Caddy and reload it
#   ACTION=stop      stop the stack (keeps the database volume and the dumps)
#
# The shared Caddy serves every site on this server. The caddy action only ever appends one
# marked block, validates the whole file first, and restores the backup if the reload fails.
#
# Variables named ODDVEX_ROOT, ODDVEX_MEMINFO and ODDVEX_PROBE_* exist so the tests in tests/ can
# run this script against a temporary directory and a stub docker; the server never sets them.
# Of the other ODDVEX_ variables read below, only ODDVEX_BUILD_LIMITS reaches this script through
# ops.compose.yaml; the rest keep their defaults unless that file is changed to pass them.
set -eu
umask 077

ROOT=${ODDVEX_ROOT:-/opt/oddvex}
REPO=$ROOT/repo
ENV_FILE=$ROOT/.env
BACKUPS=$ROOT/backups
LOG_FILE=$ROOT/ops.log
HEALTHY_FILE=$ROOT/release.healthy
PREVIOUS_FILE=$ROOT/release.previous
COMPOSE_FILE=$REPO/infrastructure/hostinger/compose.yaml
PROJECT=oddvex
EDGE=${ODDVEX_EDGE_NETWORK:-medivh-automation_default}
CADDY=${ODDVEX_CADDY_CONTAINER:-medivh-automation-caddy-1}
CADDYFILE=${ODDVEX_CADDYFILE:-/opt/medivh/n8n/Caddyfile}
WEB_HOST=${ODDVEX_WEB_HOST:-preview.oddvex.com}
API_HOST=${ODDVEX_API_HOST:-api-preview.oddvex.com}
PROBE_IMAGE=${ODDVEX_PROBE_IMAGE:-curlimages/curl:8.21.0}
MEMINFO=${ODDVEX_MEMINFO:-/proc/meminfo}
MIN_FREE_KB=${ODDVEX_MIN_FREE_KB:-2500000}
# The build ceiling: memory in MB, CPU time per 100000 microseconds (100000 is one CPU) and the
# CPU weight against other containers when the server is busy (their default is 1024).
BUILD_LIMITS=${ODDVEX_BUILD_LIMITS:-on}
BUILDER=${ODDVEX_BUILDER:-oddvex-builder}
BUILD_MEMORY_MB=${ODDVEX_BUILD_MEMORY_MB:-2048}
BUILD_CPU_QUOTA=${ODDVEX_BUILD_CPU_QUOTA:-100000}
BUILD_CPU_SHARES=${ODDVEX_BUILD_CPU_SHARES:-128}
WAIT_TIMEOUT=${ODDVEX_WAIT_TIMEOUT:-180}
PROBE_TRIES=${ODDVEX_PROBE_TRIES:-10}
PROBE_WAIT=${ODDVEX_PROBE_WAIT:-3}
KEEP_PREDEPLOY=${ODDVEX_KEEP_PREDEPLOY:-5}
DEFAULT_CONTACT_EMAIL=${ODDVEX_DEFAULT_CONTACT_EMAIL:-support@oddvex.com}
# Keys the setenv action may write. All are non-secret and all are read by compose.yaml.
SETTABLE="ODDVEX_CONTACT_EMAIL ODDVEX_ADMIN_EMAILS ODDVEX_PASSWORD_HASH_CONCURRENCY ODDVEX_PASSWORD_HASH_WAIT_SECONDS ODDVEX_BACKUP_KEEP_DAYS"
MARK="# >>> oddvex preview (managed by infrastructure/hostinger/ops.sh)"

say() { echo "[oddvex] $*"; }
stop() { say "STOP: $*"; exit 2; }
rule() { say "=================================================================="; }
secret() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }
now() { date -u +%Y%m%dT%H%M%SZ; }
record() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG_FILE" || say "WARNING: could not write to $LOG_FILE"; }
compose() { docker compose -p "$PROJECT" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
probe() { docker run --rm --network "$EDGE" "$PROBE_IMAGE" -fsS -o /dev/null -w '%{http_code}' --max-time 10 "$1"; }

# ---------------------------------------------------------------------------------------------
# /opt/oddvex/.env
# ---------------------------------------------------------------------------------------------

env_has() { grep -q "^$1=" "$ENV_FILE"; }
env_get() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1; }

# Replaces or adds one line. Every other line is copied as it is and nothing is printed.
env_set() {
  { grep -v "^$1=" "$ENV_FILE" || true; printf '%s=%s\n' "$1" "$2"; } > "$ENV_FILE.new"
  mv "$ENV_FILE.new" "$ENV_FILE"
}

is_email() {
  case "$1" in
    *[!A-Za-z0-9@._+-]* | *@*@*) return 1 ;;
    ?*@?*.?*) return 0 ;;
    *) return 1 ;;
  esac
}

lower() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }

ensure_env() {
  if [ ! -f "$ENV_FILE" ]; then
    {
      echo "ODDVEX_DB_PASSWORD=$(secret 24)"
      echo "ODDVEX_JWT_SECRET=$(secret 32)"
      echo "ODDVEX_PUBLIC_URL=https://$WEB_HOST"
      echo "ODDVEX_CONTACT_EMAIL=$DEFAULT_CONTACT_EMAIL"
      echo "ODDVEX_ADMIN_EMAILS="
    } > "$ENV_FILE"
    say "created $ENV_FILE with generated secrets (not printed)"
  fi
  # The contact page is compiled with this address (a build argument of the web image). An
  # empty value is what the first deploy wrote before the mailbox existed, so it counts as unset.
  if [ -z "$(env_get ODDVEX_CONTACT_EMAIL)" ]; then
    env_set ODDVEX_CONTACT_EMAIL "$DEFAULT_CONTACT_EMAIL"
    say "ODDVEX_CONTACT_EMAIL was missing or empty in $ENV_FILE: set to $DEFAULT_CONTACT_EMAIL. No other line was changed."
  fi
  say "the contact page of this build will show: $(env_get ODDVEX_CONTACT_EMAIL)"
}

setenv() {
  [ -f "$ENV_FILE" ] || stop "there is no $ENV_FILE yet; the first ACTION=deploy creates it"
  key=${KEY:-}
  value=${VALUE-}
  [ -n "$key" ] || stop "setenv needs KEY and VALUE. Keys that can be set: $SETTABLE"
  # KEY must be one whole name of the list. A space or a line break in it would otherwise be
  # written into the file, and Compose refuses a file with such a line.
  allowed=no
  case "$key" in
    *[!A-Z0-9_]*) ;;
    *)
      for name in $SETTABLE; do
        if [ "$key" = "$name" ]; then allowed=yes; fi
      done ;;
  esac
  [ "$allowed" = "yes" ] || stop "that KEY cannot be set with this action; nothing was changed. Keys that can be set: $SETTABLE. Secrets are never set or shown here."
  case "$value" in
    *[!A-Za-z0-9@._,+-]*) stop "VALUE holds a character that is not allowed (letters, digits and @ . _ , + - only); nothing was changed" ;;
  esac
  case "$key" in
    ODDVEX_CONTACT_EMAIL)
      is_email "$value" || stop "VALUE must be one email address; nothing was changed" ;;
    ODDVEX_ADMIN_EMAILS)
      old_ifs=$IFS
      IFS=,
      for address in $value; do
        IFS=$old_ifs
        is_email "$address" || stop "'$address' is not an email address (use a comma-separated list, or an empty VALUE for no administrator); nothing was changed"
        if [ "$(lower "$address")" = "$(lower "$(env_get ODDVEX_CONTACT_EMAIL)")" ] || [ "$(lower "$address")" = "$(lower "$DEFAULT_CONTACT_EMAIL")" ]; then
          say "WARNING: $address is the public contact address. It is printed on the site and in this public repository, so it is the first address a stranger would try. Use a personal address that only the administrator reads."
        fi
      done
      IFS=$old_ifs ;;
    ODDVEX_PASSWORD_HASH_CONCURRENCY)
      case "$value" in
        [1-8]) ;;
        *) stop "VALUE must be a whole number from 1 to 8 (each slot holds about 64 MiB and the API container is limited to 768 MB); nothing was changed" ;;
      esac ;;
    ODDVEX_PASSWORD_HASH_WAIT_SECONDS)
      case "$value" in
        [0-9] | [12][0-9] | 30 | 30.0 | 30.00) ;;
        [0-9].[0-9] | [0-9].[0-9][0-9] | [12][0-9].[0-9] | [12][0-9].[0-9][0-9]) ;;
        *) stop "VALUE must be a number of seconds from 0 to 30 with at most two decimals, such as 1.0; nothing was changed" ;;
      esac ;;
    ODDVEX_BACKUP_KEEP_DAYS)
      case "$value" in
        [1-9] | [1-9][0-9]) ;;
        *) stop "VALUE must be a whole number of days from 1 to 99; nothing was changed" ;;
      esac ;;
  esac
  if env_has "$key" && [ "$(env_get "$key")" = "$value" ]; then
    say "$key is already '$value' in $ENV_FILE; nothing was changed"
  else
    old=$(env_get "$key")
    env_set "$key" "$value"
    record "setenv $key"
    say "$key: '$old' -> '$value' in $ENV_FILE. No other line was changed."
  fi
  if [ "$key" = "ODDVEX_ADMIN_EMAILS" ]; then
    say "Listing an address gives nobody the administrator role by itself. The role goes only to an account whose address is verified."
    say "After the deploy, run ACTION=admin with EMAIL set to the address: it sets a new password for it and prints it once."
  fi
  say "The running containers still use the old value. A deploy is needed for the change to take effect: ACTION=deploy with REF set to the release to run."
}

admin() {
  [ -f "$ENV_FILE" ] || stop "there is no $ENV_FILE: nothing is deployed here"
  email=${EMAIL:-}
  [ -n "$email" ] || stop "admin needs EMAIL: an address that is listed in ODDVEX_ADMIN_EMAILS"
  is_email "$email" || stop "EMAIL is not an email address"
  case ",$(lower "$(env_get ODDVEX_ADMIN_EMAILS)" | tr -d ' ')," in
    *",$(lower "$email"),"*) ;;
    *) stop "$email is not listed in ODDVEX_ADMIN_EMAILS in $ENV_FILE. Add it with ACTION=setenv (KEY=ODDVEX_ADMIN_EMAILS), deploy, then run this again. Nothing was changed." ;;
  esac
  say "running scripts/bootstrap_admin.py --email $email in the API container. Its output follows."
  if compose exec -T oddvex-api python scripts/bootstrap_admin.py --email "$email" < /dev/null; then
    record "admin $email"
    say "Done. The password above is not shown again. It stays in the output of this run until the ops container is replaced by the next run or removed."
    say "Sign in with it and change it. Any password set for $email before this run no longer works."
  else
    code=$?
    say "The script failed with status $code; see its output above."
    say "If it says the address is not listed: the running API was started before ODDVEX_ADMIN_EMAILS was changed, so deploy first."
    say "If the file is missing: the running release is older than the script, so deploy a release that has it."
    exit 2
  fi
}

# ---------------------------------------------------------------------------------------------
# What is running
# ---------------------------------------------------------------------------------------------

# Containers of this project for one compose service, running or not. Matching is by the labels
# Compose writes, so a container of another project on this server can never be listed.
service_containers() {
  docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$1"
}

running_containers() {
  docker ps -q --filter "label=com.docker.compose.project=$PROJECT" --filter "label=com.docker.compose.service=$1"
}

# The image tag of the first container found for the given service names (new name first).
image_tag_of() {
  for service in "$@"; do
    id=$(service_containers "$service" | head -n 1)
    [ -n "$id" ] || continue
    image=$(docker inspect --format '{{.Config.Image}}' "$id" 2>/dev/null || true)
    case "$image" in
      *:*) echo "${image##*:}"; return 0 ;;
    esac
  done
  return 0
}

images_exist() {
  docker image inspect "oddvex-api:$1" > /dev/null 2>&1 && docker image inspect "oddvex-web:$1" > /dev/null 2>&1
}

# Records the image tags that are running before anything is replaced, and works out which
# release can be started again if the new one fails: the one that is running, or else the last
# one a deploy saw healthy.
note_running() {
  RUN_API=$(image_tag_of oddvex-api api)
  RUN_WEB=$(image_tag_of oddvex-web web)
  PREV=""
  if [ -n "$RUN_API" ] && [ "$RUN_API" = "$RUN_WEB" ]; then
    PREV=$RUN_API
  elif [ -f "$HEALTHY_FILE" ]; then
    PREV=$(cat "$HEALTHY_FILE")
  fi
  {
    echo "recorded=$(now)"
    echo "api=oddvex-api:${RUN_API:-none}"
    echo "web=oddvex-web:${RUN_WEB:-none}"
    echo "put_back=${PREV:-none}"
  } > "$PREVIOUS_FILE"
  say "running before this change: oddvex-api:${RUN_API:-none} and oddvex-web:${RUN_WEB:-none} (written to $PREVIOUS_FILE)"
}

# Before the services were renamed they were called `api` and `web`, and those two generic names
# were registered on the shared network. Their containers are removed by label. A removal that
# fails is said and does not end the script: the start that follows removes orphans too, and the
# removal is tried once more after it.
remove_legacy() {
  for service in api web; do
    for id in $(service_containers "$service"); do
      if docker rm -f "$id" > /dev/null 2>&1; then
        say "removed container $id of the old service name '$service'"
      else
        say "WARNING: container $id of the old service name '$service' could not be removed; it is tried again below"
      fi
    done
  done
}

# True when no container of an old service name is left. Otherwise says which ones are.
legacy_gone() {
  left=$(for service in api web; do service_containers "$service" || true; done | tr '\n' ' ')
  left=${left% }
  [ -n "$left" ] || return 0
  say "A CONTAINER OF AN OLD SERVICE NAME IS STILL THERE: $left"
  say "While it runs it answers on the shared network next to the new containers: to 'api' or 'web', and to the name the proxy uses, so requests can reach either."
  say "ACTION=deploy tries the removal again. ACTION=status shows the names registered on the shared network."
  return 1
}

answering() {
  tries=0
  api=none
  web=none
  while [ "$tries" -lt "$PROBE_TRIES" ]; do
    api=$(probe http://oddvex-api:8000/health 2> /dev/null || true)
    web=$(probe http://oddvex-web:3000/ 2> /dev/null || true)
    case "$api/$web" in
      200/[23][0-9][0-9]) return 0 ;;
    esac
    tries=$((tries + 1))
    sleep "$PROBE_WAIT"
  done
  say "after $PROBE_TRIES tries the API health check answered '${api:-nothing}' and the web home page '${web:-nothing}'"
  return 1
}

# Starts the stack on one release from images that already exist. Never builds.
start_release() {
  ODDVEX_RELEASE=$1
  export ODDVEX_RELEASE
  compose up -d --no-build --remove-orphans --wait --wait-timeout "$WAIT_TIMEOUT" || return 1
  answering
}

# ---------------------------------------------------------------------------------------------
# Database: revision, dumps
# ---------------------------------------------------------------------------------------------

db_psql() { compose exec -T db psql -U oddvex -d "$1" -v ON_ERROR_STOP=1 -qAtc "$2" < /dev/null; }

# Prints the Alembic revision of a database, "none" when it has no migration table (no migration
# has run in it), or "unstamped" when the table is there without a revision. Fails when the
# database cannot be asked.
db_revision() {
  has=$(db_psql "$1" "SELECT to_regclass('public.alembic_version') IS NOT NULL") || return 1
  if [ "$has" != "t" ]; then
    echo none
    return 0
  fi
  revision=$(db_psql "$1" "SELECT version_num FROM alembic_version LIMIT 1") || return 1
  echo "${revision:-unstamped}"
}

file_size() { stat -c %s "$1"; }
file_age() {
  seconds=$(($(date -u +%s) - $(stat -c %Y "$1")))
  if [ "$seconds" -lt 7200 ]; then
    echo "$((seconds / 60)) min"
  elif [ "$seconds" -lt 172800 ]; then
    echo "$((seconds / 3600)) h"
  else
    echo "$((seconds / 86400)) d"
  fi
}

# The newest file in the backups directory whose name matches one glob pattern.
newest() {
  # shellcheck disable=SC2012,SC2086
  ls -t "$BACKUPS"/$1 2> /dev/null | head -n 1
}

# Writes one custom-format dump of the live database to the backups directory. The file gets
# its name only after pg_dump succeeded, it is not empty and pg_restore can read its contents.
take_dump() {
  mkdir -p "$BACKUPS"
  part=$BACKUPS/$1.part
  if ! compose exec -T db pg_dump -U oddvex -Fc oddvex < /dev/null > "$part"; then
    rm -f "$part"
    return 1
  fi
  if [ ! -s "$part" ] || ! compose exec -T db pg_restore -l < "$part" > /dev/null 2>&1; then
    rm -f "$part"
    return 1
  fi
  mv "$part" "$BACKUPS/$1"
}

# Keeps the newest pre-deploy dumps. Called only after a new one has been written.
prune_predeploy() {
  # shellcheck disable=SC2012
  ls -t "$BACKUPS"/predeploy-*.dump 2> /dev/null | tail -n "+$((KEEP_PREDEPLOY + 1))" | while read -r old; do
    rm -f "$old"
    say "removed old pre-deploy dump $(basename "$old") (the newest $KEEP_PREDEPLOY are kept)"
  done
}

restore_lines() {
  say "To put the database back as it was in that dump, run the ops container with:"
  say "    ACTION=restore"
  say "    DUMP=$1"
  say "    CONFIRM=$1"
  say "That replaces the whole database: everything written after the dump was taken is no longer in the live database."
}

# ---------------------------------------------------------------------------------------------
# Building
# ---------------------------------------------------------------------------------------------

builder_container() { docker ps -aq --filter "name=buildx_buildkit_$BUILDER" | head -n 1; }

# memory-swap equal to memory means no swap on top. default-load puts finished images into
# Docker's image store, where `compose up` and the worker look for them.
builder_create() {
  docker buildx create --name "$BUILDER" --driver docker-container \
    --driver-opt "memory=${BUILD_MEMORY_MB}m" --driver-opt "memory-swap=${BUILD_MEMORY_MB}m" \
    --driver-opt "cpu-period=100000" --driver-opt "cpu-quota=$BUILD_CPU_QUOTA" \
    --driver-opt "cpu-shares=$BUILD_CPU_SHARES" --driver-opt "default-load=true" > /dev/null
}

# True when the builder container exists and Docker reports the wanted ceiling on it.
builder_limited() {
  id=$(builder_container)
  [ -n "$id" ] || return 1
  actual=$(docker inspect --format '{{.HostConfig.Memory}} {{.HostConfig.CpuQuota}} {{.HostConfig.CpuShares}}' "$id" 2> /dev/null) || return 1
  [ "$actual" = "$((BUILD_MEMORY_MB * 1048576)) $BUILD_CPU_QUOTA $BUILD_CPU_SHARES" ]
}

# `nice` on the docker command lowers only the client: the build steps run under the Docker
# daemon. So the images are built in a separate BuildKit container that carries a memory limit,
# a CPU limit and a low CPU weight. With cgroup v2 and Docker's private cgroup namespaces (its
# default there) every build step is a child of that container's control group and cannot use
# more than the container may. Both are checked first.
ensure_builder() {
  engine=$(docker info --format '{{.CgroupVersion}} {{.SecurityOptions}}' 2> /dev/null || true)
  cgroup=${engine%% *}
  [ "$cgroup" = "2" ] || stop "the server reports cgroup version '${cgroup:-unknown}', not 2, so the build ceiling could not be relied on. Nothing was changed. (ODDVEX_BUILD_LIMITS=off builds without a ceiling.)"
  case "$engine" in
    *cgroupns*) ;;
    *) stop "Docker on this server does not give containers their own cgroup namespace, so build steps could run outside the build container's ceiling. Nothing was changed. (ODDVEX_BUILD_LIMITS=off builds without a ceiling.)" ;;
  esac
  if ! docker buildx inspect "$BUILDER" > /dev/null 2>&1; then
    builder_create || stop "could not create the build container $BUILDER; nothing was changed"
  fi
  docker buildx inspect --bootstrap "$BUILDER" > /dev/null 2>&1 || stop "could not start the build container $BUILDER; nothing was changed"
  if ! builder_limited; then
    say "the build container does not carry the wanted ceiling (it was made with other settings); making it again"
    docker buildx rm -f "$BUILDER" > /dev/null 2>&1 || true
    id=$(builder_container)
    if [ -n "$id" ]; then docker rm -f "$id" > /dev/null; fi
    builder_create || stop "could not create the build container $BUILDER; nothing was changed"
    docker buildx inspect --bootstrap "$BUILDER" > /dev/null 2>&1 || stop "could not start the build container $BUILDER; nothing was changed"
    builder_limited || stop "the build container does not carry the memory and CPU ceiling after it was made again. Nothing was changed. (ODDVEX_BUILD_LIMITS=off builds without a ceiling.)"
  fi
  say "build container $BUILDER: at most ${BUILD_MEMORY_MB} MB of memory, CPU quota $BUILD_CPU_QUOTA per 100000 (100000 is one CPU), CPU weight $BUILD_CPU_SHARES against 1024 for other containers; confirmed with docker inspect"
}

# The build container is only needed while a build runs.
builder_stop() {
  if [ "$BUILD_LIMITS" != "off" ]; then
    docker buildx stop "$BUILDER" > /dev/null 2>&1 || true
  fi
}

# Builds both images for the release in ODDVEX_RELEASE, one at a time. Stops the script, with
# nothing replaced, if memory is short, the build fails or an image is missing afterwards.
build_images() {
  free=$(awk '/MemAvailable/ {print $2}' "$MEMINFO")
  [ "$free" -ge "$MIN_FREE_KB" ] || stop "only ${free} kB memory available; the build needs ${MIN_FREE_KB} kB. Nothing was changed."
  if [ "$BUILD_LIMITS" = "off" ]; then
    say "WARNING: ODDVEX_BUILD_LIMITS=off: this build has NO memory or CPU ceiling and can slow the other sites on this server"
    set -- build
  else
    ensure_builder
    set -- build --builder "$BUILDER"
  fi
  for service in oddvex-api oddvex-web; do
    say "building $service for release $ODDVEX_RELEASE"
    if ! compose "$@" "$service"; then
      builder_stop
      stop "the build of $service failed (a build that needs more than the ceiling is killed inside the build container). The running containers were not touched."
    fi
  done
  builder_stop
  for image in "oddvex-api:$ODDVEX_RELEASE" "oddvex-web:$ODDVEX_RELEASE"; do
    docker image inspect "$image" > /dev/null 2>&1 || stop "the build finished but image $image is not in Docker's image store. The running containers were not touched."
  done
}

# ---------------------------------------------------------------------------------------------
# deploy, rollback
# ---------------------------------------------------------------------------------------------

# $1 the release that failed, $2 what was being done. Starts the previous images again when
# there are any, and says which of the two outcomes happened.
put_back() {
  compose logs --tail 40 oddvex-api oddvex-web || true
  rule
  say "$2 FAILED: release $1 did not become healthy."
  if [ -z "$PREV" ]; then
    say "NOTHING WAS PUT BACK: no earlier release was running and none is recorded in $HEALTHY_FILE."
    say "The containers of release $1 are left as they are. ACTION=stop stops them."
  elif [ "$PREV" = "$1" ]; then
    say "NOTHING WAS PUT BACK: the release that ran before has the same tag ($PREV), so its images are the ones that just failed."
  elif ! images_exist "$PREV"; then
    say "NOTHING WAS PUT BACK: the images of the previous release $PREV are no longer on this server."
    say "Run ACTION=rollback with REF set to a good commit; it builds the images again."
  elif start_release "$PREV"; then
    echo "$PREV" > "$HEALTHY_FILE"
    say "THE PREVIOUS RELEASE $PREV WAS PUT BACK and answers. Release $1 is not running."
    remove_legacy
    legacy_gone || true
  else
    say "PUTTING BACK RELEASE $PREV FAILED TOO. OddVex is not answering. State of the containers:"
    compose ps --all --format 'table {{.Service}}\t{{.State}}\t{{.Status}}' || true
  fi
}

deploy() {
  [ -f "$COMPOSE_FILE" ] || stop "no repository at $REPO"
  docker network inspect "$EDGE" > /dev/null 2>&1 || stop "network $EDGE not found"
  ensure_env
  new=$(git -C "$REPO" rev-parse --short HEAD)
  # The administrator rule (verified accounts only) and scripts/bootstrap_admin.py arrive in the
  # API in the same change. A commit without the script has the earlier rule, which gave the role
  # to whoever used an account with a listed address.
  if [ -n "$(env_get ODDVEX_ADMIN_EMAILS)" ] && [ ! -f "$REPO/services/api/scripts/bootstrap_admin.py" ]; then
    stop "ODDVEX_ADMIN_EMAILS lists an address, but this commit has no services/api/scripts/bootstrap_admin.py: it is from before the administrator rule changed, and its API gives the role to whoever uses an account with a listed address. Nothing was changed. Deploy a commit that has the script, or empty the list first (ACTION=setenv with KEY=ODDVEX_ADMIN_EMAILS and an empty VALUE)."
  fi
  note_running
  ODDVEX_RELEASE=$new
  export ODDVEX_RELEASE
  say "deploying release $new: build, dump the database, apply migrations, replace the containers"
  build_images

  compose up -d --wait --wait-timeout "$WAIT_TIMEOUT" db || stop "the database container did not start. The other containers were not touched."
  before=$(db_revision oddvex) || stop "could not read the database revision. Migrations were not run and no container was replaced."
  dump=""
  if [ "$before" = "none" ]; then
    say "the database has no migration table yet (first deploy), so there is nothing to dump"
  else
    dump=predeploy-$(now)-${PREV:-none}-to-$new.dump
    take_dump "$dump" || stop "the pre-deploy dump failed. Migrations were not run and no container was replaced."
    say "pre-deploy dump written: $BACKUPS/$dump ($(file_size "$BACKUPS/$dump") bytes), database revision $before"
    prune_predeploy
  fi

  say "applying migrations (alembic upgrade head) in a one-shot container; the running release keeps serving"
  migrated=yes
  compose run --rm -T migrate < /dev/null || migrated=no
  after=$(db_revision oddvex) || after=unknown
  if [ "$migrated" = "no" ]; then
    record "deploy release=$new previous=${PREV:-none} revision=$before->$after dump=${dump:-none} result=migration-failed"
    rule
    say "DEPLOY FAILED: the migration step failed. No container was replaced: release ${PREV:-none} is still the one running."
    if [ "$after" = "unknown" ]; then
      say "The database revision could not be read after the failure; it was $before before."
      if [ -n "$dump" ]; then restore_lines "$dump"; fi
    elif [ "$after" != "$before" ] && [ -n "$dump" ]; then
      say "THE DATABASE REVISION CHANGED from $before to $after before the failure."
      restore_lines "$dump"
    else
      say "The database revision is still $before."
    fi
    say "If release $new is an earlier one and the database is already ahead of it, a deploy cannot start it: use ACTION=rollback with the same REF, which starts a release without applying migrations."
    rule
    exit 2
  fi
  if [ "$after" = "unknown" ]; then
    say "WARNING: the database revision could not be read after the migration step, so it is not known whether a migration was applied; it was $before before"
  elif [ "$after" = "$before" ]; then
    say "no migration was pending: the database stays at revision $after"
  else
    say "MIGRATION APPLIED: the database went from revision $before to $after"
  fi

  remove_legacy
  if start_release "$new"; then
    echo "$new" > "$HEALTHY_FILE"
    remove_legacy
    if legacy_gone; then
      record "deploy release=$new previous=${PREV:-none} revision=$before->$after dump=${dump:-none} result=ok"
      say "release $new is running and answers"
      status
      return 0
    fi
    record "deploy release=$new previous=${PREV:-none} revision=$before->$after dump=${dump:-none} result=old-container-left"
    rule
    say "DEPLOY NOT COMPLETE: Release $new is running and answers, but the container of an old service name named above could not be removed."
    say "Nothing was put back, because the previous release would run next to that container in the same way."
    rule
    exit 2
  fi

  put_back "$new" DEPLOY
  if [ "$after" = "unknown" ]; then
    say "IT IS NOT KNOWN WHETHER THIS DEPLOY APPLIED A MIGRATION: the database revision could not be read after the migration step; it was $before before. ACTION=status shows it once the database answers."
    say "An older release runs on a newer schema only while migrations are additive (new tables and columns only)."
    if [ -n "$dump" ]; then restore_lines "$dump"; fi
  elif [ "$after" != "$before" ]; then
    say "A MIGRATION WAS APPLIED BY THIS DEPLOY AND WAS NOT UNDONE: the database is at revision $after, it was at $before."
    say "An older release runs on the newer schema only while migrations are additive (new tables and columns only)."
    if [ -n "$dump" ]; then restore_lines "$dump"; fi
  else
    say "No migration was applied by this deploy: the database is at revision $before, as before."
  fi
  rule
  record "deploy release=$new previous=${PREV:-none} revision=$before->$after dump=${dump:-none} result=failed"
  exit 2
}

# Prints the revisions the migrations inside one release's image know, newest first.
known_revisions() {
  ODDVEX_RELEASE=$1
  export ODDVEX_RELEASE
  compose run --rm -T migrate alembic history < /dev/null 2> /dev/null | sed -n 's/^[^ ]* -> \([^ ,]*\).*$/\1/p'
}

rollback() {
  [ -f "$COMPOSE_FILE" ] || stop "no repository at $REPO"
  [ -f "$ENV_FILE" ] || stop "there is no $ENV_FILE: nothing is deployed here"
  docker network inspect "$EDGE" > /dev/null 2>&1 || stop "network $EDGE not found"
  ref=${REF:-}
  case "$ref" in
    "" | -* | *[!A-Za-z0-9._/-]*) stop "rollback needs REF: the commit, tag or release to return to. Nothing was changed." ;;
  esac

  # REF may be a release tag that status lists, or a git ref of a commit that was deployed.
  if images_exist "$ref"; then
    target=$ref
    commit=""
  else
    if git -C "$REPO" fetch -q origin "$ref" 2> /dev/null; then
      commit=$(git -C "$REPO" rev-parse --verify -q "FETCH_HEAD^{commit}") || commit=""
    else
      commit=$(git -C "$REPO" rev-parse --verify -q "$ref^{commit}" 2> /dev/null) || commit=""
    fi
    [ -n "$commit" ] || stop "REF '$ref' is neither a release with images on this server nor a commit in the repository. Nothing was changed."
    target=""
    for tag in $(docker image ls --format '{{.Tag}}' oddvex-api 2> /dev/null); do
      case "$commit" in
        "$tag"*) target=$tag ;;
      esac
    done
    [ -n "$target" ] || target=$(git -C "$REPO" rev-parse --short "$commit")
  fi

  note_running
  if [ "$RUN_API" = "$target" ] && [ "$RUN_WEB" = "$target" ] && answering; then
    say "release $target is already running and answers; nothing was changed"
    return 0
  fi
  say "rolling back to release $target. Migrations are neither applied nor undone."

  ODDVEX_RELEASE=$target
  export ODDVEX_RELEASE
  if images_exist "$target"; then
    say "the images of release $target are on this server; nothing is built"
  else
    [ -n "$commit" ] || stop "the images of release $target are not on this server and REF is not a commit to build them from"
    say "the images of release $target are not on this server; building them from commit $commit"
    source_dir=$ROOT/rollback-source
    rm -rf "$source_dir"
    mkdir -p "$source_dir"
    # Removed again however the script ends, also when the build stops it.
    trap 'rm -rf "$source_dir"' EXIT
    git -C "$REPO" archive "$commit" | tar -x -f - -C "$source_dir" || true
    [ -f "$source_dir/services/api/Dockerfile" ] || stop "could not export commit $commit from the repository. Nothing was changed."
    ODDVEX_BUILD_ROOT=$source_dir
    export ODDVEX_BUILD_ROOT
    build_images
    rm -rf "$source_dir"
  fi

  compose up -d --wait --wait-timeout "$WAIT_TIMEOUT" db || stop "the database container did not start. The other containers were not touched."
  current=$(db_revision oddvex) || stop "could not read the database revision. No container was replaced."
  known=$(known_revisions "$target" || true)
  newest_known=$(printf '%s\n' "$known" | head -n 1)
  ahead=no
  if [ -z "$newest_known" ]; then
    say "WARNING: could not read which migrations release $target knows; the database is at revision $current"
  elif [ "$current" = "$newest_known" ]; then
    say "the database is at revision $current, the newest one release $target knows"
  elif printf '%s\n' "$known" | grep -qxF "$current" || [ "$current" = "none" ] || [ "$current" = "unstamped" ]; then
    stop "the database is at revision $current but release $target needs $newest_known. A rollback never applies migrations: use ACTION=deploy for that release. No container was replaced."
  else
    ahead=yes
  fi

  remove_legacy
  if start_release "$target"; then
    echo "$target" > "$HEALTHY_FILE"
    remove_legacy
    if ! legacy_gone; then
      record "rollback release=$target previous=${PREV:-none} revision=$current result=old-container-left"
      rule
      say "ROLLBACK NOT COMPLETE: Release $target is running and answers, but the container of an old service name named above could not be removed."
      say "Nothing was put back, because the release that ran before would run next to that container in the same way."
      rule
      exit 2
    fi
    record "rollback release=$target previous=${PREV:-none} revision=$current result=ok"
    say "release $target is running and answers"
  else
    put_back "$target" ROLLBACK
    rule
    record "rollback release=$target previous=${PREV:-none} revision=$current result=failed"
    exit 2
  fi

  if [ "$ahead" = "yes" ]; then
    rule
    say "THE DATABASE IS NEWER THAN THIS RELEASE: it is at revision $current; the newest migration release $target knows is $newest_known."
    say "Nothing was undone in the database. Release $target runs on the newer schema only while the migrations after $newest_known are additive (new tables and columns only)."
    suggestion=$(newest "predeploy-*-$target-to-*.dump")
    if [ -n "$suggestion" ]; then
      say "The newest dump taken while release $target was running is $(basename "$suggestion") ($(file_size "$suggestion") bytes, written $(file_age "$suggestion") ago)."
      restore_lines "$(basename "$suggestion")"
    else
      say "No pre-deploy dump taken while release $target was running is in $BACKUPS. ACTION=restore without DUMP lists the dumps that exist."
    fi
    rule
  fi
  status
}

# ---------------------------------------------------------------------------------------------
# restore
# ---------------------------------------------------------------------------------------------

list_dumps() {
  # shellcheck disable=SC2012
  ls -t "$BACKUPS"/*.dump 2> /dev/null | head -n 20 | while read -r path; do
    say "    $(basename "$path")  $(file_size "$path") bytes  written $(file_age "$path") ago"
  done
}

restore() {
  [ -f "$COMPOSE_FILE" ] || stop "no repository at $REPO"
  [ -f "$ENV_FILE" ] || stop "there is no $ENV_FILE: nothing is deployed here"
  dump=${DUMP:-}
  if [ -z "$dump" ]; then
    say "dumps in $BACKUPS, newest first:"
    list_dumps
    stop "restore needs DUMP (one of the file names above) and CONFIRM (the same file name). Nothing was changed."
  fi
  case "$dump" in
    */* | .* | *[!A-Za-z0-9._-]*) stop "DUMP must be the name of a file in $BACKUPS, without a path. Nothing was changed." ;;
  esac
  file=$BACKUPS/$dump
  [ -s "$file" ] || stop "there is no dump named $dump in $BACKUPS, or it is empty. Nothing was changed."
  say "dump $dump: $(file_size "$file") bytes, written $(file_age "$file") ago"
  # The ops project can be started again with the environment it was last sent. A restore that
  # is sent twice must not swap the database twice, so when the last restore recorded in the log
  # loaded this same dump, CONFIRM has to carry the number of the restore as well. That number
  # changes with every restore, so no value works a second time.
  wanted=$dump
  done_before=$(grep -c ' restore dump=.* result=ok$' "$LOG_FILE" 2> /dev/null || true)
  last=$(grep ' restore dump=.* result=ok$' "$LOG_FILE" 2> /dev/null | tail -n 1 || true)
  case "$last" in
    *" restore dump=$dump "*)
      wanted=$dump:restore-$((done_before + 1))
      if [ "${CONFIRM:-}" != "$wanted" ]; then
        say "$dump is the dump the last restore on this server loaded (${last%% *}). Loading it again would discard everything written since then from the live database."
        stop "nothing was changed. If this is the same request sent twice, that is the end of it. To load the same dump once more on purpose, run it again with CONFIRM=$wanted"
      fi ;;
  esac
  if [ "${CONFIRM:-}" != "$wanted" ]; then
    say "This action REPLACES the whole OddVex database with that dump. Accounts, bets and everything else written after the dump was taken would no longer be in the live database."
    stop "not confirmed, so nothing was changed. To go ahead, run it again with CONFIRM=$dump"
  fi

  compose up -d --wait --wait-timeout "$WAIT_TIMEOUT" db || stop "the database container did not start. Nothing was changed."
  compose exec -T db pg_restore -l < "$file" > /dev/null 2>&1 || stop "pg_restore cannot read $dump. Nothing was changed."
  current=$(db_revision oddvex) || stop "could not read the live database. Nothing was changed."

  safety=prerestore-$(now).dump
  if take_dump "$safety"; then
    say "the live database as it is now was dumped first: $BACKUPS/$safety ($(file_size "$BACKUPS/$safety") bytes, revision $current)"
  else
    safety=""
    say "WARNING: the live database could not be dumped first. It is still kept inside the database server under a new name (see below)."
  fi

  # The dump is loaded into a new database. The live one is untouched until that has worked.
  db_psql postgres "DROP DATABASE IF EXISTS oddvex_restore" || stop "could not prepare the database server. Nothing was changed."
  db_psql postgres "CREATE DATABASE oddvex_restore OWNER oddvex" || stop "could not create a database to load the dump into. Nothing was changed."
  if ! compose exec -T db pg_restore -U oddvex -d oddvex_restore --no-owner --exit-on-error < "$file"; then
    db_psql postgres "DROP DATABASE IF EXISTS oddvex_restore" || true
    stop "the dump did not load cleanly. The live database was not touched."
  fi
  restored=$(db_revision oddvex_restore) || restored=unknown
  say "the dump loaded cleanly into a new database (revision $restored)"

  # Swap the two names. Nothing may be connected while a database is renamed, so the containers
  # that use the database are stopped for the swap and the same containers are started again.
  release=$(image_tag_of oddvex-api api)
  paused=""
  for service in oddvex-api api worker backup oddvex-web web; do
    for id in $(running_containers "$service"); do
      docker stop "$id" > /dev/null || true
      paused="$paused $id"
    done
  done
  [ -z "$paused" ] || say "stopped the API, worker, backup and web containers for the swap"
  kept=oddvex_replaced_$(date -u +%Y%m%d_%H%M%S)
  db_psql postgres "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('oddvex', 'oddvex_restore') AND pid <> pg_backend_pid()" > /dev/null || true
  swapped=yes
  compose exec -T db psql -U oddvex -d postgres -v ON_ERROR_STOP=1 -q -1 \
    -c "ALTER DATABASE oddvex RENAME TO $kept" -c "ALTER DATABASE oddvex_restore RENAME TO oddvex" < /dev/null || swapped=no

  started=yes
  if [ -n "$paused" ]; then
    for id in $paused; do docker start "$id" > /dev/null || started=no; done
    if [ "$started" = "yes" ]; then answering || started=no; fi
  fi

  rule
  if [ "$swapped" = "no" ]; then
    record "restore dump=$dump result=not-swapped"
    say "RESTORE FAILED: the databases could not be swapped. The live database is unchanged; the loaded copy is left in the server as oddvex_restore and is replaced by the next restore."
    if [ -n "$paused" ]; then say "The containers that were stopped were started again (answering: $started)."; fi
    rule
    exit 2
  fi
  record "restore dump=$dump revision=$current->$restored kept=$kept safety=${safety:-none} result=ok"
  say "RESTORED: the live database is now the content of $dump (revision $restored; it was at $current)."
  say "The database it replaced was not deleted: it is kept inside the database server as $kept."
  if [ -n "$safety" ]; then
    say "To undo this restore, restore the dump taken just before it: DUMP=$safety with CONFIRM=$safety."
  fi
  if [ -z "$paused" ]; then
    say "No OddVex container was running, so nothing was started. ACTION=deploy starts a release."
  elif [ "$started" = "yes" ]; then
    say "The containers of release ${release:-unknown} were started again and answer."
  else
    say "THE CONTAINERS OF RELEASE ${release:-unknown} DID NOT COME BACK HEALTHY after the swap. ACTION=status shows their state."
  fi
  if [ -n "$release" ] && [ "$restored" != "$current" ]; then
    say "Release $release was running on revision $current and the database is now at $restored."
    say "If that release needs the newer schema, run ACTION=deploy with its REF (it applies the migrations again); or ACTION=rollback to the release that matches revision $restored."
  fi
  rule
  if [ "$started" = "no" ]; then exit 2; fi
}

# ---------------------------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------------------------

# Shows which names each OddVex container registers on the shared network, and what the generic
# names `api` and `web` resolve to there. Docker's DNS answers for a container's name and its
# network aliases; Compose adds the service name as an alias, which is why the services are
# called oddvex-api and oddvex-web.
edge_names() {
  say "shared network $EDGE, names registered by OddVex containers:"
  ours=""
  generic=no
  for id in $(docker ps -q --filter "label=com.docker.compose.project=$PROJECT" --filter "network=$EDGE" 2> /dev/null || true); do
    info=$(docker inspect --format "{{.Name}} {{with index .NetworkSettings.Networks \"$EDGE\"}}{{.IPAddress}} {{range .Aliases}}{{.}} {{end}}{{range .DNSNames}}{{.}} {{end}}{{end}}" "$id" 2> /dev/null) \
      || info=$(docker inspect --format "{{.Name}} {{with index .NetworkSettings.Networks \"$EDGE\"}}{{.IPAddress}} {{range .Aliases}}{{.}} {{end}}{{end}}" "$id" 2> /dev/null) \
      || continue
    name=${info%% *}
    rest=${info#* }
    address=${rest%% *}
    names=${rest#* }
    say "    ${name#/} ($address): $names"
    ours="$ours $address"
    case " ${name#/} $names " in
      *" api "* | *" web "*) generic=yes ;;
    esac
  done
  [ -n "$ours" ] || say "    (no OddVex container is on the shared network)"
  for name in api web; do
    # shellcheck disable=SC2016
    answer=$(docker run --rm --network "$EDGE" --entrypoint sh "$PROBE_IMAGE" -c 'if command -v nslookup >/dev/null 2>&1; then nslookup "$1" 2>&1; echo lookup-done; elif command -v getent >/dev/null 2>&1; then getent hosts "$1" 2>&1; echo lookup-done; else echo lookup-unavailable; fi' lookup "$name" 2> /dev/null || true)
    case "$answer" in
      *lookup-done*) ;;
      *)
        say "    the name '$name' could not be looked up from the shared network (no lookup tool answered); the list above is what Docker registers"
        continue ;;
    esac
    addresses=$(printf '%s\n' "$answer" | grep -oE '([0-9]{1,3}\.){3}[0-9]{1,3}' | grep -v '^127\.' | sort -u | tr '\n' ' ' || true)
    if [ -z "$addresses" ]; then
      say "    the name '$name' does not resolve on the shared network"
      continue
    fi
    for address in $addresses; do
      case " $ours " in
        *" $address "*)
          generic=yes
          say "    the name '$name' resolves to $address, which IS AN OddVex CONTAINER" ;;
        *) say "    the name '$name' resolves to $address, which is not an OddVex container" ;;
      esac
    done
  done
  if [ "$generic" = "yes" ]; then
    say "WARNING: an OddVex container still answers to 'api' or 'web' on the shared network. ACTION=deploy removes the containers of the old service names."
  else
    say "OK: no OddVex container answers to 'api' or 'web' on the shared network"
  fi
}

backup_status() {
  daily=$(newest "oddvex-*.dump")
  if [ -z "$daily" ]; then
    say "daily dumps in $BACKUPS: none"
  else
    age=$(($(date -u +%s) - $(stat -c %Y "$daily")))
    # shellcheck disable=SC2012
    say "daily dumps in $BACKUPS: $(ls "$BACKUPS"/oddvex-*.dump | wc -l | tr -d ' '); newest $(basename "$daily"), $(file_size "$daily") bytes, written $(file_age "$daily") ago"
    if [ "$age" -gt 93600 ]; then
      say "WARNING: the newest daily dump is more than 26 hours old, so the backup loop is failing or stopped. Its last lines are below."
    fi
  fi
  predeploy=$(newest "predeploy-*.dump")
  if [ -n "$predeploy" ]; then
    say "newest pre-deploy dump: $(basename "$predeploy"), $(file_size "$predeploy") bytes, written $(file_age "$predeploy") ago"
  else
    say "pre-deploy dumps: none"
  fi
  say "last lines of the backup container:"
  compose logs --no-log-prefix --tail 4 backup 2>&1 | sed 's/^/[oddvex]     /' || true
}

status() {
  if [ ! -f "$ENV_FILE" ] || [ ! -f "$COMPOSE_FILE" ]; then
    say "nothing is deployed here yet (no $ENV_FILE or no repository at $REPO)"
    return 0
  fi
  compose ps --all --format 'table {{.Service}}\t{{.State}}\t{{.Status}}' || true
  say "api health: $(probe http://oddvex-api:8000/health 2>&1 || true)"
  say "web home:   $(probe http://oddvex-web:3000/ 2>&1 || true)"
  say "running images: oddvex-api:$(image_tag_of oddvex-api api || true) and oddvex-web:$(image_tag_of oddvex-web web || true); last release a deploy saw healthy: $(cat "$HEALTHY_FILE" 2> /dev/null || echo "not recorded")"
  say "releases with images on this server (ACTION=rollback can start these without a build): $(docker image ls --format '{{.Tag}}' oddvex-api 2> /dev/null | tr '\n' ' ' || true)"
  say "database revision: $(db_revision oddvex 2> /dev/null || echo "could not be read")"
  kept=$(db_psql postgres "SELECT datname FROM pg_database WHERE datname LIKE 'oddvex\_re%' ORDER BY 1" 2> /dev/null | tr '\n' ' ' || true)
  [ -z "$kept" ] || say "databases kept by earlier restores: $kept"
  say "contact address in $ENV_FILE: $(env_get ODDVEX_CONTACT_EMAIL); administrator addresses listed: $(env_get ODDVEX_ADMIN_EMAILS)"
  backup_status
  edge_names
  if [ -f "$LOG_FILE" ]; then
    say "last operations ($LOG_FILE):"
    tail -n 5 "$LOG_FILE" | sed 's/^/[oddvex]     /'
  fi
}

# ---------------------------------------------------------------------------------------------
# caddy
# ---------------------------------------------------------------------------------------------

caddy() {
  docker inspect "$CADDY" > /dev/null 2>&1 || stop "container $CADDY not found"
  [ -f "$CADDYFILE" ] || stop "no Caddyfile at $CADDYFILE"
  if grep -qF "$MARK" "$CADDYFILE"; then
    say "the OddVex block is already in the Caddyfile; nothing changed"
    return 0
  fi
  [ "$(probe http://oddvex-web:3000/ 2> /dev/null || true)" = "200" ] || stop "the web container does not answer; deploy first"
  if [ ! -f "$ROOT/preview-password" ]; then secret 9 > "$ROOT/preview-password"; fi
  hash=$(docker exec "$CADDY" caddy hash-password --plaintext "$(cat "$ROOT/preview-password")")
  block=$ROOT/caddy-block
  {
    echo ""
    echo "$MARK"
    echo "$WEB_HOST {"
    echo "	header X-Robots-Tag \"noindex, nofollow\""
    echo "	encode zstd gzip"
    echo "	basic_auth {"
    echo "		oddvex $hash"
    echo "	}"
    echo "	reverse_proxy oddvex-web:3000"
    echo "}"
    echo ""
    echo "# The mobile app calls the API directly and signs in with its own token: no password prompt."
    echo "$API_HOST {"
    echo "	header X-Robots-Tag \"noindex, nofollow\""
    echo "	encode zstd gzip"
    echo "	reverse_proxy oddvex-api:8000"
    echo "}"
    echo "# <<< oddvex preview"
  } > "$block"
  backup=$ROOT/Caddyfile.before-oddvex-$(now)
  cp "$CADDYFILE" "$backup"
  cat "$CADDYFILE" "$block" | docker exec -i "$CADDY" sh -c 'cat > /tmp/oddvex-candidate && caddy validate --adapter caddyfile --config /tmp/oddvex-candidate >/tmp/oddvex-validate.log 2>&1' \
    || { docker exec "$CADDY" tail -5 /tmp/oddvex-validate.log || true; stop "the new Caddyfile did not validate; the live file was not touched"; }
  # Append in place: the file is bind-mounted into the Caddy container, so it must keep its inode.
  cat "$block" >> "$CADDYFILE"
  if ! docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile > /dev/null 2>&1; then
    cat "$backup" > "$CADDYFILE"
    docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile > /dev/null 2>&1 || true
    stop "Caddy refused the reload; the previous Caddyfile was restored"
  fi
  say "Caddy reloaded. Backup of the previous file: $backup"
  say "preview login: user oddvex, password $(cat "$ROOT/preview-password")"
}

case "${ACTION:-status}" in
  status) status ;;
  deploy) deploy ;;
  rollback) rollback ;;
  restore) restore ;;
  setenv) setenv ;;
  admin) admin ;;
  caddy) caddy ;;
  stop)
    [ -f "$ENV_FILE" ] || stop "there is no $ENV_FILE: nothing is deployed here"
    compose down --remove-orphans
    say "stopped; the database volume and the dumps in $BACKUPS are kept" ;;
  *) stop "unknown ACTION '${ACTION}'. Known: status, deploy, rollback, restore, setenv, admin, caddy, stop" ;;
esac
