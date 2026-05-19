from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RecallItem:
    query: str
    verify: str | None = None
    model_name: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "RecallItem":
        query = (
            payload.get("query")
            or payload.get("keyword")
            or payload.get("model")
            or payload.get("model_name")
            or payload.get("product_name")
            or payload.get("name")
            or ""
        )
        verify = (
            payload.get("verify")
            or payload.get("brand")
            or payload.get("manufacturer")
            or payload.get("maker")
        )
        source_id = payload.get("source_id") or payload.get("id") or payload.get("recall_id")
        return cls(
            query=str(query).strip(),
            verify=str(verify).strip() if verify else None,
            model_name=payload.get("model_name") or payload.get("model"),
            source_id=str(source_id) if source_id is not None else None,
            metadata={k: v for k, v in payload.items() if k not in {"query", "verify"}},
        )


@dataclass(slots=True)
class ProductHit:
    title: str
    url: str | None = None
    price: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScanResult:
    platform: str
    query: str
    verify: str | None
    status: str
    matches: list[ProductHit] = field(default_factory=list)
    searched_items: int = 0
    screenshot: str | None = None
    error: str | None = None
    source_id: str | None = None
    model_name: str | None = None
    searched_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
