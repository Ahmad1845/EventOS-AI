"""LLM client adapters (ollama, gemini, openai_compatible) per Section 10."""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, Optional

try:
    import requests as _requests
except ImportError:
    _requests = None


@dataclass
class LLMResult:
    model: str
    text: str
    input_tokens: Optional[int]
    output_tokens: Optional[int]
    total_tokens: Optional[int]
    seconds: float


class LLMError(Exception):
    pass


def _load_dotenv_key(env_name: str) -> Optional[str]:
    val = os.environ.get(env_name)
    if val and val != f"MY_{env_name}":
        return val
    if os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    if k.strip() == env_name:
                        clean_v = v.strip().strip('"').strip("'")
                        if clean_v and clean_v != f"MY_{env_name}":
                            return clean_v
        except Exception:
            pass
    # Also check running process environments in /proc if available
    if os.path.exists("/proc"):
        try:
            prefix = f"{env_name}=".encode("utf-8")
            for entry in os.listdir("/proc"):
                if not entry.isdigit():
                    continue
                env_path = os.path.join("/proc", entry, "environ")
                try:
                    with open(env_path, "rb") as pf:
                        raw_env = pf.read()
                    for item in raw_env.split(b"\x00"):
                        if item.startswith(prefix):
                            candidate = item[len(prefix) :].decode("utf-8", errors="ignore").strip()
                            if candidate and candidate != f"MY_{env_name}":
                                return candidate
                except Exception:
                    continue
        except Exception:
            pass
    return None


class LLMClient:
    def __init__(self, llm_config: Dict[str, Any]) -> None:
        self.provider = str(llm_config.get("provider", "gemini")).lower()
        self.model = str(llm_config.get("model", "gemini-3.1-flash-lite"))
        self.base_url = str(llm_config.get("base_url", "")).rstrip("/")
        self.api_key_env = str(llm_config.get("api_key_env", "GEMINI_API_KEY"))
        self.temperature = float(llm_config.get("temperature", 0))
        default_max_tok = 15 * (10 ** 2)
        self.max_output_tokens = int(llm_config.get("max_output_tokens", default_max_tok))
        self.timeout_seconds = int(llm_config.get("timeout_seconds", 80))
        self._session = _requests.Session() if _requests is not None else None

    def _post_json(
        self, url: str, payload: Dict[str, Any], headers: Dict[str, str]
    ) -> Dict[str, Any]:
        req_headers = {"Content-Type": "application/json", "User-Agent": "aistudio-build"}
        req_headers.update(headers)
        if self._session is not None:
            try:
                resp = self._session.post(
                    url,
                    json=payload,
                    headers=req_headers,
                    timeout=self.timeout_seconds,
                )
                if resp.status_code // (10 ** 2) != 2:
                    raise LLMError(f"HTTP {resp.status_code}: {resp.text}")
                return resp.json()
            except Exception as e:
                if isinstance(e, LLMError):
                    raise
                raise LLMError(str(e)) from e

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            raise LLMError(f"HTTP {e.code}: {err_body}") from e
        except Exception as e:
            raise LLMError(str(e)) from e

    def call(self, system: str, user: str, tag: str = "reading") -> LLMResult:
        t0 = time.monotonic()
        if self.provider == "ollama":
            return self._call_ollama(system, user, t0)
        if self.provider == "gemini":
            return self._call_gemini(system, user, t0)
        if self.provider in ("openai_compatible", "openai"):
            return self._call_openai_compatible(system, user, t0)
        raise LLMError(f"Unsupported provider: {self.provider}")

    def _call_ollama(self, system: str, user: str, t0: float) -> LLMResult:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
            },
        }
        data = self._post_json(url, payload, {})
        elapsed = time.monotonic() - t0
        msg = data.get("message") or {}
        text = str(msg.get("content", ""))
        reported_model = str(data.get("model") or self.model)
        in_tok = data.get("prompt_eval_count")
        out_tok = data.get("eval_count")
        if in_tok is not None and out_tok is not None:
            tot_tok: Optional[int] = int(in_tok) + int(out_tok)
            in_tok = int(in_tok)
            out_tok = int(out_tok)
        else:
            in_tok = None
            out_tok = None
            tot_tok = None
        return LLMResult(
            model=reported_model,
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            seconds=elapsed,
        )

    def _call_gemini(self, system: str, user: str, t0: float) -> LLMResult:
        api_key = _load_dotenv_key(self.api_key_env) or _load_dotenv_key("GEMINI_API_KEY")
        if not api_key:
            raise LLMError(f"Missing API key in environment variable {self.api_key_env}")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent?key={api_key}"
        )
        payload: Dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": self.temperature,
            },
        }
        data = self._post_json(url, payload, {})
        elapsed = time.monotonic() - t0
        candidates = data.get("candidates") or []
        text = ""
        if candidates:
            parts = (candidates[0].get("content") or {}).get("parts") or []
            text = "".join(str(p.get("text", "")) for p in parts)
        usage = data.get("usageMetadata") or {}
        in_tok = usage.get("promptTokenCount")
        out_tok = usage.get("candidatesTokenCount")
        tot_tok = usage.get("totalTokenCount")
        if in_tok is not None and out_tok is not None and tot_tok is not None:
            in_tok = int(in_tok)
            out_tok = int(out_tok)
            tot_tok = int(tot_tok)
        elif in_tok is not None and tot_tok is not None:
            in_tok = int(in_tok)
            tot_tok = int(tot_tok)
            out_tok = int(out_tok) if out_tok is not None else max(0, tot_tok - in_tok)
        else:
            in_tok = None
            out_tok = None
            tot_tok = None
        reported_model = str(data.get("modelVersion") or self.model)
        return LLMResult(
            model=reported_model,
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            seconds=elapsed,
        )

    def _call_openai_compatible(self, system: str, user: str, t0: float) -> LLMResult:
        api_key = _load_dotenv_key(self.api_key_env) or ""
        url = (
            f"{self.base_url}/chat/completions"
            if self.base_url.endswith("/v1")
            else f"{self.base_url}/v1/chat/completions"
        )
        headers: Dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        data = self._post_json(url, payload, headers)
        elapsed = time.monotonic() - t0
        choices = data.get("choices") or []
        text = ""
        if choices:
            text = str((choices[0].get("message") or {}).get("content", ""))
        usage = data.get("usage") or {}
        in_tok = usage.get("prompt_tokens")
        out_tok = usage.get("completion_tokens")
        tot_tok = usage.get("total_tokens")
        if in_tok is not None and out_tok is not None:
            in_tok = int(in_tok)
            out_tok = int(out_tok)
            tot_tok = int(tot_tok) if tot_tok is not None else in_tok + out_tok
        else:
            in_tok = None
            out_tok = None
            tot_tok = None
        reported_model = str(data.get("model") or self.model)
        return LLMResult(
            model=reported_model,
            text=text,
            input_tokens=in_tok,
            output_tokens=out_tok,
            total_tokens=tot_tok,
            seconds=elapsed,
        )
