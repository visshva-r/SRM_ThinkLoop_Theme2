"""End-to-end troubleshooting pipeline."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from app.cache import SemanticCache, normalize_query
from app.catalog import DeeplinkCatalog
from app.embedder import SharedEmbedder
from app.config import DUMMY_CATALOG_ID, LLM_TIMEOUT_SECONDS
from app.fallback import extract_plan, generate_variations
from app.grounding import filter_grounded_steps
from app.llm import stage1_extract_plan, stage2_pick_deeplinks
from app.repair import dummy_deeplink_from_steps, repair_response, validate_response
from app.retrieval import HybridRetriever
from app.schema import ContextDeeplinkResponse


class TroubleshootPipeline:
    def __init__(self) -> None:
        self.catalog = DeeplinkCatalog()
        self.embedder = SharedEmbedder()
        self.retriever = HybridRetriever(self.catalog, self.embedder)
        self.cache = SemanticCache(self.embedder)
        self.ready = False

    def initialize(self) -> None:
        self.catalog.load()
        self.retriever.initialize()
        if not LIGHTWEIGHT_MODE:
            self.cache.initialize()
        warmed = self.cache.warm_from_results()
        self.ready = True
        self._warmed_count = warmed

    def is_ready(self) -> bool:
        return self.ready

    def _attach_deeplinks(
        self, contexts: List[Dict[str, Any]], use_llm: bool = True
    ) -> List[Dict[str, Any]]:
        out_contexts: List[Dict[str, Any]] = []
        for ctx in contexts:
            actions_out: List[Dict[str, Any]] = []
            for action in ctx.get("actions", []):
                sgs_out: List[Dict[str, Any]] = []
                step_groups = action.get("stepGroups", [])
                all_candidates: List[List[Dict[str, Any]]] = []
                for sg in step_groups:
                    steps = sg.get("steps", [])
                    cands = self.retriever.search(" ".join(steps), top_k=5)
                    all_candidates.append(cands)

                choices: Optional[List[str]] = None
                if use_llm:
                    choices, _ = stage2_pick_deeplinks(step_groups, all_candidates)

                for idx, sg in enumerate(step_groups):
                    steps = sg.get("steps", [])
                    chosen = choices[idx] if choices and idx < len(choices) else None
                    if chosen == "DUMMY" or chosen == "NONE":
                        actionable = None
                        validation = None
                        if chosen == "DUMMY":
                            dl = dummy_deeplink_from_steps(steps)
                            actionable = dl.model_dump()
                    elif chosen and chosen not in ("NONE", "DUMMY"):
                        actionable = self.catalog.build_actionable(chosen)
                        validation = self.catalog.build_validation(chosen)
                    else:
                        hits = all_candidates[idx] if idx < len(all_candidates) else []
                        if hits:
                            cid = hits[0]["id"]
                            actionable = self.catalog.build_actionable(cid)
                            validation = self.catalog.build_validation(cid)
                        else:
                            dl = dummy_deeplink_from_steps(steps)
                            actionable = dl.model_dump()
                            validation = None
                    sgs_out.append(
                        {
                            "steps": steps,
                            "actionableDeeplink": actionable,
                            "validationDeeplink": validation,
                        }
                    )
                actions_out.append({**action, "stepGroups": sgs_out})
            out_contexts.append({**ctx, "actions": actions_out})
        return out_contexts

    def _ground_contexts(
        self, contexts: List[Dict[str, Any]], siis_content: str
    ) -> List[Dict[str, Any]]:
        grounded: List[Dict[str, Any]] = []
        for ctx in contexts:
            actions: List[Dict[str, Any]] = []
            for action in ctx.get("actions", []):
                sgs: List[Dict[str, Any]] = []
                for sg in action.get("stepGroups", []):
                    steps = filter_grounded_steps(sg.get("steps", []), siis_content)
                    if steps:
                        sgs.append({**sg, "steps": steps})
                if sgs:
                    actions.append({**action, "stepGroups": sgs})
            if actions:
                grounded.append({**ctx, "actions": actions})
        return grounded

    def run(
        self,
        query: str,
        siis_response: Optional[Dict[str, Any]] = None,
        use_llm: bool = True,
        skip_cache: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        start = time.perf_counter()
        meta: Dict[str, Any] = {
            "cache_hit": False,
            "model": "fallback",
            "cost_usd": 0.0,
            "latency_ms": 0,
        }

        if not skip_cache:
            cached = self.cache.get(query, siis_response)
            if cached:
                contexts = cached.get("contexts") or cached.get("response", {}).get("contexts", [])
                variations = cached.get("query_variations", [])
                meta["cache_hit"] = True
                meta["model"] = "cache"
                meta["latency_ms"] = int((time.perf_counter() - start) * 1000)
                return self._assemble_body(query, variations, contexts, meta), meta

        if siis_response is None:
            meta["reason"] = "no_siis_context"
            meta["latency_ms"] = int((time.perf_counter() - start) * 1000)
            return self._assemble_body(query, [], [], meta), meta

        cost = 0.0
        topic = "Device"
        variations: List[str] = []
        contexts: List[Dict[str, Any]] = []
        siis_content = siis_response.get("content", "")

        if use_llm:
            plan, c1, model = stage1_extract_plan(query, siis_response)
            cost += c1
            if plan:
                meta["model"] = model
                topic = plan.get("topic", topic)
                variations = plan.get("query_variations") or generate_variations(query)
                contexts = plan.get("contexts") or []
                contexts = self._ground_contexts(contexts, siis_content)
                if not any(c.get("actions") for c in contexts):
                    plan = None

        if not contexts:
            meta["model"] = "fallback"
            contexts, topic, _ = extract_plan(query, siis_response)
            variations = generate_variations(query)

        contexts = self._attach_deeplinks(contexts, use_llm=use_llm and meta["model"] != "fallback")
        repaired = repair_response(contexts, topic, score=0.88)
        ok, errors = validate_response(repaired)
        if not ok:
            contexts, topic, _ = extract_plan(query, siis_response)
            contexts = self._attach_deeplinks(contexts, use_llm=False)
            repaired = repair_response(contexts, topic, score=0.75)
            meta["model"] = "fallback"
            meta["repair_errors"] = errors

        contexts_dict = [g.model_dump() for g in repaired.contexts]
        if not variations or len(variations) < 8:
            variations = generate_variations(query, count=9)
        variations = variations[:10]

        payload = {
            "query_variations": variations,
            "contexts": contexts_dict,
            "response": {"contexts": contexts_dict},
        }
        self.cache.put(query, siis_response, payload, variations)

        meta["cost_usd"] = round(cost, 6)
        meta["latency_ms"] = int((time.perf_counter() - start) * 1000)
        return self._assemble_body(query, variations, contexts_dict, meta), meta

    def _assemble_body(
        self,
        query: str,
        variations: List[str],
        contexts: List[Dict[str, Any]],
        meta: Dict[str, Any],
    ) -> Dict[str, Any]:
        response = {"contexts": contexts}
        return {
            "query": query,
            "query_variations": variations,
            "contexts": contexts,
            "response": response,
            "meta": meta,
        }


_pipeline: Optional[TroubleshootPipeline] = None


def get_pipeline() -> TroubleshootPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = TroubleshootPipeline()
        _pipeline.initialize()
    return _pipeline
