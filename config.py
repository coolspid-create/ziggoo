from __future__ import annotations

import os
from pathlib import Path


def _load_local_env() -> None:
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_local_env()


API_KEY = os.getenv("ZIGGOO_API_KEY", "")
RECALL_HUB_BASE_URL = os.getenv(
    "ZIGGOO_RECALL_HUB_BASE_URL",
    "https://recall-hub-admin-dev.vercel.app",
).rstrip("/")
API_BASE_URL = os.getenv("ZIGGOO_API_BASE_URL", f"{RECALL_HUB_BASE_URL}/api/v1/recalls")
GOOGLE_VISION_API_KEY = os.getenv("ZIGGOO_GOOGLE_VISION_API_KEY", "")

HEADLESS = os.getenv("ZIGGOO_HEADLESS", "1").lower() not in {"0", "false", "no"}
REQUEST_TIMEOUT_SECONDS = int(os.getenv("ZIGGOO_REQUEST_TIMEOUT", "25"))
MAX_SEARCH_ITEMS = int(os.getenv("ZIGGOO_MAX_ITEMS", "20"))
IMAGE_SEARCH_MAX_RESULTS = int(os.getenv("ZIGGOO_IMAGE_SEARCH_MAX_RESULTS", "20"))
IMAGE_SEARCH_MATCH_THRESHOLD = int(os.getenv("ZIGGOO_IMAGE_SEARCH_MATCH_THRESHOLD", "80"))
IMAGE_SEARCH_CANDIDATE_THRESHOLD = int(os.getenv("ZIGGOO_IMAGE_SEARCH_CANDIDATE_THRESHOLD", "50"))
IMAGE_SEARCH_DISPLAY_THRESHOLD = int(os.getenv("ZIGGOO_IMAGE_SEARCH_DISPLAY_THRESHOLD", "80"))
RETRY_COUNT = int(os.getenv("ZIGGOO_RETRY_COUNT", "2"))
MANUAL_VERIFICATION_TIMEOUT_SECONDS = int(os.getenv("ZIGGOO_MANUAL_TIMEOUT", "180"))
MANUAL_VERIFICATION_POLL_SECONDS = float(os.getenv("ZIGGOO_MANUAL_POLL", "2.0"))

MIN_DELAY_SECONDS = float(os.getenv("ZIGGOO_MIN_DELAY", "0.8"))
MAX_DELAY_SECONDS = float(os.getenv("ZIGGOO_MAX_DELAY", "2.4"))

PROJECT_RESULTS_DIR = Path("results")
DESKTOP_RESULTS_DIR = Path.home() / "Desktop" / "ZIGGOO"
MANUAL_FIRST_PLATFORMS = tuple(
    platform.strip()
    for platform in os.getenv("ZIGGOO_MANUAL_FIRST_PLATFORMS", "coupang,gmarket").split(",")
    if platform.strip()
)

COUPANG_SEARCH_URL = (
    "https://www.coupang.com/np/search?q={query}&filterType=coupang_global%2C&channel=plp_C1"
)
ELEVENST_SEARCH_URL = "https://search.11st.co.kr/pc/amazontab?kwd={query}"
GMARKET_SEARCH_URL = "https://www.gmarket.co.kr/n/search?keyword={query}"
GMARKET_GLOBAL_SEARCH_URL = (
    "https://gsearch.gmarket.co.kr/Listview/Search?"
    "DelFee=&IsBookCash=False&IsDeliveryFee=&IsDiscount=False&IsFeature=&"
    "IsGlobalSearch=undefined&IsGmarketBest=False&IsGmileage=False&IsGstamp=False&"
    "IsOversea=True&keyword={query}&ordertype=&page=1&pagesize=60&type=LIST"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]
