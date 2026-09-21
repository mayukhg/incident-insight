from __future__ import annotations

import json
import os
import time
from pathlib import Path

from engine.dag import HypothesisDAG, parse_dag_payload, template_dag
from engine.taxonomy import DIMENSIONS, FILTER_COLUMNS, GEMINI_MODEL, HYPOTHESIS_TYPES, MAX_DAG_NODES, TESTS


def load_gemini_api_key() -> str | None:
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key:
        return env_key.strip() or None
    for candidate in (
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ):
        if not candidate.exists():
            continue
        for line in candidate.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            name, value = stripped.split("=", 1)
            if name.strip() in {"GEMINI_API_KEY", "GOOGLE_API_KEY"}:
                token = value.strip().strip('"').strip("'")
                if token:
                    return token
    return None


def gemini_enabled() -> bool:
    return load_gemini_api_key() is not None


def compile_prompt_to_dag(prompt: str, scenario_id: str) -> tuple[HypothesisDAG, str]:
    """Map natural language to a schema-bound HypothesisDAG. Never returns SQL."""
    text = (prompt or "").strip()
    if not text:
        return template_dag(scenario_id), "template"
    key = load_gemini_api_key()
    if not key:
        return template_dag(scenario_id), "template"
    try:
        payload = _generate_json(key, text, scenario_id)
        dag = parse_dag_payload(payload)
        return dag, "gemini"
    except Exception:
        return template_dag(scenario_id), "template_fallback"


def _generate_json(api_key: str, prompt: str, scenario_id: str) -> dict:
    from google import genai
    from google.genai import types

    instruction = (
        "You compile a bounded payment-forensics HypothesisDAG from an incident description. "
        "Windows are already bound by the server; do not invent timestamps. "
        "Never emit SQL, p-values, routing policy JSON, or free-text filter values. "
        f"hypothesis_type must be one of: {sorted(HYPOTHESIS_TYPES)}. "
        f"dimension must be one of: {sorted(DIMENSIONS)}. "
        f"test must be one of: {sorted(TESTS)}. "
        f"filter_column if present must be one of: {sorted(FILTER_COLUMNS)}. "
        "filter_value if present must be an exact catalog token (gateway adyen|stripe|checkout; "
        "ISO country GB|US|DE|FR|NL|IE|ES|IT; card_type debit|credit; brand visa|mastercard|amex). "
        f"Return at most {MAX_DAG_NODES} nodes. Prefer global_shift then gateway_isolation then a dimensional_slice. "
        "Use inherit_parent_filter=true on the drill node instead of guessing a gateway filter. "
        f"Scenario id for playbook context only: {scenario_id}."
    )
    client = genai.Client(api_key=api_key)
    response = None
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=f"{instruction}\n\nIncident:\n{prompt[:2000]}",
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                ),
            )
            break
        except Exception as exc:
            last_error = exc
            if "503" not in str(exc) or attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))
    if response is None:
        raise last_error or RuntimeError("Gemini returned no response")
    raw = getattr(response, "text", None) or ""
    if not raw and getattr(response, "candidates", None):
        parts = response.candidates[0].content.parts if response.candidates[0].content else []
        raw = "".join(getattr(part, "text", "") or "" for part in parts)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    payload = json.loads(raw)
    if "nodes" not in payload and isinstance(payload.get("dag"), dict):
        payload = payload["dag"]
    if not isinstance(payload, dict):
        raise ValueError("Gemini did not return a JSON object")
    return payload
