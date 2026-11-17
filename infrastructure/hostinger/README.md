# OddVex on the Hostinger VPS (private preview)

Founder decision D-016 (2026-11-17): host on the Hostinger VPS with the `oddvex.com` domain, starting with a
password-protected preview at `preview.oddvex.com`. This replaces Vercel + Neon in `../DEPLOYMENT_PLAN.md` for the
preview. **Nothing here has been run on the server yet.**

## What the server looks like (read through the Hostinger API on 2026-11-17)

- `srv2032315`, KVM 2: 2 CPUs, 8 GB memory, 100 GB disk, Ubuntu 26.04, IP `179.236.240.236`.
- It is shared. About ten other Docker projects run on it, several of them live products with their own databases.
- One Caddy container (project `medivh-automation`) owns ports 80 and 443 for the whole server. OddVex must be
  added to that Caddy's configuration; it cannot bring its own proxy on those ports.
- Port 3000 on localhost is taken by another project, so OddVex uses 3410.
- A Traefik container (`traefik-zxwy`) is in a restart loop. It is not ours and is left alone.
- `oddvex.com` and `www` currently point to `2.57.91.91`, not to this server. They are not changed for the preview.
- No mailbox exists for `oddvex.com`, so `support@oddvex.com` does not receive mail yet.

## Steps

1. DNS: add an `A` record `preview` → `179.236.240.236` (and `AAAA` → `2a02:4780:95:965d::1`).
2. On the server: clone the repository to `/opt/oddvex/app`, create `/opt/oddvex/.env` from `.env.example`.
3. Start: `docker compose -p oddvex --env-file /opt/oddvex/.env -f infrastructure/hostinger/compose.yaml up -d --build`.
   The API applies database migrations when it starts.
4. Add `Caddyfile.snippet` to the shared Caddy configuration and reload Caddy. This is the only step that touches
   something other projects depend on: validate the file before reloading (`caddy validate`).
5. Check `https://preview.oddvex.com/` asks for the password and then loads; check `/app/games`.

## Limits of this setup

- Memory is capped (about 1.8 GB in total) so OddVex cannot starve the other projects.
- The build runs on the server and needs about 2 GB free while it runs.
- No backups are configured for the OddVex database yet. Fine for a preview with synthetic data; not for launch.
- Alerts are still only evaluated when a user opens the app (no scheduler).
- Email stays in the outbox table; nothing is sent.
- Going public (`oddvex.com` itself, no password) is a separate Founder decision.

## Rollback

`docker compose -p oddvex -f infrastructure/hostinger/compose.yaml down` stops OddVex and keeps its database volume.
Remove the Caddy block and the DNS record to take the address away.
