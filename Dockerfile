# Sentinel Mesh playground — Cloud Run image (repo-root context so the real
# referee/memory/plane modules ship unmodified into the container).
FROM python:3.12-slim
WORKDIR /app
COPY playground/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY referee.py memory.py plane.py ./
COPY demo_data/demo_memory.db demo_data/demo_memory.db
COPY playground/ playground/
ENV SENTINEL_MEMORY_DB=/app/demo_data/demo_memory.db \
    SENTINEL_VERTEX=1 \
    PYTHONUNBUFFERED=1
CMD exec uvicorn playground.app:app --host 0.0.0.0 --port ${PORT:-8080}
