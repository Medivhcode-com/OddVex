#!/usr/bin/env bash
# Starts the production build of the web app. Run `pnpm build` first.
set -euo pipefail
cd "$(dirname "$0")/.."
# The standalone server does not ship static assets; copy them next to it.
mkdir -p .next/standalone/apps/web/.next
rm -rf .next/standalone/apps/web/.next/static
cp -R .next/static .next/standalone/apps/web/.next/static
exec node .next/standalone/apps/web/server.js
