from __future__ import annotations

from ziggoo.scanners.coupang import CoupangScanner
from ziggoo.scanners.elevenst import ElevenStScanner
from ziggoo.scanners.gmarket import GmarketScanner


SCANNER_REGISTRY = {
    "coupang": CoupangScanner,
    "elevenst": ElevenStScanner,
    "gmarket": GmarketScanner,
}

