from __future__ import annotations

import config
from ziggoo.models import ProductHit
from ziggoo.scanners.base import BaseScanner


class ElevenStScanner(BaseScanner):
    name = "elevenst"
    search_url_template = config.ELEVENST_SEARCH_URL
    result_selectors = (
        "a[href*='www.11st.co.kr/products/pa/']",
        "a[href*='/products/pa/']",
    )
    title_selectors = (
        "*",
    )
    price_selectors = (
        ".c_prd_price",
        "[class*='price']",
        "[class*='sale']",
    )
    link_selectors = (
        "a[href*='products']",
        "a[href*='Product']",
        "a",
    )
    blocked_markers = BaseScanner.blocked_markers + (
        "서비스 접속이 차단",
        "보안문자",
    )

    async def extract_products(self, page: object) -> list[ProductHit]:
        links = []
        for selector in self.result_selectors:
            links = await page.query_selector_all(selector)
            if links:
                break

        products: list[ProductHit] = []
        seen: set[tuple[str, str]] = set()

        for link in links:
            title = " ".join((await link.inner_text()).split())
            href = await link.get_attribute("href")
            if not title or not href:
                continue

            key = (href.split("?")[0], title)
            if key in seen:
                continue
            seen.add(key)
            products.append(ProductHit(title=title, url=href))

            if len(products) >= self.max_items:
                break

        return products
