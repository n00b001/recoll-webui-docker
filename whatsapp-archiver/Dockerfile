FROM node:20-slim AS builder

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --production

FROM node:20-slim

WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY index.js ./

# Run as non-root (node:20-slim provides a 'node' user at UID 1000)
RUN chown -R node:node /app
USER node

VOLUME ["/config", "/data"]
CMD ["node", "index.js"]
