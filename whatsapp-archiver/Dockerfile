FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production

FROM node:20-slim

WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY *.js ./

# Run as non-root (node:20-slim provides a 'node' user at UID 1000)
RUN chown -R 1000:1000 /app
USER 1000

VOLUME ["/config", "/data"]
CMD ["node", "index.js"]
