# OddVex API. Build from this directory: docker build -t oddvex-api services/api
FROM python:3.13-slim AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY pyproject.toml README.md ./
COPY src ./src
RUN python -m venv /opt/venv && /opt/venv/bin/pip install .

FROM python:3.13-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/opt/venv/bin:$PATH"
RUN useradd --system --uid 10001 --create-home --home-dir /app oddvex
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --chown=oddvex:oddvex alembic.ini ./
COPY --chown=oddvex:oddvex alembic ./alembic
COPY --chown=oddvex:oddvex scripts ./scripts
USER oddvex
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"
# Apply migrations, then serve. Migrations here are additive; see README for the approval rule.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn oddvex_api.main:app --host 0.0.0.0 --port 8000"]
