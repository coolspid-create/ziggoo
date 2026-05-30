from __future__ import annotations

import argparse
import io
import json
import mimetypes
import os
import re
import subprocess
import sys
import zipfile
from datetime import datetime
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from tempfile import NamedTemporaryFile
from xml.sax.saxutils import escape
from urllib.parse import parse_qs, unquote, urlparse

import config
from ziggoo.image_search import ImageSearchError, run_image_search
from ziggoo.product_search import run_product_search
from ziggoo.recall_api import RecallApiClient
from ziggoo.recall_mapping import enrich_recall, recall_to_scan_payload


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_ROOT = PROJECT_ROOT / "dashboard"
RESULT_DIRS = (PROJECT_ROOT / "results", config.DESKTOP_RESULTS_DIR)
SCAN_TIMEOUT_SECONDS = 600


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _append_manual_verification_flags(command: list[str], payload: dict[str, Any]) -> None:
    if not _truthy(payload.get("manual_verify_blocked")):
        return

    command.append("--manual-verify-blocked")
    timeout = payload.get("manual_timeout")
    if timeout:
        command.extend(["--manual-timeout", str(timeout)])


def _scanner_creationflags(payload: dict[str, Any]) -> int:
    if os.name != "nt" or not _truthy(payload.get("manual_verify_blocked")):
        return 0
    return int(getattr(subprocess, "CREATE_NEW_CONSOLE", 0))


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _safe_result_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None

    candidate = Path(unquote(raw_path))
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = candidate.resolve()

    if any(_is_within(candidate, directory) for directory in RESULT_DIRS):
        return candidate
    return None


def _safe_local_asset_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None

    candidate = Path(unquote(raw_path))
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    candidate = candidate.resolve()

    allowed_roots = (*RESULT_DIRS, PROJECT_ROOT)
    if any(_is_within(candidate, directory) for directory in allowed_roots):
        return candidate
    return None


def _safe_progress_path(raw_id: str | None) -> Path | None:
    progress_id = str(raw_id or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", progress_id):
        return None
    return (config.PROJECT_RESULTS_DIR / f"scan_progress_{progress_id}.json").resolve()


def _write_progress_file(path: Path | None, updates: dict[str, Any]) -> None:
    if path is None:
        return
    payload: dict[str, Any] = {}
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as fp:
                loaded = json.load(fp)
            if isinstance(loaded, dict):
                payload = loaded
        except Exception:
            payload = {}
    payload.update(updates)
    payload.setdefault("started_at", datetime.now().isoformat(timespec="seconds"))
    payload["updated_at"] = datetime.now().isoformat(timespec="seconds")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.tmp")
    with tmp_path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fp:
        payload = json.load(fp)
    if not isinstance(payload, dict):
        return {"generated_at": None, "count": 0, "results": []}
    payload.setdefault("results", [])
    payload.setdefault("count", len(payload["results"]))
    return payload


def _save_image_search_result(payload: dict[str, Any]) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    directory = config.PROJECT_RESULTS_DIR / "image_search"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"ziggoo_image_search_{timestamp}.json"
    with path.open("w", encoding="utf-8") as fp:
        json.dump(payload, fp, ensure_ascii=False, indent=2)
    return path


def _discover_result_files() -> list[dict[str, Any]]:
    files: list[dict[str, Any]] = []
    seen: set[Path] = set()
    seen_names: set[str] = set()

    for directory in RESULT_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob("ziggoo_results_*.json"):
            resolved = path.resolve()
            if resolved in seen or path.name in seen_names:
                continue
            seen.add(resolved)
            seen_names.add(path.name)
            stat = path.stat()
            files.append(
                {
                    "name": path.name,
                    "path": str(resolved),
                    "directory": str(directory.resolve()),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "size": stat.st_size,
                }
            )

    files.sort(key=lambda item: item["modified_at"], reverse=True)
    return files


def _summarize(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("results") or []
    status_counts: dict[str, int] = {}
    platform_counts: dict[str, int] = {}
    matched_rows = 0
    match_items = 0
    attention_rows = 0

    for row in results:
        if not isinstance(row, dict):
            continue
        status = str(row.get("status") or "unknown")
        platform = str(row.get("platform") or "unknown")
        matches = row.get("matches") if isinstance(row.get("matches"), list) else []
        status_counts[status] = status_counts.get(status, 0) + 1
        platform_counts[platform] = platform_counts.get(platform, 0) + 1
        if status == "matched":
            matched_rows += 1
            match_items += len(matches)
        if status in {"blocked", "manual_required", "error"}:
            attention_rows += 1

    return {
        "scan_count": len(results),
        "matched_rows": matched_rows,
        "match_items": match_items,
        "attention_rows": attention_rows,
        "status_counts": status_counts,
        "platform_counts": platform_counts,
        "generated_at": payload.get("generated_at"),
    }


def _content_disposition(filename: str) -> str:
    safe_name = re.sub(r'[^A-Za-z0-9._ -]+', "_", filename).strip() or "ziggoo_results"
    return f'attachment; filename="{safe_name}"'


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xml_text(value: Any) -> str:
    return re.sub(r"[\x00-\x08\x0B\x0C\x0E-\x1F]", "", str(value))


def _xlsx_cell(value: Any, row: int, column: int, style: int | None = None) -> str:
    reference = f"{_column_name(column)}{row}"
    style_attr = f' s="{style}"' if style is not None else ""

    if value is None or value == "":
        return f'<c r="{reference}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{reference}" t="b"{style_attr}><v>{int(value)}</v></c>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{reference}"{style_attr}><v>{value}</v></c>'

    raw_text = _xml_text(value)
    text = escape(raw_text)
    preserve = ' xml:space="preserve"' if raw_text.strip() != raw_text else ""
    return f'<c r="{reference}" t="inlineStr"{style_attr}><is><t{preserve}>{text}</t></is></c>'


def _xlsx_sheet(rows: list[list[Any]], column_widths: list[int]) -> str:
    if not rows:
        rows = [[""]]

    row_count = len(rows)
    column_count = max(len(row) for row in rows)
    dimension = f"A1:{_column_name(column_count)}{row_count}"
    columns = "".join(
        f'<col min="{idx}" max="{idx}" width="{width}" customWidth="1"/>'
        for idx, width in enumerate(column_widths[:column_count], start=1)
    )
    if len(column_widths) < column_count:
        columns += f'<col min="{len(column_widths) + 1}" max="{column_count}" width="18" customWidth="1"/>'

    sheet_rows = []
    for row_number, row in enumerate(rows, start=1):
        cells = "".join(
            _xlsx_cell(value, row_number, column_number, 1 if row_number == 1 else None)
            for column_number, value in enumerate(row, start=1)
        )
        sheet_rows.append(f'<row r="{row_number}">{cells}</row>')

    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <dimension ref="{dimension}"/>
  <sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <cols>{columns}</cols>
  <sheetData>{"".join(sheet_rows)}</sheetData>
  <autoFilter ref="{dimension}"/>
</worksheet>'''


def _flatten_result_rows(payload: dict[str, Any]) -> list[list[Any]]:
    rows: list[list[Any]] = [[
        "상태",
        "플랫폼",
        "검색어",
        "검증어",
        "소스 ID",
        "모델명",
        "확인 상품 수",
        "탐지 상품 수",
        "상품명",
        "가격",
        "상품 URL",
        "스크린샷",
        "오류",
        "스캔 시각",
    ]]

    for result in payload.get("results") or []:
        if not isinstance(result, dict):
            continue

        matches = result.get("matches") if isinstance(result.get("matches"), list) else []
        base = [
            result.get("status") or "",
            result.get("platform") or "",
            result.get("query") or "",
            result.get("verify") or "",
            result.get("source_id") or "",
            result.get("model_name") or "",
            result.get("searched_items") or 0,
            len(matches),
        ]

        if matches:
            for match in matches:
                match = match if isinstance(match, dict) else {}
                rows.append(
                    base
                    + [
                        match.get("title") or "",
                        match.get("price") or "",
                        match.get("url") or "",
                        result.get("screenshot") or "",
                        result.get("error") or "",
                        result.get("searched_at") or "",
                    ]
                )
        else:
            rows.append(
                base
                + [
                    "",
                    "",
                    "",
                    result.get("screenshot") or "",
                    result.get("error") or "",
                    result.get("searched_at") or "",
                ]
            )

    return rows


def _build_xlsx(payload: dict[str, Any]) -> bytes:
    summary = _summarize(payload)
    summary_rows = [
        ["항목", "값"],
        ["생성 시각", payload.get("generated_at") or ""],
        ["스캔 행", summary["scan_count"]],
        ["탐지 행", summary["matched_rows"]],
        ["탐지 상품", summary["match_items"]],
        ["확인 필요", summary["attention_rows"]],
    ]
    for status, count in sorted(summary["status_counts"].items()):
        summary_rows.append([f"상태: {status}", count])
    for platform, count in sorted(summary["platform_counts"].items()):
        summary_rows.append([f"플랫폼: {platform}", count])

    result_rows = _flatten_result_rows(payload)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
    <sheet name="요약" sheetId="1" r:id="rId1"/>
    <sheet name="결과" sheetId="2" r:id="rId2"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/styles.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2"><font><sz val="11"/><name val="맑은 고딕"/></font><font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="맑은 고딕"/></font></fonts>
  <fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF2F6F9F"/><bgColor indexed="64"/></patternFill></fill></fills>
  <borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>
  <cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
  <cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1"/></cellXfs>
</styleSheet>""",
        )
        archive.writestr("xl/worksheets/sheet1.xml", _xlsx_sheet(summary_rows, [24, 18]))
        archive.writestr(
            "xl/worksheets/sheet2.xml",
            _xlsx_sheet(result_rows, [12, 16, 28, 20, 18, 22, 14, 14, 48, 16, 48, 36, 30, 20]),
        )
    return buffer.getvalue()


class DashboardHandler(SimpleHTTPRequestHandler):
    server_version = "ZIGGOODashboard/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[dashboard] {self.address_string()} - {format % args}")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/results":
            self._handle_results(parsed.query)
            return
        if parsed.path == "/api/download":
            self._handle_download(parsed.query)
            return
        if parsed.path == "/api/scan-progress":
            self._handle_scan_progress(parsed.query)
            return
        if parsed.path == "/api/screenshot":
            self._handle_screenshot(parsed.query)
            return
        if parsed.path == "/image-search":
            self._serve_static(DASHBOARD_ROOT / "image-search.html")
            return
        if parsed.path in {"/", "/dashboard"}:
            self._serve_static(DASHBOARD_ROOT / "index.html")
            return
        if parsed.path.startswith("/assets/"):
            rel = parsed.path.removeprefix("/assets/")
            self._serve_static(DASHBOARD_ROOT / "assets" / rel)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/recalls":
            self._handle_recalls()
            return
        if parsed.path == "/api/scan":
            self._handle_scan()
            return
        if parsed.path == "/api/scan-recalls":
            self._handle_scan_recalls()
            return
        if parsed.path == "/api/image-search":
            self._handle_image_search()
            return
        if parsed.path == "/api/product-search":
            self._handle_product_search()
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(
        self,
        body: bytes,
        content_type: str,
        filename: str,
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", _content_disposition(filename))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, path: Path) -> None:
        resolved = path.resolve()
        if not _is_within(resolved, DASHBOARD_ROOT) or not resolved.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        content_type = mimetypes.guess_type(str(resolved))[0] or "application/octet-stream"
        body = resolved.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _handle_results(self, query: str) -> None:
        params = parse_qs(query)
        files = _discover_result_files()
        requested = _safe_result_path((params.get("file") or [None])[0])
        selected = requested if requested and requested.exists() else None

        if selected is None and files:
            selected = Path(files[0]["path"])

        if selected is None:
            payload = {"generated_at": None, "count": 0, "results": []}
            self._send_json(
                {
                    "files": files,
                    "selected": None,
                    "payload": payload,
                    "summary": _summarize(payload),
                }
            )
            return

        try:
            payload = _read_json(selected)
        except Exception as exc:
            self._send_json(
                {"error": f"Could not read result file: {exc}", "files": files},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json(
            {
                "files": files,
                "selected": str(selected.resolve()),
                "payload": payload,
                "summary": _summarize(payload),
            }
        )

    def _handle_download(self, query: str) -> None:
        params = parse_qs(query)
        files = _discover_result_files()
        requested = _safe_result_path((params.get("file") or [None])[0])
        selected = requested if requested and requested.exists() else None
        if selected is None and files:
            selected = Path(files[0]["path"])

        if selected is None or not selected.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Result file not found")
            return

        file_format = str((params.get("format") or ["json"])[0]).lower()
        if file_format == "json":
            self._send_bytes(
                selected.read_bytes(),
                "application/json; charset=utf-8",
                selected.name,
            )
            return

        if file_format == "xlsx":
            try:
                payload = _read_json(selected)
                body = _build_xlsx(payload)
            except Exception as exc:
                self._send_json(
                    {"error": f"Could not build Excel file: {exc}"},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return
            self._send_bytes(
                body,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                f"{selected.stem}.xlsx",
            )
            return

        self._send_json({"error": "Unsupported download format."}, HTTPStatus.BAD_REQUEST)

    def _handle_scan_progress(self, query: str) -> None:
        params = parse_qs(query)
        progress_path = _safe_progress_path((params.get("id") or [None])[0])
        if progress_path is None:
            self._send_json({"error": "Invalid progress id."}, HTTPStatus.BAD_REQUEST)
            return
        if not progress_path.exists():
            self._send_json(
                {
                    "state": "waiting",
                    "message": "Waiting for scan to start",
                    "completed": 0,
                    "total": 0,
                    "items": [],
                }
            )
            return

        try:
            with progress_path.open("r", encoding="utf-8") as fp:
                payload = json.load(fp)
            if not isinstance(payload, dict):
                raise ValueError("Progress file must contain a JSON object.")
        except Exception as exc:
            self._send_json(
                {"error": f"Could not read progress: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self._send_json(payload)

    def _handle_screenshot(self, query: str) -> None:
        params = parse_qs(query)
        path = _safe_local_asset_path((params.get("path") or [None])[0])
        if path is None or not path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "Screenshot not found")
            return

        content_type = mimetypes.guess_type(str(path))[0] or "image/png"
        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception:
            return None
        return payload if isinstance(payload, dict) else None

    def _handle_recalls(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        api_key = str(payload.get("api_key") or config.API_KEY or "").strip()
        if not api_key:
            self._send_json({"error": "Recall Hub API key is required."}, HTTPStatus.BAD_REQUEST)
            return

        mode = str(payload.get("mode") or "list")
        client = RecallApiClient.for_recall_hub(api_key=api_key)

        try:
            if mode == "recent":
                result = client.recent_recalls(
                    days=int(payload.get("days") or 30),
                    limit=int(payload.get("limit") or 50),
                    source=str(payload.get("source") or "").strip() or None,
                )
            else:
                result = client.list_recalls(
                    q=str(payload.get("q") or "").strip() or None,
                    source=str(payload.get("source") or "").strip() or None,
                    risk_bucket=str(payload.get("risk_bucket") or "").strip() or None,
                    korea_relevance=str(payload.get("korea_relevance") or "").strip() or None,
                    date_from=str(payload.get("date_from") or "").strip() or None,
                    date_to=str(payload.get("date_to") or "").strip() or None,
                    limit=int(payload.get("limit") or 50),
                    offset=int(payload.get("offset") or 0),
                )
        except Exception as exc:
            self._send_json(
                {"error": f"Recall Hub request failed: {exc}"},
                HTTPStatus.BAD_GATEWAY,
            )
            return

        rows = result.get("data") if isinstance(result.get("data"), list) else []
        result["data"] = [enrich_recall(row) for row in rows if isinstance(row, dict)]
        self._send_json(result)

    def _handle_scan(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        keyword = str(payload.get("keyword") or "").strip()
        verify = str(payload.get("verify") or "").strip()
        platform = str(payload.get("platform") or "").strip()
        max_items = str(payload.get("max_items") or "").strip()

        if not keyword:
            self._send_json({"error": "Keyword is required."}, HTTPStatus.BAD_REQUEST)
            return

        command = [sys.executable, str(PROJECT_ROOT / "scanner.py"), keyword]
        if verify:
            command.extend(["--verify", verify])
        if platform:
            command.extend(["--platform", platform])
        if max_items:
            command.extend(["--max-items", max_items])
        _append_manual_verification_flags(command, payload)

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                shell=False,
                creationflags=_scanner_creationflags(payload),
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            self._send_json(
                {"error": "Scan timed out.", "timeout_seconds": SCAN_TIMEOUT_SECONDS},
                HTTPStatus.REQUEST_TIMEOUT,
            )
            return

        self._send_json(
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
            HTTPStatus.OK if completed.returncode == 0 else HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def _handle_scan_recalls(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        recalls = payload.get("recalls")
        if not isinstance(recalls, list) or not recalls:
            self._send_json({"error": "Select at least one recall."}, HTTPStatus.BAD_REQUEST)
            return

        items = []
        skipped = []
        for recall in recalls:
            if not isinstance(recall, dict):
                continue
            item = recall_to_scan_payload(recall)
            if item["query"]:
                items.append(item)
            else:
                skipped.append(recall.get("id") or recall.get("guid") or "unknown")

        if not items:
            self._send_json(
                {"error": "Selected recalls do not contain searchable product or model names."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        platform = str(payload.get("platform") or "").strip()
        max_items = str(payload.get("max_items") or "").strip()
        progress_path = _safe_progress_path(str(payload.get("progress_id") or ""))
        if payload.get("progress_id") and progress_path is None:
            self._send_json({"error": "Invalid progress id."}, HTTPStatus.BAD_REQUEST)
            return

        config.PROJECT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            "w",
            encoding="utf-8",
            suffix=".json",
            prefix="recall_selection_",
            dir=config.PROJECT_RESULTS_DIR,
            delete=False,
        ) as fp:
            json.dump(items, fp, ensure_ascii=False, indent=2)
            selection_path = Path(fp.name)

        command = [sys.executable, str(PROJECT_ROOT / "scanner.py"), "--file", str(selection_path)]
        if platform:
            command.extend(["--platform", platform])
        if max_items:
            command.extend(["--max-items", max_items])
        _append_manual_verification_flags(command, payload)
        if progress_path is not None:
            _write_progress_file(
                progress_path,
                {
                    "state": "queued",
                    "message": "Scan queued",
                    "completed": 0,
                    "total": 0,
                    "items": [],
                },
            )
            command.extend(["--progress-file", str(progress_path)])

        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")

        try:
            completed = subprocess.run(
                command,
                cwd=PROJECT_ROOT,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                shell=False,
                creationflags=_scanner_creationflags(payload),
                timeout=SCAN_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            _write_progress_file(
                progress_path,
                {
                    "state": "error",
                    "message": "Scan timed out.",
                },
            )
            self._send_json(
                {"error": "Scan timed out.", "timeout_seconds": SCAN_TIMEOUT_SECONDS},
                HTTPStatus.REQUEST_TIMEOUT,
            )
            return

        if completed.returncode != 0:
            _write_progress_file(
                progress_path,
                {
                    "state": "error",
                    "message": completed.stderr.strip() or "Scan failed.",
                },
            )

        self._send_json(
            {
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "selection_file": str(selection_path),
                "selected_count": len(items),
                "skipped": skipped,
            },
            HTTPStatus.OK if completed.returncode == 0 else HTTPStatus.INTERNAL_SERVER_ERROR,
        )

    def _handle_image_search(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        recall = payload.get("recall") if isinstance(payload.get("recall"), dict) else {}
        direct_fields = {
            "query": payload.get("query"),
            "verify": payload.get("verify"),
            "brand_name": payload.get("brand_name"),
            "model_name": payload.get("model_name"),
            "product_name": payload.get("product_name"),
            "image_url": payload.get("image_url"),
        }
        if not recall:
            recall = {key: value for key, value in direct_fields.items() if value}
        elif payload.get("image_url"):
            recall = dict(recall)
            recall["image_url"] = payload.get("image_url")

        api_key = str(payload.get("vision_api_key") or config.GOOGLE_VISION_API_KEY or "").strip()
        target_platforms = payload.get("target_platforms")
        if not isinstance(target_platforms, list):
            target_platforms = None

        try:
            result = run_image_search(
                recall,
                api_key=api_key,
                image_url=str(payload.get("image_url") or "").strip(),
                image_base64=str(payload.get("image_base64") or "").strip(),
                max_results=int(payload.get("max_results") or config.IMAGE_SEARCH_MAX_RESULTS),
                target_platforms=[str(platform) for platform in target_platforms] if target_platforms else None,
            )
        except ImageSearchError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except Exception as exc:
            self._send_json(
                {"error": f"Image search failed: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        try:
            saved_path = _save_image_search_result(result)
            result["saved_path"] = str(saved_path.resolve())
        except Exception as exc:
            result["save_error"] = str(exc)

        self._send_json(result)

    def _handle_product_search(self) -> None:
        payload = self._read_json_body()
        if payload is None:
            self._send_json({"error": "Invalid JSON body."}, HTTPStatus.BAD_REQUEST)
            return

        recall = payload.get("recall") if isinstance(payload.get("recall"), dict) else {}
        if not recall:
            recall = {
                key: value
                for key, value in {
                    "query": payload.get("query"),
                    "verify": payload.get("verify"),
                    "brand_name": payload.get("brand_name"),
                    "model_name": payload.get("model_name"),
                    "product_name": payload.get("product_name"),
                }.items()
                if value
            }
        if not recall:
            self._send_json({"error": "검색할 제품 정보가 필요합니다."}, HTTPStatus.BAD_REQUEST)
            return

        target_platforms = payload.get("target_platforms")
        if not isinstance(target_platforms, list):
            target_platforms = None

        try:
            result = run_product_search(
                recall,
                target_platforms=[str(platform) for platform in target_platforms] if target_platforms else None,
                max_items=int(payload.get("max_items") or 8),
                max_queries=int(payload.get("max_queries") or 6),
            )
        except Exception as exc:
            self._send_json(
                {"error": f"Product search failed: {exc}"},
                HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        self._send_json(result)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the ZIGGOO dashboard server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    url = f"http://{args.host}:{server.server_port}"
    print(f"ZIGGOO dashboard: {url}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Dashboard stopped.")
    finally:
        server.server_close()
    return 0
