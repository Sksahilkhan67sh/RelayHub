# Adding a new AI provider to RelayHub

RelayHub's AI features (Insights AI analysis, Copilot chat) talk to AI
providers through one gateway: `backend/app/modules/ai_gateway/`. Nothing in
`insights/ai/service.py`, `insights/copilot/service.py`,
`insights/copilot/routes.py`, `workers/insight_tasks.py`, the frontend, or the
database schema needs to change to add a provider.

## What you need to add

For a hypothetical new provider `"acme"`:

### 1. An adapter

Create `backend/app/modules/ai_gateway/adapters/acme.py` implementing the
`ProviderAdapter` protocol from `adapters/base.py`:

```python
class AcmeAdapter:
    provider_name = "acme"

    def __init__(self, *, api_key: str, model: str) -> None:
        ...

    async def health_check(self) -> bool:
        """Config-only check -- never a real API call."""
        ...

    async def complete(self, request: AIGatewayRequest) -> AIGatewayResponse:
        """Translate AIGatewayRequest into Acme's API shape, call it, and
        translate the response back into AIGatewayResponse. Map every
        failure mode (network error, timeout, 401/403, 429, 4xx, 5xx,
        malformed body) into the normalized errors from ai_gateway/contracts.py
        -- AIAuthenticationError, AIRateLimitError, AITimeoutError,
        AIUnavailableError, AIInvalidRequestError, AIContextLimitError,
        AIMalformedResponseError. Never let a provider-specific exception
        escape this method."""
        ...
```

Follow `adapters/anthropic.py` (simplest, single-provider case) or
`adapters/gemini.py` (an example of a provider whose API shape genuinely
differs from the OpenAI-style chat-message convention) as templates. Use
`httpx` directly, matching every other external-service client in this
codebase (`delivery/executor.py`, `billing/*`) -- don't add a new SDK
dependency unless the vendor's API can't reasonably be called with plain
HTTP.

### 2. Registration

In `backend/app/modules/ai_gateway/registry.py`, add an entry to `_PROVIDERS`:

```python
"acme": ProviderInfo(
    name="acme",
    default_model_env="AI_ACME_MODEL",
    capabilities=frozenset({Capability.CHAT, Capability.STRUCTURED_OUTPUT}),
),
```

Only list capabilities the adapter actually implements (Step 11: "do NOT
assume every model supports everything"). If Acme's models don't support
structured/JSON-mode output, leave `Capability.STRUCTURED_OUTPUT` off the set
-- the gateway will raise `AICapabilityError` for any caller that requests it,
rather than silently producing unvalidatable output.

In `backend/app/modules/ai_gateway/gateway.py`, add the adapter class to
`_ADAPTER_CLASSES`:

```python
_ADAPTER_CLASSES: dict[str, type] = {
    "anthropic": AnthropicAdapter,
    "openai": OpenAIAdapter,
    "gemini": GeminiAdapter,
    "xai": XAIAdapter,
    "acme": AcmeAdapter,
}
```

### 3. Configuration

In `backend/app/core/config.py`, add the provider's credential/model
settings, following the existing `AI_OPENAI_*` / `AI_GEMINI_*` / `AI_XAI_*`
pattern:

```python
AI_ACME_API_KEY: str = ""
AI_ACME_MODEL: str = "acme-large"
```

Document them in `backend/.env.example` next to the others. Never commit a
real key.

`ai_gateway/gateway.py`'s `_resolve_credentials()` needs no changes -- it
already resolves `AI_<PROVIDER>_API_KEY`/`AI_<PROVIDER>_MODEL` generically by
uppercasing the provider name, so `"acme"` automatically resolves to
`AI_ACME_API_KEY`/`AI_ACME_MODEL`.

Once these three pieces exist, `AI_PROVIDER=acme` (as the primary) or
`AI_FALLBACK_PROVIDER=acme` (as the fallback) both work immediately --
Copilot, RCA, and Insights AI analysis all pick it up automatically through
the existing `get_ai_provider()` / gateway path with no further code changes.

### 4. Tests

Add adapter tests to `backend/tests/unit/test_ai_gateway_adapters.py` (or a
new file) using `httpx.MockTransport`, following the existing pattern for
each current provider: a happy-path response, the request shape actually
sent (headers, body), and at least one test per normalized error your
adapter can raise (auth, rate limit, unavailable, malformed response).

If real credentials for the new provider are available in your environment,
also run it through the existing `FakeAIProvider`-based end-to-end tests
(`test_insights_ai.py`, `test_copilot.py`) by pointing `AI_PROVIDER` at it in
a local `.env` -- this is the closest thing to Step 37's cross-provider RCA/
Copilot test without adding a live-network CI job.

## What you do NOT need to touch

- `insights/ai/service.py`, `insights/ai/prompt.py`, `insights/ai/schemas.py`
- `insights/copilot/service.py`, `insights/copilot/prompt.py`,
  `insights/copilot/schemas.py`, `insights/copilot/routes.py`
- `workers/insight_tasks.py`
- The frontend (`apps/web`) -- it only ever calls RelayHub's own
  `/insights/intelligence/copilot/chat` endpoint, never a provider directly.
- Any database migration -- no per-provider schema exists; provider/model
  selection is server-side configuration only.
- Prompt-injection defenses, structured-output validation, or citation
  grounding -- all of that lives above the gateway and is provider-independent
  by construction; a new adapter cannot weaken it.

## Capability validation

If a feature ever needs a capability no current provider/model supports
(e.g. vision), the gateway raises `AICapabilityError` before ever calling the
adapter -- callers see this the same way they see any other
`AIProviderError` today (fails safe, no code change required at the call
site). Add the capability to `Capability` in `contracts.py` first, then add
it to the `capabilities` set of whichever providers actually support it.

## Fallback

A provider only needs to be added to `AI_FALLBACK_PROVIDER` handling by being
registered (steps 1-3 above) -- `ai_gateway/gateway.py`'s fallback logic
already works with any two registered providers. Fallback is only attempted
for transient failures (`AITimeoutError`, `AIRateLimitError`,
`AIUnavailableError`, `AIMalformedResponseError`, `AICapabilityError`,
generic `AIProviderError`) -- never for `AIAuthenticationError` or
`AIInvalidRequestError`, since retrying an invalid request or a bad key
against a different provider doesn't fix either problem.
