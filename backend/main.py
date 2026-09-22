from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db import init_db
from engine.gemini_compiler import jev_enabled
from engine.taxonomy import JEV_MODEL
from routers import investigation, remediation, scenarios, telemetry


def _load_env() -> None:
    for candidate in (Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parents[1] / ".env"):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            key = name.strip()
            token = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = token


_load_env()


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Incident Insight RCA Engine", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:8080", "http://127.0.0.1:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(scenarios.router)
app.include_router(investigation.router)
app.include_router(telemetry.router)
app.include_router(remediation.router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "llm": JEV_MODEL if jev_enabled() else "disabled",
        "llm_role": "hypothesis_dag_compiler",
    }
