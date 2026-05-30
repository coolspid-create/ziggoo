from __future__ import annotations

from typing import Any

from ziggoo.models import RecallItem


EMPTY_VALUES = {"", "-", "n/a", "na", "none", "null", "unknown", "미상", "없음"}

SEARCH_ALIAS_RULES: dict[str, tuple[str, ...]] = {
    "스팀청소기": ("스팀 클리너", "스팀기", "steam cleaner"),
    "전기포트": ("무선포트", "전기주전자", "electric kettle"),
    "봉제인형": ("인형", "플러시", "plush toy"),
    "원목 울타리": ("원목 베이비룸", "아기 울타리", "유아 울타리", "wooden playpen"),
    "영유아용 원목 울타리": ("원목 베이비룸", "아기 울타리", "baby playpen"),
    "치발기": ("아기 치발기", "유아 치발기", "teether"),
    "딸랑이": ("아기 딸랑이", "유아 딸랑이", "rattle"),
}


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return "" if text.casefold() in EMPTY_VALUES else text


def build_scan_query(recall: dict[str, Any]) -> str:
    model = clean_text(recall.get("model_name") or recall.get("model"))
    if model:
        return model

    product = clean_text(recall.get("product_name") or recall.get("product_name_original"))
    brand = clean_text(recall.get("brand_name") or recall.get("brand"))
    if brand and product and brand.casefold() not in product.casefold():
        return f"{brand} {product}"
    return product or brand


def build_verify_term(recall: dict[str, Any]) -> str:
    return ""


def _append_unique(items: list[str], value: Any) -> None:
    text = clean_text(value)
    if not text:
        return
    folded = text.casefold()
    if any(item.casefold() == folded for item in items):
        return
    items.append(text)


def build_search_queries(recall: dict[str, Any], limit: int = 8) -> list[str]:
    queries: list[str] = []
    product = clean_text(recall.get("product_name") or recall.get("product_name_original"))
    original_product = clean_text(recall.get("product_name_original"))
    brand = clean_text(recall.get("brand_name") or recall.get("brand"))
    model = clean_text(recall.get("model_name") or recall.get("model"))
    base_query = clean_text(recall.get("scan_query")) or build_scan_query(recall)

    _append_unique(queries, base_query)
    _append_unique(queries, model)
    if brand and product and brand.casefold() not in product.casefold():
        _append_unique(queries, f"{brand} {product}")
    _append_unique(queries, product)
    _append_unique(queries, original_product)
    _append_unique(queries, brand)

    haystack = " ".join(
        value for value in (product, original_product, brand, model, base_query) if value
    ).casefold()
    for trigger, aliases in SEARCH_ALIAS_RULES.items():
        if trigger.casefold() not in haystack:
            continue
        for alias in aliases:
            if brand:
                _append_unique(queries, f"{brand} {alias}")
            _append_unique(queries, alias)

    return queries[: max(1, limit)]


def recall_to_scan_payload(recall: dict[str, Any]) -> dict[str, Any]:
    if "scan_query_override" in recall:
        query = clean_text(recall.get("scan_query_override"))
    else:
        query = (
            clean_text(recall.get("query"))
            or clean_text(recall.get("scan_query"))
            or build_scan_query(recall)
        )

    if "scan_verify_override" in recall:
        verify = clean_text(recall.get("scan_verify_override"))
    else:
        verify = (
            clean_text(recall.get("verify"))
            or clean_text(recall.get("scan_verify"))
            or build_verify_term(recall)
        )
    source_id = clean_text(recall.get("source_id")) or clean_text(recall.get("id"))
    model_name = clean_text(recall.get("model_name") or recall.get("model"))

    return {
        "query": query,
        "verify": verify or None,
        "model_name": model_name or None,
        "source_id": source_id or None,
        "metadata": {
            "recall": recall,
            "product_name": clean_text(recall.get("product_name")),
            "brand_name": clean_text(recall.get("brand_name")),
            "source": clean_text(recall.get("source")),
            "guid": clean_text(recall.get("guid")),
            "published_date": clean_text(recall.get("published_date")),
            "risk_level": clean_text(recall.get("risk_level")),
            "hazard_type": clean_text(recall.get("hazard_type")),
        },
    }


def recall_to_item(recall: dict[str, Any]) -> RecallItem:
    payload = recall_to_scan_payload(recall)
    return RecallItem(
        query=payload["query"],
        verify=payload["verify"],
        model_name=payload["model_name"],
        source_id=payload["source_id"],
        metadata=payload["metadata"],
    )


def enrich_recall(recall: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(recall)
    enriched["scan_query"] = build_scan_query(recall)
    enriched["scan_verify"] = build_verify_term(recall)
    enriched["display_title"] = (
        clean_text(recall.get("product_name"))
        or clean_text(recall.get("product_name_original"))
        or clean_text(recall.get("model_name"))
        or "이름 없는 리콜"
    )
    return enriched
