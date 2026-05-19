const state = {
  rows: [],
  files: [],
  recalls: [],
  summary: {},
  selectedPath: null,
  selectedIndex: null,
  selectedRecalls: new Set(),
  recallEdits: new Map(),
  isScanning: false,
  activeRecallScanKey: null,
  activeProgressId: null,
  progressTimer: null,
  scanProgress: null,
  lastRecallLoadedAt: null,
};

const els = {
  serverState: document.querySelector("#serverState"),
  resultTimestamp: document.querySelector("#resultTimestamp"),
  refreshButton: document.querySelector("#refreshButton"),
  recallForm: document.querySelector("#recallForm"),
  apiKeyInput: document.querySelector("#apiKeyInput"),
  recallModeInput: document.querySelector("#recallModeInput"),
  recallSearchInput: document.querySelector("#recallSearchInput"),
  sourceInput: document.querySelector("#sourceInput"),
  riskInput: document.querySelector("#riskInput"),
  koreaInput: document.querySelector("#koreaInput"),
  daysInput: document.querySelector("#daysInput"),
  recallLimitInput: document.querySelector("#recallLimitInput"),
  selectedRecallCount: document.querySelector("#selectedRecallCount"),
  selectVisibleButton: document.querySelector("#selectVisibleButton"),
  clearSelectionButton: document.querySelector("#clearSelectionButton"),
  recallScanPlatformInput: document.querySelector("#recallScanPlatformInput"),
  recallScanMaxInput: document.querySelector("#recallScanMaxInput"),
  recallManualVerifyInput: document.querySelector("#recallManualVerifyInput"),
  scanSelectedButton: document.querySelector("#scanSelectedButton"),
  recallLoadedCount: document.querySelector("#recallLoadedCount"),
  recallFreshness: document.querySelector("#recallFreshness"),
  scanProgress: document.querySelector("#scanProgress"),
  scanProgressTitle: document.querySelector("#scanProgressTitle"),
  scanProgressCount: document.querySelector("#scanProgressCount"),
  scanProgressBar: document.querySelector("#scanProgressBar"),
  scanProgressDetail: document.querySelector("#scanProgressDetail"),
  recallList: document.querySelector("#recallList"),
  recallEmptyState: document.querySelector("#recallEmptyState"),
  scanForm: document.querySelector("#scanForm"),
  keywordInput: document.querySelector("#keywordInput"),
  verifyInput: document.querySelector("#verifyInput"),
  scanPlatformInput: document.querySelector("#scanPlatformInput"),
  maxItemsInput: document.querySelector("#maxItemsInput"),
  manualVerifyInput: document.querySelector("#manualVerifyInput"),
  runButton: document.querySelector("#runButton"),
  runLog: document.querySelector("#runLog"),
  resultFileSelect: document.querySelector("#resultFileSelect"),
  downloadJsonButton: document.querySelector("#downloadJsonButton"),
  downloadExcelButton: document.querySelector("#downloadExcelButton"),
  tableSearchInput: document.querySelector("#tableSearchInput"),
  statusFilter: document.querySelector("#statusFilter"),
  platformFilter: document.querySelector("#platformFilter"),
  tableBody: document.querySelector("#resultTableBody"),
  emptyState: document.querySelector("#emptyState"),
  detailPanel: document.querySelector("#detailPanel"),
  metricScans: document.querySelector("#metricScans"),
  metricMatched: document.querySelector("#metricMatched"),
  metricProducts: document.querySelector("#metricProducts"),
  metricAttention: document.querySelector("#metricAttention"),
  resultInsight: document.querySelector("#resultInsight"),
  filteredResultCount: document.querySelector("#filteredResultCount"),
};

const statusLabels = {
  matched: "탐지",
  no_match: "미탐지",
  manual_required: "수동 필요",
  blocked: "차단",
  error: "오류",
  unknown: "알 수 없음",
};

const statusDescriptions = {
  matched: "검색 결과에서 검색어와 검증어 조건을 만족하는 상품명을 찾았습니다.",
  no_match: "플랫폼 검색과 상품 목록 확인은 됐지만, 현재 검색어/검증어 조건에 맞는 상품명은 찾지 못했습니다.",
  manual_required: "이 플랫폼은 기본 자동 스캔에서 제외되었습니다. 수동 검증 재스캔으로 확인하세요.",
  blocked: "플랫폼이 자동화 접근, 보안 확인, 접근 거부 등으로 정상 검색 결과를 보여주지 않았습니다.",
  error: "스캔 중 예외가 발생해 결과를 확정하지 못했습니다.",
  unknown: "결과 상태를 판단할 수 없습니다.",
};

const platformLabels = {
  coupang: "쿠팡",
  elevenst: "11번가 아마존",
  gmarket: "G마켓",
};

const savedApiKey = sessionStorage.getItem("recallHubApiKey");
if (savedApiKey) els.apiKeyInput.value = savedApiKey;

function setServerState(label, mode = "") {
  els.serverState.textContent = label;
  els.serverState.className = `state-pill ${mode}`.trim();
}

function formatDate(value) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("ko-KR", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function formatRecallDate(value) {
  const text = compactText(value, "");
  if (!text) return "";
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return text;
  const date = new Date(text);
  if (Number.isNaN(date.getTime())) return text;
  return new Intl.DateTimeFormat("ko-KR", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function recallDateInfo(recall) {
  const fields = [
    ["updated_at", "업데이트"],
    ["updated_date", "업데이트"],
    ["last_updated", "업데이트"],
    ["modified_at", "업데이트"],
    ["refreshed_at", "업데이트"],
    ["ingested_at", "수집"],
    ["crawled_at", "수집"],
    ["created_at", "생성"],
    ["published_date", "게시"],
  ];
  for (const [field, label] of fields) {
    const formatted = formatRecallDate(recall[field]);
    if (formatted) return { field, label, formatted, raw: recall[field] };
  }
  return null;
}

function dateTimeValue(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function updateRecallSummary() {
  els.recallLoadedCount.textContent = `${state.recalls.length}건`;
  if (!els.recallFreshness) return;
  if (!state.recalls.length) {
    els.recallFreshness.textContent = state.lastRecallLoadedAt ? "표시할 리콜 없음" : "불러오기 전";
    return;
  }

  const latest = state.recalls
    .map(recallDateInfo)
    .filter(Boolean)
    .sort((a, b) => dateTimeValue(b.raw) - dateTimeValue(a.raw))[0];
  const loadedAt = state.lastRecallLoadedAt
    ? new Intl.DateTimeFormat("ko-KR", { hour: "2-digit", minute: "2-digit" }).format(state.lastRecallLoadedAt)
    : "";
  const latestText = latest ? `최신 ${latest.label} ${latest.formatted}` : "날짜 정보 없음";
  els.recallFreshness.textContent = loadedAt ? `${latestText} · 불러옴 ${loadedAt}` : latestText;
}

function compactText(value, fallback = "-") {
  const text = `${value || ""}`.replace(/\s+/g, " ").trim();
  return text || fallback;
}

function recallKey(recall) {
  return `${recall.source || "src"}:${recall.guid || recall.id || recall.display_title}`;
}

function getDefaultRecallTerms(recall) {
  return {
    query: compactText(
      recall.query ||
        recall.scan_query ||
        recall.model_name ||
        recall.product_name ||
        recall.product_name_original ||
        recall.brand_name,
      ""
    ),
    verify: "",
  };
}

function getRecallEdit(recall) {
  const key = recallKey(recall);
  if (!state.recallEdits.has(key)) {
    state.recallEdits.set(key, getDefaultRecallTerms(recall));
  }
  return state.recallEdits.get(key);
}

function updateRecallEdit(recall, field, value) {
  const key = recallKey(recall);
  const current = getRecallEdit(recall);
  state.recallEdits.set(key, { ...current, [field]: value });
}

function resetRecallEdit(recall) {
  state.recallEdits.set(recallKey(recall), getDefaultRecallTerms(recall));
  renderRecalls();
}

function buildRecallScanPayload(recall) {
  const edit = getRecallEdit(recall);
  const query = edit.query.trim();
  const verify = edit.verify.trim();
  return {
    ...recall,
    query,
    verify,
    scan_query_override: query,
    scan_verify_override: verify,
  };
}

function makeEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function makeStatusPill(status) {
  const pill = makeEl("span", `status-pill ${status}`, statusLabels[status] || status);
  pill.title = statusDescriptions[status] || "";
  return pill;
}

function setEmptyState(container, title, copy = "") {
  container.replaceChildren();
  container.append(makeEl("p", "empty-title", title));
  if (copy) container.append(makeEl("p", "empty-copy", copy));
}

function countRowsByStatus(rows = state.rows) {
  return rows.reduce((counts, row) => {
    counts[row.status] = (counts[row.status] || 0) + 1;
    return counts;
  }, {});
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function normalizeRows(payload) {
  const rows = Array.isArray(payload?.results) ? payload.results : [];
  return rows.map((row, index) => {
    const metadata = row.metadata && typeof row.metadata === "object" ? row.metadata : {};
    const recall = metadata.recall && typeof metadata.recall === "object" ? metadata.recall : {};
    const sourceId = row.source_id || recall.source_id || recall.id || "";
    return {
      index,
      platform: row.platform || "unknown",
      query: row.query || "",
      verify: row.verify || "",
      status: row.status || "unknown",
      matches: Array.isArray(row.matches) ? row.matches : [],
      searched_items: row.searched_items || 0,
      screenshot: row.screenshot || "",
      error: row.error || "",
      model_name: row.model_name || recall.model_name || "",
      source_id: sourceId,
      searched_at: row.searched_at || "",
      metadata,
      manual_verification:
        metadata.manual_verification && typeof metadata.manual_verification === "object"
          ? metadata.manual_verification
          : null,
      recall,
      recall_key: Object.keys(recall).length ? recallKey(recall) : "",
    };
  });
}

function renderMetrics(summary) {
  els.metricScans.textContent = summary?.scan_count ?? 0;
  els.metricMatched.textContent = summary?.matched_rows ?? 0;
  els.metricProducts.textContent = summary?.match_items ?? 0;
  els.metricAttention.textContent = summary?.attention_rows ?? 0;
}

function renderResultInsight(summary = state.summary || {}) {
  els.resultInsight.replaceChildren();
  if (!state.rows.length) {
    els.resultInsight.hidden = true;
    return;
  }

  const statusCounts = summary.status_counts || countRowsByStatus();
  const chips = [
    ["전체", state.rows.length, ""],
    ["탐지", statusCounts.matched || 0, "matched"],
    ["미탐지", statusCounts.no_match || 0, "no_match"],
    ["수동 필요", statusCounts.manual_required || 0, "manual_required"],
    ["차단", statusCounts.blocked || 0, "blocked"],
    ["오류", statusCounts.error || 0, "error"],
  ];

  chips.forEach(([label, count, status]) => {
    const chip = makeEl(
      "button",
      `insight-chip ${els.statusFilter.value === status ? "active" : ""}`.trim()
    );
    chip.type = "button";
    chip.addEventListener("click", () => {
      els.statusFilter.value = status;
      renderTable();
      renderResultInsight();
    });
    chip.append(document.createTextNode(`${label} `), makeEl("strong", "", String(count)));
    els.resultInsight.append(chip);
  });
  els.resultInsight.hidden = false;
}

function renderResultTimestamp(summary = {}) {
  els.resultTimestamp.textContent = summary.generated_at
    ? `최근 결과 ${formatDate(summary.generated_at)}`
    : "최근 결과 없음";
}

function renderFileSelect(files, selectedPath) {
  els.resultFileSelect.replaceChildren();
  if (!files.length) {
    els.resultFileSelect.append(new Option("결과 파일 없음", ""));
    els.resultFileSelect.disabled = true;
    setDownloadButtons(false);
    return;
  }

  els.resultFileSelect.disabled = false;
  files.forEach((file) => {
    const label = `${file.name} · ${formatDate(file.modified_at)}`;
    const option = new Option(label, file.path);
    option.selected = file.path === selectedPath;
    els.resultFileSelect.append(option);
  });
  setDownloadButtons(Boolean(selectedPath));
}

function setDownloadButtons(enabled) {
  els.downloadJsonButton.disabled = !enabled;
  els.downloadExcelButton.disabled = !enabled;
}

function downloadResults(format) {
  if (!state.selectedPath) return;
  const params = new URLSearchParams({
    file: state.selectedPath,
    format,
  });
  window.location.href = `/api/download?${params.toString()}`;
}

function renderPlatformFilter(rows) {
  const current = els.platformFilter.value;
  const platforms = [...new Set(rows.map((row) => row.platform))].sort();
  els.platformFilter.replaceChildren(new Option("전체", ""));
  platforms.forEach((platform) => {
    els.platformFilter.append(new Option(platformLabels[platform] || platform, platform));
  });
  if (platforms.includes(current)) els.platformFilter.value = current;
}

function createProgressId() {
  return `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`;
}

function stopProgressPolling() {
  if (state.progressTimer) {
    window.clearInterval(state.progressTimer);
    state.progressTimer = null;
  }
}

function renderScanProgress() {
  const progress = state.scanProgress;
  els.scanProgress.hidden = !progress;
  if (!progress) return;

  const completed = Number(progress.completed || 0);
  const total = Number(progress.total || 0);
  const percent = total > 0 ? Math.min(100, Math.round((completed / total) * 100)) : 0;
  const current = progress.current || progress.last || {};
  const platform = current.platform ? platformLabels[current.platform] || current.platform : "";
  const query = current.query || "";
  const stateLabel =
    progress.state === "completed"
      ? "선택 스캔 완료"
      : progress.state === "error"
        ? "선택 스캔 오류"
        : progress.state === "queued" || progress.state === "waiting"
          ? "선택 스캔 대기 중"
          : "선택 스캔 진행 중";

  els.scanProgressTitle.textContent = stateLabel;
  els.scanProgressCount.textContent = total > 0 ? `${completed} / ${total}` : "준비 중";
  els.scanProgressBar.style.width = `${percent}%`;
  els.scanProgressDetail.textContent =
    [platform, query].filter(Boolean).join(" · ") || progress.message || "";
}

async function pollScanProgress(progressId) {
  const response = await fetch(`/api/scan-progress?id=${encodeURIComponent(progressId)}`, {
    cache: "no-store",
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  if (state.activeProgressId !== progressId) return;
  state.scanProgress = data;
  renderScanProgress();
}

function startProgressPolling(progressId) {
  stopProgressPolling();
  state.activeProgressId = progressId;
  state.scanProgress = {
    state: "waiting",
    message: "Waiting for scan to start",
    completed: 0,
    total: 0,
    items: [],
  };
  renderScanProgress();
  state.progressTimer = window.setInterval(() => {
    pollScanProgress(progressId).catch(() => {});
  }, 900);
  pollScanProgress(progressId).catch(() => {});
}

function recallResultRows(recall, key) {
  const edit = getRecallEdit(recall);
  const identifiers = [
    recall.source_id,
    recall.id,
    recall.guid,
    recall.recall_id,
  ]
    .filter(Boolean)
    .map((value) => String(value));

  return state.rows.filter((row) => {
    if (row.recall_key && row.recall_key === key) return true;
    if (row.source_id && identifiers.includes(String(row.source_id))) return true;
    return Boolean(edit.query && row.query === edit.query);
  });
}

function renderRecallResults(rows) {
  const group = makeEl("div", "recall-result-group");
  group.append(makeEl("div", "recall-result-title", "플랫폼별 결과"));
  rows
    .slice()
    .sort((a, b) => a.platform.localeCompare(b.platform))
    .forEach((row) => {
      const button = makeEl(
        "button",
        `recall-result-row ${state.selectedIndex === row.index ? "active" : ""}`
      );
      button.type = "button";
      button.addEventListener("click", () => {
        state.selectedIndex = row.index;
        renderTable();
        els.detailPanel.scrollIntoView({ behavior: "smooth", block: "start" });
      });
      const countLabel =
        row.status === "matched"
          ? `${row.matches.length}개 탐지`
          : row.status === "manual_required"
            ? "수동 확인 필요"
            : `${row.searched_items}개 확인`;
      button.append(
        makeEl("span", "recall-result-platform", platformLabels[row.platform] || row.platform),
        makeStatusPill(row.status),
        makeEl("span", "recall-result-count", countLabel)
      );
      group.append(button);
    });
  return group;
}

function renderRecalls() {
  els.recallList.replaceChildren();
  updateRecallSummary();
  els.recallEmptyState.hidden = state.recalls.length > 0;
  if (!state.recalls.length) {
    setEmptyState(els.recallEmptyState, "리콜 없음", "조건에 맞는 리콜이 없습니다.");
  }

  state.recalls.forEach((recall) => {
    const key = recallKey(recall);
    const selected = state.selectedRecalls.has(key);
    const edit = getRecallEdit(recall);
    const activeScan = state.activeRecallScanKey === key;
    const card = makeEl("article", `recall-card ${selected ? "selected" : ""}`);

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selected;
    checkbox.disabled = state.isScanning;
    checkbox.addEventListener("change", () => {
      if (checkbox.checked) state.selectedRecalls.add(key);
      else state.selectedRecalls.delete(key);
      renderRecalls();
    });

    const title = makeEl("h3", "", compactText(recall.display_title, "이름 없는 리콜"));
    const meta = makeEl("div", "recall-meta");
    const freshness = recallDateInfo(recall);
    [
      recall.brand_name && `브랜드 ${recall.brand_name}`,
      recall.model_name && `모델 ${recall.model_name}`,
      recall.source,
      recall.recall_country,
      freshness && `${freshness.label} ${freshness.formatted}`,
      recall.risk_level,
    ]
      .filter(Boolean)
      .forEach((item) => meta.append(makeEl("span", "meta-chip", item)));

    const body = makeEl("div", "recall-body");
    if (recall.image_1) {
      const image = document.createElement("img");
      image.src = recall.image_1;
      image.alt = "";
      image.loading = "lazy";
      body.append(image);
    } else {
      body.classList.add("no-image");
    }

    const content = makeEl("div", "recall-content");
    const header = makeEl("div", "recall-card-header");
    header.append(checkbox, title);
    content.append(header, meta);
    if (recall.hazard_type || recall.hazard_description) {
      content.append(
        makeEl(
          "p",
          "recall-hazard",
          compactText(recall.hazard_type || recall.hazard_description, "")
        )
      );
    }
    const scanButton = makeEl("button", "button small primary", activeScan ? "스캔 중" : "이 카드 스캔");
    scanButton.type = "button";
    scanButton.disabled = state.isScanning || !edit.query.trim();
    scanButton.addEventListener("click", () => scanRecall(recall));

    const resetButton = makeEl("button", "button small", "기본값");
    resetButton.type = "button";
    resetButton.disabled = state.isScanning;
    resetButton.addEventListener("click", () => resetRecallEdit(recall));

    const scanEditor = makeEl("div", "scan-editor");
    const queryField = makeEl("label", "scan-field");
    const queryInput = document.createElement("input");
    queryInput.value = edit.query;
    queryInput.autocomplete = "off";
    queryInput.placeholder = "모델명 또는 제품명";
    queryInput.addEventListener("input", (event) => {
      updateRecallEdit(recall, "query", event.target.value);
      scanButton.disabled = state.isScanning || !event.target.value.trim();
    });
    queryField.append(makeEl("span", "", "검색어"), queryInput);

    const verifyField = makeEl("label", "scan-field optional");
    const verifyInput = document.createElement("input");
    verifyInput.value = edit.verify;
    verifyInput.autocomplete = "off";
    verifyInput.placeholder = "브랜드, 제조사";
    verifyInput.addEventListener("input", (event) => {
      updateRecallEdit(recall, "verify", event.target.value);
    });
    verifyField.append(makeEl("span", "", "검증어"), verifyInput);
    scanEditor.append(queryField, verifyField);

    const cardActions = makeEl("div", "recall-card-actions");
    cardActions.append(resetButton, scanButton);
    content.append(scanEditor, cardActions);

    const resultRows = recallResultRows(recall, key);
    if (resultRows.length) {
      content.append(renderRecallResults(resultRows));
    }

    if (recall.source_url) {
      const sourceLink = makeEl("a", "detail-link", "원문");
      sourceLink.href = recall.source_url;
      sourceLink.target = "_blank";
      sourceLink.rel = "noreferrer";
      content.append(sourceLink);
    }

    body.append(content);
    card.append(body);
    els.recallList.append(card);
  });

  els.selectedRecallCount.textContent = state.selectedRecalls.size;
  const selectionSummary = els.selectedRecallCount.closest(".selection-summary");
  if (selectionSummary) {
    selectionSummary.classList.toggle("active", state.selectedRecalls.size > 0);
  }
  els.selectVisibleButton.disabled = state.isScanning || state.recalls.length === 0;
  els.clearSelectionButton.disabled = state.isScanning || state.selectedRecalls.size === 0;
  els.scanSelectedButton.disabled = state.isScanning || state.selectedRecalls.size === 0;
}

async function loadRecalls(event) {
  if (event) event.preventDefault();
  const apiKey = els.apiKeyInput.value.trim();
  if (apiKey) sessionStorage.setItem("recallHubApiKey", apiKey);

  setServerState("리콜 조회 중", "busy");
  try {
    const payload = {
      api_key: apiKey,
      mode: els.recallModeInput.value,
      q: els.recallSearchInput.value.trim(),
      source: els.sourceInput.value,
      risk_bucket: els.riskInput.value,
      korea_relevance: els.koreaInput.value,
      days: Number(els.daysInput.value || 30),
      limit: Number(els.recallLimitInput.value || 30),
    };
    const data = await postJson("/api/recalls", payload);
    state.recalls = Array.isArray(data.data) ? data.data : [];
    state.lastRecallLoadedAt = new Date();
    state.selectedRecalls.clear();
    state.recallEdits.clear();
    renderRecalls();
    setServerState("준비됨", "ready");
  } catch (error) {
    setServerState("오류", "error");
    els.recallEmptyState.hidden = false;
    els.recallEmptyState.textContent = error.message;
  }
}

async function scanRecallBatch(recalls, label, activeKey = null) {
  if (!recalls.length || state.isScanning) return;

  const scanPayload = recalls.map(buildRecallScanPayload);
  const progressId = createProgressId();
  state.isScanning = true;
  state.activeRecallScanKey = activeKey;
  els.scanSelectedButton.disabled = true;
  els.runLog.hidden = false;
  els.runLog.textContent = els.recallManualVerifyInput.checked
    ? `${label} 스캔 실행 중...\n차단 화면이 뜨면 열린 브라우저에서 보안 확인을 완료하세요.`
    : `${label} 스캔 실행 중...`;
  setServerState("스캔 중", "busy");
  startProgressPolling(progressId);
  renderRecalls();

  try {
    const result = await postJson("/api/scan-recalls", {
      recalls: scanPayload,
      platform: els.recallScanPlatformInput.value,
      max_items: Number(els.recallScanMaxInput.value || 20),
      manual_verify_blocked: els.recallManualVerifyInput.checked,
      progress_id: progressId,
    });
    await pollScanProgress(progressId).catch(() => {});
    const logLines = [result.stdout, result.stderr].filter(Boolean);
    if (Array.isArray(result.skipped) && result.skipped.length) {
      logLines.push(`검색어가 비어 있는 리콜 ${result.skipped.length}개를 건너뛰었습니다.`);
    }
    els.runLog.textContent = logLines.join("\n").trim() || "스캔 완료";
    state.selectedIndex = null;
    await loadResults();
  } catch (error) {
    await pollScanProgress(progressId).catch(() => {});
    setServerState("오류", "error");
    els.runLog.textContent = `${els.runLog.textContent}\n${error.message}`.trim();
  } finally {
    stopProgressPolling();
    state.activeProgressId = null;
    state.isScanning = false;
    state.activeRecallScanKey = null;
    renderRecalls();
  }
}

async function scanSelectedRecalls() {
  const selected = state.recalls.filter((recall) => state.selectedRecalls.has(recallKey(recall)));
  await scanRecallBatch(selected, `${selected.length}개 리콜`);
}

async function scanRecall(recall) {
  await scanRecallBatch([recall], compactText(recall.display_title, "선택한 리콜"), recallKey(recall));
}

function getFilteredRows() {
  const term = els.tableSearchInput.value.trim().toLowerCase();
  const status = els.statusFilter.value;
  const platform = els.platformFilter.value;

  return state.rows.filter((row) => {
    const text = [row.platform, row.query, row.verify, row.model_name, row.source_id]
      .join(" ")
      .toLowerCase();
    return (
      (!term || text.includes(term)) &&
      (!status || row.status === status) &&
      (!platform || row.platform === platform)
    );
  });
}

function renderTable() {
  const rows = getFilteredRows();
  els.tableBody.replaceChildren();
  els.emptyState.hidden = rows.length > 0;
  els.filteredResultCount.textContent = `${rows.length}건 표시`;
  if (!rows.length) {
    setEmptyState(els.emptyState, "결과 없음", "현재 필터에 맞는 결과가 없습니다.");
  }

  rows.forEach((row) => {
    const tr = document.createElement("tr");
    tr.tabIndex = 0;
    tr.className = `status-${row.status} ${state.selectedIndex === row.index ? "selected" : ""}`.trim();
    tr.addEventListener("click", () => selectRow(row.index));
    tr.addEventListener("keydown", (event) => {
      if (event.key === "Enter") selectRow(row.index);
    });

    const statusCell = document.createElement("td");
    statusCell.append(makeStatusPill(row.status));

    tr.append(
      statusCell,
      makeEl("td", "", platformLabels[row.platform] || row.platform),
      makeEl("td", "", row.query || "-"),
      makeEl("td", "muted", row.verify || "-"),
      makeEl("td", "", String(row.matches.length)),
      makeEl("td", "muted", formatDate(row.searched_at))
    );
    els.tableBody.append(tr);
  });

  if (state.selectedIndex !== null && !rows.some((row) => row.index === state.selectedIndex)) {
    state.selectedIndex = rows[0]?.index ?? null;
  }
  renderDetail();
}

function selectRow(index) {
  state.selectedIndex = index;
  renderTable();
}

function renderDetail() {
  els.detailPanel.replaceChildren();
  const row = state.rows.find((item) => item.index === state.selectedIndex);
  if (!row) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "상세 없음"));
    empty.append(makeEl("p", "empty-copy", "결과 행을 선택하면 상품과 스크린샷을 확인할 수 있습니다."));
    els.detailPanel.append(empty);
    return;
  }

  const header = makeEl("div", "detail-header");
  const title = makeEl("h2", "", row.query || "검색어 없음");
  const status = makeStatusPill(row.status);
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", platformLabels[row.platform] || row.platform));
  meta.append(makeEl("span", "meta-chip", `${row.searched_items}개 확인`));
  if (row.verify) meta.append(makeEl("span", "meta-chip", row.verify));
  if (row.source_id) meta.append(makeEl("span", "meta-chip", row.source_id));
  if (row.manual_verification?.required || row.manual_verification?.requested) {
    meta.append(
      makeEl(
        "span",
        "meta-chip",
        row.manual_verification.completed
          ? "수동 검증 완료"
          : row.manual_verification.required
            ? "수동 검증 필요"
            : "수동 검증 미완료"
      )
    );
  }
  header.append(status, title, meta);
  els.detailPanel.append(header);
  if (statusDescriptions[row.status]) {
    els.detailPanel.append(makeEl("p", "detail-note", statusDescriptions[row.status]));
  }

  const actions = makeEl("div", "detail-actions");
  if (row.status === "blocked" || row.status === "manual_required") {
    const manualButton = makeEl(
      "button",
      "button small primary",
      state.isScanning
        ? "수동 검증 중"
        : row.status === "manual_required"
          ? "수동 검증 스캔"
          : "수동 검증 재스캔"
    );
    manualButton.type = "button";
    manualButton.disabled = state.isScanning || !row.query || row.platform === "unknown";
    manualButton.addEventListener("click", () => manualVerifyRow(row));
    actions.append(manualButton);
  }
  if (row.screenshot) {
    const screenshot = makeEl("a", "detail-link", "스크린샷 열기");
    screenshot.href = `/api/screenshot?path=${encodeURIComponent(row.screenshot)}`;
    screenshot.target = "_blank";
    screenshot.rel = "noreferrer";
    actions.append(screenshot);
  }
  if (row.error) actions.append(makeEl("span", "meta-chip", row.error));
  if (actions.childNodes.length) els.detailPanel.append(actions);

  const list = makeEl("div", "match-list");
  if (!row.matches.length) {
    list.append(makeEl("div", "empty-state", "탐지 상품 없음"));
  } else {
    row.matches.forEach((match) => {
      const item = makeEl("article", "match-item");
      item.append(makeEl("h3", "", match.title || "상품명 없음"));
      if (match.price) item.append(makeEl("p", "muted", match.price));
      if (match.url) {
        const link = makeEl("a", "", "상품 열기");
        link.href = match.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        item.append(link);
      }
      list.append(item);
    });
  }
  els.detailPanel.append(list);
}

async function loadResults(path = "") {
  setServerState("불러오는 중", "busy");
  const suffix = path ? `?file=${encodeURIComponent(path)}` : "";
  const response = await fetch(`/api/results${suffix}`, { cache: "no-store" });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  const data = await response.json();

  state.files = data.files || [];
  state.selectedPath = data.selected || "";
  state.rows = normalizeRows(data.payload);
  if (state.selectedIndex === null && state.rows.length) {
    state.selectedIndex = state.rows[0].index;
  }

  state.summary = data.summary || {};
  renderMetrics(state.summary);
  renderResultInsight();
  renderResultTimestamp(state.summary);
  renderFileSelect(state.files, state.selectedPath);
  renderPlatformFilter(state.rows);
  renderTable();
  renderRecalls();
  setServerState("준비됨", "ready");
}

async function runScan(event) {
  event.preventDefault();
  const payload = {
    keyword: els.keywordInput.value.trim(),
    verify: els.verifyInput.value.trim(),
    platform: els.scanPlatformInput.value,
    max_items: Number(els.maxItemsInput.value || 20),
    manual_verify_blocked: els.manualVerifyInput.checked,
  };

  if (!payload.keyword) {
    els.keywordInput.focus();
    return;
  }

  els.runButton.disabled = true;
  state.isScanning = true;
  els.runLog.hidden = false;
  els.runLog.textContent = payload.manual_verify_blocked
    ? "스캔 실행 중...\n차단 화면이 뜨면 열린 브라우저에서 보안 확인을 완료하세요."
    : "스캔 실행 중...";
  setServerState("스캔 중", "busy");
  renderRecalls();

  try {
    const result = await postJson("/api/scan", payload);
    els.runLog.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    state.selectedIndex = null;
    await loadResults();
  } catch (error) {
    setServerState("오류", "error");
    els.runLog.textContent = `${els.runLog.textContent}\n${error.message}`.trim();
  } finally {
    els.runButton.disabled = false;
    state.isScanning = false;
    renderRecalls();
  }
}

async function manualVerifyRow(row) {
  if (!row || state.isScanning) return;

  state.isScanning = true;
  els.runButton.disabled = true;
  els.runLog.hidden = false;
  els.runLog.textContent =
    "차단 항목 수동 검증 중...\n열린 브라우저에서 보안 확인을 완료하면 스캔이 자동으로 이어집니다.";
  setServerState("수동 검증 중", "busy");
  renderRecalls();
  renderDetail();

  try {
    const result = await postJson("/api/scan", {
      keyword: row.query,
      verify: row.verify,
      platform: row.platform === "unknown" ? "" : row.platform,
      max_items: Number(els.maxItemsInput.value || 20),
      manual_verify_blocked: true,
    });
    els.runLog.textContent = [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
    state.selectedIndex = null;
    await loadResults();
  } catch (error) {
    setServerState("오류", "error");
    els.runLog.textContent = `${els.runLog.textContent}\n${error.message}`.trim();
  } finally {
    els.runButton.disabled = false;
    state.isScanning = false;
    renderRecalls();
    renderDetail();
  }
}

function showLoadError(error) {
  setServerState("오류", "error");
  els.emptyState.hidden = false;
  els.emptyState.textContent = `결과를 불러오지 못했습니다. ${error.message}`;
}

els.refreshButton.addEventListener("click", () => loadResults(state.selectedPath).catch(showLoadError));
els.recallForm.addEventListener("submit", loadRecalls);
els.selectVisibleButton.addEventListener("click", () => {
  state.recalls.forEach((recall) => state.selectedRecalls.add(recallKey(recall)));
  renderRecalls();
});
els.clearSelectionButton.addEventListener("click", () => {
  state.selectedRecalls.clear();
  renderRecalls();
});
els.scanSelectedButton.addEventListener("click", scanSelectedRecalls);
els.resultFileSelect.addEventListener("change", () => {
  state.selectedIndex = null;
  loadResults(els.resultFileSelect.value).catch(showLoadError);
});
els.downloadJsonButton.addEventListener("click", () => downloadResults("json"));
els.downloadExcelButton.addEventListener("click", () => downloadResults("xlsx"));
els.tableSearchInput.addEventListener("input", renderTable);
els.statusFilter.addEventListener("change", () => {
  renderTable();
  renderResultInsight();
});
els.platformFilter.addEventListener("change", renderTable);
els.scanForm.addEventListener("submit", runScan);

renderRecalls();
setDownloadButtons(false);
els.resultInsight.hidden = true;
loadResults().catch(showLoadError);
