from __future__ import annotations

from ziggoo.scanners.coupang import CoupangScanner
from ziggoo.scanners.elevenst import ElevenStScanner
from ziggoo.scanners.gmarket import GmarketScanner
from ziggoo.scanners.naver import NaverScanner


SCANNER_REGISTRY = {
    "coupang": CoupangScanner,
    "elevenst": ElevenStScanner,
    "gmarket": GmarketScanner,
    "naver": NaverScanner,
}
