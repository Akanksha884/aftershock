"""LLM provider abstraction. No key -> DEMO MODE (deterministic). Output is always Pydantic-validated;
invalid output is retried, then replaced by a deterministic fallback. Never raises to the caller."""
import json, logging, os, re
from typing import Awaitable, Callable, Literal, Optional, Type, TypeVar
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("aftershock.llm")
T = TypeVar("T", bound=BaseModel)

class IncidentSummary(BaseModel):
    severity: Literal["low", "medium", "high", "critical"]
    location: str = ""
    summary: str
    key_risks: list[str] = []

def heuristic_summary(text: str) -> IncidentSummary:
    t = text.lower()
    sev = "high" if any(k in t for k in ("bank", "sim", "passport", "injur", "hacked", "stolen")) else "medium"
    m = re.search(r"\b(?:in|at|near)\s+([A-Z][\w-]+(?:\s[A-Z][\w-]+)?)", text)
    risks = [r for k, r in (("bank", "financial exposure"), ("sim", "OTP interception"), ("account", "account takeover"),
                            ("passport", "identity misuse")) if k in t]
    return IncidentSummary(severity=sev, location=m.group(1) if m else "", summary=" ".join(text.split())[:140], key_risks=risks)

class LLMProvider:
    mode = "DEMO MODE"
    async def generate(self, system: str, prompt: str) -> str:
        raise NotImplementedError

class DemoProvider(LLMProvider):
    async def generate(self, system: str, prompt: str) -> str:
        return heuristic_summary(prompt).model_dump_json()

class AnthropicProvider(LLMProvider):
    mode = "LLM MODE"
    def __init__(self, key: str, model: Optional[str] = None):
        self.key, self.model = key, model or os.getenv("LLM_MODEL", "claude-sonnet-5-5")
    async def generate(self, system: str, prompt: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post("https://api.anthropic.com/v1/messages",
                             headers={"x-api-key": self.key, "anthropic-version": "2023-06-01"},
                             json={"model": self.model, "max_tokens": 600, "system": system,
                                   "messages": [{"role": "user", "content": prompt}]})
            r.raise_for_status()
            return "".join(b.get("text", "") for b in r.json()["content"])

def get_provider() -> LLMProvider:
    key = os.getenv("LLM_API_KEY")
    return AnthropicProvider(key) if key else DemoProvider()

async def structured(provider: LLMProvider, schema: Type[T], system: str, prompt: str,
                     fallback: Callable[[], T], retries: int = 1) -> tuple[T, bool, list[str]]:
    """Returns (validated object, used_fallback, issues-to-log)."""
    issues: list[str] = []
    for attempt in range(retries + 1):
        try:
            raw = await provider.generate(system, prompt)
            raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
            return schema.model_validate(json.loads(raw)), False, issues
        except (ValidationError, json.JSONDecodeError, ValueError) as e:
            issues.append(f"LLM output invalid (attempt {attempt + 1}): {type(e).__name__}")
        except Exception as e:  # network, timeout, auth, provider outage
            issues.append(f"LLM unavailable (attempt {attempt + 1}): {type(e).__name__}")
    logger.warning("LLM failed; using deterministic fallback: %s", issues)
    issues.append("Using deterministic fallback")
    return fallback(), True, issues
