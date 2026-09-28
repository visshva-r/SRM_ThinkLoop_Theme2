"""Gemini LLM integration for plan extraction and deeplink selection."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from app.config import GEMINI_API_KEY, GEMINI_MODEL

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=GEMINI_API_KEY or os.getenv("GEMINI_API_KEY"))
    return _client


def _extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def _normalize_stage1_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Convert common Gemini layout mistakes into Goal -> actions -> stepGroups."""
    contexts = plan.get("contexts") or []
    if not contexts:
        return plan

    first = contexts[0]
    if "actions" in first:
        return plan

    if "actionName" in first:
        actions: List[Dict[str, Any]] = []
        for item in contexts:
            if not isinstance(item, dict):
                continue
            step_groups: List[Dict[str, Any]] = []
            steps: List[str] = []
            for sg in item.get("stepGroups") or []:
                if not isinstance(sg, dict):
                    continue
                if sg.get("steps"):
                    steps.extend(str(s) for s in sg["steps"] if str(s).strip())
                elif sg.get("step"):
                    steps.append(str(sg["step"]).strip())
            if steps:
                step_groups.append({"steps": steps[:8]})
            if step_groups:
                actions.append(
                    {
                        "actionName": str(item.get("actionName", "Follow steps")),
                        "description": str(item.get("description", "")),
                        "stepGroups": step_groups,
                    }
                )
        topic = str(plan.get("topic") or "Device")
        title = str(plan.get("title") or topic)
        plan["contexts"] = [
            {
                "goal": f"Follow these steps to perform this {topic} Troubleshooting",
                "title": " ".join(title.split()[:3]),
                "score": 0.9,
                "actions": actions,
            }
        ]
    return plan


def stage1_extract_plan(
    query: str, siis: Dict[str, Any], variation_count: int = 9
) -> Tuple[Optional[Dict[str, Any]], float, str]:
    if not GEMINI_API_KEY and not os.getenv("GEMINI_API_KEY"):
        return None, 0.0, "none"

    content = siis.get("content", "")[:12000]
    title = siis.get("title", "")
    prompt = f"""You extract a structured troubleshooting plan from Samsung support text.
Return ONLY valid JSON with this exact nesting:
{{
  "normalized_query": "...",
  "topic": "Short Topic Name",
  "title": "Two Three Words",
  "query_variations": ["...", "..."],
  "contexts": [
    {{
      "goal": "Follow these steps to perform this <topic> Troubleshooting",
      "title": "Two Three Words",
      "score": 0.9,
      "actions": [
        {{
          "actionName": "...",
          "description": "draft",
          "stepGroups": [{{ "steps": ["Navigate to Settings.", "Tap Wi-Fi."] }}]
        }}
      ]
    }}
  ]
}}
Rules:
- Derive ALL steps ONLY from the SIIS text below. Do not invent steps.
- Each action has actionName, description (draft), stepGroups with imperative one-tap steps.
- title must be 2-3 words. topic is used in goal like "Follow these steps to perform this <topic> Troubleshooting".
- query_variations: exactly {variation_count} diverse paraphrases of the user query.
- No URLs anywhere.

User query: {query}
SIIS title: {title}
SIIS content:
{content}
"""
    try:
        client = _get_client()
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={
                "temperature": 0.2,
                "response_mime_type": "application/json",
            },
        )
        data = _extract_json(resp.text or "{}")
        data = _normalize_stage1_plan(data)
        cost = 0.001
        return data, cost, GEMINI_MODEL
    except Exception:
        return None, 0.0, GEMINI_MODEL


def stage2_pick_deeplinks(
    step_groups: List[Dict[str, Any]], candidates: List[List[Dict[str, Any]]]
) -> Tuple[Optional[List[str]], float]:
    if not GEMINI_API_KEY and not os.getenv("GEMINI_API_KEY"):
        return None, 0.0

    options = []
    for i, (sg, cands) in enumerate(zip(step_groups, candidates)):
        steps = sg.get("steps", [])
        cand_lines = []
        for c in cands[:5]:
            e = c["entry"]
            cand_lines.append(
                f"  - {c['id']}: {e.get('description','')} | {e.get('qna_description','')}"
            )
        options.append(
            {
                "index": i,
                "steps": steps,
                "candidates": "\n".join(cand_lines) or "  - NONE",
            }
        )
    prompt = f"""Pick the best deeplink catalog id for each step group, or NONE if no match, or DUMMY if Settings-related but no match.
Return JSON: {{"choices": ["DL-0001", "NONE", "DUMMY", ...]}} one per group in order.
Only use ids from the candidate lists or NONE or DUMMY.

{json.dumps(options, indent=2)}
"""
    try:
        client = _get_client()
        resp = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config={"temperature": 0.0, "response_mime_type": "application/json"},
        )
        data = _extract_json(resp.text or "{}")
        choices = data.get("choices", [])
        return choices, 0.0005
    except Exception:
        return None, 0.0
