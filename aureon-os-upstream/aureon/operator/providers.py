"""
Aureon Operator — provider adapters (the switchboard's lines).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Each external AI (ChatGPT, Grok, Gemini, Claude) is one *line* on the
switchboard. They all speak the in-house ``LLMAdapter`` interface
(:mod:`aureon.inhouse_ai.llm_adapter`), so the operator never learns a vendor
SDK — it only ever calls ``prompt()`` / ``stream()``.

Design rules (offline-first):
  • A provider is only wired when its API key is present.
  • With no keys — or under the repo's audit/offline guards
    (``AUREON_LLM_OFFLINE`` / ``AUREON_AUDIT_MODE`` / ``AUREON_DISABLE_LLM_HTTP``)
    — the switchboard returns an explicit unavailable status without
    classifying a static placeholder as model reasoning.

OpenAI and xAI/Grok both expose an OpenAI-compatible ``/v1/chat/completions``,
so those adapters reuse ``AureonLocalAdapter`` almost verbatim (base-URL + key).
Gemini speaks its own ``generativelanguage`` REST shape and gets a thin adapter
that normalises into the shared ``LLMResponse``.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Generator, List
from urllib.parse import urlsplit

from aureon.inhouse_ai.llm_adapter import (
    AureonLocalAdapter,
    AureonStubAdapter,
    LLMAdapter,
    LLMResponse,
    StreamChunk,
    _llm_http_disabled,
)
from aureon.ollama_config import OLLAMA_CLOUD_OPENAI_BASE_URL, ensure_ollama_runtime_config

logger = logging.getLogger("aureon.operator.providers")


# ─────────────────────────────────────────────────────────────────────────────
# OpenAI-compatible providers (ChatGPT, Grok) — thin base-URL + key wrappers
# ─────────────────────────────────────────────────────────────────────────────


class AureonOpenAIAdapter(AureonLocalAdapter):
    """ChatGPT via the OpenAI ``/v1`` API. OpenAI-compatible → reuse the local adapter."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"
    DEFAULT_MODEL = "gpt-4o-mini"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        super().__init__(
            base_url=base_url or os.environ.get("OPENAI_BASE_URL", self.DEFAULT_BASE_URL),
            model=model or os.environ.get("OPENAI_MODEL", self.DEFAULT_MODEL),
            api_key=api_key or os.environ.get("OPENAI_API_KEY", ""),
        )
        # Cloud vendors are never the Ollama native endpoint; keep the OpenAI path.
        self._prefer_native = False


class AureonGrokAdapter(AureonLocalAdapter):
    """Grok via the xAI ``/v1`` API. OpenAI-compatible → reuse the local adapter."""

    DEFAULT_BASE_URL = "https://api.x.ai/v1"
    DEFAULT_MODEL = "grok-2-latest"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        super().__init__(
            base_url=base_url or os.environ.get("XAI_BASE_URL", self.DEFAULT_BASE_URL),
            model=model or os.environ.get("XAI_MODEL", self.DEFAULT_MODEL),
            api_key=api_key or os.environ.get("XAI_API_KEY", ""),
        )
        self._prefer_native = False


# ─────────────────────────────────────────────────────────────────────────────
# Gemini — Google generativelanguage REST, normalised into LLMResponse
# ─────────────────────────────────────────────────────────────────────────────


class AureonGeminiAdapter(LLMAdapter):
    """
    Gemini via Google's ``generativelanguage`` REST API.

    Kept deliberately thin: one POST to ``:generateContent`` and a
    normalisation of the ``candidates[0].content.parts[*].text`` shape into the
    shared ``LLMResponse``. Tool-calling is not wired (not needed by the
    operator's fan-out); the operator only reads ``.text``.
    """

    DEFAULT_MODEL = "gemini-1.5-flash"
    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self.model = model or os.environ.get("GEMINI_MODEL", self.DEFAULT_MODEL)
        self.base_url = (base_url or os.environ.get("GEMINI_BASE_URL", self.DEFAULT_BASE_URL)).rstrip("/")
        self._session: Any | None = None
        try:
            import requests

            self._session = requests.Session()
        except ImportError:
            self._session = None
            logger.warning("requests not installed — Gemini adapter degraded")

    @staticmethod
    def _to_gemini_contents(messages: List[Dict], system: str) -> Dict:
        """Flatten the shared message list into Gemini ``contents`` + system instruction."""
        contents = []
        for msg in messages:
            role = "model" if msg.get("role") == "assistant" else "user"
            content = msg.get("content", "")
            if isinstance(content, list):
                parts_text = []
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text":
                        parts_text.append(str(c.get("text", "")))
                    elif isinstance(c, str):
                        parts_text.append(c)
                content = "\n".join(parts_text)
            contents.append({"role": role, "parts": [{"text": str(content)}]})
        payload: Dict = {"contents": contents}
        if system:
            payload["systemInstruction"] = {"parts": [{"text": str(system)}]}
        return payload

    def prompt(
        self,
        messages: List[Dict],
        system: str = "",
        tools: List[Dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> LLMResponse:
        if not self._session:
            return LLMResponse(text="[ERROR] requests library not available", stop_reason="error")
        if _llm_http_disabled():
            return LLMResponse(text="[ERROR] LLM HTTP disabled by audit/offline mode", stop_reason="error")

        payload = self._to_gemini_contents(messages, system)
        payload["generationConfig"] = {
            "maxOutputTokens": int(max_tokens),
            "temperature": float(temperature),
        }
        # Keep the reusable tenant credential out of the URL. URLs are routinely
        # copied into exception strings, proxy logs, traces and provider-test
        # receipts; Gemini supports the x-goog-api-key header for this API.
        url = f"{self.base_url}/models/{self.model}:generateContent"
        try:
            timeout = float(os.environ.get("AUREON_LLM_REQUEST_TIMEOUT_S", "30") or "30")
            resp = self._session.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
                timeout=max(1.0, timeout),
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:  # noqa: BLE001 — normalise any transport failure
            # Exception messages can contain full request URLs or echoed
            # headers. Log only the class and return a fixed status.
            logger.error("Gemini request failed (%s)", type(e).__name__)
            return LLMResponse(text="[ERROR] Gemini provider request failed", stop_reason="error")

        text_parts: List[str] = []
        for cand in data.get("candidates", []) or []:
            for part in (cand.get("content", {}) or {}).get("parts", []) or []:
                if part.get("text"):
                    text_parts.append(str(part["text"]))
        usage_meta = data.get("usageMetadata", {}) or {}
        return LLMResponse(
            text="\n".join(text_parts),
            stop_reason="end_turn",
            usage={
                "input_tokens": int(usage_meta.get("promptTokenCount", 0) or 0),
                "output_tokens": int(usage_meta.get("candidatesTokenCount", 0) or 0),
            },
            model=self.model,
            raw=data,
        )

    def stream(
        self,
        messages: List[Dict],
        system: str = "",
        tools: List[Dict] | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        **kwargs,
    ) -> Generator[StreamChunk, None, None]:
        # Simulate streaming from the one-shot response (keeps the adapter thin).
        response = self.prompt(messages, system, tools, max_tokens, temperature, **kwargs)
        for word in response.text.split(" "):
            yield StreamChunk(text=word + " ")
        yield StreamChunk(done=True, stop_reason=response.stop_reason)

    def health_check(self) -> bool:
        return bool(self.api_key) and self._session is not None and not _llm_http_disabled()


# ─────────────────────────────────────────────────────────────────────────────
# Provider set assembly — the switchboard's line-up
# ─────────────────────────────────────────────────────────────────────────────

_OFFLINE_STUB_ANSWER = (
    "[Aureon offline provider] No cloud AI key configured, so this line answers "
    "from the grounded repo context only. Set OPENAI_API_KEY / XAI_API_KEY / "
    "GEMINI_API_KEY to fan out across live models."
)


class AureonUnavailableAdapter(AureonStubAdapter):
    """Operator fallback status, never a successful model response."""

    def __init__(self):
        super().__init__(
            "[ERROR] No enabled model adapter is available. Review provider "
            "configuration, connectivity, and audit/offline settings.",
            model="aureon-operator-unavailable",
        )

    @property
    def model(self) -> str:
        return self._model

    def prompt(self, *args, **kwargs) -> LLMResponse:
        return LLMResponse(
            text=self._message, stop_reason="error", usage={},
            model=self.model, raw=None,
        )

    def stream(self, *args, **kwargs) -> Generator[StreamChunk, None, None]:
        yield StreamChunk(text=self._message)
        yield StreamChunk(done=True, stop_reason="error")

    def health_check(self) -> bool:
        return False


def _build_from_spec(spec) -> LLMAdapter | None:
    """Resolve one ModelSpec into a live adapter, or None if it can't run."""
    kind = spec.kind
    try:
        if kind == "openai":
            return AureonOpenAIAdapter(model=spec.model or None)
        if kind == "openai_compat":
            # Any OpenAI-compatible vendor (DeepSeek, Mistral, Groq, OpenRouter,
            # Perplexity, …). Reuse the OpenAI adapter but bind it to THIS spec's
            # own key/base-URL env vars, so each provider is independent.
            api_key = os.environ.get(spec.key_env or "", "")
            base_url = os.environ.get(spec.base_url_env or "", "") or None
            adapter = AureonOpenAIAdapter(
                api_key=api_key, base_url=base_url, model=spec.model or None
            )
            return adapter if adapter.health_check() else None
        if kind == "grok":
            return AureonGrokAdapter(model=spec.model or None)
        if kind == "gemini":
            return AureonGeminiAdapter(model=spec.model or None)
        if kind == "anthropic":
            from aureon.inhouse_ai.llm_adapter import AureonAnthropicAdapter

            adapter = AureonAnthropicAdapter(model=spec.model or None)
            return adapter if adapter.health_check() else None
        if kind == "local":
            from aureon.integrations.ollama import OllamaModelSwitchboard

            adapter, _selection = OllamaModelSwitchboard().compatible_adapter_for(
                "general",
                preferred=spec.model or "",
            )
            return adapter if adapter.health_check() else None
        if kind == "stub":
            return AureonStubAdapter(spec.options.get("message", _OFFLINE_STUB_ANSWER), model=spec.model or "stub")
    except Exception as exc:  # noqa: BLE001 — a bad line must never sink the board
        logger.warning("provider %s (%s) failed to initialise: %s", spec.name, kind, exc)
    return None


def build_registry(
    specs=None,
    *,
    allow_local: bool = True,
    force_offline: bool | None = None,
) -> Dict[str, LLMAdapter]:
    """
    Assemble the switchboard from a list of ``ModelSpec`` (config-driven).

    Only rows that are enabled, key-present, and successfully initialised are
    included — so the registry can list every flagship model you *might* use and
    the runtime dials only the ones actually configured. With none available
    (or under the repo's offline/audit guards), an error-status adapter reports
    the missing model without presenting a static placeholder as a working line.
    """
    from aureon.operator.config import default_registry

    if specs is None:
        if force_offline is not True:
            ensure_ollama_runtime_config()
        specs = default_registry()
    offline = _llm_http_disabled() if force_offline is None else bool(force_offline)

    providers: Dict[str, LLMAdapter] = {}
    if not offline:
        for spec in specs:
            if not spec.enabled or not spec.key_present():
                continue
            if spec.kind == "local" and not allow_local:
                continue
            adapter = _build_from_spec(spec)
            if adapter is not None:
                providers[spec.name] = adapter

    if providers:
        return providers

    return {"offline": AureonUnavailableAdapter()}


def build_provider_set(
    *,
    allow_local: bool = True,
    force_offline: bool | None = None,
) -> Dict[str, LLMAdapter]:
    """Convenience wrapper: assemble from the default registry (back-compat)."""
    return build_registry(allow_local=allow_local, force_offline=force_offline)


def tenant_provider_base_url(info: Any, supplied: Any = None) -> str | None:
    """Return the one catalog-pinned cloud endpoint allowed for a tenant.

    Per-user URLs are credentials-plus-network input. Allowing an arbitrary URL
    would turn cognition and the connection-test route into an authenticated
    SSRF primitive. Tenant adapters therefore use only reviewed provider
    endpoints; Ollama is pinned to its cloud API rather than host loopback.
    """
    provider_id = str(getattr(info, "id", "") or "")
    pinned = (
        OLLAMA_CLOUD_OPENAI_BASE_URL
        if provider_id == "ollama"
        else str(getattr(info, "default_base_url", "") or "").strip()
    )
    requested = str(supplied or "").strip()

    # Providers such as Anthropic fix their endpoint inside the SDK. They do
    # not accept any tenant-supplied override.
    if not pinned:
        if requested:
            raise ValueError("tenant_provider_custom_url_rejected")
        return None

    candidate = requested or pinned
    try:
        parsed = urlsplit(candidate)
    except ValueError as exc:
        raise ValueError("tenant_provider_custom_url_rejected") from exc
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or candidate.rstrip("/") != pinned.rstrip("/")
    ):
        raise ValueError("tenant_provider_custom_url_rejected")
    return pinned


def _harden_tenant_transport(adapter: LLMAdapter) -> LLMAdapter:
    """Disable ambient proxies and redirect following for tenant HTTP calls."""
    session = getattr(adapter, "_session", None)
    if session is not None:
        session.trust_env = False
        session.proxies.clear()
        session.max_redirects = 0
        original_request = session.request

        def pinned_request(method: str, url: str, **kwargs: Any) -> Any:
            if kwargs.get("allow_redirects") not in (None, False):
                raise RuntimeError("tenant_provider_redirects_forbidden")
            if kwargs.get("proxies"):
                raise RuntimeError("tenant_provider_proxy_forbidden")
            kwargs["allow_redirects"] = False
            kwargs["proxies"] = {}
            response = original_request(method, url, **kwargs)
            status = int(getattr(response, "status_code", 0) or 0)
            if (
                300 <= status < 400
                or bool(getattr(response, "is_redirect", False))
                or bool(getattr(response, "is_permanent_redirect", False))
                or bool(getattr(response, "history", ()))
            ):
                raise RuntimeError("tenant_provider_redirect_rejected")
            return response

        session.request = pinned_request
    adapter._aureon_tenant_network_policy = "catalog_pinned_no_redirects"
    return adapter


def build_adapter(
    kind: str,
    *,
    api_key: str,
    base_url: Any = None,
    model: str = "",
    tenant_network: bool = False,
) -> LLMAdapter:
    """Construct one adapter of ``kind`` from an EXPLICIT key — no ``os.environ`` read or write.

    The single source of truth for the catalog-kind → adapter-class mapping, shared by the live
    ``/api/providers/<id>/test`` round-trip and the per-tenant provider-set builder below. Because it
    never touches the process env, it is safe to call per-request with a tenant's own key.
    """
    if kind in ("openai", "openai_compat"):
        adapter = AureonOpenAIAdapter(api_key=api_key, base_url=base_url, model=model)
    elif kind == "grok":
        adapter = AureonGrokAdapter(api_key=api_key, base_url=base_url, model=model)
    elif kind == "gemini":
        adapter = AureonGeminiAdapter(api_key=api_key, model=model, base_url=base_url)
    elif kind == "anthropic":
        from aureon.inhouse_ai.llm_adapter import AureonAnthropicAdapter

        adapter = AureonAnthropicAdapter(api_key=api_key, model=model)
    else:
        from aureon.inhouse_ai.llm_adapter import AureonLocalAdapter  # local / self-hosted (Ollama)

        adapter = AureonLocalAdapter(api_key=api_key, base_url=base_url, model=model)
    return _harden_tenant_transport(adapter) if tenant_network else adapter


def build_provider_set_from_entries(
    entries: Dict[str, Dict[str, Any]], *, tenant_mode: bool = False,
) -> Dict[str, LLMAdapter]:
    """Assemble a switchboard from explicit keystore ``entries`` — **no ``os.environ`` reads/writes**.

    ``entries`` is a keystore dict (``{provider_id: {api_key, base_url, model, enabled}}``), e.g.
    ``keystore.load(tenant)``. Only enabled LLM providers with a key are built. Keyed by the provider's
    registry name, matching ``build_registry``. This is the seam for per-tenant live reasoning: a future
    ``AureonOperator(providers=build_provider_set_from_entries(keystore.load(tenant)))`` runs a tenant's
    own models without ever mutating the shared process env.
    """
    from aureon.operator.provider_catalog import get_provider

    out: Dict[str, LLMAdapter] = {}
    for provider_id, entry in entries.items():
        if not bool(entry.get("enabled", True)):
            continue
        api_key = str(entry.get("api_key", "") or "")
        info = get_provider(provider_id)
        if info is None or not api_key:
            continue
        try:
            base_url = (
                tenant_provider_base_url(info, entry.get("base_url"))
                if tenant_mode
                else str(entry.get("base_url", "") or "") or info.default_base_url
            )
            out[info.registry_name] = build_adapter(
                info.kind, api_key=api_key,
                base_url=base_url,
                model=str(entry.get("model", "") or "") or info.default_model,
                tenant_network=tenant_mode,
            )
        except Exception:  # noqa: BLE001 — a bad entry is skipped, never sinks the set
            logger.warning("could not build adapter for provider %s", provider_id)
    return out


def describe_provider_set(providers: Dict[str, LLMAdapter]) -> List[Dict[str, Any]]:
    """Log-safe configuration metadata; attachment is not a live response receipt."""
    described = []
    for name, adapter in providers.items():
        fallback = isinstance(adapter, AureonStubAdapter)
        described.append(
            {
                "name": name,
                "adapter": type(adapter).__name__,
                "model": str(getattr(adapter, "model", "") or getattr(adapter, "_model", "") or ""),
                "is_fallback": fallback,
                "configured": not fallback,
                "status": "unavailable" if fallback else "configured",
            }
        )
    return described


__all__ = [
    "AureonOpenAIAdapter",
    "AureonGrokAdapter",
    "AureonGeminiAdapter",
    "AureonUnavailableAdapter",
    "build_registry",
    "build_provider_set",
    "build_adapter",
    "build_provider_set_from_entries",
    "tenant_provider_base_url",
    "describe_provider_set",
]
