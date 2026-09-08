# ForexMatch API. Built from the repository root:
#   docker build -f backend/Dockerfile -t forexmatch-api .
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app
RUN pip install --no-cache-dir .

COPY backend/migrations ./migrations
COPY backend/alembic.ini ./alembic.ini
COPY backend/scripts ./scripts
COPY backend/data ./data

# Run as a non-root user.
RUN useradd --create-home --uid 10001 forexmatch && chown -R forexmatch /app
USER forexmatch

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4).status==200 else 1)"

# Migrations are run as a separate step in deployment, not on container start,
# so that scaling to several instances cannot race on the schema.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
