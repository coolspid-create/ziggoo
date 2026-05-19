from __future__ import annotations

import config
from ziggoo.scanners.base import BaseScanner


class CoupangScanner(BaseScanner):
    name = "coupang"
    search_url_template = config.COUPANG_SEARCH_URL
    result_selectors = (
        "li.search-product",
        "li[class*='search-product']",
        "[data-testid*='product']",
    )
    title_selectors = (
        ".name",
        ".descriptions-inner .name",
        "[class*='name']",
        "a",
    )
    price_selectors = (
        ".price-value",
        "[class*='price']",
    )
    link_selectors = (
        "a.search-product-link",
        "a[href*='/vp/products']",
        "a",
    )
    blocked_markers = BaseScanner.blocked_markers + (
        "access denied",
        "error: access denied",
    )

