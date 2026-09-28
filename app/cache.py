"""Semantic and exact query cache."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.config import CACHE_SIMILARITY_THRESHOLD, RESULTS_PATH
from app.embedder import SharedEmbedder


def normalize_query(q: str) -> str:
    return " ".join(q.lower().strip().split())


def siis_hash(siis: Optional[Dict[str, Any]]) -> str:
    if not siis:
        return ""
    payload = json.dumps(siis, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


class SemanticCache:
    def __init__(self, embedder: SharedEmbedder, threshold: float = CACHE_SIMILARITY_THRESHOLD) -> None:
        self.threshold = threshold
        self.exact: Dict[str, Dict[str, Any]] = {}
        self.entries: List[Dict[str, Any]] = []
        self.model = embedder
        self._ready = False

    def initialize(self) -> None:
        self.model.initialize()
        self._ready = True

    def ensure_ready(self) -> None:
        if not self._ready:
            self.initialize()

    def _exact_key(self, query: str, siis: Optional[Dict[str, Any]]) -> str:
        return f"{normalize_query(query)}|{siis_hash(siis)}"

    def get(self, query: str, siis: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        key = self._exact_key(query, siis)
        hit = self.exact.get(key)
        if hit:
            return {**hit, "cache_hit": True}
        if not siis and not self.entries:
            return None
        self.ensure_ready()
        assert self.model is not None
        q_emb = self.model.encode([normalize_query(query)])[0]
        sh = siis_hash(siis)
        best_score = 0.0
        best_entry: Optional[Dict[str, Any]] = None
        for entry in self.entries:
            if sh and entry.get("siis_hash") != sh:
                continue
            sim = float(np.dot(q_emb, entry["embedding"]))
            if sim > best_score:
                best_score = sim
                best_entry = entry
        if best_entry and best_score >= self.threshold:
            return {**best_entry["payload"], "cache_hit": True, "cache_similarity": best_score}
        return None

    def put(
        self,
        query: str,
        siis: Optional[Dict[str, Any]],
        payload: Dict[str, Any],
        variations: Optional[List[str]] = None,
    ) -> None:
        self.ensure_ready()
        assert self.model is not None
        key = self._exact_key(query, siis)
        self.exact[key] = payload
        sh = siis_hash(siis)
        texts = [normalize_query(query)] + [normalize_query(v) for v in (variations or [])]
        embs = self.model.encode(texts)
        for text, emb in zip(texts, embs):
            self.entries.append(
                {
                    "text": text,
                    "embedding": emb,
                    "siis_hash": sh,
                    "payload": payload,
                }
            )

    def warm_from_results(self, path: Path | None = None) -> int:
        path = path or RESULTS_PATH
        if not path.exists():
            return 0
        count = 0
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                row = json.loads(line)
                query = row.get("query", "")
                variations = row.get("query_variations", [])
                response = row.get("response") or {"contexts": row.get("contexts", [])}
                payload = {
                    "query_variations": variations,
                    "contexts": response.get("contexts", []),
                    "response": response,
                }
                self.put(query, None, payload, variations)
                count += 1
        return count
