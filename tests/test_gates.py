"""Gate and schema tests (fallback-only, no LLM required)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.main import app
from app.pipeline import TroubleshootPipeline
from app.repair import has_url_leak


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def kit_first():
    with open(PROJECT_ROOT / "data" / "siis_responses.json", encoding="utf-8") as f:
        return json.load(f)["responses"][0]


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_troubleshoot_returns_contexts(client, kit_first):
    r = client.post(
        "/v1/troubleshoot",
        json={
            "query": kit_first["original_query"],
            "siis_response": kit_first["siis_response"],
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "contexts" in body
    assert "response" in body
    assert "meta" in body
    assert body["contexts"] == body["response"]["contexts"]
    assert len(body["contexts"]) >= 1
    assert not has_url_leak(body)


def test_no_siis_empty_contexts(client):
    r = client.post(
        "/v1/troubleshoot",
        json={"query": "zzxy_unique_no_siis_probe_999"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["contexts"] == []
    assert body.get("meta", {}).get("reason") == "no_siis_context"


def test_cache_hit_second_request(client, kit_first):
    payload = {
        "query": "unique cache test query for pytest",
        "siis_response": kit_first["siis_response"],
    }
    r1 = client.post("/v1/troubleshoot", json=payload)
    r2 = client.post("/v1/troubleshoot", json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r2.json()["meta"]["cache_hit"] is True


def test_variation_count(client, kit_first):
    r = client.post(
        "/v1/troubleshoot",
        json={
            "query": kit_first["original_query"],
            "siis_response": kit_first["siis_response"],
        },
    )
    vars_ = r.json().get("query_variations", [])
    assert 8 <= len(vars_) <= 10


def test_goal_format(client, kit_first):
    r = client.post(
        "/v1/troubleshoot",
        json={
            "query": kit_first["original_query"],
            "siis_response": kit_first["siis_response"],
        },
    )
    goal = r.json()["contexts"][0]
    assert goal["goal"].startswith("Follow these steps to perform this")
    assert "Troubleshooting" in goal["goal"] or "Configuration" in goal["goal"]
