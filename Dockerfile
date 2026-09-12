FROM node:22-bookworm-slim AS codex
ARG CODEX_VERSION=0.154.0
RUN npm install -g @openai/codex@${CODEX_VERSION}

FROM python:3.11-slim-bookworm

COPY --from=codex /usr/local/bin/node /usr/local/bin/node
COPY --from=codex /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/@openai/codex/bin/codex.js /usr/local/bin/codex
ENV CODEX_HOME=/data/codex

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn==22.0.0

COPY . .

RUN DATABASE_URL=sqlite:////tmp/stats-test.db \
    python -m unittest discover -s tests -v \
    && rm -f /tmp/stats-test.db

RUN mkdir -p /data/codex && chmod 700 /data/codex

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:5000/ || exit 1

CMD ["gunicorn", "app:app", "--workers", "2", "--bind", "0.0.0.0:5000", "--timeout", "60"]
