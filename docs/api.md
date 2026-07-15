# API Reference

Base: `http://localhost:11435`

All endpoints match the [Ollama API](https://github.com/ollama/ollama/blob/main/docs/api.md).

## Routing

| Backend | Base URL | Auth |
|---|---|---|
| Local | `http://localhost:11434` | None |
| Cloud | `WARP_CLOUD_OLLAMA_BASE_URL` | `Authorization: Bearer <token>` |

### Rules

1. **Model suffix** — model ending in the configured suffix (default `-cloud`) routes to cloud; suffix is stripped before forwarding
2. **`?source=` param** — overrides model-based routing. `?source=local` forces local (model name kept as-is). `?source=cloud` forces cloud (suffix stripped). Invalid values → `422`

Cloud requires URL + token. Missing either → `503`.

## Model name behavior

| Request | Route | model forwarded |
|---|---|---|
| `model: "gemma4:26b"` | local | `gemma4:26b` |
| `model: "gemma4:31b-cloud"` | cloud | `gemma4:31b` |
| `model: "gemma4:31b-cloud", ?source=local` | local | `gemma4:31b-cloud` (kept) |
| `model: "gemma4:26b", ?source=cloud` | cloud | `gemma4:26b` |

The suffix is configurable via `WARP_CLOUD_MODEL_SUFFIX` (default `-cloud`).

## Endpoints

### Native Ollama (`/api/*`)

| Method | Path | Notes |
|---|---|---|
| `GET` | `/api/version` | `?source=local\|cloud` |
| `GET` | `/api/tags` | List models |
| `GET` | `/api/ps` | Running models |
| `POST` | `/api/chat` | Chat |
| `POST` | `/api/generate` | Completion (`messages`→`prompt`/`system` conversion) |
| `POST` | `/api/embed`, `/api/embeddings` | Embeddings |
| `POST` | `/api/create`, `/api/pull`, `/api/push`, `/api/show`, `/api/copy` | Model management |
| `DELETE` | `/api/delete` | Delete model |
| `*` | `/api/{rest}` | Catch-all proxy for other native paths |

### OpenAI-compatible (`/v1/*`)

| Method | Path | Notes |
|---|---|---|
| `POST` | `/v1/chat/completions` | OpenAI chat |
| `POST` | `/v1/completions` | OpenAI completions |
| `POST` | `/v1/embeddings` | OpenAI embeddings |
| `POST` | `/v1/responses` | OpenAI responses |
| `GET` | `/v1/models` | List models (`?source=`) |
| `GET` | `/v1/models/{model}` | Show model (`-cloud` suffix routing applies) |
| `*` | `/v1/{rest}` | Catch-all proxy for other OpenAI-compatible paths |

Streaming: `/api/*` → `application/x-ndjson`; `/v1/*` → `text/event-stream`.

### `GET /api/version`

```python
r = requests.get("http://localhost:11435/api/version")
r = requests.get("http://localhost:11435/api/version?source=cloud")
```

### `GET /api/tags`

```python
r = requests.get("http://localhost:11435/api/tags")
r = requests.get("http://localhost:11435/api/tags?source=cloud")
```

### `POST /api/{chat,generate,embeddings,create,pull,push,show,copy}`

```python
import requests

# Local model
r = requests.post("http://localhost:11435/api/chat", json={
    "model": "gemma4:26b",
    "messages": [{"role": "user", "content": "hi"}],
})

# Cloud via -cloud suffix
r = requests.post("http://localhost:11435/api/chat", json={
    "model": "gemma4:31b-cloud",
    "messages": [{"role": "user", "content": "hi"}],
})

# Cloud via ?source=
r = requests.post("http://localhost:11435/api/generate?source=cloud", json={
    "model": "gemma4:26b",
    "prompt": "hello",
})
```

**Note:** The `/api/generate` endpoint accepts `messages` in the same format as `/api/chat`. The proxy converts `messages` → `prompt`/`system` before forwarding.

```python
r = requests.post("http://localhost:11435/api/generate", json={
    "model": "gemma4:31b-cloud",
    "messages": [
        {"role": "system", "content": "You are a pirate."},
        {"role": "user", "content": "What is the capital of France?"},
    ],
    "stream": False,
})
```

### `POST /v1/chat/completions`

```python
r = requests.post("http://localhost:11435/v1/chat/completions", json={
    "model": "gemma4:31b-cloud",
    "messages": [{"role": "user", "content": "hi"}],
    "stream": False,
})
```

OpenAI SDK:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:11435/v1", api_key="ollama")
r = client.chat.completions.create(
    model="gemma4:26b",
    messages=[{"role": "user", "content": "hi"}],
)
```

### `DELETE /api/delete`

```python
r = requests.delete("http://localhost:11435/api/delete", json={"model": "gemma4:26b"})
```

## Errors

| Status | Meaning |
|---|---|
| `429` | All cloud keys locked or none available |
| `502` | Backend unreachable |
| `503` | Cloud URL or key missing |
| `504` | Backend timed out |
| `422` | Invalid `source` value |

## Auth

1. `secrets/keys.txt` (round-robin with health checks)
2. `WARP_CLOUD_API_KEY` env var
3. `503` if neither

### Key locking

Keys are auto-locked on `429` responses or 3 consecutive timeouts. Locked keys are stored in
`secrets/ollama_keys_lock.txt` with a timestamp. Unlocking happens automatically via:
- Background cleanup every **10 minutes**
- Lock file check on **every endpoint call**
- **5-hour expiry** of lock entries
