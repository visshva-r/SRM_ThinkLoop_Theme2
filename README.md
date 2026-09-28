# Smart Guided Troubleshooting Engine

Theme 2 submission for Samsung PRISM Gen AI Hackathon 3.0.

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
cd Project
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
copy .env.example .env     # add GEMINI_API_KEY (optional for fallback mode)
uvicorn app.main:app --host 0.0.0.0 --port 7860
```

## Build offline results (no API key)

```bash
python scripts/build_results.py
python scripts/eval_local.py --offline
```

## Build with Gemini

```bash
python scripts/build_results.py --use-llm
python scripts/eval_local.py --url http://127.0.0.1:7860
```

## Docker

```bash
docker build -t smart-troubleshoot .
docker run -p 7860:7860 -e GEMINI_API_KEY=your_key smart-troubleshoot
```

## Hugging Face Spaces

1. Create a new **Docker** Space (public).
2. Push this repo or upload files.
3. Set Space secret `GEMINI_API_KEY`.
4. Space URL becomes your live judge endpoint (no auth).

If cache p95 from India exceeds 300ms on a US Space, deploy the same image to a Singapore-region host and list both URLs here.

## Tests

```bash
pytest tests/ -q
```

## Submission checklist

- [ ] `results.jsonl` — 20 kit queries, 8–10 variations each
- [ ] `metrics.md` — gate and score report
- [ ] Demo video (≤5 min) linked in README
- [ ] PPT in `submission/`
- [ ] AI disclosure in `submission/`
- [ ] Git tag `PRISM_GENAI_HACKATHON_Y2026`

## Architecture

```
Query → Cache? → Gemini plan → Grounding → Hybrid deeplink retrieval → Repair → JSON
                     ↓ miss/timeout
              Extractive fallback (SIIS Step parser)
```

Hybrid retrieval: BM25 + `all-MiniLM-L6-v2` embeddings, reciprocal rank fusion over 578 masked deeplinks.

## Team

SRM Think Loop — Theme 2 (Guided Troubleshooting)

Repository: https://github.com/visshva-r/SRM_ThinkLoop_Theme2
