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
- No mailbox exists for `oddvex.com`, so `support@oddvex.com` does not receive mail yet.

## How it is deployed

Like the other projects on this server, OddVex is operated through a one-shot "ops" container sent to Hostinger's
Docker Manager (`ops.compose.yaml`). It fetches this public repository to `/opt/oddvex/repo` and runs `ops.sh`:

| `ACTION` | What it does |
|---|---|
| `status` | Lists the containers and checks the API and web answer. Changes nothing |
| `deploy` | Creates `/opt/oddvex/.env` with generated secrets on first run, builds both images one at a time at low priority, starts the stack and waits for it to be healthy. Refuses to build with less than about 2.5 GB of memory available |
| `caddy` | Appends one marked block for `preview.oddvex.com` and `api-preview.oddvex.com` to the shared Caddyfile. It validates the whole new file first, keeps a backup under `/opt/oddvex/`, appends in place and reloads; if the reload fails it restores the backup. It prints the preview user and password once |
| `stop` | Stops the stack and keeps the database volume |

The containers publish no ports. `web` and `api` join the shared proxy network `medivh-automation_default` as
`oddvex-web` and `oddvex-api`. `api-preview.oddvex.com` has no password prompt because the mobile app signs in with
its own token.

DNS: `A` records `preview` and `api-preview` → `179.236.240.236`.

## Limits of this setup

- Memory is capped (about 1.8 GB in total) so OddVex cannot starve the other projects.
- The build runs on the server and needs about 2 GB free while it runs.
- No backups are configured for the OddVex database yet. Fine for a preview with synthetic data; not for launch.
- Alerts are still only evaluated when a user opens the app (no scheduler).
- Email stays in the outbox table; nothing is sent.
- Going public (`oddvex.com` itself, no password) is a separate Founder decision.

## Rollback

`ACTION=stop` stops OddVex and keeps its database volume. To take the address away, remove the block between the
`# >>> oddvex preview` and `# <<< oddvex preview` markers from the shared Caddyfile (a backup of the file from before
the block was added is in `/opt/oddvex/`), reload Caddy, and delete the two DNS records.
