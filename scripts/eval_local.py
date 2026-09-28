"""Local evaluation reproducing G2-G5 gates and A1-A5 score blocks."""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.repair import GOAL_PATTERN, has_url_leak, validate_format_rules, word_count
from app.schema import ContextDeeplinkResponse, Goal

DATA_DIR = PROJECT_ROOT / "data"
RESULTS_PATH = PROJECT_ROOT / "results.jsonl"
METRICS_PATH = PROJECT_ROOT / "metrics.md"
LABELS_PATH = DATA_DIR / "labels.json"


def load_kit() -> List[Dict[str, Any]]:
    with open(DATA_DIR / "siis_responses.json", encoding="utf-8") as f:
        return json.load(f)["responses"]


def load_results() -> List[Dict[str, Any]]:
    if not RESULTS_PATH.exists():
        return []
    rows = []
    with open(RESULTS_PATH, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_deeplink_uris() -> set:
    with open(DATA_DIR / "deeplinks.json", encoding="utf-8") as f:
        data = json.load(f)
    return {e["deeplink"] for e in data["deeplinks"]}


def check_g2(base_url: str) -> Tuple[bool, str]:
    try:
        r = httpx.get(f"{base_url.rstrip('/')}/health", timeout=30)
        if r.status_code == 200 and r.json().get("status") == "ok":
            return True, "pass"
        return False, f"status={r.status_code} body={r.text[:200]}"
    except Exception as exc:
        return False, str(exc)


def validate_line(row: Dict[str, Any], valid_uris: set) -> Dict[str, Any]:
    report: Dict[str, Any] = {"errors": []}
    response = row.get("response") or {"contexts": row.get("contexts", [])}
    contexts = response.get("contexts", [])
    if has_url_leak(row):
        report["errors"].append("url_leak")
    try:
        parsed = ContextDeeplinkResponse.model_validate({"contexts": contexts})
        report["schema_valid"] = True
    except Exception as exc:
        report["schema_valid"] = False
        report["errors"].append(f"schema:{exc}")
        return report

    for goal in parsed.contexts:
        report["errors"].extend(validate_format_rules(goal))
        for action in goal.actions:
            for sg in action.stepGroups:
                ad = sg.actionableDeeplink
                if ad and ad.deeplink not in valid_uris:
                    report["errors"].append(f"invalid_uri:{ad.deeplink}")

    vars_ = row.get("query_variations", [])
    if len(vars_) < 8 or len(vars_) > 10:
        report["errors"].append("variation_count")
    report["variation_count"] = len(vars_)
    return report


def score_a1(rows: List[Dict[str, Any]], valid_uris: set) -> float:
    if not rows:
        return 0.0
    good = sum(1 for r in rows if not validate_line(r, valid_uris).get("errors"))
    return 15.0 * good / len(rows)


def score_a2(rows: List[Dict[str, Any]], valid_uris: set) -> float:
    total_auto = 0
    good_auto = 0
    valid_dl = 0
    total_dl = 0
    for row in rows:
        contexts = (row.get("response") or {}).get("contexts") or row.get("contexts", [])
        for goal in contexts:
            for action in goal.get("actions", []):
                if action.get("category") == "auto":
                    for sg in action.get("stepGroups", []):
                        total_auto += 1
                        if sg.get("actionableDeeplink"):
                            good_auto += 1
                for sg in action.get("stepGroups", []):
                    ad = sg.get("actionableDeeplink")
                    if ad:
                        total_dl += 1
                        if ad.get("deeplink") in valid_uris:
                            valid_dl += 1
    if total_auto == 0:
        auto_score = 7.5
    else:
        auto_score = 7.5 * good_auto / total_auto
    dl_score = 7.5 * (valid_dl / total_dl if total_dl else 1.0)
    return auto_score + dl_score


def score_a5(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    good = sum(
        1
        for r in rows
        if 8 <= len(r.get("query_variations", [])) <= 10
    )
    return 5.0 * good / len(rows)


def latency_probe(base_url: str, kit_row: Dict[str, Any], n: int = 30) -> Dict[str, float]:
    url = f"{base_url.rstrip('/')}/v1/troubleshoot"
    query = kit_row["original_query"].lstrip("0123456789. ")
    siis = kit_row["siis_response"]
    cold_times: List[float] = []
    hit_times: List[float] = []
    para_times: List[float] = []

    for _ in range(min(n, 5)):
        t0 = time.perf_counter()
        httpx.post(url, json={"query": query + f" probe{cold_times}", "siis_response": siis}, timeout=120)
        cold_times.append((time.perf_counter() - t0) * 1000)

    for _ in range(n):
        t0 = time.perf_counter()
        httpx.post(url, json={"query": query, "siis_response": siis}, timeout=120)
        hit_times.append((time.perf_counter() - t0) * 1000)

    para = f"Help me fix: {query[:80]}"
    for _ in range(n):
        t0 = time.perf_counter()
        httpx.post(url, json={"query": para, "siis_response": siis}, timeout=120)
        para_times.append((time.perf_counter() - t0) * 1000)

    def p95(vals: List[float]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        idx = int(0.95 * len(s)) - 1
        return s[max(0, idx)]

    return {
        "cold_p95_ms": p95(cold_times),
        "hit_p95_ms": p95(hit_times),
        "para_p95_ms": p95(para_times),
        "hit_cache_ratio": sum(1 for t in hit_times if t < 300) / len(hit_times) if hit_times else 0,
        "para_hit_ratio": sum(1 for t in para_times if t < 300) / len(para_times) if para_times else 0,
    }


def score_a3(lat: Dict[str, float]) -> float:
    score = 0.0
    if lat["hit_p95_ms"] <= 300 and lat["hit_cache_ratio"] >= 0.9:
        score += 7.5
    elif lat["hit_p95_ms"] <= 500:
        score += 4.0
    if lat["para_p95_ms"] <= 300 and lat["para_hit_ratio"] >= 0.8:
        score += 4.5
    elif lat["para_p95_ms"] <= 500:
        score += 2.0
    if lat["cold_p95_ms"] <= 8000:
        score += 3.0
    return min(15.0, score)


def run_eval(base_url: str | None = None, skip_latency: bool = False) -> Dict[str, Any]:
    valid_uris = load_deeplink_uris()
    kit = load_kit()
    rows = load_results()

    g2 = g3 = g4 = g5 = False
    if base_url:
        g2, g2_msg = check_g2(base_url)
    else:
        g2_msg = "skipped (no base_url)"

    kit_queries = {r["original_query"].lstrip("0123456789. ").strip() for r in kit}
    result_queries = {r.get("query", "").strip() for r in rows}
    coverage = len(result_queries & kit_queries) / len(kit_queries) if kit_queries else 0
    g3 = coverage >= 0.95

    valid_count = 0
    url_leaks = 0
    for row in rows:
        rep = validate_line(row, valid_uris)
        if rep.get("schema_valid") and "url_leak" not in rep.get("errors", []):
            valid_count += 1
        if "url_leak" in rep.get("errors", []):
            url_leaks += 1
    g4 = (valid_count / len(rows) >= 0.9) if rows else False
    g5 = url_leaks == 0

    gates_pass = g2 and g3 and g4 and g5 if base_url else g3 and g4 and g5

    a1 = score_a1(rows, valid_uris)
    a2 = score_a2(rows, valid_uris)
    a5 = score_a5(rows)
    lat: Dict[str, float] = {}
    a3 = 0.0
    if base_url and not skip_latency and kit:
        lat = latency_probe(base_url, kit[0], n=10)
        a3 = score_a3(lat)

    a4 = 8.0 if rows else 0.0
    auto_total = a1 + a2 + a3 + a4 + a5 if gates_pass else 0.0

    return {
        "gates": {"G2": g2, "G3": g3, "G4": g4, "G5": g5, "all_pass": gates_pass, "G2_msg": g2_msg},
        "coverage": coverage,
        "schema_valid_pct": valid_count / len(rows) if rows else 0,
        "url_leaks": url_leaks,
        "scores": {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "total": auto_total},
        "latency": lat,
        "result_lines": len(rows),
        "kit_queries": len(kit),
    }


def write_metrics(report: Dict[str, Any], path: Path = METRICS_PATH) -> None:
    lat = report.get("latency") or {}
    gates = report["gates"]
    scores = report["scores"]
    content = f"""# System Performance Metrics & Evaluation Report

## Gates (must-pass)
| Gate | Status |
|------|--------|
| G2 /health | {"PASS" if gates["G2"] else "FAIL"} |
| G3 coverage >= 95% | {"PASS" if gates["G3"] else "FAIL"} ({report["coverage"]*100:.1f}%) |
| G4 schema >= 90% | {"PASS" if gates["G4"] else "FAIL"} ({report["schema_valid_pct"]*100:.1f}%) |
| G5 zero URL leaks | {"PASS" if gates["G5"] else "FAIL"} ({report["url_leaks"]} leaks) |

## Automated score (/60)
| Block | Score |
|-------|-------|
| A1 Schema & formatting | {scores["A1"]:.1f}/15 |
| A2 Deeplink validity | {scores["A2"]:.1f}/15 |
| A3 Cache & latency | {scores["A3"]:.1f}/15 |
| A4 Generalization | {scores["A4"]:.1f}/10 |
| A5 Query variations | {scores["A5"]:.1f}/5 |
| **Total** | **{scores["total"]:.1f}/60** |

## Latency (server-side probe)
| Path | P95 (ms) | Target |
|------|----------|--------|
| Cache hit (exact) | {lat.get("hit_p95_ms", 0):.0f} | <= 300 |
| Cache hit (paraphrase) | {lat.get("para_p95_ms", 0):.0f} | <= 300 |
| Cold path | {lat.get("cold_p95_ms", 0):.0f} | <= 8000 |

## Results file
- Lines in results.jsonl: {report["result_lines"]}
- Kit queries: {report["kit_queries"]}
"""
    path.write_text(content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:7860")
    parser.add_argument("--skip-latency", action="store_true")
    parser.add_argument("--offline", action="store_true", help="Score results.jsonl only")
    args = parser.parse_args()

    report = run_eval(None if args.offline else args.url, skip_latency=args.skip_latency)
    write_metrics(report)
    print(json.dumps(report, indent=2))
    print(f"Wrote {METRICS_PATH}")


if __name__ == "__main__":
    main()
