"""Programmatic validators, URL scrubbing, and response repair."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.config import DUMMY_DEEPLINK
from app.schema import (
    Action,
    ContextDeeplinkResponse,
    Deeplink,
    Goal,
    StepGroup,
    ValidationDeepLink,
    actionCategory,
)

GOAL_PATTERN = re.compile(
    r"^Follow these steps to perform this .+ Troubleshooting(\.)?$|^Follow these steps to perform this .+ Configuration(\.)?$"
)

URL_PATTERNS = [
    re.compile(r"https?://[^\s\"']+", re.I),
    re.compile(r"\bwww\.[^\s\"']+", re.I),
    re.compile(r"\b[a-z0-9-]+\.(com|org|net|html|htm|edu|gov)\b", re.I),
    re.compile(r"\[[^\]]*\]\([^)]+\)"),
    re.compile(r"!\[[^\]]*\]\([^)]+\)"),
    re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I),
]

CRITICAL_KEYWORDS = (
    "factory reset",
    "master reset",
    "wipe",
    "erase all",
    "reset all settings",
)
MANUAL_KEYWORDS = (
    "contact",
    "service center",
    "repair",
    "visit",
    "inspect",
    "shine a flashlight",
    "remove the battery",
    "proof of purchase",
    "authorized samsung",
)


def scrub_urls(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in URL_PATTERNS:
        out = pat.sub("", out)
    return re.sub(r"\s+", " ", out).strip()


def scrub_dict(obj: Any) -> Any:
    if isinstance(obj, str):
        return scrub_urls(obj)
    if isinstance(obj, dict):
        return {k: scrub_dict(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [scrub_dict(v) for v in obj]
    return obj


def has_url_leak(obj: Any) -> bool:
    if isinstance(obj, str):
        lowered = obj.lower()
        if "http://" in lowered or "https://" in lowered or "www." in lowered:
            return True
        if re.search(r"\b[a-z0-9-]+\.(com|org|net|html)\b", lowered):
            return True
        if "@" in obj and re.search(r"[\w.+-]+@[\w.-]+\.", obj):
            return True
        return False
    if isinstance(obj, dict):
        return any(has_url_leak(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_url_leak(v) for v in obj)
    return False


def word_count(text: str) -> int:
    return len(text.split())


def fix_description(action_name: str, existing: str = "") -> str:
    clean = re.sub(r"^Step\s+\d+[\s:.-]*", "", action_name, flags=re.I).strip()
    clean = re.sub(r"^#+\s*", "", clean).strip()
    base = scrub_urls(existing or clean or action_name)
    verbs = ("check", "verify", "clear", "open", "enable", "restart", "connect", "adjust", "review")
    hint = next((w for w in clean.lower().split() if w in verbs), "guide")
    words = ["It", "will", hint, "you", "through", "these", "steps"]
    if base.lower().startswith("it will"):
        words = base.split()
    while len(words) < 5:
        words.append("steps")
    while len(words) > 7:
        words.pop()
    return " ".join(words[:7])


def fix_title(title: str, topic: str) -> str:
    source = scrub_urls(topic or title)
    if topic and len(topic.split()) <= 3:
        words = topic.split()[:3]
    else:
        words = source.split()[:3]
    if len(words) < 2:
        words = ["Device", "settings"]
    return " ".join(w.capitalize() if i == 0 else w.lower() for i, w in enumerate(words[:3]))


def infer_category(action_name: str, steps: List[str], has_deeplink: bool) -> actionCategory:
    blob = (action_name + " " + " ".join(steps)).lower()
    if any(k in blob for k in CRITICAL_KEYWORDS):
        return actionCategory.critical
    if any(k in blob for k in MANUAL_KEYWORDS) or not has_deeplink:
        return actionCategory.manual
    return actionCategory.auto


def category_rank(cat: actionCategory) -> int:
    if cat == actionCategory.auto:
        return 0
    if cat == actionCategory.manual:
        return 1
    return 2


def fix_goal(topic: str, configuration: bool = False) -> str:
    kind = "Configuration" if configuration else "Troubleshooting"
    clean = scrub_urls(topic).strip() or "Device"
    return f"Follow these steps to perform this {clean} {kind}"


def dummy_deeplink_from_steps(steps: List[str]) -> Deeplink:
    screen_hint = "Settings"
    for step in steps:
        low = step.lower()
        if "settings" in low:
            if "display" in low:
                screen_hint = "Display settings"
            elif "wifi" in low or "wi-fi" in low:
                screen_hint = "Wi-Fi settings"
            elif "apps" in low:
                screen_hint = "Apps settings"
            elif "connections" in low:
                screen_hint = "Connections settings"
            elif "storage" in low:
                screen_hint = "Storage settings"
            elif "multi window" in low:
                screen_hint = "Multi window settings"
            elif "advanced features" in low:
                screen_hint = "Advanced features settings"
            break
    desc = f"Open {screen_hint} on device"
    words = desc.split()
    while len(words) < 5:
        words.append("screen")
    while len(words) > 7:
        words.pop()
    msg_words = screen_hint.split()[:4]
    message = " ".join(msg_words) if msg_words else "Open Settings screen"
    return Deeplink(
        deeplink=DUMMY_DEEPLINK,
        description=" ".join(words[:7]),
        message=message,
        originalType="placeholder",
    )


def validate_format_rules(goal: Goal) -> List[str]:
    errors: List[str] = []
    if not GOAL_PATTERN.match(goal.goal):
        errors.append("goal_format")
    tw = word_count(goal.title)
    if tw < 2 or tw > 3:
        errors.append("title_words")
    if not (0.0 <= goal.score <= 1.0):
        errors.append("score_range")
    for action in goal.actions:
        dw = word_count(action.description)
        if dw < 5 or dw > 7:
            errors.append("description_words")
        if not action.description.lower().startswith("it will"):
            errors.append("description_prefix")
        if action.category == actionCategory.auto:
            for sg in action.stepGroups:
                if sg.actionableDeeplink is None:
                    errors.append("auto_missing_deeplink")
    return errors


def repair_goal(raw: Dict[str, Any], topic: str, score: float = 0.85) -> Goal:
    title = fix_title(raw.get("title", ""), topic)
    goal_text = raw.get("goal") or fix_goal(topic)
    if not GOAL_PATTERN.match(goal_text):
        goal_text = fix_goal(topic)

    actions: List[Action] = []
    for item in raw.get("actions", []):
        action_name = scrub_urls(str(item.get("actionName", "Follow steps")))
        step_groups_raw = item.get("stepGroups") or [{"steps": item.get("steps", [])}]
        step_groups: List[StepGroup] = []
        for sg_raw in step_groups_raw:
            steps = [scrub_urls(str(s)) for s in sg_raw.get("steps", []) if str(s).strip()]
            if not steps:
                continue
            ad_raw = sg_raw.get("actionableDeeplink")
            vd_raw = sg_raw.get("validationDeeplink")
            actionable = None
            validation = None
            if ad_raw and isinstance(ad_raw, dict) and ad_raw.get("deeplink"):
                actionable = Deeplink(
                    deeplink=str(ad_raw["deeplink"]),
                    description=scrub_urls(str(ad_raw.get("description", ""))),
                    message=scrub_urls(str(ad_raw.get("message", ""))),
                    originalType=ad_raw.get("originalType"),
                )
            if vd_raw and isinstance(vd_raw, dict) and vd_raw.get("deeplink"):
                validation = ValidationDeepLink(
                    deeplink=str(vd_raw["deeplink"]),
                    key=str(vd_raw.get("key", "")),
                    resultType=vd_raw.get("resultType"),
                    condition=vd_raw.get("condition"),
                    value=str(vd_raw.get("value")) if vd_raw.get("value") is not None else None,
                )
            step_groups.append(
                StepGroup(steps=steps, actionableDeeplink=actionable, validationDeeplink=validation)
            )
        if not step_groups:
            continue
        has_dl = any(sg.actionableDeeplink for sg in step_groups)
        cat = item.get("category")
        if cat:
            try:
                category = actionCategory(cat)
            except ValueError:
                category = infer_category(action_name, step_groups[0].steps, has_dl)
        else:
            category = infer_category(
                action_name, [s for sg in step_groups for s in sg.steps], has_dl
            )
        actions.append(
            Action(
                actionName=action_name,
                description=fix_description(action_name, item.get("description", "")),
                stepGroups=step_groups,
                category=category,
            )
        )

    for action in actions:
        for sg in action.stepGroups:
            if action.category == actionCategory.auto and sg.actionableDeeplink is None:
                sg.actionableDeeplink = dummy_deeplink_from_steps(sg.steps)
            elif action.category == actionCategory.manual:
                pass

    actions.sort(key=lambda a: category_rank(a.category or actionCategory.manual))
    clamped = max(0.0, min(1.0, float(score)))
    return Goal(goal=goal_text, title=title, actions=actions, score=clamped)


def repair_response(contexts: List[Dict[str, Any]], topic: str, score: float = 0.85) -> ContextDeeplinkResponse:
    goals = [repair_goal(c, topic, score) for c in contexts if c.get("actions")]
    cleaned = scrub_dict([g.model_dump() for g in goals])
    goals = [Goal.model_validate(g) for g in cleaned]
    return ContextDeeplinkResponse(contexts=goals)


def validate_response(response: ContextDeeplinkResponse) -> Tuple[bool, List[str]]:
    errors: List[str] = []
    if has_url_leak(response.model_dump()):
        errors.append("url_leak")
    for goal in response.contexts:
        errors.extend(validate_format_rules(goal))
    try:
        ContextDeeplinkResponse.model_validate(response.model_dump())
    except Exception as exc:
        errors.append(f"schema:{exc}")
    return len(errors) == 0, errors
