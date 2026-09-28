# System Performance Metrics & Evaluation Report

## Gates (must-pass)
| Gate | Status |
|------|--------|
| G2 /health | FAIL |
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

## Latency (server-side probe)
| Path | P95 (ms) | Target |
|------|----------|--------|
| Cache hit (exact) | 0 | <= 300 |
| Cache hit (paraphrase) | 0 | <= 300 |
| Cold path | 0 | <= 8000 |

## Results file
- Lines in results.jsonl: 20
- Kit queries: 20
