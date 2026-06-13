FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
        libxcomposite1 libxrandr2 libgbm1 libpango-1.0-0 \
        libcairo2 libasound2 libxdamage1 libxshmfence1 && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src/ src/

RUN pip install --no-cache-dir . && \
    playwright install --with-deps chromium

EXPOSE 3000

CMD ["applai", "serve"]
