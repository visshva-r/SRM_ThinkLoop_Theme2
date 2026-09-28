FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY scripts ./scripts
COPY results.jsonl ./results.jsonl

ENV DATA_DIR=/app/data
ENV RESULTS_PATH=/app/results.jsonl
ENV PYTHONUNBUFFERED=1

EXPOSE 7860

# Render sets PORT at runtime. Hugging Face Spaces use 7860.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}
