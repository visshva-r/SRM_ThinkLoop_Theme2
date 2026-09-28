# System Performance Metrics & Evaluation Report

## Gates (must-pass)
| Gate | Status |
|------|--------|
| G2 /health | PASS |
| G3 coverage >= 95% | PASS (100.0%) |
| G4 schema >= 90% | PASS (100.0%) |
| G5 zero URL leaks | PASS (0 leaks) |

## Automated score (/60)
| Block | Score |
|-------|-------|
| A1 Schema & formatting | 15.0/15 |
| A2 Deeplink validity | 15.0/15 |
| A3 Cache & latency | 0.0/15 |
| A4 Generalization | 8.0/10 |
| A5 Query variations | 5.0/5 |
| **Total** | **43.0/60** |

## Live deployment probe
- URL: https://srm-thinkloop-theme2.onrender.com
- Probe query: My Samsung A115G tablet screen flashes and then goes completely blank whenever I...
- Probe paraphrase: My A115G tablet screen flickers and turns off when I open Gmail....

| Path | P95 (ms) | cache_hit ratio | Target |
|------|----------|-----------------|--------|
| Cache hit (exact) | 730 | 100% | <= 300 ms, >= 90% |
| Cache hit (paraphrase) | 709 | 100% | <= 300 ms, >= 80% |
| Cold path | 42707 | n/a | <= 8000 ms |

Render free tier adds network latency; `meta.cache_hit` confirms cache behavior even when p95 exceeds 300 ms.

## Results file
- Lines in results.jsonl: 20
- Kit queries: 20
