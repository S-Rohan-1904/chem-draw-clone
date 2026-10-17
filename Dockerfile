# Stage 1: build the frontend
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: xtb (GFN2-xTB, LGPL-3.0) for calculated IR spectra, from conda-forge (amd64 and arm64).
# Installed at the same prefix it is copied to, so its libraries resolve.
FROM mambaorg/micromamba:2.9.0-debian12-slim AS xtb
USER root
RUN micromamba create -y -p /opt/xtb -c conda-forge xtb=6.7.1 \
 && micromamba clean -a -y \
 && /opt/xtb/bin/xtb --version > /dev/null

# Stage 3: backend runtime (Python + JRE for OPSIN)
FROM python:3.12-slim
# JAVA_TOOL_OPTIONS keeps the OPSIN JVM small enough for 512 MB hosts.
ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    PORT=7860 \
    CHEM_DB_PATH=/data/data.db \
    CHEM_XTB=/opt/xtb/bin/xtb \
    JAVA_TOOL_OPTIONS="-Xmx192m -Xss512k -XX:+UseSerialGC -XX:TieredStopAtLevel=1 -Xshare:auto"

RUN apt-get update \
 && apt-get install -y --no-install-recommends default-jre-headless libexpat1 libfreetype6 libfontconfig1 libxrender1 libxext6 \
 && rm -rf /var/lib/apt/lists/* \
 && pip install --no-cache-dir uv

COPY --from=xtb /opt/xtb /opt/xtb

# Run unprivileged (uid 1000 also satisfies hosts that require it).
RUN useradd -m -u 1000 app && mkdir -p /data /app && chown -R app:app /data /app
USER app
WORKDIR /app

COPY --chown=app:app backend/pyproject.toml backend/uv.lock backend/
RUN cd backend && uv sync --frozen --no-dev

COPY --chown=app:app backend/ backend/
COPY --chown=app:app --from=web /web/dist frontend/dist

# Reaction index for the Reactions card (public HF dataset, see backend/scripts/reactions_index.py).
# Without REACTIONS_REPO the card says the index is not installed.
ARG REACTIONS_REPO=""
RUN cd backend && REACTIONS_REPO=${REACTIONS_REPO} uv run --no-sync python scripts/reactions_index.py download

# Build the common-names cache into the image (also proves RDKit and OPSIN work here).
ARG PREWARM_LIMIT=0
RUN cd backend && uv run --no-sync python scripts/prewarm.py -j 4 --limit ${PREWARM_LIMIT}

EXPOSE 7860
WORKDIR /app/backend
CMD ["sh", "-c", "uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
