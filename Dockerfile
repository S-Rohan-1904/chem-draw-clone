# Stage 1: build the frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: backend runtime (Python + JRE for OPSIN)
FROM python:3.14-slim
# JAVA_TOOL_OPTIONS keeps the OPSIN JVM small enough for 512 MB hosts.
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PORT=7860 \
    CHEM_DB_PATH=/data/data.db \
    JAVA_TOOL_OPTIONS="-Xmx192m -Xss512k -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -Xshare:auto"

RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless libxrender1 libxext6 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv

# Run unprivileged (uid 1000 also satisfies hosts that require it).
RUN useradd -m -u 1000 app && mkdir -p /data /app && chown -R app:app /data /app
USER app
WORKDIR /app

COPY --chown=app:app backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev

COPY --chown=app:app backend/ backend/
COPY --chown=app:app --from=web /web/dist frontend/dist

# Sanity check: OPSIN must run inside the image.
RUN cd backend && uv run --no-sync python -c "from app.opsin import strict; assert strict.convert('ethanol')[0]; strict.stop()"

EXPOSE 7860
WORKDIR /app/backend
CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
