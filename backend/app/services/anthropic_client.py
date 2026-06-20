"""
Anthropic Claude API wrapper.

Encapsulates:
- Sync + streaming clients
- In-memory response cache (saves tokens during development)
- Graceful fallback when API key missing (returns mock responses)
- Structured logging for every call

Why a wrapper:
- Centralized rate limiting / retry logic
- Consistent observability (every LLM call logged)
- Easy to mock in tests
- Single place to swap providers later (e.g., to a local model)
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import AsyncIterator, Iterator
from datetime import datetime, timedelta
from typing import Any

import anthropic
from anthropic.types import MessageStreamEvent

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class _CacheEntry:
    """Single cached response with expiration."""
    
    def __init__(self, value: str, ttl_seconds: int = 3600):
        self.value = value
        self.expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
    
    @property
    def is_expired(self) -> bool:
        return datetime.utcnow() > self.expires_at


class AnthropicClient:
    """
    Wrapper around the Anthropic SDK with caching and observability.
    
    Two modes:
    - real: actual API calls (requires ANTHROPIC_API_KEY in .env)
    - mock: returns deterministic fake responses (when key missing)
    
    Mock mode is essential for:
    - Development without burning tokens
    - CI/CD pipelines
    - Demo if internet fails at hackathon
    """
    
    def __init__(self) -> None:
        self._api_key = settings.anthropic_api_key
        self._client: anthropic.Anthropic | None = None
        self._async_client: anthropic.AsyncAnthropic | None = None
        self._cache: dict[str, _CacheEntry] = {}
        # Snapshot real-vs-mock ONCE at construction. The SDK clients below are
        # created (or not) based on this, so is_mock must read the same snapshot —
        # otherwise a later flip of settings.external_apis_enabled would make
        # is_mock report real while self._client is still None (RuntimeError).
        self._real_mode: bool = self._is_real_mode()

        if self._real_mode:
            self._client = anthropic.Anthropic(api_key=self._api_key)
            self._async_client = anthropic.AsyncAnthropic(api_key=self._api_key)
            logger.info("anthropic_client_initialized", mode="real")
        else:
            logger.warning(
                "anthropic_client_mock_mode",
                hint="Set ANTHROPIC_API_KEY in backend/.env for real responses",
            )
    
    def _is_real_mode(self) -> bool:
        """Real API calls only if external APIs are enabled AND a valid-looking
        key is set. The master switch forces mock mode when offline regardless
        of any configured key, so the offline demo never reaches Anthropic."""
        return bool(
            settings.external_apis_enabled
            and self._api_key
            and self._api_key.startswith("sk-ant-")
            and len(self._api_key) > 20
        )
    
    @property
    def is_mock(self) -> bool:
        # Reads the construction-time snapshot, NOT live settings, so it can never
        # disagree with whether self._client was actually created.
        return not self._real_mode
    
    def _cache_key(self, prompt: str, model: str, max_tokens: int) -> str:
        """Stable hash of inputs for cache lookup."""
        payload = json.dumps(
            {"prompt": prompt, "model": model, "max_tokens": max_tokens},
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()
    
    # === Sync (non-streaming) completion ===
    
    def complete(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
        use_cache: bool = True,
    ) -> tuple[str, bool, int]:
        """
        Non-streaming completion.

        Returns:
            (text, was_cached, tokens_used)
            tokens_used is input+output tokens for real calls; 0 for mock/cached.
        """
        if model is None:
            model = settings.anthropic_model_main
        if max_tokens is None:
            max_tokens = settings.anthropic_max_tokens

        # === Cache lookup ===
        cache_key = self._cache_key(
            f"{system or ''}::{prompt}", model, max_tokens
        )
        if use_cache and cache_key in self._cache:
            entry = self._cache[cache_key]
            if not entry.is_expired:
                logger.info("anthropic_cache_hit", model=model)
                return entry.value, True, 0
            else:
                del self._cache[cache_key]

        # === Mock mode ===
        if self.is_mock:
            response = self._mock_response(prompt, system)
            self._cache[cache_key] = _CacheEntry(response)
            return response, False, 0

        # === Real API call ===
        if self._client is None:
            raise RuntimeError(
                "AnthropicClient._client is None but is_mock is False — "
                "this indicates a construction bug."
            )

        start = time.perf_counter()
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]

        try:
            response = self._client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages,
            )

            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.info(
                "anthropic_completion",
                model=model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                tokens_used=tokens_used,
                elapsed_ms=round(elapsed_ms),
            )

            if use_cache:
                self._cache[cache_key] = _CacheEntry(text)

            return text, False, tokens_used

        except anthropic.APIError as e:
            logger.error("anthropic_api_error", error=str(e))
            # Partial token charges may have been incurred before the error; 0 is a safe undercount.
            return self._mock_response(prompt, system), False, 0
    
    # === Async streaming ===
    
    async def stream(
        self,
        prompt: str,
        *,
        model: str | None = None,
        max_tokens: int | None = None,
        system: str | None = None,
    ) -> AsyncIterator[str]:
        """
        Streaming completion — yields text chunks as they arrive.
        
        Used by SSE endpoint for live "AI thinking" UX.
        """
        model = model or settings.anthropic_model_main
        max_tokens = max_tokens or settings.anthropic_max_tokens
        
        # Mock mode: simulate streaming
        if self.is_mock:
            full_text = self._mock_response(prompt, system)
            # Stream word-by-word for realistic feel
            import asyncio
            for word in full_text.split(" "):
                yield word + " "
                await asyncio.sleep(0.025)  # 40 words/sec
            return
        
        # Real streaming
        assert self._async_client is not None
        
        messages: list[dict[str, str]] = [{"role": "user", "content": prompt}]
        
        try:
            async with self._async_client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system or "",
                messages=messages,
            ) as stream:
                async for text_chunk in stream.text_stream:
                    yield text_chunk
        except anthropic.APIError as e:
            logger.error("anthropic_stream_error", error=str(e))
            yield f"\n\n[AI service unavailable: {e}]"
    
    # === Mock responses ===
    
    def _mock_response(self, prompt: str, system: str | None) -> str:
        """
        Deterministic fake response based on prompt content.
        
        Used when no API key is set OR when API fails.
        Good enough for development and demo backup.
        """
        prompt_lower = prompt.lower()
        
        # Pattern-match on prompt content to return relevant mock text
        if "adjudicate this t2 kyc drift case" in prompt_lower:
            verdict = "ambiguous"
            confidence = 0.52
            action = "Request information"
            evidence = [
                "T2 cascade routing indicates elevated or uncertain drift.",
                "Structured evidence should be reviewed by a compliance officer.",
            ]
            rationale = (
                "Mock adjudication based only on the supplied drift evidence. "
                "A human analyst should resolve remaining uncertainty before action."
            )
            if '"label": "risk"' in prompt_lower or '"is_suspicious": true' in prompt_lower:
                verdict = "risk"
                confidence = 0.78
                action = "Escalate to enhanced due diligence"
                evidence = [
                    "Causal assessment or suspicious-stability context indicates risk-shaped drift.",
                    "The case reached T2_LLM under the cascade routing policy.",
                ]
                rationale = (
                    "The provided evidence leans toward risk-shaped drift, but "
                    "the recommendation remains a human compliance review."
                )
            elif '"label": "benign"' in prompt_lower:
                verdict = "benign"
                confidence = 0.66
                action = "Monitor and document business rationale"
                evidence = [
                    "Causal assessment labels the drift as benign.",
                    "The case still reached T2_LLM because the cascade found enough uncertainty or risk.",
                ]
                rationale = (
                    "The supplied causal evidence is more consistent with a "
                    "benign business-change hypothesis than a risk hypothesis."
                )
            return json.dumps(
                {
                    "verdict": verdict,
                    "confidence": confidence,
                    "rationale": rationale,
                    "key_evidence": evidence,
                    "recommended_action": action,
                }
            )
        elif "executive summary" in prompt_lower:
            return (
                "This case exhibits multiple risk indicators that warrant "
                "elevated scrutiny. The transaction amount significantly "
                "exceeds the client's baseline behavior, and contextual "
                "signals from the communication channel suggest possible "
                "social engineering tactics. Recommended action is escalation "
                "with mandatory step-up verification before proceeding."
            )
        elif "risk factor" in prompt_lower:
            return (
                "Three primary risk factors drove the elevated score. First, "
                "the requested amount represents approximately 15 times the "
                "client's typical transaction volume, a strong deviation from "
                "established behavioral baseline. Second, multiple linguistic "
                "pressure markers were detected in the conversation transcript, "
                "consistent with known social engineering patterns documented "
                "by AMINA research. Third, the destination jurisdiction "
                "carries elevated regulatory risk."
            )
        elif "counterfactual" in prompt_lower or "alternative" in prompt_lower:
            return (
                "The model identified scenarios where this transaction would "
                "be acceptable. If the destination were a lower-risk jurisdiction "
                "and the communication patterns showed fewer pressure markers, "
                "this case would receive an approval recommendation. This "
                "suggests the underlying client relationship is sound, but "
                "the specific request profile triggers concerns."
            )
        elif "recommend" in prompt_lower or "action" in prompt_lower:
            return (
                "Given the combination of behavioral anomalies and contextual "
                "red flags, immediate blocking is recommended pending a "
                "verified callback to the client through a known secure channel. "
                "Document the rationale per audit requirements and consider "
                "filing a suspicious activity report if patterns persist."
            )
        elif "jurisdiction" in prompt_lower:
            return (
                "Under FINMA AMLA requirements, transactions exceeding "
                "CHF 100,000 with high-risk indicators must undergo Enhanced "
                "Due Diligence. Suspicious activity reports to MROS are "
                "required within 24 hours of detection."
            )
        else:
            return (
                "[Mock LLM response] This is a placeholder explanation generated "
                "without calling the Anthropic API. Set ANTHROPIC_API_KEY in "
                "backend/.env to enable real Claude responses."
            )
    
    # === Cache management ===
    
    def clear_cache(self) -> int:
        """Clear all cached responses. Returns count cleared."""
        count = len(self._cache)
        self._cache.clear()
        logger.info("anthropic_cache_cleared", count=count)
        return count
    
    @property
    def cache_size(self) -> int:
        return len(self._cache)


# === Singleton ===
_client: AnthropicClient | None = None


def get_anthropic_client() -> AnthropicClient:
    """FastAPI dependency for the shared Anthropic client."""
    global _client
    if _client is None:
        _client = AnthropicClient()
    return _client
