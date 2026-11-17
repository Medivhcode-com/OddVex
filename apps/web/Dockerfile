# Build from the repository root: docker build -f apps/web/Dockerfile .
FROM node:22-alpine AS build
WORKDIR /repo
RUN corepack enable
COPY pnpm-lock.yaml pnpm-workspace.yaml package.json ./
COPY apps/web/package.json apps/web/
COPY packages/types/package.json packages/types/
# The lockfile covers every workspace package, so each manifest must be present for a frozen install.
COPY apps/mobile/package.json apps/mobile/
RUN pnpm install --frozen-lockfile --filter @oddvex/web...
COPY packages/types packages/types
COPY apps/web apps/web
# Public values are compiled into the pages, so they are build arguments, not runtime variables.
# Leave the contact address empty until its mailbox exists: the contact page then says so.
ARG NEXT_PUBLIC_SITE_URL=https://oddvex.com
ARG NEXT_PUBLIC_CONTACT_EMAIL=
ENV NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL NEXT_PUBLIC_CONTACT_EMAIL=$NEXT_PUBLIC_CONTACT_EMAIL
RUN pnpm --filter @oddvex/web build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app
COPY --from=build --chown=app:app /repo/apps/web/.next/standalone ./
COPY --from=build --chown=app:app /repo/apps/web/.next/static ./apps/web/.next/static
USER app
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
