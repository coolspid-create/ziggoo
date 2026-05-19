from __future__ import annotations

from typing import Any

from ziggoo.models import RecallItem


EMPTY_VALUES = {"", "-", "n/a", "na", "none", "null", "unknown", "미상", "없음"}


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
