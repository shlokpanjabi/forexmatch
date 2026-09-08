# AgentCore Runtime image. Built from the repository root:
#   docker build -f agentcore/Dockerfile -t forexmatch-agent .
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY backend/pyproject.toml ./backend/pyproject.toml
COPY agentcore/requirements.txt ./agentcore/requirements.txt
RUN pip install --no-cache-dir "./backend" && \
    pip install --no-cache-dir -r ./agentcore/requirements.txt

COPY backend/ ./backend/
COPY agentcore/ ./agentcore/

# No AWS credentials are baked in. AgentCore supplies them through the
# execution role, which boto3 picks up from the standard credential chain.
ENV PYTHONPATH=/app/backend

EXPOSE 8080
CMD ["python", "agentcore/entrypoint.py"]
