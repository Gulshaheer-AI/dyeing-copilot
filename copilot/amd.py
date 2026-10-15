"""Participant-configured AMD chat completions; no provider/model fallback."""

import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


class AMDConnectionError(ValueError):
    """Only curated, secret-free errors cross this boundary."""


@dataclass(frozen=True)
class AMDConfig:
    api_key: str = field(repr=False)
    base_url: str
    model: str


def load_config(env_path=ROOT / ".env", environ=None):
    env = os.environ if environ is None else environ
    # dotenv parses values only; it never executes or modifies the environment.
    values = dotenv_values(env_path) if Path(env_path).exists() else {}
    selected = {key: env.get(key, values.get(key) or "").strip()
                for key in ("AMD_API_KEY", "AMD_BASE_URL", "AMD_MODEL")}
    missing = [key for key, value in selected.items() if not value or "PASTE_" in value]
    if missing:
        raise AMDConnectionError("AMD configuration missing: " + ", ".join(missing) + ". See reports/amd_setup.md.")
    url = urlsplit(selected["AMD_BASE_URL"])
    # This adapter implements the documented participant shared Radeon endpoint only.
    # A different participant endpoint needs its own verified documentation, not a guessed fallback.
    if (url.scheme != "https" or url.hostname != "developer.amd.com.cn" or url.port not in (None, 443)
            or url.username or url.password or url.query or url.fragment
            or url.path.rstrip("/") not in ("/radeon/api/v1", "/radeon/v1")):
        raise AMDConnectionError("AMD_BASE_URL is not a documented shared Radeon Token Factory base URL. "
                                 "Check the participant Quickstart; this adapter does not substitute another provider.")
    if any(c in selected["AMD_API_KEY"] for c in "\r\n") or len(selected["AMD_MODEL"]) > 200:
        raise AMDConnectionError("Invalid AMD configuration format.")
    return AMDConfig(selected["AMD_API_KEY"], selected["AMD_BASE_URL"].rstrip("/"), selected["AMD_MODEL"])


def request_completion(config, messages, *, post=None, sleep=time.sleep, attempts=2):
    if attempts not in (1, 2):
        raise ValueError("AMD requests allow one or two attempts only.")
    post = requests.post if post is None else post
    started = time.perf_counter()
    timestamp = datetime.now(timezone.utc).isoformat()
    payload = {"model": config.model, "messages": messages, "stream": False,
               "temperature": 0, "max_tokens": 3000}
    for attempt in range(attempts):
        try:
            response = post(config.base_url + "/chat/completions", json=payload,
                            headers={"Authorization": "Bearer " + config.api_key, "Content-Type": "application/json"},
                            timeout=(5, 45), allow_redirects=False)
        except (requests.Timeout, requests.ConnectionError):
            if attempt + 1 < attempts:
                sleep(0.5)
                continue
            raise AMDConnectionError("AMD request timed out or could not connect after bounded attempts; "
                                     "check connectivity and retry manually.") from None
        except requests.RequestException:
            raise AMDConnectionError("AMD transport failed. Check local connectivity; no credentials were logged.") from None
        status = response.status_code
        if status in (408, 429, 502, 503, 504) and attempt + 1 < attempts:
            sleep(0.5)
            continue
        if status != 200:
            guidance = {400: "Request/model rejected; copy the participant model ID and check the documented format.",
                        401: "Authentication failed; check AMD_API_KEY locally.",
                        403: "Access denied; check participant account/model permissions.",
                        429: "Quota or rate limit reached; check the participant dashboard before retrying.",
                        408: "The AMD endpoint timed out.", 502: "AMD backend unavailable.",
                        503: "AMD backend saturated/unavailable.", 504: "AMD gateway timed out."}
            raise AMDConnectionError(f"AMD HTTP {status}: " + guidance.get(status, "Unexpected response; check the participant service."))
        try:
            data = response.json()
            choice = data["choices"][0]
            content = choice["message"]["content"]
            actual_model = data["model"]
            if choice.get("finish_reason") != "stop" or choice["message"].get("tool_calls"):
                raise ValueError
            if not isinstance(content, str) or not content.strip() or not isinstance(actual_model, str) or not actual_model:
                raise ValueError
            # Never render/log a key even if a malfunctioning service echoes it.
            if config.api_key in content or config.api_key in actual_model:
                raise ValueError
        except (ValueError, KeyError, IndexError, TypeError):
            raise AMDConnectionError("AMD returned an incomplete or unsupported response; no explanation was accepted.") from None
        receipt = {"origin": "live_amd", "requested_model": config.model, "actual_model": actual_model,
                   "timestamp_utc": timestamp, "latency_seconds": round(time.perf_counter() - started, 3),
                   "attempts": attempt + 1, "http_status": 200}
        return content, receipt
