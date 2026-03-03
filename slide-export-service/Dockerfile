FROM node:20-slim

# Install fonts for consistent rendering + Playwright dependencies
RUN apt-get update && apt-get install -y \
    fonts-inter \
    fonts-open-sans \
    curl \
    # Playwright Chromium dependencies
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libatspi2.0-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package*.json ./
RUN npm ci --production

# Install Playwright Chromium browser
RUN npx playwright install chromium

# Copy pre-built dist and shared package dist
COPY dist/ ./dist/

EXPOSE 4100

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s \
  CMD curl -f http://localhost:4100/health || exit 1

CMD ["node", "dist/index.js"]
