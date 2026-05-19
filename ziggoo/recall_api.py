from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

import config
from ziggoo.models import RecallItem


class RecallApiClient:
    def __init__(
        self,
        api_base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = config.REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self.api_base_url = (api_base_url or config.API_BASE_URL).strip()
        self.api_key = api_key if api_key is not None else config.API_KEY
        self.timeout = timeout

    @classmethod
    def for_recall_hub(
        cls,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: int = config.REQUEST_TIMEOUT_SECONDS,
    ) -> "RecallApiClient":
        root = (base_url or config.RECALL_HUB_BASE_URL).rstrip("/")
        return cls(api_base_url=f"{root}/api/v1/recalls", api_key=api_key, timeout=timeout)

    def fetch_recall_items(self) -> list[RecallItem]:
        if not self.api_base_url:
            return []

        payload = self._get_json(self.api_base_url)
        return self._parse_items(payload)

    def list_recalls(
        self,
        *,
        q: str | None = None,
        source: str | None = None,
        risk_bucket: str | None = None,
        korea_relevance: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {
            "limit": max(1, min(limit, 100)),
            "offset": max(0, offset),
            "order": "published_date",
            "direction": "desc",
        }
        if q:
            params["q"] = q
        if source:
            params["source"] = source
        if risk_bucket:
            params["risk_bucket"] = risk_bucket
        if korea_relevance:
            params["korea_relevance"] = korea_relevance
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        return self._get_json(self.api_base_url, params=params)

    def recent_recalls(
        self,
        *,
        days: int = 30,
        limit: int = 50,
        source: str | None = None,
    ) -> dict[str, Any]:
        endpoint = urljoin(self.api_base_url.rstrip("/") + "/", "recent")
        params: dict[str, Any] = {
            "days": max(1, min(days, 365)),
            "limit": max(1, min(limit, 200)),
        }
        if source:
            params["source"] = source
        return self._get_json(endpoint, params=params)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
            headers["X-API-Key"] = self.api_key
        return headers

    def _get_json(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_url = url
        if params:
            separator = "&" if "?" in request_url else "?"
            request_url = f"{request_url}{separator}{urlencode(params)}"
        request = Request(request_url, headers=self._headers(), method="GET")
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise ValueError(f"Recall API request failed: HTTP {exc.code} {body[:300]}") from exc
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("Recall API response must be a JSON object.")
        return payload

    def _parse_items(self, payload: Any) -> list[RecallItem]:
        if isinstance(payload, dict):
            payload = (
                payload.get("items")
                or payload.get("data")
                or payload.get("results")
                or payload.get("recalls")
                or []
            )

        if not isinstance(payload, list):
            raise ValueError("Recall API response must contain an item list.")

        items: list[RecallItem] = []
        for entry in payload:
            if isinstance(entry, str):
                items.append(RecallItem(query=entry))
            elif isinstance(entry, dict):
                item = RecallItem.from_mapping(entry)
                if item.query:
                    items.append(item)
        return items
