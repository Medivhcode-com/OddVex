#!/bin/sh
# OddVex operations on the shared Hostinger VPS. Runs inside a one-shot `docker:cli` container
# that has the Docker socket, /opt/oddvex and the shared Caddy directory mounted (see README).
#
#   ACTION=status   show containers and check health (changes nothing)
#   ACTION=deploy   build the images from /opt/oddvex/repo and start or update the stack
#   ACTION=caddy    add the OddVex site blocks to the shared Caddy and reload it
#   ACTION=stop     stop the stack (keeps the database volume)
#
# The shared Caddy serves every site on this server. The caddy action only ever appends one
# marked block, validates the whole file first, and restores the backup if the reload fails.
set -eu

ROOT=/opt/oddvex
REPO=$ROOT/repo
ENV_FILE=$ROOT/.env
COMPOSE_FILE=$REPO/infrastructure/hostinger/compose.yaml
EDGE=${ODDVEX_EDGE_NETWORK:-medivh-automation_default}
CADDY=${ODDVEX_CADDY_CONTAINER:-medivh-automation-caddy-1}
CADDYFILE=${ODDVEX_CADDYFILE:-/opt/medivh/n8n/Caddyfile}
WEB_HOST=${ODDVEX_WEB_HOST:-preview.oddvex.com}
API_HOST=${ODDVEX_API_HOST:-api-preview.oddvex.com}
MIN_FREE_KB=${ODDVEX_MIN_FREE_KB:-2500000}
MARK="# >>> oddvex preview (managed by infrastructure/hostinger/ops.sh)"

say() { echo "[oddvex] $*"; }
stop() { say "STOP: $*"; exit 2; }
secret() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }
compose() { docker compose -p oddvex --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
probe() { docker run --rm --network "$EDGE" curlimages/curl:8.21.0 -fsS -o /dev/null -w '%{http_code}' --max-time 10 "$1"; }

status() {
  compose ps --format 'table {{.Service}}\t{{.State}}\t{{.Status}}' || true
  say "api health: $(probe http://oddvex-api:8000/health 2>&1 || true)"
  say "web home:   $(probe http://oddvex-web:3000/ 2>&1 || true)"
}

deploy() {
  [ -f "$COMPOSE_FILE" ] || stop "no repository at $REPO"
  docker network inspect "$EDGE" >/dev/null 2>&1 || stop "network $EDGE not found"
  if [ ! -f "$ENV_FILE" ]; then
    umask 077
    {
      echo "ODDVEX_DB_PASSWORD=$(secret 24)"
      echo "ODDVEX_JWT_SECRET=$(secret 32)"
      echo "ODDVEX_PUBLIC_URL=https://$WEB_HOST"
      echo "ODDVEX_CONTACT_EMAIL="
      echo "ODDVEX_ADMIN_EMAILS="
    } > "$ENV_FILE"
    say "created $ENV_FILE with generated secrets (not printed)"
  fi
  free=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
  [ "$free" -ge "$MIN_FREE_KB" ] || stop "only ${free} kB memory available; the build needs ${MIN_FREE_KB} kB. Nothing was changed."
  ODDVEX_RELEASE=$(git -C "$REPO" rev-parse --short HEAD)
  export ODDVEX_RELEASE
  say "building release $ODDVEX_RELEASE (one image at a time, low priority)"
  nice -n 15 docker compose -p oddvex --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build api
  nice -n 15 docker compose -p oddvex --env-file "$ENV_FILE" -f "$COMPOSE_FILE" build web
  compose up -d --wait --wait-timeout 180 || { compose logs --tail 40 api web; stop "the stack did not become healthy"; }
  say "release $ODDVEX_RELEASE is running"
  status
}

caddy() {
  docker inspect "$CADDY" >/dev/null 2>&1 || stop "container $CADDY not found"
  [ -f "$CADDYFILE" ] || stop "no Caddyfile at $CADDYFILE"
  if grep -qF "$MARK" "$CADDYFILE"; then
    say "the OddVex block is already in the Caddyfile; nothing changed"
    return 0
  fi
  [ "$(probe http://oddvex-web:3000/ 2>/dev/null || true)" = "200" ] || stop "the web container does not answer; deploy first"
  umask 077
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
  backup=$ROOT/Caddyfile.before-oddvex-$(date -u +%Y%m%dT%H%M%SZ)
  cp "$CADDYFILE" "$backup"
  cat "$CADDYFILE" "$block" | docker exec -i "$CADDY" sh -c 'cat > /tmp/oddvex-candidate && caddy validate --adapter caddyfile --config /tmp/oddvex-candidate >/tmp/oddvex-validate.log 2>&1' \
    || { docker exec "$CADDY" tail -5 /tmp/oddvex-validate.log || true; stop "the new Caddyfile did not validate; the live file was not touched"; }
  # Append in place: the file is bind-mounted into the Caddy container, so it must keep its inode.
  cat "$block" >> "$CADDYFILE"
  if ! docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1; then
    cat "$backup" > "$CADDYFILE"
    docker exec "$CADDY" caddy reload --config /etc/caddy/Caddyfile >/dev/null 2>&1 || true
    stop "Caddy refused the reload; the previous Caddyfile was restored"
  fi
  say "Caddy reloaded. Backup of the previous file: $backup"
  say "preview login: user oddvex, password $(cat "$ROOT/preview-password")"
}

case "${ACTION:-status}" in
  status) status ;;
  deploy) deploy ;;
  caddy) caddy ;;
  stop) compose down; say "stopped; the database volume is kept" ;;
  *) stop "unknown ACTION '${ACTION}'" ;;
esac
