FROM ghcr.io/astral-sh/uv:0.12.22 AS uv
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PYTHON_DOWNLOADS=never \
    PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
# Install only runtime dependencies; never install/run the legacy setup.py.
RUN uv sync --locked --no-default-groups --no-install-project --no-cache \
    && mkdir /data \
    && chown 10001:10001 /data
COPY app/ ./app/
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
