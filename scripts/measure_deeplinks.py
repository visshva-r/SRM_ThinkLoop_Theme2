"""Measure deeplink precision and ablation variants."""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.pipeline import TroubleshootPipeline

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_PATH = PROJECT_ROOT / "results.jsonl"


def main() -> None:
    with open(DATA_DIR / "siis_responses.json", encoding="utf-8") as f:
        kit = json.load(f)["responses"]

    pipeline = TroubleshootPipeline()
    pipeline.initialize()

    rows = []
    if RESULTS_PATH.exists():
        with open(RESULTS_PATH, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    rows.append(json.loads(line))

    print("=== Ablation summary ===")
    print(f"results.jsonl lines: {len(rows)}")
    auto_with_dl = 0
    auto_total = 0
    for row in rows:
        for goal in row.get("response", {}).get("contexts", []):
            for action in goal.get("actions", []):
                if action.get("category") == "auto":
                    auto_total += 1
                    for sg in action.get("stepGroups", []):
                        if sg.get("actionableDeeplink"):
                            auto_with_dl += 1
                            break
    print(f"auto actions with deeplink: {auto_with_dl}/{auto_total}")

    print("\n=== Sample unseen probe (hold-out style) ===")
    probe = kit[0]
    query = "Unknown paraphrase: tablet email screen goes blank in Gmail"
    body, meta = pipeline.run(
        query,
        siis_response=probe["siis_response"],
        use_llm=False,
        skip_cache=True,
    )
    print(f"contexts: {len(body.get('contexts', []))} model={meta.get('model')} latency={meta.get('latency_ms')}ms")


if __name__ == "__main__":
    main()
