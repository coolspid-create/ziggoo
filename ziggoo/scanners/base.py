from __future__ import annotations

import asyncio
import random
from datetime import datetime
from pathlib import Path
from urllib.parse import quote_plus, urljoin

import config
from ziggoo.matching import check_dual_match
from ziggoo.models import ProductHit, RecallItem, ScanResult


class BaseScanner:
    name = "base"
    search_url_template = ""
    result_selectors: tuple[str, ...] = ()
    title_selectors: tuple[str, ...] = ()
    price_selectors: tuple[str, ...] = ()
    link_selectors: tuple[str, ...] = ("a",)
    blocked_markers: tuple[str, ...] = ("access denied", "captcha", "robot", "비정상")

    def __init__(
        self,
        context: object,
        max_items: int = config.MAX_SEARCH_ITEMS,
        manual_verify_blocked: bool = False,
        manual_timeout_seconds: int = config.MANUAL_VERIFICATION_TIMEOUT_SECONDS,
    ) -> None:
        self.context = context
        self.max_items = max_items
        self.manual_verify_blocked = manual_verify_blocked
        self.manual_timeout_seconds = max(1, manual_timeout_seconds)

    async def scan(self, item: RecallItem) -> ScanResult:
        searched_at = datetime.now().isoformat(timespec="seconds")
        screenshot: str | None = None
        last_error: str | None = None
        manual_verified = False

        for attempt in range(config.RETRY_COUNT + 1):
            page = await self.context.new_page()
            await self._apply_stealth(page)
            try:
                await self._delay(attempt)
                url = self.build_search_url(item.query)
                await page.goto(url, wait_until="domcontentloaded", timeout=45000)
                await self._settle_page(page)

                content = (await page.content()).lower()
                if self._is_blocked(content):
                    screenshot = await self._save_debug_screenshot(page, "blocked")
                    last_error = "Bot protection or access denial detected."
                    if self.manual_verify_blocked:
                        verified = await self._wait_for_manual_verification(page, item)
                        if not verified:
                            break
                        manual_verified = True
                    else:
                        continue

                products = await self.extract_products(page)
                matches = [
                    product
                    for product in products
                    if check_dual_match(item.query, item.verify, product.title)
                ]

                if not products:
                    screenshot = await self._save_debug_screenshot(page, "empty")

                status = "matched" if matches else "no_match"
                return ScanResult(
                    platform=self.name,
                    query=item.query,
                    verify=item.verify,
                    status=status,
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
            status="blocked" if last_error and "protection" in last_error.lower() else "error",
            matches=[],
            searched_items=0,
            screenshot=screenshot,
            error=last_error,
            source_id=item.source_id,
            model_name=item.model_name,
            searched_at=searched_at,
            metadata=self._metadata(item, manual_verified=False),
        )

    def build_search_url(self, query: str) -> str:
        return self.search_url_template.format(query=quote_plus(query))

    async def extract_products(self, page: object) -> list[ProductHit]:
        products: list[ProductHit] = []
        elements = []
        for selector in self.result_selectors:
            elements = await page.query_selector_all(selector)
            if elements:
                break

        for element in elements[: self.max_items]:
            title = await self._first_text(element, self.title_selectors)
            if not title:
                continue
            url = await self._first_href(element, self.link_selectors, page.url)
            price = await self._first_text(element, self.price_selectors)
            products.append(ProductHit(title=title, url=url, price=price))
        return products

    async def _first_text(self, element: object, selectors: tuple[str, ...]) -> str | None:
        for selector in selectors:
            target = await element.query_selector(selector)
            if not target:
                continue
            text = await target.inner_text()
            text = " ".join(text.split())
            if text:
                return text
        text = await element.inner_text()
        text = " ".join(text.split())
        return text or None

    async def _first_href(
        self,
        element: object,
        selectors: tuple[str, ...],
        base_url: str,
    ) -> str | None:
        for selector in selectors:
            target = await element.query_selector(selector)
            if not target:
                continue
            href = await target.get_attribute("href")
            if href:
                return urljoin(base_url, href)
        return None

    async def _apply_stealth(self, page: object) -> None:
        try:
            from playwright_stealth import Stealth

            await Stealth().apply_stealth_async(page)
        except Exception:
            try:
                from playwright_stealth import stealth_async

                await stealth_async(page)
            except Exception:
                return

    async def _settle_page(self, page: object) -> None:
        try:
            await page.wait_for_load_state("networkidle", timeout=8000)
        except Exception:
            pass
        await self._delay()

    async def _delay(self, attempt: int = 0) -> None:
        multiplier = 1 + (attempt * 0.7)
        await asyncio.sleep(
            random.uniform(config.MIN_DELAY_SECONDS, config.MAX_DELAY_SECONDS) * multiplier
        )

    def _is_blocked(self, content: str) -> bool:
        return any(marker in content for marker in self.blocked_markers)

    def _metadata(self, item: RecallItem, manual_verified: bool = False) -> dict[str, object]:
        if not self.manual_verify_blocked:
            return item.metadata
        metadata = dict(item.metadata)
        metadata["manual_verification"] = {
            "requested": True,
            "completed": manual_verified,
        }
        return metadata

    async def _wait_for_manual_verification(self, page: object, item: RecallItem) -> bool:
        message = (
            "ZIGGOO 수동 검증 모드: 이 브라우저에서 보안 확인을 완료하면 "
            "스캔이 자동으로 이어집니다."
        )
        print(
            f"[{self.name}] 차단 화면 수동 검증 대기: "
            f"{item.query} ({self.manual_timeout_seconds}초)"
        )
        await self._show_manual_hint(page, message)

        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.manual_timeout_seconds
        while loop.time() < deadline:
            await asyncio.sleep(config.MANUAL_VERIFICATION_POLL_SECONDS)
            try:
                content = (await page.content()).lower()
            except Exception:
                return False
            if not self._is_blocked(content):
                await self._clear_manual_hint(page)
                await self._settle_page(page)
                print(f"[{self.name}] 수동 검증 완료: {item.query}")
                return True
            await self._show_manual_hint(page, message)

        print(f"[{self.name}] 수동 검증 시간 초과: {item.query}")
        return False

    async def _show_manual_hint(self, page: object, message: str) -> None:
        try:
            await page.evaluate(
                """(message) => {
                    const id = "ziggoo-manual-verification-hint";
                    const existing = document.getElementById(id);
                    if (existing) {
                        existing.textContent = message;
                        return;
                    }
                    const banner = document.createElement("div");
                    banner.id = id;
                    banner.textContent = message;
                    Object.assign(banner.style, {
                        position: "fixed",
                        zIndex: "2147483647",
                        top: "12px",
                        left: "12px",
                        right: "12px",
                        padding: "12px 14px",
                        border: "1px solid #c99a35",
                        borderRadius: "8px",
                        background: "#fff7df",
                        color: "#3f2f08",
                        font: "700 14px/1.45 system-ui, sans-serif",
                        boxShadow: "0 10px 30px rgba(0,0,0,0.18)"
                    });
                    document.documentElement.appendChild(banner);
                }""",
                message,
            )
        except Exception:
            return

    async def _clear_manual_hint(self, page: object) -> None:
        try:
            await page.evaluate(
                """() => {
                    document.getElementById("ziggoo-manual-verification-hint")?.remove();
                }"""
            )
        except Exception:
            return

    async def _save_debug_screenshot(self, page: object, reason: str) -> str:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        directory = config.PROJECT_RESULTS_DIR / "debug"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"debug_{self.name}_{reason}_{timestamp}.png"
        await page.screenshot(path=str(path), full_page=True)
        return str(path)
