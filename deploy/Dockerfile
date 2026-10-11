FROM ghcr.io/astral-sh/uv:0.10.8 AS uv
FROM python:3.12-slim-bookworm

COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONDONTWRITEBYTECODE=1
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
COPY migrations ./migrations
COPY alembic.ini ./
RUN uv sync --locked --no-dev && useradd --uid 10001 --create-home gym
USER gym
CMD ["/app/.venv/bin/gym-web"]
