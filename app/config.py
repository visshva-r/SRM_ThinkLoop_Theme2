"""Application configuration from environment."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Hackathon requires CPU-first inference; avoid GPU OOM on shared machines.
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))
RESULTS_PATH = Path(os.getenv("RESULTS_PATH", PROJECT_ROOT / "results.jsonl"))

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
CACHE_SIMILARITY_THRESHOLD = float(os.getenv("CACHE_SIMILARITY_THRESHOLD", "0.80"))
PORT = int(os.getenv("PORT", "7860"))

LLM_TIMEOUT_SECONDS = 7.0
DUMMY_DEEPLINK = "bixby://dummy_positive"
DUMMY_CATALOG_ID = "DL-DUMMY"
