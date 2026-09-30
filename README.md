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

**Live API:** https://srm-thinkloop-theme2.onrender.com

- Health: https://srm-thinkloop-theme2.onrender.com/health
- Swagger UI: https://srm-thinkloop-theme2.onrender.com/docs

**Demo video (≤5 min):** [submission/Demo_Video.mp4](submission/Demo_Video.mp4)  
Direct GitHub link: https://github.com/visshva-r/SRM_ThinkLoop_Theme2/blob/main/submission/Demo_Video.mp4

(Hugging Face Docker Spaces require a paid plan; this API is hosted on Render free tier.)

## Endpoints

- `GET /health` → `{"status": "ok"}`
- `POST /v1/troubleshoot` → structured troubleshooting plan with masked Galaxy Settings deeplinks

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

## Deploy on Render (free)

Hugging Face Docker Spaces require a Pro subscription, so this API is hosted on Render.

1. Sign in at [render.com](https://render.com) with GitHub.
2. New → Blueprint → connect `visshva-r/SRM_ThinkLoop_Theme2` (uses `render.yaml`).
3. When asked, paste `GEMINI_API_KEY` from your local `.env`.
4. After the build is live, test `https://<your-service>.onrender.com/health` and `/docs`.

Free instances sleep after inactivity. Open the URL once before a demo so the first judged call is not a cold wake-up.

## Tests & evaluation

```bash
pytest tests/ -q
python scripts/eval_local.py --url http://127.0.0.1:7860
python scripts/eval_local.py --url https://srm-thinkloop-theme2.onrender.com
```

## GitHub

https://github.com/visshva-r/SRM_ThinkLoop_Theme2

Release tag: `PRISM_GENAI_HACKATHON_Y2026`
