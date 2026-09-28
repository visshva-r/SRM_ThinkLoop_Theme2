"""Deeplink catalog loader and lookup."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import DATA_DIR, DUMMY_CATALOG_ID, DUMMY_DEEPLINK


class DeeplinkCatalog:
    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or DATA_DIR
        self.entries: List[Dict[str, Any]] = []
        self.by_id: Dict[str, Dict[str, Any]] = {}
        self.by_uri: Dict[str, Dict[str, Any]] = {}
        self.valid_uris: set[str] = set()
        self._loaded = False

    def load(self) -> None:
        path = self.data_dir / "deeplinks.json"
        with open(path, encoding="utf-8") as f:
            payload = json.load(f)
        self.entries = payload.get("deeplinks", [])
        self.by_id = {e["id"]: e for e in self.entries}
        self.by_uri = {e["deeplink"]: e for e in self.entries}
        self.valid_uris = set(self.by_uri.keys())
        self._loaded = True

    def ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def get(self, catalog_id: str) -> Optional[Dict[str, Any]]:
        self.ensure_loaded()
        return self.by_id.get(catalog_id)

    def is_valid_uri(self, uri: str) -> bool:
        self.ensure_loaded()
        return uri in self.valid_uris or uri == DUMMY_DEEPLINK

    def build_actionable(self, catalog_id: str) -> Optional[Dict[str, Any]]:
        entry = self.get(catalog_id)
        if not entry:
            return None
        out: Dict[str, Any] = {
            "deeplink": entry["deeplink"],
            "description": entry["description"],
            "message": entry.get("message", ""),
            "originalType": entry.get("originalType"),
        }
        return out

    def build_validation(self, catalog_id: str) -> Optional[Dict[str, Any]]:
        entry = self.get(catalog_id)
        if not entry:
            return None
        val = entry.get("validation")
        if not val:
            return None
        out: Dict[str, Any] = {
            "deeplink": val["deeplink"],
            "key": val["key"],
        }
        if val.get("resultType"):
            out["resultType"] = val["resultType"]
        if val.get("condition"):
            out["condition"] = val["condition"]
        if val.get("value") is not None:
            out["value"] = str(val["value"])
        return out

    def search_text(self, entry: Dict[str, Any]) -> str:
        parts = [
            entry.get("description", ""),
            entry.get("qna_description", ""),
            entry.get("message", ""),
        ]
        val = entry.get("validation") or {}
        if val.get("key"):
            parts.append(val["key"])
        return " ".join(p for p in parts if p).lower()
