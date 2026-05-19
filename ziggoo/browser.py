from __future__ import annotations

import random
from contextlib import asynccontextmanager
from typing import AsyncIterator

import config


@asynccontextmanager
async def build_browser_context(
    headless: bool = True,
    block_heavy_assets: bool = True,
) -> AsyncIterator[object]:
    from playwright.async_api import async_playwright

    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--no-sandbox",
        ],
    )
    context = await browser.new_context(
        locale="ko-KR",
        timezone_id="Asia/Seoul",
        user_agent=random.choice(config.USER_AGENTS),
        viewport={"width": random.randint(1280, 1440), "height": random.randint(820, 940)},
    )

    async def block_route(route: object) -> None:
        request = route.request
        if request.resource_type in {"image", "media", "font"}:
            await route.abort()
        else:
            await route.continue_()

    if block_heavy_assets:
        await context.route("**/*", block_route)

    try:
        yield context
    finally:
        await context.close()
        await browser.close()
        await playwright.stop()
