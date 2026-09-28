"""Hybrid BM25 + dense retrieval over deeplink catalog."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from app.catalog import DeeplinkCatalog
from app.config import EMBEDDING_MODEL


def _tokenize(text: str) -> List[str]:
    return [t for t in text.lower().replace("/", " ").replace("-", " ").split() if len(t) > 1]


def rrf_fusion(rank_lists: List[List[str]], k: int = 60) -> List[Tuple[str, float]]:
    scores: Dict[str, float] = {}
    for ranks in rank_lists:
        for rank, cid in enumerate(ranks):
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


class HybridRetriever:
    def __init__(self, catalog: DeeplinkCatalog, model_name: str = EMBEDDING_MODEL) -> None:
        self.catalog = catalog
        self.model_name = model_name
        self.model: Optional[SentenceTransformer] = None
        self.bm25: Optional[BM25Okapi] = None
        self.ids: List[str] = []
        self.corpus: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self._ready = False

    def initialize(self) -> None:
        self.catalog.ensure_loaded()
        self.ids = []
        self.corpus = []
        for entry in self.catalog.entries:
            if entry.get("id") == "DL-DUMMY":
                continue
            self.ids.append(entry["id"])
            self.corpus.append(self.catalog.search_text(entry))
        tokenized = [_tokenize(c) for c in self.corpus]
        self.bm25 = BM25Okapi(tokenized)
        self.model = SentenceTransformer(self.model_name, device="cpu")
        self.embeddings = self.model.encode(self.corpus, normalize_embeddings=True, show_progress_bar=False)
        self._ready = True

    def ensure_ready(self) -> None:
        if not self._ready:
            self.initialize()

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        self.ensure_ready()
        assert self.bm25 is not None and self.model is not None and self.embeddings is not None

        q_tokens = _tokenize(query)
        bm25_scores = self.bm25.get_scores(q_tokens)
        bm25_rank = [self.ids[i] for i in np.argsort(bm25_scores)[::-1][: top_k * 3]]

        q_emb = self.model.encode([query.lower()], normalize_embeddings=True, show_progress_bar=False)[0]
        sims = self.embeddings @ q_emb
        dense_rank = [self.ids[i] for i in np.argsort(sims)[::-1][: top_k * 3]]

        fused = rrf_fusion([bm25_rank, dense_rank])[:top_k]
        results: List[Dict[str, Any]] = []
        for cid, score in fused:
            entry = self.catalog.get(cid)
            if entry:
                results.append({"id": cid, "score": float(score), "entry": entry})
        return results

    def attach_deeplinks_to_step_group(
        self, steps: List[str], chosen_id: Optional[str] = None
    ) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        query = " ".join(steps)
        if chosen_id and chosen_id != "NONE":
            if chosen_id == "DUMMY":
                return None, None
            actionable = self.catalog.build_actionable(chosen_id)
            validation = self.catalog.build_validation(chosen_id)
            return actionable, validation
        hits = self.search(query, top_k=1)
        if not hits:
            return None, None
        cid = hits[0]["id"]
        return self.catalog.build_actionable(cid), self.catalog.build_validation(cid)
