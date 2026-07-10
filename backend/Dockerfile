FROM ghcr.io/astral-sh/uv:python3.14-bookworm-slim

WORKDIR /app

# deps layer, cached until the lockfile changes
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

COPY . .

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

CMD ["fastapi", "run", "main.py", "--host", "0.0.0.0", "--port", "8000"]
