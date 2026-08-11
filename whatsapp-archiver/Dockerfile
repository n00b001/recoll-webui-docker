FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production

FROM node:20-slim

WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY *.js ./

# Create template and generated directories
RUN mkdir -p /templates /generated

# Install rsync for runtime synchronization
RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*

# Run as non-root (node:20-slim provides a 'node' user at UID 1000)
RUN chown -R node:node /app
USER node

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

VOLUME ["/config", "/data"]
ENTRYPOINT ["/entrypoint.sh"]
CMD ["node", "index.js"]
