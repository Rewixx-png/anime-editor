FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY requirements-bot.txt requirements-worker.txt ./
RUN uv pip install --system --no-cache -r requirements-bot.txt -r requirements-worker.txt

COPY . .

CMD ["python3", "-m", "bot.main"]
