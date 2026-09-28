"""Build results.jsonl for all kit queries via the pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import get_pipeline

DATA_DIR = PROJECT_ROOT / "data"
OUTPUT = PROJECT_ROOT / "results.jsonl"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--use-llm", action="store_true", help="Use Gemini (requires API key)")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()

    with open(DATA_DIR / "siis_responses.json", encoding="utf-8") as f:
        kit = json.load(f)["responses"]

    pipeline = get_pipeline()
    lines = []
    for row in kit:
        query = row["original_query"].lstrip("0123456789. ").strip()
        siis = row["siis_response"]
        body, meta = pipeline.run(query, siis_response=siis, use_llm=args.use_llm, skip_cache=True)
        out_row = {
            "query": query,
            "query_variations": body.get("query_variations", []),
            "response": body.get("response") or {"contexts": body.get("contexts", [])},
        }
        lines.append(out_row)
        print(f"OK {row['id']} model={meta.get('model')} latency={meta.get('latency_ms')}ms")

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        for row in lines:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {len(lines)} lines to {out_path}")


if __name__ == "__main__":
    main()
