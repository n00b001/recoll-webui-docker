FROM node:22-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production

FROM node:22-slim

WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY *.js ./

# Create template and generated directories
RUN mkdir -p /templates /generated

# Install rsync for runtime synchronization
RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*

COPY --chmod=0755 entrypoint.sh /entrypoint.sh

VOLUME ["/config", "/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "index.js"]
