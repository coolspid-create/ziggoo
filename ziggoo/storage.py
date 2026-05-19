from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import config


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_results(results: list[object]) -> list[Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ziggoo_results_{timestamp}.json"
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(results),
        "results": results,
    }

    saved_paths: list[Path] = []
    for directory in (config.PROJECT_RESULTS_DIR,):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / filename
            with path.open("w", encoding="utf-8") as fp:
                json.dump(payload, fp, ensure_ascii=False, indent=2, default=_json_default)
            saved_paths.append(path)
        except OSError as exc:
            print(f"결과 저장을 건너뜁니다: {directory} ({exc})")
    return saved_paths
