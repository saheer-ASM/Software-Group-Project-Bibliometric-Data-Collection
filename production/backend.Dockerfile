# Production image for the Express backend (backend/server.js).
# Build context is the repository root -- see ../.dockerignore.

# Node 24: the backend reads the local SQLite database through the built-in
# node:sqlite module, which needs Node 22.13 or newer. Node 24 also ships
# npm 11, the version that generated the lock files in this repo (npm 10
# rejects them with "Missing: yaml@2.9.1 from lock file").
FROM node:24-alpine

ENV NODE_ENV=production

WORKDIR /app

# Install dependencies first so this layer is cached unless the lockfile moves.
# --omit=dev drops nodemon; the app only needs the runtime dependencies.
COPY backend/package.json backend/package-lock.json ./
# This network drops TLS connections under npm's default 15-way parallelism
# (seen as ERR_SSL_CIPHER_OPERATION_FAILED / "tls: bad record MAC"). Fewer
# concurrent sockets plus retries makes the install survive it.
RUN npm config set fetch-retries 5  && npm config set fetch-retry-maxtimeout 120000  && npm config set maxsockets 3

# npm's cache is a BuildKit cache mount, kept between builds: a build that
# fails part-way on this slow network, or any rebuild, reuses every package
# already downloaded instead of fetching them all again.
RUN --mount=type=cache,target=/root/.npm npm ci --omit=dev --prefer-offline --no-audit --no-fund

COPY backend/ ./

# server.js reads process.env.PORT (default 5005) and process.env.HOST.
# HOST=0.0.0.0 is required in a container: the original code bound to
# 'localhost', which inside a container means the container's own loopback and
# would make the service unreachable from nginx. See the HOST change in
# backend/server.js.
ENV PORT=5005
ENV HOST=0.0.0.0

EXPOSE 5005

# Run as the image's unprivileged user rather than root.
USER node

CMD ["node", "server.js"]
