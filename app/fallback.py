"""No-LLM extractive fallback planner from SIIS markdown content."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from app.repair import fix_goal, fix_title

STEP_HEADER = re.compile(
    r"^(?:#{1,3}\s*)?(?:Step\s+\d+|###\s+\d+\.|##\s+\d+\.)[\s:.-]*(.*)$",
    re.I | re.M,
)
SECTION_HEADER = re.compile(r"^#{1,3}\s+(.+)$", re.M)
IMPERATIVE = re.compile(
    r"^(Navigate to|Go to|Tap |Open |Select |Swipe |Press and hold|Touch and hold|Enable |Disable |Check |Try |Connect |Clear |Restart |Verify |Review |Adjust |Enter |Drag |Remove |Insert |Shine )",
    re.I,
)


def _clean_content(content: str) -> str:
    lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("Note:"):
            continue
        if line.startswith("Smartphone,") and ":" in line[:120]:
            continue
        lines.append(line)
    return "\n".join(lines)


def _topic_from_siis(siis: Dict[str, Any]) -> str:
    title = siis.get("title", "Device")
    content = siis.get("content", "")
    if "email" in title.lower() or "email" in content.lower()[:500]:
        return "Email Connection"
    if "blank" in title.lower() or "black" in title.lower():
        return "Display"
    if "flicker" in title.lower():
        return "Camera Display"
    if "crack" in title.lower() or "damage" in title.lower():
        return "Screen Damage"
    if "touch" in title.lower():
        return "Touchscreen"
    if "rotate" in title.lower():
        return "Screen Rotation"
    if "multi window" in title.lower() or "edge panel" in content.lower()[:400]:
        return "Multi Window"
    if "smart switch" in title.lower() or "smart switch" in content.lower()[:400]:
        return "Smart Switch"
    if "mirroring" in title.lower() or "smart view" in content.lower()[:400]:
        return "Screen Mirroring"
    if "secure folder" in title.lower():
        return "Secure Folder"
    words = title.split()[:3]
    return " ".join(words) if words else "Device"


def _split_sentences_to_steps(block: str) -> List[str]:
    steps: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", block):
        part = part.strip()
        if not part or len(part) < 8:
            continue
        if IMPERATIVE.match(part):
            steps.append(part.rstrip("."))
        elif part.lower().startswith(("first,", "next,", "then,", "alternatively,")):
            steps.append(part.rstrip("."))
    return steps[:6]


def extract_plan(query: str, siis: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], str, str]:
    content = _clean_content(siis.get("content", ""))
    topic = _topic_from_siis(siis)
    title = fix_title(siis.get("title", ""), topic)
    goal = fix_goal(topic)

    actions: List[Dict[str, Any]] = []
    sections = list(SECTION_HEADER.finditer(content))
    blocks: List[Tuple[str, str]] = []

    if sections:
        for i, match in enumerate(sections):
            start = match.end()
            end = sections[i + 1].start() if i + 1 < len(sections) else len(content)
            blocks.append((match.group(1).strip(), content[start:end].strip()))
    else:
        blocks = [("Troubleshooting steps", content)]

    for section_name, block in blocks:
        step_groups: List[Dict[str, Any]] = []
        header_steps = STEP_HEADER.findall(block)
        if header_steps:
            for header in header_steps[:4]:
                sub_block = block
                idx = block.find(header)
                if idx >= 0:
                    sub_block = block[idx : idx + 800]
                steps = _split_sentences_to_steps(sub_block)
                if not steps:
                    steps = [header.strip()]
                if steps:
                    step_groups.append({"steps": steps[:5]})
        else:
            steps = _split_sentences_to_steps(block)
            if steps:
                step_groups.append({"steps": steps[:5]})

        if not step_groups:
            continue
        action_name = re.sub(r"^#+\s*", "", section_name)[:60].strip() or "Follow troubleshooting steps"
        actions.append(
            {
                "actionName": action_name,
                "description": "",
                "stepGroups": step_groups,
            }
        )
        if len(actions) >= 5:
            break

    if not actions:
        steps = _split_sentences_to_steps(content) or [
            "Restart your device and check if the issue persists."
        ]
        actions = [
            {
                "actionName": "Basic troubleshooting",
                "description": "",
                "stepGroups": [{"steps": steps[:5]}],
            }
        ]

    contexts = [{"goal": goal, "title": title, "score": 0.75, "actions": actions}]
    return contexts, topic, title


def generate_variations(query: str, count: int = 9) -> List[str]:
    base = query.strip().lstrip("0123456789. ")
    variations = [
        base,
        base.lower(),
        base.replace("My ", "The ").replace("my ", "the "),
        re.sub(r"\bGalaxy\b", "Samsung phone", base, flags=re.I),
        re.sub(r"\bSamsung\b", "my Galaxy", base, flags=re.I),
        base.replace("completely", "totally").replace("Completely", "Totally"),
        "Help: " + base[:120],
        "Issue: " + base[:100],
        "Phone problem - " + base[:80],
        "Need fix for " + base[:70].lower(),
    ]
    seen = set()
    out: List[str] = []
    for v in variations:
        v = v.strip()
        if v and v not in seen:
            seen.add(v)
            out.append(v)
        if len(out) >= count:
            break
    while len(out) < 8:
        out.append(f"{base[:60]} (variant {len(out)+1})")
    return out[:10]
