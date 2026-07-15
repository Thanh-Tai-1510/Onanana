from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from src.onanana.ollama.models import (
    ChatRequest,
    CopyRequest,
    CreateRequest,
    DeleteRequest,
    EmbedRequest,
    GenerateRequest,
    PullRequest,
    PushRequest,
    ShowRequest,
)

logger = logging.getLogger(__name__)

ENDPOINTS = {
    "generate": {"method": "POST", "model": GenerateRequest},
    "chat": {"method": "POST", "model": ChatRequest},
    "embeddings": {"method": "POST", "model": EmbedRequest},
    "embed": {"method": "POST", "model": EmbedRequest},
    "create": {"method": "POST", "model": CreateRequest},
    "pull": {"method": "POST", "model": PullRequest},
    "push": {"method": "POST", "model": PushRequest},
    "show": {"method": "POST", "model": ShowRequest},
    "copy": {"method": "POST", "model": CopyRequest},
    "delete": {"method": "DELETE", "model": DeleteRequest},
}

GET_PREFIXES = (
    "api/version",
    "api/tags",
    "api/ps",
    "v1/models",
)


class OllamaRequestBuilder:
    def __init__(self, client: httpx.AsyncClient):
        self._client = client

    def build_request(
        self,
        path: str,
        base_url: str,
        body: dict[str, Any] | None,
        *,
        model_override: str | None = None,
        headers: dict[str, str] | None = None,
        method: str | None = None,
    ) -> httpx.Request:
        api_path = path.lstrip("/")
        url = f"{base_url.rstrip('/')}/{api_path}"
        payload = dict(body) if body else None

        if payload is not None and model_override is not None:
            payload["model"] = model_override

        resolved_method = (method or self._method_for_path(api_path)).upper()
        logger.debug("Building %s %s", resolved_method, url)
        kwargs: dict[str, Any] = {"headers": headers}
        if resolved_method != "GET" and payload is not None:
            kwargs["json"] = payload
        elif resolved_method == "GET" and payload:
            kwargs["params"] = payload
        return self._client.build_request(resolved_method, url, **kwargs)

    async def send_request(
        self,
        path: str,
        base_url: str,
        body: dict[str, Any] | None,
        *,
        model_override: str | None = None,
        headers: dict[str, str] | None = None,
        stream: bool = True,
        method: str | None = None,
    ) -> httpx.Response:
        req = self.build_request(
            path,
            base_url,
            body,
            model_override=model_override,
            headers=headers,
            method=method,
        )
        return await self._client.send(req, stream=stream)

    @staticmethod
    def _method_for_path(api_path: str) -> str:
        normalized = api_path.lstrip("/")
        for prefix in GET_PREFIXES:
            if normalized == prefix or normalized.startswith(prefix + "/"):
                return "GET"
        for name, info in ENDPOINTS.items():
            if normalized.endswith(f"/api/{name}") or normalized == f"api/{name}":
                return info["method"]
            if normalized.endswith(f"/v1/{name}") or normalized == f"v1/{name}":
                return info["method"]
        return "POST"

    @staticmethod
    def parse_model_field(body: dict[str, Any] | None) -> str:
        return (body or {}).get("model", "")

    @staticmethod
    def is_streaming(body: dict[str, Any] | None) -> bool:
        return bool((body or {}).get("stream", False))

    @staticmethod
    def serialize_stream_chunk(data: dict[str, Any]) -> bytes:
        return (json.dumps(data, ensure_ascii=False) + "\n").encode()
