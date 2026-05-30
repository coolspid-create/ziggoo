from __future__ import annotations

from datetime import datetime
from typing import Any

import config
from ziggoo.browser import build_browser_context
from ziggoo.matching import normalize_text
from ziggoo.models import RecallItem, ScanResult
from ziggoo.recall_mapping import build_search_queries, clean_text, recall_to_scan_payload
from ziggoo.scanners import SCANNER_REGISTRY


PRODUCT_SEARCH_PLATFORMS = ("elevenst", "coupang", "gmarket", "naver")


def _tokens(value: str) -> list[str]:
    normalized = normalize_text(value)
    return [token for token in normalized.replace("/", " ").replace(",", " ").split() if len(token) >= 2]


def _score_product_hit(hit: dict[str, Any], recall: dict[str, Any], query: str) -> tuple[int, list[str]]:
    title = normalize_text(str(hit.get("title") or ""))
    url = normalize_text(str(hit.get("url") or ""))
    haystack = f"{title} {url}"
    reasons = ["제품명 검색 결과"]
    score = 55

    query_tokens = _tokens(query)
    if query_tokens:
        matched = [token for token in query_tokens if token in haystack]
        if matched:
            score += min(20, round(20 * len(matched) / len(query_tokens)))
            reasons.append(f"검색어 토큰 {len(matched)}/{len(query_tokens)}개")

    for label, value, points in (
        ("모델", recall.get("model_name") or recall.get("model"), 18),
        ("브랜드", recall.get("brand_name") or recall.get("brand") or recall.get("manufacturer"), 14),
        ("제품명", recall.get("product_name") or recall.get("product_name_original") or recall.get("display_title"), 14),
    ):
        tokens = _tokens(clean_text(value))
        if not tokens:
            continue
        matched = [token for token in tokens if token in haystack]
        if matched:
            score += min(points, round(points * len(matched) / len(tokens)))
            reasons.append(f"{label} 토큰 {len(matched)}/{len(tokens)}개")

    return min(score, 100), reasons


def _scan_result_to_candidates(result: ScanResult, recall: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for hit in result.matches:
        payload = {
            "platform": result.platform,
            "platform_label": {
                "elevenst": "11번가",
                "coupang": "쿠팡",
                "gmarket": "G마켓",
                "naver": "네이버",
            }.get(result.platform, result.platform),
            "query": result.query,
            "title": hit.title,
            "url": hit.url or "",
            "price": hit.price or "",
            "source": "product_search",
            "searched_at": result.searched_at,
        }
        score, reasons = _score_product_hit(payload, recall, result.query)
        payload["score"] = score
        payload["status"] = "text_matched" if score >= config.IMAGE_SEARCH_MATCH_THRESHOLD else "text_candidate"
        payload["reasons"] = reasons
        candidates.append(payload)
    return candidates


def _dedupe_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for candidate in candidates:
        key = (
            str(candidate.get("platform") or ""),
            str(candidate.get("url") or candidate.get("title") or "").split("#", 1)[0].casefold(),
        )
        existing = merged.get(key)
        if existing is None or int(candidate.get("score") or 0) > int(existing.get("score") or 0):
            merged[key] = candidate
            continue
        queries = existing.setdefault("queries", [existing.get("query")])
        if candidate.get("query") and candidate.get("query") not in queries:
            queries.append(candidate.get("query"))
    return sorted(merged.values(), key=lambda item: int(item.get("score") or 0), reverse=True)


async def _run_product_search_async(
    recall: dict[str, Any],
    *,
    target_platforms: list[str] | None = None,
    max_items: int = 8,
    max_queries: int = 6,
) -> dict[str, Any]:
    platforms = [platform for platform in (target_platforms or list(PRODUCT_SEARCH_PLATFORMS)) if platform in SCANNER_REGISTRY]
    queries = build_search_queries(recall, limit=max_queries)
    scan_payload = recall_to_scan_payload(recall)
    results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []

    if not queries:
        return {
            "status": "text_no_query",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "recall": recall,
            "queries": [],
            "results": [],
            "candidates": [],
            "candidate_count": 0,
        }

    async with build_browser_context(headless=config.HEADLESS, block_heavy_assets=True) as context:
        scanners = {
            platform: SCANNER_REGISTRY[platform](
                context,
                max_items=max(1, max_items),
                manual_verify_blocked=False,
            )
            for platform in platforms
        }
        for query in queries:
            item = RecallItem(
                query=query,
                verify=scan_payload.get("verify"),
                model_name=scan_payload.get("model_name"),
                source_id=scan_payload.get("source_id"),
                metadata=scan_payload.get("metadata") or {},
            )
            for platform, scanner in scanners.items():
                try:
                    result = await scanner.scan(item)
                    results.append(
                        {
                            "platform": platform,
                            "query": query,
                            "status": result.status,
                            "searched_items": result.searched_items,
                            "match_count": len(result.matches),
                            "error": result.error,
                            "screenshot": result.screenshot,
                        }
                    )
                    candidates.extend(_scan_result_to_candidates(result, recall))
                except Exception as exc:
                    results.append(
                        {
                            "platform": platform,
                            "query": query,
                            "status": "error",
                            "searched_items": 0,
                            "match_count": 0,
                            "error": str(exc),
                        }
                    )

    candidates = _dedupe_candidates(candidates)
    status = "text_matched" if candidates else "text_no_match"
    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "recall": recall,
        "queries": queries,
        "results": results,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


def run_product_search(
    recall: dict[str, Any],
    *,
    target_platforms: list[str] | None = None,
    max_items: int = 8,
    max_queries: int = 6,
) -> dict[str, Any]:
    import asyncio

    return asyncio.run(
        _run_product_search_async(
            recall,
            target_platforms=target_platforms,
            max_items=max_items,
            max_queries=max_queries,
        )
    )
