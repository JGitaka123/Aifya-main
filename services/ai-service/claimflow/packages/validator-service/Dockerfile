# ClaimFlow validator service — stateless SHA claim rule engine over HTTP.
# Build context is the claimflow root (needs shared + rule-engine + rulepacks).
FROM node:20-slim AS build
WORKDIR /build
RUN corepack enable
COPY pnpm-workspace.yaml package.json ./
COPY packages/shared/package.json packages/shared/
COPY packages/rule-engine/package.json packages/rule-engine/
COPY packages/validator-service/package.json packages/validator-service/
RUN pnpm install --frozen-lockfile=false
COPY packages/shared packages/shared
COPY packages/rule-engine packages/rule-engine
COPY packages/validator-service packages/validator-service
RUN pnpm --filter @claimflow/validator-service build

FROM node:20-slim AS runtime
WORKDIR /app
RUN corepack enable
ENV NODE_ENV=production
# App code + node_modules. dist/server.js is an esbuild bundle with the
# workspace TS (shared, rule-engine) inlined; only real npm deps
# (fastify, jose, yaml, zod) are external and resolved from node_modules.
COPY --from=build /build /app
# Rulepacks the engine loads at boot.
COPY rulepacks /app/rulepacks
ENV RULEPACK_DIR=/app/rulepacks
EXPOSE 8030
CMD ["node", "packages/validator-service/dist/server.js"]
