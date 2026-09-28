---
title: Smart Guided Troubleshooting Engine
emoji: 🔧
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
---

# Smart Guided Troubleshooting Engine

Theme 2 submission for Samsung PRISM Gen AI Hackathon 3.0 — **SRM Think Loop**.

**Live API:** https://huggingface.co/spaces/visshva-r/SRM-ThinkLoop-Theme2 (after deploy)

## Endpoints

- `GET /health` → `{"status": "ok"}`
- `POST /v1/troubleshoot` → structured troubleshooting plan with masked Galaxy Settings deeplinks

Open `/docs` on the Space URL for the interactive Swagger UI.

### Request

```json
{
  "query": "My Galaxy S24 screen is completely black",
  "siis_response": {
    "title": "...",
    "content": "..."
  }
}
```

### Response

Returns hedged shape: top-level `contexts`, nested `response.contexts`, `query_variations`, and `meta` (latency, cache_hit, model, cost).

## Quick start (local)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

## Docker

```bash
docker build -t smart-troubleshoot .
docker run -p 7860:7860 -e GEMINI_API_KEY=your_key smart-troubleshoot
```

## Hugging Face Space secrets

Set in Space **Settings → Secrets**:

- `GEMINI_API_KEY` — required for Gemini responses (fallback works without it)
- Optional: `GEMINI_MODEL=gemini-2.5-flash`

## Tests & evaluation

```bash
pytest tests/ -q
python scripts/eval_local.py --url http://127.0.0.1:7860
```

## GitHub

https://github.com/visshva-r/SRM_ThinkLoop_Theme2

Release tag: `PRISM_GENAI_HACKATHON_Y2026`
