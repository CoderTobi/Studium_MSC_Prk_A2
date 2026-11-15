# Production image of the frontend (SvelteKit with adapter-node).
#
# Build:  docker build -t shopping-list-frontend frontend/
# Run:    docker run --rm -p 3000:3000 \
#           -e PUBLIC_BACKEND_URL=http://localhost:8000 -e PUBLIC_AUTH_MODE=debug \
#           shopping-list-frontend
#
# The configuration is read when the container starts, so one image works with any
# backend URL. The backend must allow the frontend's origin via CORS_ALLOWED_ORIGINS.

# ---- build stage --------------------------------------------------------------
FROM node:24-alpine AS build

WORKDIR /app

# Dependencies first, so this layer is cached while only the source changes.
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

COPY . .
# SvelteKit starts the app once during the build to analyse it, which validates the
# environment variables. These placeholder values are NOT baked into the build: the
# real values are read at runtime.
RUN PUBLIC_BACKEND_URL=http://backend.invalid PUBLIC_AUTH_MODE=debug npm run build


# ---- runtime stage: only the self-contained server bundle ----------------------
FROM node:24-alpine AS runtime

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000

WORKDIR /app

# The bundle has no runtime dependencies; package.json is needed for "type": "module".
COPY --from=build /app/package.json ./
COPY --from=build /app/build ./build

# Unprivileged user that ships with the node image.
USER node
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["node", "-e", "fetch('http://127.0.0.1:3000/health').then(r => process.exit(r.ok ? 0 : 1), () => process.exit(1))"]

CMD ["node", "build"]
