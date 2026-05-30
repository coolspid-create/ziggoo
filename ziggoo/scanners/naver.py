from __future__ import annotations

import config
from ziggoo.scanners.base import BaseScanner


class NaverScanner(BaseScanner):
    name = "naver"
    search_url_template = config.NAVER_SEARCH_URL
    result_selectors = (
        "div[class*='product_item']",
        "li[class*='basicList_item']",
        "div[class*='basicList_info_area']",
        "div[class*='product_info_area']",
    )
    title_selectors = (
        "a[class*='product_link']",
        "a[class*='basicList_link']",
        "[class*='product_title']",
        "[class*='basicList_title']",
        "a[href*='smartstore.naver.com']",
        "a[href*='shopping.naver.com']",
        "a",
    )
    price_selectors = (
        "[class*='price_num']",
        "[class*='product_price']",
        "[class*='basicList_price']",
        "[class*='price']",
    )
    link_selectors = (
        "a[class*='product_link']",
        "a[class*='basicList_link']",
        "a[href*='smartstore.naver.com']",
        "a[href*='shopping.naver.com']",
        "a",
    )
    blocked_markers = BaseScanner.blocked_markers + (
        "자동입력",
        "captcha",
        "비정상적인 접근",
    )
