from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib import request
from urllib.error import HTTPError

from engine.dag import HypothesisDAG, parse_dag_payload, template_dag
from engine.taxonomy import DIMENSIONS, FILTER_COLUMNS, HYPOTHESIS_TYPES, JEV_MODEL, MAX_DAG_NODES, TESTS


def load_openrouter_api_key() -> str | None:
    env_key = os.environ.get("OPENROUTER_API_KEY")
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
            if name.strip() == "OPENROUTER_API_KEY":
                token = value.strip().strip('"').strip("'")
                if token:
                    return token
    return None


def jev_enabled() -> bool:
    return load_openrouter_api_key() is not None


def compile_prompt_to_dag(prompt: str, scenario_id: str) -> tuple[HypothesisDAG, str]:
    """Map natural language to a schema-bound HypothesisDAG via Jev (System One). Never returns SQL."""
    text = (prompt or "").strip()
    if not text:
        return template_dag(scenario_id), "template"
    key = load_openrouter_api_key()
    if not key:
        return template_dag(scenario_id), "template"
    try:
        payload = _generate_json(key, text, scenario_id)
        dag = parse_dag_payload(payload)
        return dag, "jev"
    except Exception as exc:
        import sys
        print(f"[DAG Compiler] Jev invocation failed: {exc}", file=sys.stderr)
        return template_dag(scenario_id), "template_fallback"


def _generate_json(api_key: str, prompt: str, scenario_id: str) -> dict:
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

    payload_body = {
        "model": JEV_MODEL,
        "messages": [
            {"role": "system", "content": instruction},
            {"role": "user", "content": f"Incident:\n{prompt[:2000]}"}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0
    }

    req = request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(payload_body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/incident-insight",
            "X-Title": "Incident Insight DAG Compiler"
        },
        method="POST"
    )

    response_data = None
    last_error: Exception | None = None

    for attempt in range(3):
        try:
            with request.urlopen(req, timeout=10) as response:
                response_data = json.loads(response.read().decode("utf-8"))
            break
        except HTTPError as exc:
            last_error = exc
            if exc.code == 503 and attempt < 2:
                time.sleep(2 * (attempt + 1))
                continue
            raise RuntimeError(f"OpenRouter API error: HTTP {exc.code}") from exc
        except Exception as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))

    if response_data is None:
        raise last_error or RuntimeError("Jev returned no response")

    if "choices" not in response_data or not response_data["choices"]:
        raise RuntimeError("Jev returned empty choices array")

    raw = response_data["choices"][0]["message"]["content"].strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    payload = json.loads(raw)
    if "nodes" not in payload and isinstance(payload.get("dag"), dict):
        payload = payload["dag"]
    if not isinstance(payload, dict):
        raise ValueError("Jev did not return a JSON object")

    return payload
