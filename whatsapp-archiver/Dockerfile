FROM node:20-slim AS builder

WORKDIR /app
COPY package.json ./
RUN npm ci --production

FROM node:20-slim

WORKDIR /app
COPY --from=builder /app/node_modules ./node_modules
COPY package.json ./
COPY index.js ./

# Run as non-root
RUN useradd -m -u 1000 archiver && chown -R archiver:archiver /app
USER archiver

VOLUME ["/data"]
CMD ["node", "index.js"]
