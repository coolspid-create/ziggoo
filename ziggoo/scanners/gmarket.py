from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import quote_plus

import config
from ziggoo.matching import check_dual_match
from ziggoo.models import ProductHit, RecallItem, ScanResult
from ziggoo.scanners.base import BaseScanner


class GmarketScanner(BaseScanner):
    name = "gmarket"
    search_url_template = config.GMARKET_SEARCH_URL
    fallback_search_url_template = config.GMARKET_GLOBAL_SEARCH_URL
    result_selectors = (
        ".box__component-itemcard",
        ".box__item-container",
        "div.box__item-info",
        "#srplist > tr",
        "#srplist > li",
        ".item_list tbody > tr",
        "li.item",
        "tr.item",
    )
    title_selectors = (
        ".text__item",
        ".link__item",
        ".itemname",
        ".item_name",
        ".item_name a",
        "a.item_name",
        "a[gdno]",
        "a[href*='item.gmarket.co.kr']",
        "a[href*='global.gmarket.co.kr/item']",
        "[class*='title']",
        "a",
    )
    price_selectors = (
        ".text__value",
        ".price",
        ".item_price",
        "[class*='price']",
    )
    link_selectors = (
        "a.link__item",
        "a[href*='item.gmarket.co.kr']",
        "a[href*='global.gmarket.co.kr/item']",
        ".item_name a",
        "a.item_name",
        "a[gdno]",
        "a",
    )
    blocked_markers = BaseScanner.blocked_markers + (
        "요청하신 페이지를 찾을 수 없습니다",
        "자동입력",
        "잠시만 기다리십시오",
        "봇 확인",
        "원활한 서비스 이용을 위한 간단한 확인 안내",
        "enable javascript and cookies",
        "just a moment",
    )

    def build_search_url_from_template(self, query: str, template: str) -> str:
        return template.format(query=quote_plus(query))

    async def scan(self, item: RecallItem) -> ScanResult:
        primary = await self._scan_template(
            item,
            self.search_url_template,
            fallback_name="한국어 검색",
            retry_blocked=False,
        )
        if primary.status != "blocked":
            return primary

        fallback = await self._scan_template(
            item,
            self.fallback_search_url_template,
            fallback_name="글로벌 검색",
            retry_blocked=False,
        )
        if fallback.status == "matched":
            fallback.error = primary.error
            return fallback

        primary.error = (
            "G마켓 한국어 검색은 자동화 접근 확인 화면으로 차단되었습니다. "
            f"글로벌 검색 보조 확인 결과는 {fallback.status}입니다."
        )
        primary.searched_items = fallback.searched_items
        return primary

    async def extract_products(self, page: object) -> list[ProductHit]:
        products = await super().extract_products(page)
        filtered: list[ProductHit] = []
        for product in products:
            title = product.title.casefold()
            if "no search results" in title or "there are no search results" in title:
                continue
            if not product.url:
                continue
            filtered.append(product)
        return filtered

    async def _first_href(
        self,
        element: object,
        selectors: tuple[str, ...],
        base_url: str,
    ) -> str | None:
        href = await super()._first_href(element, selectors, base_url)
        if not href:
            return None
        match = re.search(r"viewUrl\('([^']+)'", href)
        if match:
            return match.group(1)
        return href

    async def _scan_template(
        self,
        item: RecallItem,
        template: str,
        fallback_name: str,
        retry_blocked: bool,
    ) -> ScanResult:
        searched_at = datetime.now().isoformat(timespec="seconds")
        screenshot: str | None = None
        last_error: str | None = None
        manual_verified = False

        for attempt in range(config.RETRY_COUNT + 1):
            page = await self.context.new_page()
            await self._apply_stealth(page)
            try:
                await self._delay(attempt)
                url = self.build_search_url_from_template(item.query, template)
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await self._settle_page(page)

                content = (await page.content()).lower()
                if self._is_blocked(content):
                    screenshot = await self._save_debug_screenshot(page, "blocked")
                    last_error = f"{fallback_name} blocked by bot verification."
                    if self.manual_verify_blocked:
                        verified = await self._wait_for_manual_verification(page, item)
                        if not verified:
                            return ScanResult(
                                platform=self.name,
                                query=item.query,
                                verify=item.verify,
                                status="blocked",
                                matches=[],
                                searched_items=0,
                                screenshot=screenshot,
                                error=last_error,
                                source_id=item.source_id,
                                model_name=item.model_name,
                                searched_at=searched_at,
                                metadata=self._metadata(item, manual_verified=False),
                            )
                        manual_verified = True
                    elif retry_blocked:
                        continue
                    else:
                        return ScanResult(
                            platform=self.name,
                            query=item.query,
                            verify=item.verify,
                            status="blocked",
                            matches=[],
                            searched_items=0,
                            screenshot=screenshot,
                            error=last_error,
                            source_id=item.source_id,
                            model_name=item.model_name,
                            searched_at=searched_at,
                            metadata=self._metadata(item, manual_verified=False),
                        )

                products = await self.extract_products(page)
                matches = [
                    product
                    for product in products
                    if check_dual_match(item.query, item.verify, product.title)
                ]

                if not products:
                    screenshot = await self._save_debug_screenshot(page, "empty")

                return ScanResult(
                    platform=self.name,
                    query=item.query,
                    verify=item.verify,
                    status="matched" if matches else "no_match",
                    matches=matches,
                    searched_items=len(products),
                    screenshot=screenshot,
                    source_id=item.source_id,
                    model_name=item.model_name,
                    searched_at=searched_at,
                    metadata=self._metadata(item, manual_verified=manual_verified),
                )
            except Exception as exc:
                last_error = str(exc)
                try:
                    screenshot = await self._save_debug_screenshot(page, "error")
                except Exception:
                    pass
            finally:
                await page.close()

        return ScanResult(
            platform=self.name,
            query=item.query,
            verify=item.verify,
            status="error",
            matches=[],
            searched_items=0,
            screenshot=screenshot,
            error=last_error,
            source_id=item.source_id,
            model_name=item.model_name,
            searched_at=searched_at,
            metadata=self._metadata(item, manual_verified=False),
        )
