FROM node:20-slim

# Install fonts for consistent PPTX rendering
RUN apt-get update && apt-get install -y \
    fonts-inter \
    fonts-open-sans \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm ci --production

COPY dist/ ./dist/

EXPOSE 4100

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
  CMD curl -f http://localhost:4100/health || exit 1

CMD ["node", "dist/index.js"]
