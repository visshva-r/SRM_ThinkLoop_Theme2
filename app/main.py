"""FastAPI service for Smart Guided Troubleshooting."""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from app.pipeline import get_pipeline


class SiisPayload(BaseModel):
    title: str = ""
    content: str = ""


class TroubleshootRequest(BaseModel):
    query: str
    siis_response: Optional[SiisPayload] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline = get_pipeline()
    app.state.pipeline = pipeline
    yield


app = FastAPI(
    title="Smart Guided Troubleshooting Engine",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> Dict[str, str]:
    pipeline = get_pipeline()
    if not pipeline.is_ready():
        raise HTTPException(status_code=503, detail="not ready")
    return {"status": "ok"}


@app.post("/v1/troubleshoot")
def troubleshoot(body: TroubleshootRequest) -> Dict[str, Any]:
    pipeline = get_pipeline()
    siis = body.siis_response.model_dump() if body.siis_response else None
    result, _meta = pipeline.run(body.query, siis_response=siis)
    return result
