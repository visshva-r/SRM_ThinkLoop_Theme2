"""Ground steps against SIIS source text."""
from __future__ import annotations

import re
from typing import List, Set


def _tokens(text: str) -> Set[str]:
    return {t.lower() for t in re.findall(r"[a-z0-9]+", text) if len(t) > 2}


def step_grounded(step: str, siis_content: str, min_overlap: int = 2) -> bool:
    step_t = _tokens(step)
    if len(step_t) <= 2:
        return step.lower() in siis_content.lower()
    content_t = _tokens(siis_content)
    overlap = step_t & content_t
    if len(overlap) >= min_overlap:
        return True
    for phrase in re.split(r"[.!?\n]", siis_content):
        if len(phrase) > 20 and step[:40].lower() in phrase.lower():
            return True
    return False


def filter_grounded_steps(steps: List[str], siis_content: str) -> List[str]:
    kept = [s for s in steps if step_grounded(s, siis_content)]
    return kept if kept else steps[:1]
