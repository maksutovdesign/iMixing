FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HOST=0.0.0.0 \
    PORT=8000 \
    IMIXING_DATABASE_URL=sqlite:////data/imixing_app.db \
    IMIXING_JOB_ROOT=/data/jobs \
    IMIXING_STORAGE_ROOT=/data/storage

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        ffmpeg \
        libgomp1 \
        libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
COPY marketing_assets ./marketing_assets
COPY migrations ./migrations

RUN pip install --upgrade pip \
    && pip install .

RUN useradd --create-home --shell /usr/sbin/nologin imixing \
    && mkdir -p /data/jobs /data/storage \
    && chown -R imixing:imixing /data /app

USER imixing

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/health || exit 1

CMD ["imixing-midi-web"]
