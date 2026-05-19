from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Iterable

import config
from ziggoo.browser import build_browser_context
from ziggoo.models import RecallItem, ScanResult
from ziggoo.recall_mapping import recall_to_item
from ziggoo.recall_api import RecallApiClient
from ziggoo.scanners import SCANNER_REGISTRY
from ziggoo.storage import save_results


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="ZIGGOO recall product monitoring scanner",
    )
    parser.add_argument("keyword", nargs="?", help="단일 검색어")
    parser.add_argument("--verify", help="추가 검증어. 상품명에 함께 포함되어야 탐지됩니다.")
    parser.add_argument(
        "--platform",
        choices=sorted(SCANNER_REGISTRY),
        help="특정 플랫폼만 스캔합니다.",
    )
    parser.add_argument("--file", type=Path, help="배치 검색 JSON 파일 경로")
    parser.add_argument("--headful", action="store_true", help="브라우저 창을 표시합니다.")
    parser.add_argument(
        "--manual-verify-blocked",
        action="store_true",
        help="차단 화면이 나오면 브라우저를 열어 사용자의 보안 확인 완료를 기다립니다.",
    )
    parser.add_argument(
        "--manual-timeout",
        type=int,
        default=config.MANUAL_VERIFICATION_TIMEOUT_SECONDS,
        help="수동 검증을 기다릴 최대 초",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=config.MAX_SEARCH_ITEMS,
        help="플랫폼별 확인할 최대 검색 결과 수",
    )
    parser.add_argument("--progress-file", type=Path, help="JSON progress file path")
    return parser.parse_args()


def _write_json(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


class ProgressTracker:
    def __init__(
        self,
        path: Path | None,
        items: list[RecallItem],
        platforms: list[str],
    ) -> None:
        self.path = path
        self.started_at = datetime.now().isoformat(timespec="seconds")
        self.completed = 0
        self.current: dict[str, object] | None = None
        self.last: dict[str, object] | None = None
        self.records = [
            {
                "platform": platform,
                "query": item.query,
                "verify": item.verify or "",
                "source_id": item.source_id or "",
                "model_name": item.model_name or "",
                "status": "pending",
                "matches": 0,
            }
            for item in items
            for platform in platforms
        ]

    @property
    def total(self) -> int:
        return len(self.records)

    def write(self, state: str = "running", message: str = "") -> None:
        payload: dict[str, object] = {
            "state": state,
            "message": message,
            "started_at": self.started_at,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "completed": self.completed,
            "total": self.total,
            "current": self.current,
            "last": self.last,
            "items": self.records,
        }
        _write_json(self.path, payload)

    def mark_running(self, index: int) -> None:
        record = self.records[index]
        record["status"] = "running"
        self.current = {
            "platform": record["platform"],
            "query": record["query"],
            "source_id": record["source_id"],
        }
        self.write("running", "Scanning")

    def mark_done(self, index: int, result: ScanResult) -> None:
        record = self.records[index]
        record["status"] = result.status
        record["matches"] = len(result.matches)
        record["searched_items"] = result.searched_items
        record["error"] = result.error or ""
        self.completed += 1
        self.last = {
            "platform": result.platform,
            "query": result.query,
            "status": result.status,
            "matches": len(result.matches),
        }
        self.current = None
        self.write("running", "Scanning")


def finalize_progress(progress_file: Path | None, paths: list[Path]) -> None:
    if progress_file is None:
        return
    try:
        with progress_file.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(
        {
            "state": "completed",
            "message": "Scan completed",
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "output_files": [str(path) for path in paths],
        }
    )
    _write_json(progress_file, payload)


def fail_progress(progress_file: Path | None, message: str) -> None:
    if progress_file is None:
        return
    try:
        with progress_file.open("r", encoding="utf-8") as fp:
            payload = json.load(fp)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload.update(
        {
            "state": "error",
            "message": message,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )
    _write_json(progress_file, payload)


def load_items_from_file(path: Path) -> list[RecallItem]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)

    if isinstance(payload, dict):
        payload = payload.get("items") or payload.get("data") or payload.get("recalls") or []

    if not isinstance(payload, list):
        raise ValueError("배치 파일은 JSON 배열이거나 items/data/recalls 배열을 가진 객체여야 합니다.")

    items: list[RecallItem] = []
    for entry in payload:
        if isinstance(entry, str):
            items.append(RecallItem(query=entry))
        elif isinstance(entry, dict):
            items.append(recall_to_item(entry) if "product_name" in entry else RecallItem.from_mapping(entry))
        else:
            raise ValueError(f"지원하지 않는 배치 항목 형식입니다: {entry!r}")
    return [item for item in items if item.query]


def resolve_scan_items(args: argparse.Namespace) -> list[RecallItem]:
    if args.keyword:
        return [RecallItem(query=args.keyword, verify=args.verify)]

    if args.file:
        return load_items_from_file(args.file)

    client = RecallApiClient()
    return client.fetch_recall_items()


def select_platforms(platform: str | None) -> Iterable[str]:
    if platform:
        return [platform]
    return SCANNER_REGISTRY.keys()


def requires_manual_first(platform: str, args: argparse.Namespace) -> bool:
    return not args.manual_verify_blocked and platform in config.MANUAL_FIRST_PLATFORMS


def manual_required_result(platform: str, item: RecallItem) -> ScanResult:
    metadata = dict(item.metadata)
    metadata["manual_verification"] = {
        "required": True,
        "requested": False,
        "completed": False,
        "reason": "manual_first_platform",
    }
    return ScanResult(
        platform=platform,
        query=item.query,
        verify=item.verify,
        status="manual_required",
        matches=[],
        searched_items=0,
        error=(
            "이 플랫폼은 기본 자동 스캔에서 제외되었습니다. "
            "대시보드에서 수동 검증 재스캔을 실행하세요."
        ),
        source_id=item.source_id,
        model_name=item.model_name,
        searched_at=datetime.now().isoformat(timespec="seconds"),
        metadata=metadata,
    )


async def run_scan(args: argparse.Namespace, items: list[RecallItem]) -> list[ScanResult]:
    headless = False if args.headful or args.manual_verify_blocked else config.HEADLESS
    results: list[ScanResult] = []
    platforms = list(select_platforms(args.platform))
    runnable_platforms = [
        platform for platform in platforms if not requires_manual_first(platform, args)
    ]
    progress = ProgressTracker(args.progress_file, items, platforms)
    progress.write("running", "Scan started")
    progress_index = 0

    async def scan_all(scanners: dict[str, object]) -> None:
        nonlocal progress_index
        for item in items:
            for platform_name in platforms:
                progress.mark_running(progress_index)
                print(f"[{platform_name}] 검색: {item.query}")
                if requires_manual_first(platform_name, args):
                    result = manual_required_result(platform_name, item)
                else:
                    scanner = scanners[platform_name]
                    result = await scanner.scan(item)
                results.append(result)
                progress.mark_done(progress_index, result)
                progress_index += 1
                print(
                    f"[{platform_name}] {result.status} "
                    f"matches={len(result.matches)} query={item.query}"
                )

    if runnable_platforms:
        async with build_browser_context(
            headless=headless,
            block_heavy_assets=not args.manual_verify_blocked,
        ) as context:
            scanners = {
                name: scanner_cls(
                    context=context,
                    max_items=args.max_items,
                    manual_verify_blocked=args.manual_verify_blocked,
                    manual_timeout_seconds=args.manual_timeout,
                )
                for name, scanner_cls in SCANNER_REGISTRY.items()
                if name in runnable_platforms
            }
            await scan_all(scanners)
    else:
        await scan_all({})

    return results


def main() -> int:
    args = parse_args()

    try:
        items = resolve_scan_items(args)
    except Exception as exc:
        print(f"검색 대상을 불러오지 못했습니다: {exc}", file=sys.stderr)
        return 2

    if not items:
        print(
            "검색 대상이 없습니다. 키워드를 입력하거나 --file 또는 Recall API 설정을 확인하세요.",
            file=sys.stderr,
        )
        return 2

    try:
        results = asyncio.run(run_scan(args, items))
    except KeyboardInterrupt:
        fail_progress(args.progress_file, "Scan interrupted")
        print("사용자 요청으로 중단했습니다.", file=sys.stderr)
        return 130
    except Exception as exc:
        fail_progress(args.progress_file, str(exc))
        print(f"스캔 중 오류가 발생했습니다: {exc}", file=sys.stderr)
        return 1

    paths = save_results(results)
    finalize_progress(args.progress_file, paths)
    print("결과 저장 완료:")
    for path in paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
