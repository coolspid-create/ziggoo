from __future__ import annotations

import base64
import html
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import config
from ziggoo.recall_mapping import build_search_queries, clean_text, recall_to_scan_payload


VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
IMAGE_ASSET_EXTENSIONS = (".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp")

MARKET_DOMAINS: dict[str, tuple[str, ...]] = {
    "elevenst": ("11st.co.kr", "www.11st.co.kr"),
    "coupang": ("coupang.com", "www.coupang.com"),
    "gmarket": (
        "gmarket.co.kr",
        "www.gmarket.co.kr",
        "item.gmarket.co.kr",
        "global.gmarket.co.kr",
        "gsearch.gmarket.co.kr",
    ),
    "naver": ("shopping.naver.com", "smartstore.naver.com"),
}

MARKET_HOST_KEYWORDS: dict[str, tuple[str, ...]] = {
    "elevenst": ("11st",),
    "coupang": ("coupang",),
    "gmarket": ("gmarket",),
    "naver": ("naver", "smartstore"),
}

PLATFORM_LABELS = {
    "elevenst": "11번가",
    "coupang": "쿠팡",
    "gmarket": "G마켓",
    "naver": "네이버",
}

RELATED_COMMERCE_DOMAINS: dict[str, tuple[str, ...]] = {
    "amazon": ("amazon.com", "www.amazon.com", "amazon.co.jp", "www.amazon.co.jp"),
    "ebay": ("ebay.com", "www.ebay.com"),
    "alibaba": ("alibaba.com", "www.alibaba.com"),
    "aliexpress": ("aliexpress.com", "www.aliexpress.com"),
    "walmart": ("walmart.com", "www.walmart.com"),
    "etsy": ("etsy.com", "www.etsy.com"),
    "temu": ("temu.com", "www.temu.com"),
    "rakuten": ("rakuten.co.jp", "www.rakuten.co.jp", "search.rakuten.co.jp"),
    "naver": ("shopping.naver.com", "smartstore.naver.com"),
    "auction": ("auction.co.kr", "www.auction.co.kr"),
    "lotteon": ("lotteon.com", "www.lotteon.com"),
    "ssg": ("ssg.com", "www.ssg.com"),
}

RELATED_COMMERCE_LABELS = {
    "amazon": "Amazon",
    "ebay": "eBay",
    "alibaba": "Alibaba",
    "aliexpress": "AliExpress",
    "walmart": "Walmart",
    "etsy": "Etsy",
    "temu": "Temu",
    "rakuten": "Rakuten",
    "naver": "네이버 쇼핑",
    "auction": "옥션",
    "lotteon": "롯데ON",
    "ssg": "SSG",
    "visual": "유사 이미지",
}


class ImageSearchError(RuntimeError):
    pass


def _strip_markup(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return " ".join(text.split())


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", _strip_markup(value).casefold()).strip()


def _tokens(value: str) -> list[str]:
    normalized = re.sub(r"[^0-9a-zA-Z가-힣]+", " ", value or "").casefold()
    seen: set[str] = set()
    tokens: list[str] = []
    for token in normalized.split():
        if len(token) < 2:
            continue
        if token in seen:
            continue
        seen.add(token)
        tokens.append(token)
    return tokens


def _hostname(url: str) -> str:
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def _detect_platform(url: str) -> str | None:
    host = _hostname(url).casefold()
    if not host:
        return None
    for platform, domains in MARKET_DOMAINS.items():
        for domain in domains:
            if host == domain or host.endswith(f".{domain}"):
                return platform
    for platform, keywords in MARKET_HOST_KEYWORDS.items():
        if any(keyword in host for keyword in keywords):
            return platform
    return None


def _detect_related_commerce(url: str) -> str | None:
    host = _hostname(url).casefold()
    if not host:
        return None
    for platform, domains in RELATED_COMMERCE_DOMAINS.items():
        for domain in domains:
            if host == domain or host.endswith(f".{domain}"):
                return platform
    return None


def _looks_like_image_asset_url(url: str) -> bool:
    try:
        path = urlparse(url).path.casefold()
    except Exception:
        return False
    return path.endswith(IMAGE_ASSET_EXTENSIONS)


def _market_page_from_image_asset(platform: str | None, url: str) -> str:
    if platform != "gmarket":
        return ""
    try:
        path_parts = [part for part in urlparse(url).path.split("/") if part]
    except Exception:
        return ""
    for part in reversed(path_parts):
        if re.fullmatch(r"\d{8,12}", part):
            return f"https://item.gmarket.co.kr/Item?goodscode={part}"
    return ""


def _is_market_page_url(url: str) -> bool:
    return bool(_detect_platform(url)) and not _looks_like_image_asset_url(url)


def _is_shopping_product_result_url(url: str) -> bool:
    platform = _detect_platform(url)
    if platform:
        return _is_market_page_url(url) or bool(_market_page_from_image_asset(platform, url))
    commerce = _detect_related_commerce(url)
    return bool(commerce) and not _looks_like_image_asset_url(url) and _looks_like_related_product_url(commerce, url)


def _shopping_product_display_url(url: str) -> str:
    platform = _detect_platform(url)
    if platform and _looks_like_image_asset_url(url):
        return _market_page_from_image_asset(platform, url) or url
    return url


def _looks_like_product_url(platform: str | None, url: str) -> bool:
    normalized = url.casefold()
    if platform == "elevenst":
        return "/products/" in normalized or "/product/" in normalized
    if platform == "coupang":
        return "/vp/products/" in normalized or "itemid=" in normalized
    if platform == "gmarket":
        return "item.gmarket.co.kr" in normalized or "/item/" in normalized or "goodscode=" in normalized
    if platform == "naver":
        return "/products/" in normalized or "/catalog/" in normalized
    return False


def _looks_like_related_product_url(platform: str | None, url: str) -> bool:
    normalized = url.casefold()
    if platform == "amazon":
        return "/dp/" in normalized or "/gp/product/" in normalized or "/gp/aw/d/" in normalized
    if platform == "ebay":
        return "/itm/" in normalized
    if platform == "alibaba":
        return "/product-detail/" in normalized
    if platform == "aliexpress":
        return "/item/" in normalized
    if platform == "walmart":
        return "/ip/" in normalized
    if platform == "etsy":
        return "/listing/" in normalized
    if platform == "temu":
        return "/goods.html" in normalized or "/product/" in normalized
    if platform == "rakuten":
        return "/item/" in normalized or "/product/" in normalized
    if platform == "naver":
        return "/products/" in normalized or "/catalog/" in normalized
    if platform == "auction":
        return "/item/" in normalized or "itemno=" in normalized
    if platform == "lotteon":
        return "/p/product/" in normalized or "goodsno=" in normalized
    if platform == "ssg":
        return "/item/itemview.ssg" in normalized or "itemid=" in normalized
    return False


def find_recall_image_urls(recall: dict[str, Any]) -> list[str]:
    image_keys = (
        "image_url",
        "image",
        "image_1",
        "image_2",
        "image_3",
        "image_4",
        "image_5",
        "image1",
        "image2",
        "thumbnail",
        "thumbnail_url",
        "main_image_url",
        "product_image_url",
    )
    urls: list[str] = []

    def add(value: Any) -> None:
        text = clean_text(value)
        if text and text not in urls:
            urls.append(text)

    for key in image_keys:
        add(recall.get(key))

    images = recall.get("images")
    if isinstance(images, list):
        for image in images:
            if isinstance(image, str):
                add(image)
            if isinstance(image, dict):
                for key in image_keys:
                    before = len(urls)
                    add(image.get(key))
                    if len(urls) > before:
                        break
    return urls


def find_recall_image_url(recall: dict[str, Any]) -> str:
    urls = find_recall_image_urls(recall)
    return urls[0] if urls else ""


def _recall_terms(recall: dict[str, Any]) -> dict[str, Any]:
    scan_payload = recall_to_scan_payload(recall)
    brand = clean_text(recall.get("brand_name") or recall.get("brand") or recall.get("manufacturer"))
    model = clean_text(recall.get("model_name") or recall.get("model") or scan_payload.get("model_name"))
    product = clean_text(
        recall.get("product_name")
        or recall.get("product_name_original")
        or recall.get("display_title")
        or scan_payload.get("query")
    )
    query = clean_text(recall.get("query") or recall.get("scan_query") or scan_payload.get("query"))
    verify = clean_text(recall.get("verify") or recall.get("scan_verify") or scan_payload.get("verify"))
    return {
        "brand": brand,
        "model": model,
        "product": product,
        "query": query,
        "verify": verify,
        "tokens": {
            "brand": _tokens(brand),
            "model": _tokens(model),
            "product": _tokens(product),
            "query": _tokens(query),
            "verify": _tokens(verify),
        },
    }


def _download_image(url: str) -> bytes:
    request = Request(
        url,
        headers={"User-Agent": config.USER_AGENTS[0], "Accept": "image/*,*/*;q=0.8"},
    )
    with urlopen(request, timeout=config.REQUEST_TIMEOUT_SECONDS) as response:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                raise ImageSearchError("이미지 파일이 너무 큽니다. 8MB 이하 이미지를 사용하세요.")
            chunks.append(chunk)
    return b"".join(chunks)


def _image_payload(image_url: str = "", image_path: str = "", image_base64: str = "") -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if image_base64:
        content = image_base64.split(",", 1)[-1].strip()
        return {"content": content}, warnings

    if image_path:
        path = Path(image_path)
        if not path.is_file():
            raise ImageSearchError("이미지 파일을 찾을 수 없습니다.")
        raw = path.read_bytes()
        if len(raw) > MAX_IMAGE_BYTES:
            raise ImageSearchError("이미지 파일이 너무 큽니다. 8MB 이하 이미지를 사용하세요.")
        return {"content": base64.b64encode(raw).decode("ascii")}, warnings

    if not image_url:
        raise ImageSearchError("이미지 URL 또는 이미지 파일이 필요합니다.")

    if image_url.startswith(("http://", "https://")):
        try:
            raw = _download_image(image_url)
            return {"content": base64.b64encode(raw).decode("ascii")}, warnings
        except Exception as exc:
            warnings.append(f"이미지를 직접 내려받지 못해 Vision 원격 URL 방식으로 재시도합니다: {exc}")
            return {"source": {"imageUri": image_url}}, warnings

    path = Path(image_url)
    if path.is_file():
        raw = path.read_bytes()
        if len(raw) > MAX_IMAGE_BYTES:
            raise ImageSearchError("이미지 파일이 너무 큽니다. 8MB 이하 이미지를 사용하세요.")
        return {"content": base64.b64encode(raw).decode("ascii")}, warnings

    raise ImageSearchError("지원하지 않는 이미지 경로입니다.")


def call_vision_web_detection(
    *,
    api_key: str,
    image_url: str = "",
    image_path: str = "",
    image_base64: str = "",
    max_results: int = config.IMAGE_SEARCH_MAX_RESULTS,
) -> tuple[dict[str, Any], list[str]]:
    if not api_key:
        raise ImageSearchError("Google Vision API 키가 필요합니다.")

    image, warnings = _image_payload(
        image_url=image_url,
        image_path=image_path,
        image_base64=image_base64,
    )
    payload = {
        "requests": [
            {
                "image": image,
                "features": [
                    {
                        "type": "WEB_DETECTION",
                        "maxResults": max(1, min(int(max_results or 20), 50)),
                    }
                ],
            }
        ]
    }
    request = Request(
        f"{VISION_ENDPOINT}?{urlencode({'key': api_key})}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=config.REQUEST_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()
            raw_body = response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        status_code = exc.code
        raw_body = exc.read().decode("utf-8", errors="replace")
    try:
        body = json.loads(raw_body)
    except ValueError as exc:
        raise ImageSearchError(f"Vision API 응답을 읽지 못했습니다: {raw_body[:300]}") from exc

    if status_code < 200 or status_code >= 300:
        message = body.get("error", {}).get("message") if isinstance(body, dict) else None
        raise ImageSearchError(message or f"Vision API 요청 실패: HTTP {status_code}")

    annotation = ((body.get("responses") or [{}])[0] or {}) if isinstance(body, dict) else {}
    if annotation.get("error"):
        raise ImageSearchError(annotation["error"].get("message") or "Vision API 분석 실패")
    return annotation.get("webDetection") or {}, warnings


def _web_entities(web_detection: dict[str, Any]) -> list[dict[str, Any]]:
    entities = []
    for entity in web_detection.get("webEntities") or []:
        if not isinstance(entity, dict):
            continue
        description = _strip_markup(str(entity.get("description") or ""))
        if not description:
            continue
        entities.append(
            {
                "description": description,
                "score": float(entity.get("score") or 0),
            }
        )
    return entities


def _best_guess_labels(web_detection: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for label in web_detection.get("bestGuessLabels") or []:
        if not isinstance(label, dict):
            continue
        text = _strip_markup(str(label.get("label") or ""))
        if text:
            labels.append(text)
    return labels


def _matching_count(page: dict[str, Any], key: str) -> int:
    value = page.get(key)
    return len(value) if isinstance(value, list) else 0


def _list_count(web_detection: dict[str, Any], key: str) -> int:
    value = web_detection.get(key)
    return len(value) if isinstance(value, list) else 0


def _detected_url_rows(web_detection: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for page in web_detection.get("pagesWithMatchingImages") or []:
        if not isinstance(page, dict):
            continue
        url = str(page.get("url") or "")
        if url:
            rows.append(
                {
                    "source": "pagesWithMatchingImages",
                    "url": url,
                    "title": _strip_markup(str(page.get("pageTitle") or "")),
                    "domain": _hostname(url),
                    "platform": _detect_platform(url),
                    "is_image_asset": _looks_like_image_asset_url(url),
                }
            )
        for key in ("fullMatchingImages", "partialMatchingImages"):
            for image in page.get(key) or []:
                if not isinstance(image, dict):
                    continue
                image_url = str(image.get("url") or "")
                if image_url:
                    rows.append(
                        {
                            "source": f"page.{key}",
                            "url": image_url,
                            "title": _strip_markup(str(page.get("pageTitle") or "")),
                            "domain": _hostname(image_url),
                            "platform": _detect_platform(image_url),
                            "parent_url": url,
                            "is_image_asset": _looks_like_image_asset_url(image_url),
                        }
                    )

    for key in ("fullMatchingImages", "partialMatchingImages", "visuallySimilarImages"):
        for image in web_detection.get(key) or []:
            if not isinstance(image, dict):
                continue
            url = str(image.get("url") or "")
            if url:
                rows.append(
                    {
                        "source": key,
                        "url": url,
                        "title": "",
                        "domain": _hostname(url),
                        "platform": _detect_platform(url),
                        "is_image_asset": _looks_like_image_asset_url(url),
                    }
                )
    return rows


def _vision_diagnostics(
    web_detection: dict[str, Any],
    requested_platforms: set[str],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    rows = _detected_url_rows(web_detection)
    shopping_rows = [row for row in rows if _is_shopping_product_result_url(str(row.get("url") or ""))]
    domain_counts = Counter(row["domain"] for row in shopping_rows if row.get("domain"))
    source_counts = Counter(row["source"] for row in rows if row.get("source"))
    platform_counts = {platform: 0 for platform in sorted(requested_platforms)}
    platform_asset_counts = {platform: 0 for platform in sorted(requested_platforms)}
    for row in rows:
        platform = row.get("platform")
        if platform in platform_counts and not row.get("is_image_asset"):
            platform_counts[platform] += 1
        elif platform in platform_asset_counts:
            platform_asset_counts[platform] += 1

    counts = {
        "web_entities": _list_count(web_detection, "webEntities"),
        "best_guess_labels": _list_count(web_detection, "bestGuessLabels"),
        "pages_with_matching_images": _list_count(web_detection, "pagesWithMatchingImages"),
        "full_matching_images": _list_count(web_detection, "fullMatchingImages"),
        "partial_matching_images": _list_count(web_detection, "partialMatchingImages"),
        "visually_similar_images": _list_count(web_detection, "visuallySimilarImages"),
        "detected_urls": len(rows),
        "target_platform_urls": sum(platform_counts.values()),
        "target_platform_image_urls": sum(platform_asset_counts.values()),
    }

    has_any_signal = any(value for value in counts.values())
    if not has_any_signal:
        reason = "검색 단서가 거의 없습니다."
    elif counts["detected_urls"] == 0:
        reason = "제품명 같은 단서는 있지만 확인할 링크가 없습니다."
    elif counts["pages_with_matching_images"] == 0 and counts["target_platform_urls"] == 0:
        reason = "이미지 파일만 찾았습니다. 쇼핑몰 상품 페이지는 찾지 못했습니다."
    elif candidates and counts["target_platform_urls"] == 0 and counts["target_platform_image_urls"] > 0:
        reason = "마켓 이미지 파일에서 상품 페이지 후보를 추정했습니다."
    elif counts["target_platform_urls"] == 0 and counts["target_platform_image_urls"] > 0:
        reason = "마켓 이미지 파일은 찾았지만 쇼핑몰 상품 페이지는 찾지 못했습니다."
    elif counts["target_platform_urls"] == 0:
        reason = "쇼핑몰 상품 페이지 후보가 기준 점수 이상으로 확인되지 않았습니다."
    elif not candidates:
        reason = "마켓 링크는 보였지만 80점 이상 후보로 쓰기에는 정보가 부족합니다."
    else:
        weak_count = len([candidate for candidate in candidates if candidate.get("status") == "image_weak"])
        if weak_count == len(candidates):
            reason = "마켓 후보는 있지만 80점 기준을 넘지 못했습니다."
        else:
            reason = "마켓 후보를 찾았습니다."

    return {
        "reason": reason,
        "counts": counts,
        "platform_counts": platform_counts,
        "platform_image_counts": platform_asset_counts,
        "source_counts": dict(source_counts),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in domain_counts.most_common(8)
        ],
        "sample_urls": [
            {
                "source": row.get("source"),
                "domain": _hostname(_shopping_product_display_url(str(row.get("url") or ""))) or row.get("domain"),
                "platform": PLATFORM_LABELS.get(row.get("platform"), row.get("platform") or ""),
                "title": row.get("title") or "",
                "url": _shopping_product_display_url(str(row.get("url") or "")),
            }
            for row in shopping_rows[:10]
        ],
    }


def _candidate_score(
    candidate: dict[str, Any],
    terms: dict[str, Any],
    web_entities: list[dict[str, Any]],
    best_guess_labels: list[str],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    url = str(candidate.get("url") or "")
    title = str(candidate.get("title") or "")
    platform = candidate.get("platform")
    text = _normalize(" ".join([title, url, " ".join(best_guess_labels)]))
    entity_text = _normalize(" ".join(entity["description"] for entity in web_entities[:8]))
    all_text = f"{text} {entity_text}".strip()

    if platform:
        score += 20
        reasons.append(f"{PLATFORM_LABELS.get(platform, platform)} 도메인 결과")

    if _looks_like_product_url(platform, url):
        score += 15
        reasons.append("상품 상세 URL 패턴")

    match_type = candidate.get("match_type")
    if match_type == "full":
        score += 45
        reasons.append("동일 이미지 매칭")
    elif match_type == "partial":
        score += 30
        reasons.append("부분 이미지 매칭")
    elif match_type == "page":
        score += 10
        reasons.append("이미지를 포함한 웹페이지")
    elif match_type == "similar":
        score += 6
        reasons.append("유사 이미지")

    full_model = _normalize(terms.get("model") or "")
    if full_model and full_model in all_text:
        score += 25
        reasons.append("모델명 일치")

    brand = _normalize(terms.get("brand") or terms.get("verify") or "")
    if brand and brand in all_text:
        score += 12
        reasons.append("브랜드/제조사 일치")

    token_groups = terms.get("tokens") or {}
    model_tokens = token_groups.get("model") or []
    product_tokens = token_groups.get("product") or token_groups.get("query") or []
    verify_tokens = token_groups.get("verify") or []

    matched_model_tokens = [token for token in model_tokens if token in all_text]
    if model_tokens and matched_model_tokens:
        points = min(15, round(15 * len(matched_model_tokens) / len(model_tokens)))
        score += points
        reasons.append(f"모델 토큰 {len(matched_model_tokens)}/{len(model_tokens)}개 일치")

    matched_product_tokens = [token for token in product_tokens if token in all_text]
    if product_tokens and matched_product_tokens:
        points = min(20, round(20 * len(matched_product_tokens) / len(product_tokens)))
        score += points
        reasons.append(f"제품명 토큰 {len(matched_product_tokens)}/{len(product_tokens)}개 일치")

    matched_verify_tokens = [token for token in verify_tokens if token in all_text]
    if verify_tokens and matched_verify_tokens:
        score += min(8, 4 * len(matched_verify_tokens))
        reasons.append("검증어 일치")

    if web_entities:
        top_entities = [entity for entity in web_entities[:5] if entity["score"] >= 0.5]
        if top_entities:
            score += min(8, len(top_entities) * 2)
            reasons.append("Vision 엔티티 신뢰도 반영")

    if candidate.get("derived_from_image"):
        score += 8
        reasons.append("마켓 이미지 URL에서 상품 코드 추정")

    return min(score, 100), reasons


def _candidate_status(score: int) -> str:
    if score >= config.IMAGE_SEARCH_MATCH_THRESHOLD:
        return "image_matched"
    if score >= config.IMAGE_SEARCH_CANDIDATE_THRESHOLD:
        return "image_candidate"
    return "image_weak"


def _similar_candidate_score(
    candidate: dict[str, Any],
    terms: dict[str, Any],
    web_entities: list[dict[str, Any]],
    best_guess_labels: list[str],
) -> tuple[int, list[str]]:
    reasons: list[str] = []
    score = 0
    url = str(candidate.get("url") or "")
    title = str(candidate.get("title") or "")
    text = _normalize(" ".join([title, url, " ".join(best_guess_labels)]))
    entity_text = _normalize(" ".join(entity["description"] for entity in web_entities[:8]))
    all_text = f"{text} {entity_text}".strip()

    platform = str(candidate.get("platform") or "")
    if platform and platform != "visual":
        score += 18
        reasons.append(f"{RELATED_COMMERCE_LABELS.get(platform, platform)} 결과")
    elif candidate.get("is_image_asset"):
        score += 8
        reasons.append("Vision 유사 이미지")

    if not candidate.get("is_image_asset"):
        score += 12
        reasons.append("웹페이지 링크")

    match_type = candidate.get("match_type")
    if match_type == "full":
        score += 42
        reasons.append("동일 이미지 매칭")
    elif match_type == "partial":
        score += 28
        reasons.append("부분 이미지 매칭")
    elif match_type == "page":
        score += 10
        reasons.append("이미지를 포함한 웹페이지")
    elif match_type == "similar":
        score += 8
        reasons.append("유사 이미지")

    token_groups = terms.get("tokens") or {}
    product_tokens = token_groups.get("product") or token_groups.get("query") or []
    brand_tokens = token_groups.get("brand") or []
    model_tokens = token_groups.get("model") or []

    matched_product_tokens = [token for token in product_tokens if token in all_text]
    if product_tokens and matched_product_tokens:
        points = min(20, round(20 * len(matched_product_tokens) / len(product_tokens)))
        score += points
        reasons.append(f"제품명 토큰 {len(matched_product_tokens)}/{len(product_tokens)}개 일치")

    matched_brand_tokens = [token for token in brand_tokens if token in all_text]
    if brand_tokens and matched_brand_tokens:
        score += min(12, 6 * len(matched_brand_tokens))
        reasons.append("브랜드 토큰 일치")

    matched_model_tokens = [token for token in model_tokens if token in all_text]
    if model_tokens and matched_model_tokens:
        score += min(15, 5 * len(matched_model_tokens))
        reasons.append("모델 토큰 일치")

    if web_entities:
        top_entities = [entity for entity in web_entities[:5] if entity["score"] >= 0.5]
        if top_entities:
            score += min(8, len(top_entities) * 2)
            reasons.append("Vision 엔티티 신뢰도 반영")

    return min(score, 100), reasons


def _collect_candidates(
    web_detection: dict[str, Any],
    target_platforms: set[str],
) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add(url: str, title: str, match_type: str, source: str, extra: dict[str, Any] | None = None) -> None:
        if not url:
            return
        platform = _detect_platform(url)
        if not platform or (target_platforms and platform not in target_platforms):
            return
        if not _is_market_page_url(url):
            derived_url = _market_page_from_image_asset(platform, url)
            if not derived_url:
                return
            image_url = url
            url = derived_url
            platform = _detect_platform(url)
            extra = {**(extra or {}), "derived_from_image": image_url}
            extra.setdefault("matching_images", [image_url])
        key = url.split("#", 1)[0]
        existing = candidates.get(key)
        rank = {"full": 4, "partial": 3, "page": 2, "similar": 1}
        payload = existing or {
            "url": key,
            "title": _strip_markup(title),
            "platform": platform,
            "sources": [],
            "matching_images": [],
        }
        if not payload.get("title") and title:
            payload["title"] = _strip_markup(title)
        if existing is None or rank.get(match_type, 0) > rank.get(payload.get("match_type"), 0):
            payload["match_type"] = match_type
        payload["sources"].append(source)
        if extra:
            payload.update(extra)
        candidates[key] = payload

    for page in web_detection.get("pagesWithMatchingImages") or []:
        if not isinstance(page, dict):
            continue
        page_url = str(page.get("url") or "")
        full_count = _matching_count(page, "fullMatchingImages")
        partial_count = _matching_count(page, "partialMatchingImages")
        match_type = "full" if _looks_like_image_asset_url(page_url) or full_count else "partial" if partial_count else "page"
        add(
            page_url,
            str(page.get("pageTitle") or ""),
            match_type,
            "pagesWithMatchingImages",
            {
                "full_matching_images": full_count,
                "partial_matching_images": partial_count,
                "matching_images": [
                    image.get("url")
                    for key in ("fullMatchingImages", "partialMatchingImages")
                    for image in (page.get(key) or [])
                    if isinstance(image, dict) and image.get("url")
                ][:6],
            },
        )

    for key, match_type in (
        ("fullMatchingImages", "full"),
        ("partialMatchingImages", "partial"),
        ("visuallySimilarImages", "similar"),
    ):
        for image in web_detection.get(key) or []:
            if not isinstance(image, dict):
                continue
            add(str(image.get("url") or ""), "", match_type, key)

    return list(candidates.values())


def _collect_similar_candidates(web_detection: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: dict[str, dict[str, Any]] = {}

    def add(
        url: str,
        title: str,
        match_type: str,
        source: str,
        *,
        matching_images: list[str] | None = None,
        parent_url: str = "",
    ) -> None:
        if not url or _detect_platform(url):
            return

        is_image_asset = _looks_like_image_asset_url(url)
        commerce = _detect_related_commerce(url)
        if not commerce or is_image_asset:
            return
        if not _looks_like_related_product_url(commerce, url):
            return

        key = url.split("#", 1)[0]
        existing = candidates.get(key)
        rank = {"full": 4, "partial": 3, "page": 2, "similar": 1}
        platform = commerce
        payload = existing or {
            "url": key,
            "title": _strip_markup(title),
            "platform": platform,
            "platform_label": RELATED_COMMERCE_LABELS.get(platform, platform),
            "sources": [],
            "matching_images": [],
            "is_image_asset": is_image_asset,
            "thumbnail_url": "",
        }
        if not payload.get("title") and title:
            payload["title"] = _strip_markup(title)
        if existing is None or rank.get(match_type, 0) > rank.get(payload.get("match_type"), 0):
            payload["match_type"] = match_type
        payload["sources"].append(source)
        if parent_url:
            payload["parent_url"] = parent_url
        for image_url in matching_images or []:
            if image_url and image_url not in payload["matching_images"]:
                payload["matching_images"].append(image_url)
        candidates[key] = payload

    for page in web_detection.get("pagesWithMatchingImages") or []:
        if not isinstance(page, dict):
            continue
        page_url = str(page.get("url") or "")
        title = str(page.get("pageTitle") or "")
        full_images = [
            image.get("url")
            for image in (page.get("fullMatchingImages") or [])
            if isinstance(image, dict) and image.get("url")
        ]
        partial_images = [
            image.get("url")
            for image in (page.get("partialMatchingImages") or [])
            if isinstance(image, dict) and image.get("url")
        ]
        match_type = "full" if _looks_like_image_asset_url(page_url) or full_images else "partial" if partial_images else "page"
        add(
            page_url,
            title,
            match_type,
            "pagesWithMatchingImages",
            matching_images=(full_images + partial_images)[:6],
        )
        for image_url in full_images:
            add(image_url, title, "full", "page.fullMatchingImages", parent_url=page_url)
        for image_url in partial_images:
            add(image_url, title, "partial", "page.partialMatchingImages", parent_url=page_url)

    for key, match_type in (
        ("fullMatchingImages", "full"),
        ("partialMatchingImages", "partial"),
        ("visuallySimilarImages", "similar"),
    ):
        for image in web_detection.get(key) or []:
            if not isinstance(image, dict):
                continue
            add(str(image.get("url") or ""), "", match_type, key)

    return list(candidates.values())


def _status_from_candidates(candidates: list[dict[str, Any]]) -> str:
    top_score = candidates[0]["score"] if candidates else 0
    if not candidates:
        return "image_no_match"
    if top_score >= config.IMAGE_SEARCH_MATCH_THRESHOLD:
        return "image_matched"
    if top_score >= config.IMAGE_SEARCH_CANDIDATE_THRESHOLD:
        return "image_candidate"
    return "image_weak"


def _score_detection_result(
    web_detection: dict[str, Any],
    terms: dict[str, Any],
    requested_platforms: set[str],
) -> dict[str, Any]:
    entities = _web_entities(web_detection)
    labels = _best_guess_labels(web_detection)
    candidates = _collect_candidates(web_detection, requested_platforms)
    similar_candidates = _collect_similar_candidates(web_detection)

    scored_candidates: list[dict[str, Any]] = []
    for candidate in candidates:
        score, reasons = _candidate_score(candidate, terms, entities, labels)
        candidate["score"] = score
        candidate["status"] = _candidate_status(score)
        candidate["reasons"] = reasons
        candidate["platform_label"] = PLATFORM_LABELS.get(candidate["platform"], candidate["platform"])
        if score >= config.IMAGE_SEARCH_DISPLAY_THRESHOLD:
            scored_candidates.append(candidate)
    candidates = scored_candidates

    scored_similar_candidates: list[dict[str, Any]] = []
    for candidate in similar_candidates:
        score, reasons = _similar_candidate_score(candidate, terms, entities, labels)
        candidate["score"] = score
        candidate["reasons"] = reasons
        if score >= config.IMAGE_SEARCH_DISPLAY_THRESHOLD:
            scored_similar_candidates.append(candidate)
    similar_candidates = scored_similar_candidates

    candidates.sort(key=lambda item: item["score"], reverse=True)
    similar_candidates.sort(key=lambda item: item["score"], reverse=True)
    diagnostics = _vision_diagnostics(web_detection, requested_platforms, candidates)
    return {
        "status": _status_from_candidates(candidates),
        "web_entities": entities[:12],
        "best_guess_labels": labels,
        "candidates": candidates,
        "similar_candidates": similar_candidates[:20],
        "vision_diagnostics": diagnostics,
    }


def _merge_scored_candidates(groups: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}
    for group in groups:
        source_image = str(group.get("source_image") or "")
        for candidate in group.get(key) or []:
            if not isinstance(candidate, dict):
                continue
            merge_key = (
                str(candidate.get("platform") or ""),
                str(candidate.get("url") or "").split("#", 1)[0].casefold(),
            )
            payload = dict(candidate)
            payload["image_sources"] = [source_image] if source_image else []
            existing = merged.get(merge_key)
            if existing is None or int(payload.get("score") or 0) > int(existing.get("score") or 0):
                if existing:
                    payload["image_sources"] = existing.get("image_sources", []) + payload["image_sources"]
                    payload["matching_images"] = list(
                        dict.fromkeys((existing.get("matching_images") or []) + (payload.get("matching_images") or []))
                    )
                merged[merge_key] = payload
            else:
                if source_image and source_image not in existing.setdefault("image_sources", []):
                    existing["image_sources"].append(source_image)
                existing["matching_images"] = list(
                    dict.fromkeys((existing.get("matching_images") or []) + (payload.get("matching_images") or []))
                )
    return sorted(merged.values(), key=lambda item: int(item.get("score") or 0), reverse=True)


def _merge_entities(groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    entities: dict[str, dict[str, Any]] = {}
    for group in groups:
        for entity in group.get("web_entities") or []:
            description = str(entity.get("description") or "").strip()
            if not description:
                continue
            existing = entities.get(description.casefold())
            if existing is None or float(entity.get("score") or 0) > float(existing.get("score") or 0):
                entities[description.casefold()] = entity
    return sorted(entities.values(), key=lambda item: float(item.get("score") or 0), reverse=True)[:12]


def _merge_labels(groups: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for group in groups:
        for label in group.get("best_guess_labels") or []:
            if label and label not in labels:
                labels.append(label)
    return labels[:12]


def _merge_diagnostics(groups: list[dict[str, Any]]) -> dict[str, Any]:
    counts: Counter[str] = Counter()
    platform_counts: Counter[str] = Counter()
    platform_image_counts: Counter[str] = Counter()
    source_counts: Counter[str] = Counter()
    top_domains: Counter[str] = Counter()
    sample_urls: list[dict[str, Any]] = []
    reasons: list[str] = []

    for group in groups:
        diagnostics = group.get("vision_diagnostics") or {}
        counts.update(diagnostics.get("counts") or {})
        platform_counts.update(diagnostics.get("platform_counts") or {})
        platform_image_counts.update(diagnostics.get("platform_image_counts") or {})
        source_counts.update(diagnostics.get("source_counts") or {})
        for domain in diagnostics.get("top_domains") or []:
            if isinstance(domain, dict) and domain.get("domain"):
                top_domains[str(domain["domain"])] += int(domain.get("count") or 0)
        for row in diagnostics.get("sample_urls") or []:
            if isinstance(row, dict) and row.get("url") and len(sample_urls) < 10:
                sample_urls.append(row)
        reason = str(diagnostics.get("reason") or "")
        if reason and reason not in reasons:
            reasons.append(reason)

    return {
        "reason": " / ".join(reasons[:3]) or "검색 단서가 거의 없습니다.",
        "counts": dict(counts),
        "platform_counts": dict(platform_counts),
        "platform_image_counts": dict(platform_image_counts),
        "source_counts": dict(source_counts),
        "top_domains": [
            {"domain": domain, "count": count}
            for domain, count in top_domains.most_common(8)
        ],
        "sample_urls": sample_urls,
    }


def run_image_search(
    recall: dict[str, Any],
    *,
    api_key: str = "",
    image_url: str = "",
    image_base64: str = "",
    image_path: str = "",
    max_results: int = config.IMAGE_SEARCH_MAX_RESULTS,
    target_platforms: list[str] | None = None,
) -> dict[str, Any]:
    api_key = api_key or config.GOOGLE_VISION_API_KEY
    source_images = [image_url] if image_url else find_recall_image_urls(recall)
    if not source_images and not image_base64 and not image_path:
        return {
            "status": "image_no_image",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_image": "",
            "source_images": [],
            "candidates": [],
            "similar_candidates": [],
            "search_queries": build_search_queries(recall),
            "message": "리콜 항목에 이미지가 없습니다.",
        }

    terms = _recall_terms(recall)
    requested_platforms = set(target_platforms or MARKET_DOMAINS)
    image_results: list[dict[str, Any]] = []
    warnings: list[str] = []
    targets = source_images or [image_path or "uploaded-image"]

    for index, source_image in enumerate(targets):
        try:
            web_detection, image_warnings = call_vision_web_detection(
                api_key=api_key,
                image_url=source_image if source_images else "",
                image_path=image_path if not source_images else "",
                image_base64=image_base64 if not source_images else "",
                max_results=max_results,
            )
        except ImageSearchError as exc:
            if "API 키" in str(exc):
                raise
            warnings.append(f"{source_image or image_path or 'uploaded-image'} 분석 실패: {exc}")
            image_results.append(
                {
                    "status": "image_search_error",
                    "source_image": source_image or image_path or "uploaded-image",
                    "image_index": index,
                    "candidates": [],
                    "similar_candidates": [],
                    "candidate_count": 0,
                    "similar_candidate_count": 0,
                    "web_entities": [],
                    "best_guess_labels": [],
                    "vision_diagnostics": {
                        "reason": str(exc),
                        "counts": {},
                        "platform_counts": {},
                        "platform_image_counts": {},
                        "source_counts": {},
                        "top_domains": [],
                        "sample_urls": [],
                    },
                    "error": str(exc),
                }
            )
            continue
        warnings.extend(image_warnings)
        scored = _score_detection_result(web_detection, terms, requested_platforms)
        scored["source_image"] = source_image or image_path or "uploaded-image"
        scored["image_index"] = index
        scored["candidate_count"] = len(scored["candidates"])
        scored["similar_candidate_count"] = len(scored["similar_candidates"])
        image_results.append(scored)

    candidates = _merge_scored_candidates(image_results, "candidates")
    similar_candidates = _merge_scored_candidates(image_results, "similar_candidates")[:20]
    diagnostics = _merge_diagnostics(image_results)
    status = _status_from_candidates(candidates)

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source_image": targets[0] if targets else "",
        "source_images": targets,
        "recall": recall,
        "terms": terms,
        "search_queries": build_search_queries(recall),
        "web_entities": _merge_entities(image_results),
        "best_guess_labels": _merge_labels(image_results),
        "candidates": candidates,
        "candidate_count": len(candidates),
        "similar_candidates": similar_candidates,
        "similar_candidate_count": len(similar_candidates),
        "vision_diagnostics": diagnostics,
        "image_results": image_results,
        "warnings": warnings,
    }
