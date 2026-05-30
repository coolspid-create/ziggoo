const state = {
  recalls: [],
  isSearching: false,
  activeRecallKey: "",
  lastResult: null,
  lastRecallLoadedAt: null,
  activeLensContext: null,
  lensCandidates: [],
  isBatchSearching: false,
  batchCancelRequested: false,
  batchAbortController: null,
  batchResults: [],
  productResults: [],
  batchResultTab: "targets",
  batchStatusFilter: "all",
  selectedRecallKey: "",
};

const els = {
  imageSearchState: document.querySelector("#imageSearchState"),
  clearImageResultsButton: document.querySelector("#clearImageResultsButton"),
  visionApiKeyInput: document.querySelector("#visionApiKeyInput"),
  imageMaxResultsInput: document.querySelector("#imageMaxResultsInput"),
  targetPlatformInputs: Array.from(document.querySelectorAll(".targetPlatformInput")),
  directImageForm: document.querySelector("#directImageForm"),
  directImageUrlInput: document.querySelector("#directImageUrlInput"),
  directProductInput: document.querySelector("#directProductInput"),
  directBrandInput: document.querySelector("#directBrandInput"),
  directModelInput: document.querySelector("#directModelInput"),
  directLensButton: document.querySelector("#directLensButton"),
  directImageSearchButton: document.querySelector("#directImageSearchButton"),
  directProductSearchButton: document.querySelector("#directProductSearchButton"),
  batchVisionButton: document.querySelector("#batchVisionButton"),
  batchProductButton: document.querySelector("#batchProductButton"),
  cancelBatchButton: document.querySelector("#cancelBatchButton"),
  batchVisionProgress: document.querySelector("#batchVisionProgress"),
  lensCandidateInput: document.querySelector("#lensCandidateInput"),
  collectLensCandidatesButton: document.querySelector("#collectLensCandidatesButton"),
  clearLensCandidatesButton: document.querySelector("#clearLensCandidatesButton"),
  lensCandidateCount: document.querySelector("#lensCandidateCount"),
  lensCandidateList: document.querySelector("#lensCandidateList"),
  imageRecallForm: document.querySelector("#imageRecallForm"),
  imageRecallApiKeyInput: document.querySelector("#imageRecallApiKeyInput"),
  imageRecallModeInput: document.querySelector("#imageRecallModeInput"),
  imageRecallSearchInput: document.querySelector("#imageRecallSearchInput"),
  imageRecallLimitInput: document.querySelector("#imageRecallLimitInput"),
  imageRecallLoadedCount: document.querySelector("#imageRecallLoadedCount"),
  imageRecallFreshness: document.querySelector("#imageRecallFreshness"),
  imageRecallList: document.querySelector("#imageRecallList"),
  imageRecallEmptyState: document.querySelector("#imageRecallEmptyState"),
  imageResultPanel: document.querySelector("#imageResultPanel"),
};

const statusLabels = {
  image_matched: "후보 발견",
  image_candidate: "확인 후보",
  image_no_match: "대상 마켓 없음",
  image_no_image: "이미지 없음",
  image_search_error: "검색 오류",
  image_weak: "정보 부족",
  text_matched: "판매 후보",
  text_candidate: "판매 검토",
  text_no_match: "판매처 없음",
  text_no_query: "검색어 없음",
};

const platformLabels = {
  elevenst: "11번가",
  coupang: "쿠팡",
  gmarket: "G마켓",
  naver: "네이버",
};

const marketDomains = {
  elevenst: ["11st.co.kr", "www.11st.co.kr"],
  coupang: ["coupang.com", "www.coupang.com"],
  gmarket: ["gmarket.co.kr", "www.gmarket.co.kr", "item.gmarket.co.kr", "global.gmarket.co.kr", "gsearch.gmarket.co.kr"],
  naver: ["shopping.naver.com", "smartstore.naver.com"],
};

const marketHostKeywords = {
  elevenst: ["11st"],
  coupang: ["coupang"],
  gmarket: ["gmarket"],
  naver: ["naver", "smartstore"],
};

const commerceDomains = {
  amazon: ["amazon.com", "www.amazon.com", "amazon.co.jp", "www.amazon.co.jp"],
  ebay: ["ebay.com", "www.ebay.com"],
  alibaba: ["alibaba.com", "www.alibaba.com"],
  aliexpress: ["aliexpress.com", "www.aliexpress.com"],
  walmart: ["walmart.com", "www.walmart.com"],
  etsy: ["etsy.com", "www.etsy.com"],
  temu: ["temu.com", "www.temu.com"],
  rakuten: ["rakuten.co.jp", "www.rakuten.co.jp", "search.rakuten.co.jp"],
  naver: ["shopping.naver.com", "smartstore.naver.com"],
  auction: ["auction.co.kr", "www.auction.co.kr"],
  lotteon: ["lotteon.com", "www.lotteon.com"],
  ssg: ["ssg.com", "www.ssg.com"],
};

const commerceLabels = {
  amazon: "Amazon",
  ebay: "eBay",
  alibaba: "Alibaba",
  aliexpress: "AliExpress",
  walmart: "Walmart",
  etsy: "Etsy",
  temu: "Temu",
  rakuten: "Rakuten",
  naver: "네이버 쇼핑",
  auction: "옥션",
  lotteon: "롯데ON",
  ssg: "SSG",
  visual: "유사 이미지",
};

const diagnosticCountLabels = {
  web_entities: "이름/키워드 단서",
  best_guess_labels: "이미지 추정명",
  pages_with_matching_images: "관련 페이지",
  full_matching_images: "같은 이미지 파일",
  partial_matching_images: "일부 일치 이미지",
  visually_similar_images: "유사 이미지",
  detected_urls: "찾은 링크",
  target_platform_urls: "11번가/쿠팡/G마켓/네이버 링크",
  target_platform_image_urls: "마켓 이미지 파일",
};

const imageAssetExtensions = [".avif", ".bmp", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"];

const diagnosticSourceLabels = {
  pagesWithMatchingImages: "관련 페이지",
  "page.fullMatchingImages": "페이지 안 같은 이미지",
  "page.partialMatchingImages": "페이지 안 일부 일치 이미지",
  fullMatchingImages: "같은 이미지 파일",
  partialMatchingImages: "일부 일치 이미지",
  visuallySimilarImages: "유사 이미지",
};

const savedVisionKey = sessionStorage.getItem("ziggooVisionApiKey");
if (savedVisionKey) els.visionApiKeyInput.value = savedVisionKey;
const savedRecallKey = sessionStorage.getItem("recallHubApiKey");
if (savedRecallKey) els.imageRecallApiKeyInput.value = savedRecallKey;

function compactText(value, fallback = "-") {
  const text = `${value || ""}`.replace(/\s+/g, " ").trim();
  return text || fallback;
}

function tokenize(value) {
  return `${value || ""}`
    .toLowerCase()
    .replace(/[^0-9a-z가-힣]+/gi, " ")
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token, index, list) => token.length >= 2 && list.indexOf(token) === index);
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
  els.imageRecallLoadedCount.textContent = `${state.recalls.length}건`;
  if (!els.imageRecallFreshness) return;
  if (!state.recalls.length) {
    els.imageRecallFreshness.textContent = state.lastRecallLoadedAt ? "표시할 리콜 없음" : "불러오기 전";
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
  els.imageRecallFreshness.textContent = loadedAt ? `${latestText} · 불러옴 ${loadedAt}` : latestText;
}

function makeEl(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function openImagePreview(imageUrl, title = "", detail = "") {
  if (!imageUrl) return;
  const overlay = makeEl("div", "image-lightbox");
  const dialog = makeEl("div", "image-lightbox-dialog");
  const header = makeEl("div", "image-lightbox-header");
  header.append(makeEl("strong", "", compactText(title, "이미지")));
  const closeButton = makeEl("button", "image-lightbox-close", "닫기");
  closeButton.type = "button";
  header.append(closeButton);
  dialog.append(header);

  const image = document.createElement("img");
  image.src = imageUrl;
  image.alt = title || "";
  dialog.append(image);

  if (detail) {
    const caption = makeEl("p", "image-lightbox-caption", detail);
    dialog.append(caption);
  }

  overlay.append(dialog);
  const close = () => overlay.remove();
  closeButton.addEventListener("click", close);
  overlay.addEventListener("click", (event) => {
    if (event.target === overlay) close();
  });
  document.addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Escape") close();
    },
    { once: true }
  );
  document.body.append(overlay);
}

function urlHost(url) {
  try {
    return new URL(url).hostname.toLowerCase();
  } catch {
    return "";
  }
}

function hostMatches(host, domains) {
  return domains.some((domain) => host === domain || host.endsWith(`.${domain}`));
}

function hostIncludesKeyword(host, keywords) {
  return keywords.some((keyword) => host.includes(keyword));
}

function detectMarketPlatform(url) {
  const host = urlHost(url);
  if (!host) return "";
  for (const [platform, domains] of Object.entries(marketDomains)) {
    if (hostMatches(host, domains)) return platform;
  }
  for (const [platform, keywords] of Object.entries(marketHostKeywords)) {
    if (hostIncludesKeyword(host, keywords)) return platform;
  }
  return "";
}

function detectCommercePlatform(url) {
  const host = urlHost(url);
  if (!host) return "";
  const market = detectMarketPlatform(url);
  if (market) return market;
  for (const [platform, domains] of Object.entries(commerceDomains)) {
    if (hostMatches(host, domains)) return platform;
  }
  return "";
}

function looksLikeImageAssetUrl(url) {
  try {
    const path = new URL(url).pathname.toLowerCase();
    return imageAssetExtensions.some((extension) => path.endsWith(extension));
  } catch {
    return false;
  }
}

function marketPageFromImageAsset(platform, url) {
  if (platform !== "gmarket") return "";
  try {
    const parts = new URL(url).pathname.split("/").filter(Boolean);
    for (let index = parts.length - 1; index >= 0; index -= 1) {
      if (/^\d{8,12}$/.test(parts[index])) {
        return `https://item.gmarket.co.kr/Item?goodscode=${parts[index]}`;
      }
    }
  } catch {
    return "";
  }
  return "";
}

function cleanUrlCandidate(value) {
  let text = `${value || ""}`
    .replace(/&amp;/g, "&")
    .replace(/[)\].,;'"<>]+$/g, "")
    .trim();
  if (!text) return "";
  if (/^www\./i.test(text)) text = `https://${text}`;
  if (!/^https?:\/\//i.test(text)) text = `https://${text}`;

  try {
    const parsed = new URL(text);
    if (/(^|\.)google\./i.test(parsed.hostname)) {
      const redirected = parsed.searchParams.get("q")
        || parsed.searchParams.get("url")
        || parsed.searchParams.get("u")
        || parsed.searchParams.get("adurl");
      if (redirected && /^https?:\/\//i.test(redirected)) return cleanUrlCandidate(redirected);
    }
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return "";
  }
}

function extractUrlsFromLine(line) {
  const matches = [
    ...(`${line || ""}`.match(/(?:https?:\/\/|www\.)[^\s<>"'`]+/gi) || []),
    ...(`${line || ""}`.match(/\b(?:[a-z0-9-]+\.)*(?:11st|coupang|gmarket|naver|smartstore)[a-z0-9.-]*\.[a-z]{2,}[^\s<>"'`]*/gi) || []),
  ];
  return matches.map(cleanUrlCandidate).filter(Boolean);
}

function recallLensTerms(recall = {}) {
  return {
    title: compactText(recall.display_title || recall.product_name || recall.product_name_original, ""),
    brand: compactText(recall.brand_name || recall.brand || recall.manufacturer, ""),
    model: compactText(recall.model_name || recall.model, ""),
  };
}

function candidateScore(candidate, recall = {}) {
  const selected = selectedPlatforms();
  const terms = recallLensTerms(recall);
  const haystack = `${candidate.title} ${candidate.url}`.toLowerCase();
  let score = selected.includes(candidate.platform) ? 60 : 25;
  const reasons = [selected.includes(candidate.platform) ? "대상 플랫폼" : "기타 쇼핑몰"];

  [
    ["모델명", terms.model, 25],
    ["브랜드", terms.brand, 15],
    ["제품명", terms.title, 20],
  ].forEach(([label, value, points]) => {
    const tokens = tokenize(value);
    if (!tokens.length) return;
    const matched = tokens.filter((token) => haystack.includes(token));
    if (!matched.length) return;
    score += Math.round(Number(points) * matched.length / tokens.length);
    reasons.push(`${label} 토큰 ${matched.length}/${tokens.length}개`);
  });

  return { score: Math.min(score, 100), reasons };
}

function recallKey(recall) {
  return `${recall.source || "src"}:${recall.guid || recall.id || recall.display_title}`;
}

function sameRecall(a = {}, b = {}) {
  return recallKey(a) === recallKey(b);
}

function batchItemForRecall(recall) {
  return state.batchResults.find((item) => item.recall && sameRecall(item.recall, recall)) || null;
}

function productItemForRecall(recall) {
  return state.productResults.find((item) => item.recall && sameRecall(item.recall, recall)) || null;
}

function resultForRecall(recall) {
  const batchItem = batchItemForRecall(recall);
  if (batchItem) return batchItem;
  if (state.lastResult?.recall && sameRecall(state.lastResult.recall, recall)) {
    return { recall, result: state.lastResult };
  }
  return null;
}

function upsertProductResult(recall, result = null, error = "") {
  const key = recallKey(recall);
  const existingIndex = state.productResults.findIndex((item) => item.recall && recallKey(item.recall) === key);
  const payload = { recall, product_result: result, product_error: error };
  if (existingIndex >= 0) {
    state.productResults.splice(existingIndex, 1, payload);
  } else {
    state.productResults.push(payload);
  }
}

function batchDisplayItems() {
  const map = new Map();
  const ensure = (recall) => {
    const key = recallKey(recall);
    if (!map.has(key)) map.set(key, { recall });
    return map.get(key);
  };
  state.batchResults.forEach((item) => Object.assign(ensure(item.recall), item));
  state.productResults.forEach((item) => Object.assign(ensure(item.recall), item));
  return Array.from(map.values());
}

function recallImageUrls(recall) {
  const keys = [
    "image_url",
    "image",
    "image_1",
    "image_2",
    "image_3",
    "image_4",
    "image_5",
    "image1",
    "image2",
    "thumbnail",
    "thumbnail_url",
    "main_image_url",
    "product_image_url",
  ];
  const urls = [];
  const add = (value) => {
    const text = compactText(value, "");
    if (text && !urls.includes(text)) urls.push(text);
  };
  for (const key of keys) {
    add(recall[key]);
  }
  if (Array.isArray(recall.images)) {
    for (const image of recall.images) {
      if (typeof image === "string") add(image);
      if (image && typeof image === "object") {
        for (const key of keys) {
          const before = urls.length;
          add(image[key]);
          if (urls.length > before) break;
        }
      }
    }
  }
  return urls;
}

function recallImageUrl(recall) {
  return recallImageUrls(recall)[0] || "";
}

function selectedPlatforms() {
  return els.targetPlatformInputs.filter((input) => input.checked).map((input) => input.value);
}

function lensSearchUrl(imageUrl) {
  return `https://lens.google.com/uploadbyurl?url=${encodeURIComponent(imageUrl)}`;
}

function setStateLabel(text, mode = "") {
  els.imageSearchState.textContent = text;
  els.imageSearchState.className = `topbar-meta ${mode}`.trim();
}

function hasImageRecalls() {
  return state.recalls.some((recall) => Boolean(recallImageUrl(recall)));
}

function applyBusyState() {
  const busy = state.isSearching || state.isBatchSearching;
  els.directImageSearchButton.disabled = busy;
  if (els.directProductSearchButton) {
    els.directProductSearchButton.disabled = busy;
  }
  if (els.batchVisionButton) {
    els.batchVisionButton.disabled = busy || !hasImageRecalls();
  }
  if (els.batchProductButton) {
    els.batchProductButton.disabled = busy || state.recalls.length === 0;
  }
  if (els.cancelBatchButton) {
    els.cancelBatchButton.hidden = !state.isBatchSearching;
    els.cancelBatchButton.disabled = !state.isBatchSearching;
  }
  document
    .querySelectorAll(".image-recall-search-button")
    .forEach((button) => {
      button.disabled = busy || button.dataset.hasImage !== "true";
    });
  document
    .querySelectorAll(".product-recall-search-button")
    .forEach((button) => {
      button.disabled = busy;
    });
}

function setBusy(isBusy) {
  state.isSearching = isBusy;
  applyBusyState();
}

function directRecallPayload(imageUrl) {
  return {
    image_url: imageUrl,
    product_name: els.directProductInput.value.trim(),
    brand_name: els.directBrandInput.value.trim(),
    model_name: els.directModelInput.value.trim(),
  };
}

async function postJson(url, payload, options = {}) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
    signal: options.signal,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}

function baseImagePayload() {
  const visionKey = els.visionApiKeyInput.value.trim();
  if (visionKey) sessionStorage.setItem("ziggooVisionApiKey", visionKey);
  return {
    vision_api_key: visionKey,
    max_results: Number(els.imageMaxResultsInput.value || 20),
    target_platforms: selectedPlatforms(),
  };
}

function baseProductPayload() {
  return {
    target_platforms: selectedPlatforms(),
    max_items: 8,
    max_queries: 6,
  };
}

async function runImageSearch(payload, label = "이미지") {
  if (state.isSearching) return;
  setBusy(true);
  setStateLabel(`${label} 검색 중...`, "busy");
  renderLoading(label);
  try {
    const result = await postJson("/api/image-search", {
      ...baseImagePayload(),
      ...payload,
    });
    state.lastResult = result;
    setStateLabel("이미지 검색 완료", "ready");
    if (payload.recall && state.selectedRecallKey === recallKey(payload.recall)) {
      renderRecallDetail(payload.recall);
    } else {
      renderImageResult(result);
    }
  } catch (error) {
    setStateLabel("이미지 검색 오류", "error");
    renderError(error.message);
  } finally {
    state.activeRecallKey = "";
    setBusy(false);
    renderRecalls();
  }
}

async function runProductSearch(payload, label = "제품") {
  if (state.isSearching) return;
  const recall = payload.recall || directRecallPayload("");
  setBusy(true);
  setStateLabel(`${label} 판매처 검색 중...`, "busy");
  renderLoading(`${label} 판매처`);
  try {
    const result = await postJson("/api/product-search", {
      ...baseProductPayload(),
      ...payload,
    });
    upsertProductResult(recall, result);
    setStateLabel("판매처 검색 완료", "ready");
    if (payload.recall && state.selectedRecallKey === recallKey(payload.recall)) {
      renderRecallDetail(payload.recall);
    } else {
      renderProductSearchResult(result);
    }
  } catch (error) {
    upsertProductResult(recall, null, error.message);
    setStateLabel("판매처 검색 오류", "error");
    renderError(error.message);
  } finally {
    state.activeRecallKey = "";
    setBusy(false);
    renderRecalls();
  }
}

function renderLensGuide(imageUrl, recall = {}) {
  els.imageResultPanel.replaceChildren();

  const header = makeEl("div", "detail-header");
  header.append(
    makeEl("span", "status-pill image_candidate", "Lens 검증"),
    makeEl("h2", "", "Google Lens를 열었습니다")
  );
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", "1차: Lens 결과 확인"));
  meta.append(makeEl("span", "meta-chip", "2차: 플랫폼/모델명 교차 검증 예정"));
  header.append(meta);
  els.imageResultPanel.append(header);

  const source = makeEl("div", "image-source-preview");
  const image = document.createElement("img");
  image.src = imageUrl;
  image.alt = "";
  source.append(image);

  const sourceInfo = makeEl("div", "");
  sourceInfo.append(makeEl("strong", "", "검색 원본 이미지"));
  const lensLink = makeEl("a", "detail-link", "Google Lens 다시 열기");
  lensLink.href = lensSearchUrl(imageUrl);
  lensLink.target = "_blank";
  lensLink.rel = "noreferrer";
  sourceInfo.append(lensLink);
  source.append(sourceInfo);
  els.imageResultPanel.append(source);

  const terms = [
    recall.display_title || recall.product_name,
    recall.brand_name,
    recall.model_name,
  ].filter((value) => compactText(value, ""));
  if (terms.length) {
    const group = makeEl("div", "image-term-group");
    if (recall.display_title || recall.product_name) {
      group.append(makeEl("span", "meta-chip", `제품명: ${recall.display_title || recall.product_name}`));
    }
    if (recall.brand_name) group.append(makeEl("span", "meta-chip", `브랜드: ${recall.brand_name}`));
    if (recall.model_name) group.append(makeEl("span", "meta-chip", `모델명: ${recall.model_name}`));
    els.imageResultPanel.append(group);
  }

  const guide = makeEl("div", "image-warning");
  guide.append(makeEl("p", "", "우선 Lens 결과가 정상적으로 뜨는지 확인하세요."));
  guide.append(makeEl("p", "", "Lens 결과에 11번가, 쿠팡, G마켓, 네이버 상품이 보이는지와 제품명/모델명 비교를 확인합니다."));
  els.imageResultPanel.append(guide);
}

function openLensForImage(imageUrl, recall = {}) {
  if (!imageUrl) return;
  state.activeLensContext = { imageUrl, recall };
  const lensUrl = lensSearchUrl(imageUrl);
  const opened = window.open(lensUrl, "_blank");
  if (opened) {
    opened.opener = null;
  } else {
    window.location.assign(lensUrl);
  }
  state.lastResult = null;
  setStateLabel("Google Lens를 열었습니다", "ready");
  renderLensGuide(imageUrl, recall);
}

function collectLensCandidatesFromText(text) {
  const recall = state.activeLensContext?.recall || directRecallPayload(els.directImageUrlInput.value.trim());
  const selected = selectedPlatforms();
  const lines = `${text || ""}`.split(/\r?\n/);
  const seen = new Set();
  const candidates = [];
  let previousTitle = "";

  lines.forEach((rawLine) => {
    const line = rawLine.trim();
    if (!line) return;
    const urls = extractUrlsFromLine(line);
    if (!urls.length) {
      if (line.length <= 180) previousTitle = line;
      return;
    }

    urls.forEach((url) => {
      let candidateUrl = url;
      const marketPlatform = detectMarketPlatform(candidateUrl);
      if (marketPlatform && looksLikeImageAssetUrl(candidateUrl)) {
        candidateUrl = marketPageFromImageAsset(marketPlatform, candidateUrl);
        if (!candidateUrl) return;
      }
      const key = candidateUrl.toLowerCase();
      if (seen.has(key)) return;
      seen.add(key);
      const commercePlatform = marketPlatform || detectCommercePlatform(candidateUrl);
      if (!commercePlatform) return;

      const title = compactText(line.replace(url, "").trim() || previousTitle, "제목 없음");
      const candidate = {
        url: candidateUrl,
        title,
        platform: marketPlatform || commercePlatform,
        platform_label: platformLabels[marketPlatform] || commerceLabels[commercePlatform] || commercePlatform,
        is_target_platform: Boolean(marketPlatform && selected.includes(marketPlatform)),
      };
      const scored = candidateScore(candidate, recall);
      candidate.score = scored.score;
      candidate.reasons = scored.reasons;
      candidates.push(candidate);
    });
  });

  candidates.sort((a, b) => {
    if (a.is_target_platform !== b.is_target_platform) return a.is_target_platform ? -1 : 1;
    return b.score - a.score;
  });
  return candidates;
}

function renderLensCandidateList() {
  const targetCount = state.lensCandidates.filter((candidate) => candidate.is_target_platform).length;
  const totalCount = state.lensCandidates.length;
  if (els.lensCandidateCount) {
    els.lensCandidateCount.textContent = `${targetCount}/${totalCount}개`;
  }
  if (!els.lensCandidateList) return;

  els.lensCandidateList.replaceChildren();
  if (!state.lensCandidates.length) {
    els.lensCandidateList.append(makeEl("p", "empty-copy", "아직 수집된 Lens 후보가 없습니다."));
    return;
  }

  state.lensCandidates.slice(0, 5).forEach((candidate) => {
    const item = makeEl("a", `lens-candidate-chip ${candidate.is_target_platform ? "target" : ""}`, `${candidate.platform_label} · ${candidate.title}`);
    item.href = candidate.url;
    item.target = "_blank";
    item.rel = "noreferrer";
    els.lensCandidateList.append(item);
  });
}

function renderLensCandidateResult() {
  els.imageResultPanel.replaceChildren();
  const targetCandidates = state.lensCandidates.filter((candidate) => candidate.is_target_platform);
  const otherCandidates = state.lensCandidates.filter((candidate) => !candidate.is_target_platform);

  const header = makeEl("div", "detail-header");
  header.append(makeEl("span", "status-pill image_candidate", "Lens 후보"));
  header.append(makeEl("h2", "", `Lens 후보 ${targetCandidates.length}개`));
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", `대상 플랫폼 ${targetCandidates.length}`));
  meta.append(makeEl("span", "meta-chip", `기타 쇼핑 ${otherCandidates.length}`));
  header.append(meta);
  els.imageResultPanel.append(header);

  if (!state.lensCandidates.length) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "수집 후보 없음"));
    empty.append(makeEl("p", "empty-copy", "Lens 결과에서 복사한 상품 링크나 검색 결과 텍스트를 붙여넣은 뒤 후보 수집을 누르세요."));
    els.imageResultPanel.append(empty);
    return;
  }

  const list = makeEl("div", "image-candidate-list");
  state.lensCandidates.forEach((candidate) => {
    const item = makeEl("article", `image-candidate ${candidate.is_target_platform ? "image_candidate" : ""}`);
    const row = makeEl("div", "image-candidate-head");
    row.append(
      makeEl("strong", "", candidate.platform_label),
      makeEl("span", `status-pill ${candidate.is_target_platform ? "image_candidate" : "image_weak"}`, candidate.is_target_platform ? "대상 플랫폼" : "기타 쇼핑"),
      makeEl("span", "score-chip", `${candidate.score}점`)
    );
    item.append(row);
    item.append(makeEl("h3", "", candidate.title));
    const link = makeEl("a", "detail-link", candidate.url);
    link.href = candidate.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    item.append(link);
    if (candidate.reasons.length) {
      const reasons = makeEl("div", "image-reasons");
      candidate.reasons.forEach((reason) => reasons.append(makeEl("span", "meta-chip", reason)));
      item.append(reasons);
    }
    list.append(item);
  });
  els.imageResultPanel.append(list);
}

function collectLensCandidates() {
  const candidates = collectLensCandidatesFromText(els.lensCandidateInput?.value || "");
  state.lensCandidates = candidates;
  setStateLabel(`Lens 후보 ${candidates.length}개 수집`, "ready");
  renderLensCandidateList();
  renderLensCandidateResult();
}

function renderLoading(label) {
  els.imageResultPanel.replaceChildren();
  const empty = makeEl("div", "detail-empty");
  empty.append(makeEl("p", "empty-title", `${label} 검색 중`));
  empty.append(makeEl("p", "empty-copy", "Vision이 쇼핑몰 상품 페이지와 80점 이상 후보를 찾고 있습니다."));
  els.imageResultPanel.append(empty);
}

function renderError(message) {
  els.imageResultPanel.replaceChildren();
  const empty = makeEl("div", "detail-empty");
  empty.append(makeEl("p", "empty-title", "검색 실패"));
  empty.append(makeEl("p", "empty-copy", message));
  els.imageResultPanel.append(empty);
}

function makeStatusPill(status) {
  return makeEl("span", `status-pill ${status}`, statusLabels[status] || status);
}

function renderImageResult(result) {
  els.imageResultPanel.replaceChildren();
  const header = makeEl("div", "detail-header");
  header.append(makeStatusPill(result.status), makeEl("h2", "", statusLabels[result.status] || result.status));
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", `마켓 후보 ${result.candidate_count || 0}개`));
  meta.append(makeEl("span", "meta-chip", `유사 상품 ${result.similar_candidate_count || 0}개`));
  if (result.generated_at) meta.append(makeEl("span", "meta-chip", result.generated_at));
  if (result.saved_path) meta.append(makeEl("span", "meta-chip", `저장됨: ${result.saved_path}`));
  header.append(meta);
  els.imageResultPanel.append(header);

  if (result.source_image) {
    const source = makeEl("div", "image-source-preview");
    const imageButton = makeEl("button", "image-preview-button");
    imageButton.type = "button";
    const image = document.createElement("img");
    image.src = result.source_image;
    image.alt = "";
    imageButton.append(image);
    imageButton.addEventListener("click", () => {
      openImagePreview(result.source_image, result.recall?.display_title || result.terms?.product || "리콜 이미지", result.source_image);
    });
    source.append(imageButton);
    const sourceInfo = makeEl("div", "");
    sourceInfo.append(makeEl("strong", "", "리콜 이미지"));
    const link = makeEl("a", "detail-link", result.source_image);
    link.href = result.source_image;
    link.target = "_blank";
    link.rel = "noreferrer";
    sourceInfo.append(link);
    source.append(sourceInfo);
    els.imageResultPanel.append(source);
  }

  if (Array.isArray(result.warnings) && result.warnings.length) {
    const warning = makeEl("div", "image-warning");
    result.warnings.forEach((item) => warning.append(makeEl("p", "", item)));
    els.imageResultPanel.append(warning);
  }

  renderTermSummary(result);
  renderVisionDiagnostics(result.vision_diagnostics);
  renderCandidates(result.candidates || [], result.vision_diagnostics);
  renderSimilarCandidates(result.similar_candidates || []);
}

function renderTermSummary(result) {
  const terms = result.terms || {};
  const group = makeEl("div", "image-term-group");
  [
    ["제품명", terms.product],
    ["브랜드", terms.brand],
    ["모델명", terms.model],
    ["Best guess", (result.best_guess_labels || []).join(", ")],
  ]
    .filter(([, value]) => compactText(value, ""))
    .forEach(([label, value]) => {
      group.append(makeEl("span", "meta-chip", `${label}: ${value}`));
    });

  if (Array.isArray(result.web_entities) && result.web_entities.length) {
    result.web_entities.slice(0, 6).forEach((entity) => {
      group.append(
        makeEl(
          "span",
          "meta-chip",
          `${entity.description} ${Math.round((entity.score || 0) * 100)}`
        )
      );
    });
  }
  if (group.childNodes.length) els.imageResultPanel.append(group);
}

function renderVisionDiagnostics(diagnostics) {
  if (!diagnostics || typeof diagnostics !== "object") return;

  const panel = makeEl("div", "vision-diagnostics");
  panel.append(makeEl("h3", "", "Vision이 찾은 단서"));
  if (diagnostics.reason) {
    panel.append(makeEl("p", "diagnostic-reason", diagnostics.reason));
  }

  const counts = diagnostics.counts || {};
  const countGrid = makeEl("div", "diagnostic-grid");
  Object.entries(diagnosticCountLabels).forEach(([key, label]) => {
    countGrid.append(makeEl("span", "meta-chip", `${label}: ${Number(counts[key] || 0)}`));
  });
  panel.append(countGrid);

  const platforms = diagnostics.platform_counts || {};
  if (Object.keys(platforms).length) {
    const platformGrid = makeEl("div", "diagnostic-grid");
    Object.entries(platforms).forEach(([platform, count]) => {
      platformGrid.append(makeEl("span", "meta-chip", `${platformLabels[platform] || platform}: ${count}`));
    });
    panel.append(platformGrid);
  }

  const domains = Array.isArray(diagnostics.top_domains) ? diagnostics.top_domains : [];
  if (domains.length) {
    const domainGroup = makeEl("div", "diagnostic-list");
    domainGroup.append(makeEl("strong", "", "많이 나온 사이트"));
    domains.slice(0, 6).forEach((item) => {
      domainGroup.append(makeEl("span", "meta-chip", `${item.domain}: ${item.count}`));
    });
    panel.append(domainGroup);
  }

  const sampleUrls = Array.isArray(diagnostics.sample_urls) ? diagnostics.sample_urls : [];
  if (sampleUrls.length) {
    const sampleGroup = makeEl("div", "diagnostic-url-list");
    sampleGroup.append(makeEl("strong", "", "Vision이 찾은 쇼핑몰 링크 예시"));
    sampleUrls.slice(0, 5).forEach((item) => {
      const row = makeEl("a", "detail-link", `${diagnosticSourceLabels[item.source] || item.source || "URL"} · ${item.domain || item.url}`);
      row.href = item.url;
      row.target = "_blank";
      row.rel = "noreferrer";
      sampleGroup.append(row);
    });
    panel.append(sampleGroup);
  }

  els.imageResultPanel.append(panel);
}

function renderCandidates(candidates, diagnostics = null) {
  const list = makeEl("div", "image-candidate-list");
  if (!candidates.length) {
    const empty = makeEl("div", "empty-state");
    empty.append(makeEl("p", "empty-title", "대상 마켓 후보 없음"));
    empty.append(
      makeEl(
        "p",
        "empty-copy",
        diagnostics && diagnostics.reason
          ? diagnostics.reason
          : "Vision이 찾은 링크 안에 11번가, 쿠팡, G마켓, 네이버가 없습니다."
      )
    );
    list.append(empty);
    els.imageResultPanel.append(list);
    return;
  }

  candidates.forEach((candidate) => {
    const item = makeEl("article", `image-candidate ${candidate.status}`);
    const row = makeEl("div", "image-candidate-head");
    row.append(
      makeEl("strong", "", candidate.platform_label || platformLabels[candidate.platform] || candidate.platform),
      makeStatusPill(candidate.status),
      makeEl("span", "score-chip", `${candidate.score}점`)
    );
    item.append(row);
    item.append(makeEl("h3", "", compactText(candidate.title, "제목 없음")));

    const link = makeEl("a", "detail-link", candidate.url);
    link.href = candidate.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    item.append(link);

    if (Array.isArray(candidate.reasons) && candidate.reasons.length) {
      const reasons = makeEl("div", "image-reasons");
      candidate.reasons.forEach((reason) => reasons.append(makeEl("span", "meta-chip", reason)));
      item.append(reasons);
    }

    if (Array.isArray(candidate.matching_images) && candidate.matching_images.length) {
      const thumbs = makeEl("div", "candidate-thumbs");
      candidate.matching_images.slice(0, 4).forEach((url) => {
        const thumb = document.createElement("img");
        thumb.src = url;
        thumb.alt = "";
        thumb.loading = "lazy";
        thumbs.append(thumb);
      });
      item.append(thumbs);
    }
    list.append(item);
  });
  els.imageResultPanel.append(list);
}

function renderSimilarCandidates(candidates) {
  const section = makeEl("section", "similar-result-section");
  const header = makeEl("div", "section-header compact");
  const titleWrap = makeEl("div", "");
  titleWrap.append(makeEl("h2", "", "쇼핑몰 유사 상품"));
  titleWrap.append(makeEl("p", "", "80점 이상으로 확인된 쇼핑몰 상품 상세 페이지"));
  header.append(titleWrap, makeEl("span", "section-badge", `${candidates.length}개`));
  section.append(header);

  if (!candidates.length) {
    const empty = makeEl("div", "empty-state");
    empty.append(makeEl("p", "empty-title", "유사 후보 없음"));
    empty.append(makeEl("p", "empty-copy", "80점 이상으로 확인된 쇼핑몰 상품 페이지가 없습니다."));
    section.append(empty);
    els.imageResultPanel.append(section);
    return;
  }

  const list = makeEl("div", "image-candidate-list");
  candidates.slice(0, 12).forEach((candidate) => appendSimilarCandidate(list, candidate));
  section.append(list);
  els.imageResultPanel.append(section);
}

function appendProductCandidate(parent, candidate) {
  const item = makeEl("div", `image-candidate ${candidate.status || "text_candidate"}`);
  const row = makeEl("div", "image-candidate-head");
  row.append(
    makeEl("strong", "", candidate.platform_label || platformLabels[candidate.platform] || candidate.platform || "판매처"),
    makeStatusPill(candidate.status || "text_candidate"),
    makeEl("span", "score-chip", `${candidate.score || 0}점`)
  );
  item.append(row);
  item.append(makeEl("h3", "", compactText(candidate.title, "제목 없음")));
  const meta = makeEl("div", "detail-meta");
  if (candidate.query) meta.append(makeEl("span", "meta-chip", `검색어 ${candidate.query}`));
  if (candidate.price) meta.append(makeEl("span", "meta-chip", candidate.price));
  item.append(meta);
  if (candidate.url) {
    const link = makeEl("a", "detail-link", candidate.url);
    link.href = candidate.url;
    link.target = "_blank";
    link.rel = "noreferrer";
    item.append(link);
  }
  if (Array.isArray(candidate.reasons) && candidate.reasons.length) {
    const reasons = makeEl("div", "image-reasons");
    candidate.reasons.slice(0, 4).forEach((reason) => reasons.append(makeEl("span", "meta-chip", reason)));
    item.append(reasons);
  }
  parent.append(item);
}

function renderProductSearchResult(result) {
  els.imageResultPanel.replaceChildren();
  const header = makeEl("div", "detail-header");
  header.append(makeStatusPill(result.status || "text_no_match"), makeEl("h2", "", "판매처 검색 결과"));
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", `후보 ${result.candidate_count || 0}개`));
  if (Array.isArray(result.queries) && result.queries.length) {
    meta.append(makeEl("span", "meta-chip", `검색어 ${result.queries.length}개`));
  }
  if (result.generated_at) meta.append(makeEl("span", "meta-chip", result.generated_at));
  header.append(meta);
  els.imageResultPanel.append(header);

  if (Array.isArray(result.queries) && result.queries.length) {
    const group = makeEl("div", "image-term-group");
    result.queries.forEach((query) => group.append(makeEl("span", "meta-chip", query)));
    els.imageResultPanel.append(group);
  }

  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  if (!candidates.length) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "판매 후보 없음"));
    empty.append(makeEl("p", "empty-copy", "확장 검색어로 대상 쇼핑몰을 검색했지만 후보 상품을 찾지 못했습니다."));
    els.imageResultPanel.append(empty);
    return;
  }

  const list = makeEl("div", "image-candidate-list");
  candidates.forEach((candidate) => appendProductCandidate(list, candidate));
  els.imageResultPanel.append(list);
}

function renderProductSearchResultSection(result) {
  const section = makeEl("section", "similar-result-section");
  const header = makeEl("div", "section-header compact");
  const titleWrap = makeEl("div", "");
  titleWrap.append(makeEl("h3", "", "판매처 검색 후보"));
  titleWrap.append(makeEl("p", "", "제품명과 확장 검색어로 대상 쇼핑몰을 직접 검색한 결과"));
  header.append(titleWrap, makeEl("span", "section-badge", `${result.candidate_count || 0}개`));
  section.append(header);

  if (Array.isArray(result.queries) && result.queries.length) {
    const terms = makeEl("div", "image-term-group");
    result.queries.forEach((query) => terms.append(makeEl("span", "meta-chip", query)));
    section.append(terms);
  }

  const candidates = Array.isArray(result.candidates) ? result.candidates : [];
  if (!candidates.length) {
    section.append(makeEl("p", "empty-copy", "판매처 검색 후보가 없습니다."));
  } else {
    const list = makeEl("div", "image-candidate-list");
    candidates.slice(0, 12).forEach((candidate) => appendProductCandidate(list, candidate));
    section.append(list);
  }
  els.imageResultPanel.append(section);
}

function recallMetaItems(recall = {}) {
  const freshness = recallDateInfo(recall);
  return [
    recall.brand_name && `브랜드 ${recall.brand_name}`,
    recall.model_name && `모델 ${recall.model_name}`,
    recall.source,
    recall.recall_country,
    recall.guid && `ID ${recall.guid}`,
    freshness && `${freshness.label} ${freshness.formatted}`,
  ].filter(Boolean);
}

function renderRecallDetail(recall) {
  const key = recallKey(recall);
  state.selectedRecallKey = key;
  state.activeRecallKey = key;
  els.imageResultPanel.replaceChildren();

  const searchItem = resultForRecall(recall);
  const result = searchItem?.result || null;
  const productItem = productItemForRecall(recall);
  const productResult = productItem?.product_result || null;
  const imageUrl = recallImageUrl(recall);
  const imageUrls = recallImageUrls(recall);

  const header = makeEl("div", "detail-header");
  header.append(
    result ? makeStatusPill(result.status || "unknown") : makeEl("span", "status-pill image_weak", "제품 정보"),
    makeEl("h2", "", compactText(recall.display_title || recall.product_name, "이름 없는 리콜"))
  );
  const meta = makeEl("div", "detail-meta");
  recallMetaItems(recall).forEach((item) => meta.append(makeEl("span", "meta-chip", item)));
  if (result) {
    meta.append(makeEl("span", "meta-chip", `마켓 후보 ${result.candidate_count || 0}개`));
    meta.append(makeEl("span", "meta-chip", `유사 상품 ${result.similar_candidate_count || 0}개`));
    if (Array.isArray(result.source_images) && result.source_images.length > 1) {
      meta.append(makeEl("span", "meta-chip", `이미지 ${result.source_images.length}개 분석`));
    }
    if (result.generated_at) meta.append(makeEl("span", "meta-chip", result.generated_at));
  }
  if (productResult) {
    meta.append(makeEl("span", "meta-chip", `판매처 후보 ${productResult.candidate_count || 0}개`));
  }
  header.append(meta);
  els.imageResultPanel.append(header);

  if (imageUrl) {
    const source = makeEl("div", "image-source-preview");
    const imageButton = makeEl("button", "image-preview-button");
    imageButton.type = "button";
    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt = "";
    imageButton.append(image);
    imageButton.addEventListener("click", () => {
      openImagePreview(imageUrl, recall.display_title || recall.product_name || "리콜 이미지", imageUrl);
    });
    source.append(imageButton);

    const sourceInfo = makeEl("div", "");
    sourceInfo.append(makeEl("strong", "", imageUrls.length > 1 ? `리콜 이미지 ${imageUrls.length}개` : "리콜 이미지"));
    const link = makeEl("a", "detail-link", imageUrl);
    link.href = imageUrl;
    link.target = "_blank";
    link.rel = "noreferrer";
    sourceInfo.append(link);
    source.append(sourceInfo);
    els.imageResultPanel.append(source);
  }

  const actions = makeEl("div", "detail-actions");
  const lensButton = makeEl("button", "button primary", "Google Lens 열기");
  lensButton.type = "button";
  lensButton.disabled = !imageUrl;
  lensButton.addEventListener("click", () => openLensForImage(imageUrl, recall));
  actions.append(lensButton);

  const searchButton = makeEl("button", "button", "Vision 보조 분석");
  searchButton.type = "button";
  searchButton.disabled = state.isSearching || state.isBatchSearching || !imageUrl;
  searchButton.addEventListener("click", () => runImageSearch({ recall }, compactText(recall.display_title, "리콜 이미지")));
  actions.append(searchButton);

  const productButton = makeEl("button", "button", "판매처 검색");
  productButton.type = "button";
  productButton.disabled = state.isSearching || state.isBatchSearching;
  productButton.addEventListener("click", () => runProductSearch({ recall }, compactText(recall.display_title, "리콜 제품")));
  actions.append(productButton);
  els.imageResultPanel.append(actions);

  if (searchItem?.error) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "검색 실패"));
    empty.append(makeEl("p", "empty-copy", searchItem.error));
    els.imageResultPanel.append(empty);
    renderRecalls();
    return;
  }

  if (!result && !productResult && !productItem?.product_error) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "아직 검색 결과 없음"));
    empty.append(makeEl("p", "empty-copy", "Vision 분석이나 판매처 검색을 실행하면 여기에서 결과를 볼 수 있습니다."));
    els.imageResultPanel.append(empty);
    renderRecalls();
    return;
  }

  if (result) {
    renderTermSummary(result);
    renderVisionDiagnostics(result.vision_diagnostics);
    renderCandidates(result.candidates || [], result.vision_diagnostics);
    renderSimilarCandidates(result.similar_candidates || []);
  }
  if (productItem?.product_error) {
    const warning = makeEl("div", "image-warning");
    warning.append(makeEl("p", "", `판매처 검색 실패: ${productItem.product_error}`));
    els.imageResultPanel.append(warning);
  }
  if (productResult) {
    renderProductSearchResultSection(productResult);
  }
  renderRecalls();
}

function setBatchProgress(text, hidden = false) {
  if (!els.batchVisionProgress) return;
  els.batchVisionProgress.hidden = hidden;
  els.batchVisionProgress.textContent = text;
}

function renderBatchResultTabs({ inProgress = false, completed = 0, total = 0, targetTotal = 0, similarTotal = 0, productTotal = 0 } = {}) {
  const tabs = makeEl("div", "batch-result-tabs");
  [
    ["targets", `대상 마켓 ${targetTotal}`],
    ["similar", `유사 상품 ${similarTotal}`],
    ["products", `판매처 ${productTotal}`],
  ].forEach(([tabId, label]) => {
    const button = makeEl("button", `batch-result-tab ${state.batchResultTab === tabId ? "active" : ""}`, label);
    button.type = "button";
    button.setAttribute("aria-pressed", state.batchResultTab === tabId ? "true" : "false");
    button.addEventListener("click", () => {
      state.batchResultTab = tabId;
      renderBatchVisionResults({ inProgress, completed, total });
    });
    tabs.append(button);
  });
  return tabs;
}

function renderBatchFilterControls({ inProgress = false, completed = 0, total = 0 } = {}) {
  const row = makeEl("div", "batch-filter-row");
  const label = makeEl("label", "batch-filter-field");
  label.append(makeEl("span", "", "표시"));
  const select = document.createElement("select");
  [
    ["all", "전체"],
    ["matched", "후보 있음"],
    ["no_market", "마켓 없음"],
    ["errors", "오류"],
  ].forEach(([value, text]) => {
    const option = new Option(text, value);
    select.append(option);
  });
  select.value = state.batchStatusFilter;
  select.addEventListener("change", () => {
    state.batchStatusFilter = select.value;
    renderBatchVisionResults({ inProgress, completed, total });
  });
  label.append(select);
  row.append(label);
  return row;
}

function appendSimilarCandidate(parent, candidate) {
  const row = makeEl("div", "similar-candidate-row");
  const imageUrl = candidate.thumbnail_url || (Array.isArray(candidate.matching_images) ? candidate.matching_images[0] : "");
  if (imageUrl) {
    const imageButton = makeEl("button", "similar-thumb-button");
    imageButton.type = "button";
    const image = document.createElement("img");
    image.src = imageUrl;
    image.alt = "";
    image.loading = "lazy";
    imageButton.append(image);
    imageButton.addEventListener("click", () => {
      openImagePreview(imageUrl, candidate.title || candidate.platform_label || "유사 이미지", candidate.url);
    });
    row.append(imageButton);
  } else {
    row.classList.add("no-thumb");
  }

  const content = makeEl("div", "similar-candidate-content");
  const head = makeEl("div", "image-candidate-head");
  head.append(
    makeEl("strong", "", candidate.platform_label || commerceLabels[candidate.platform] || candidate.platform || "유사 상품"),
    makeEl("span", "score-chip", `${candidate.score || 0}점`)
  );
  content.append(head);
  content.append(makeEl("p", "similar-candidate-title", compactText(candidate.title, "제목 없음")));

  const links = makeEl("div", "similar-link-group");
  if (candidate.is_image_asset) {
    const imageLink = makeEl("a", "detail-link", "이미지 열기");
    imageLink.href = candidate.url;
    imageLink.target = "_blank";
    imageLink.rel = "noreferrer";
    links.append(imageLink);

    if (candidate.parent_url) {
      const sourceLink = makeEl("a", "detail-link", "출처 페이지");
      sourceLink.href = candidate.parent_url;
      sourceLink.target = "_blank";
      sourceLink.rel = "noreferrer";
      links.append(sourceLink);
    }

    const lensLink = makeEl("a", "detail-link", "Lens로 판매처 찾기");
    lensLink.href = lensSearchUrl(candidate.url);
    lensLink.target = "_blank";
    lensLink.rel = "noreferrer";
    links.append(lensLink);
  } else {
    const productLink = makeEl("a", "detail-link", "판매/상품 페이지 열기");
    productLink.href = candidate.url;
    productLink.target = "_blank";
    productLink.rel = "noreferrer";
    links.append(productLink);
  }
  content.append(links);

  if (Array.isArray(candidate.reasons) && candidate.reasons.length) {
    const reasons = makeEl("div", "image-reasons");
    candidate.reasons.slice(0, 3).forEach((reason) => reasons.append(makeEl("span", "meta-chip", reason)));
    content.append(reasons);
  }

  row.append(content);
  parent.append(row);
}

function renderBatchVisionResults({ inProgress = false, completed = 0, total = 0 } = {}) {
  els.imageResultPanel.replaceChildren();
  const results = batchDisplayItems();
  const statusCounts = results.reduce((counts, item) => {
    const status = item.error ? "error" : item.result?.status || "unknown";
    counts[status] = (counts[status] || 0) + 1;
    return counts;
  }, {});
  const targetTotal = results.reduce((sum, item) => sum + Number(item.result?.candidate_count || 0), 0);
  const similarTotal = results.reduce((sum, item) => sum + Number(item.result?.similar_candidate_count || 0), 0);
  const productTotal = results.reduce((sum, item) => sum + Number(item.product_result?.candidate_count || 0), 0);

  const header = makeEl("div", "detail-header");
  header.append(makeEl("span", "status-pill image_candidate", "Vision 일괄"));
  header.append(makeEl("h2", "", inProgress ? `Vision 일괄 분석 ${completed}/${total}` : "Vision 일괄 분석 완료"));
  const meta = makeEl("div", "detail-meta");
  meta.append(makeEl("span", "meta-chip", `분석 ${results.length}`));
  meta.append(makeEl("span", "meta-chip", `후보 발견 ${statusCounts.image_matched || 0}`));
  meta.append(makeEl("span", "meta-chip", `확인 후보 ${statusCounts.image_candidate || 0}`));
  meta.append(makeEl("span", "meta-chip", `정보 부족 ${statusCounts.image_weak || 0}`));
  meta.append(makeEl("span", "meta-chip", `마켓 없음 ${statusCounts.image_no_match || 0}`));
  meta.append(makeEl("span", "meta-chip", `유사 상품 ${similarTotal}`));
  meta.append(makeEl("span", "meta-chip", `판매처 ${productTotal}`));
  meta.append(makeEl("span", "meta-chip", `오류 ${statusCounts.error || 0}`));
  header.append(meta);
  header.append(renderBatchResultTabs({ inProgress, completed, total, targetTotal, similarTotal, productTotal }));
  header.append(renderBatchFilterControls({ inProgress, completed, total }));
  els.imageResultPanel.append(header);

  if (!results.length) {
    const empty = makeEl("div", "detail-empty");
    empty.append(makeEl("p", "empty-title", "분석 대기 중"));
    empty.append(makeEl("p", "empty-copy", "이미지가 있는 리콜을 대상으로 Vision 보조 분석을 순차 실행합니다."));
    els.imageResultPanel.append(empty);
    return;
  }

  const filteredResults = results.filter((item) => {
    if (state.batchStatusFilter === "all") return true;
    if (state.batchStatusFilter === "errors") return Boolean(item.error || item.product_error);
    if (state.batchStatusFilter === "matched") {
      return Boolean(
        Number(item.result?.candidate_count || 0) > 0
          || Number(item.result?.similar_candidate_count || 0) > 0
          || Number(item.product_result?.candidate_count || 0) > 0
      );
    }
    if (state.batchStatusFilter === "no_market") {
      return !item.error && !item.product_error
        && Number(item.result?.candidate_count || 0) === 0
        && Number(item.result?.similar_candidate_count || 0) === 0
        && Number(item.product_result?.candidate_count || 0) === 0;
    }
    return true;
  });

  const list = makeEl("div", "image-candidate-list");
  filteredResults.forEach((item) => {
    const result = item.result || {};
    const productResult = item.product_result || {};
    const card = makeEl("article", `image-candidate ${item.error || item.product_error ? "image_search_error" : result.status || productResult.status || ""}`);
    const row = makeEl("div", "image-candidate-head");
    row.append(
      makeEl("strong", "", compactText(item.recall.display_title, "이름 없는 리콜")),
      item.error || item.product_error ? makeEl("span", "status-pill image_search_error", "오류") : makeStatusPill(result.status || productResult.status || "unknown")
    );
    card.append(row);

    if (state.batchResultTab === "products") {
      const productCandidates = Array.isArray(productResult.candidates) ? productResult.candidates : [];
      if (productCandidates.length) {
        card.append(makeEl("p", "diagnostic-reason", `판매처 후보 ${productCandidates.length}개`));
        productCandidates.slice(0, 4).forEach((candidate) => appendProductCandidate(card, candidate));
      } else {
        const message = item.product_error || (Array.isArray(productResult.queries) && productResult.queries.length
          ? "판매처 검색 후보가 없습니다."
          : "판매처 검색을 실행하지 않았습니다.");
        card.append(makeEl("p", "empty-copy", message));
      }
    } else if (state.batchResultTab === "similar") {
      const similarCandidates = Array.isArray(result.similar_candidates) ? result.similar_candidates : [];
      if (similarCandidates.length) {
        card.append(makeEl("p", "diagnostic-reason", `유사 상품 ${similarCandidates.length}개`));
        similarCandidates.slice(0, 4).forEach((candidate) => appendSimilarCandidate(card, candidate));
      } else {
        card.append(makeEl("p", "empty-copy", item.error || "Vision 유사 상품 후보가 없습니다."));
      }
    } else {
      const topCandidate = Array.isArray(result.candidates) ? result.candidates[0] : null;
      if (topCandidate && result.status !== "image_no_match") {
        card.append(makeEl("p", "diagnostic-reason", `${topCandidate.platform_label || topCandidate.platform} · ${topCandidate.score}점`));
        const link = makeEl("a", "detail-link", topCandidate.url);
        link.href = topCandidate.url;
        link.target = "_blank";
        link.rel = "noreferrer";
        card.append(link);
      } else {
        card.append(
          makeEl(
            "p",
            "empty-copy",
            item.error || result.vision_diagnostics?.reason || "대상 플랫폼 후보가 없습니다."
          )
        );
      }
    }
    list.append(card);
  });
  if (!filteredResults.length) {
    list.append(makeEl("p", "empty-copy", "현재 필터에 해당하는 결과가 없습니다."));
  }
  els.imageResultPanel.append(list);
}

async function runBatchVisionAnalysis() {
  if (state.isSearching || state.isBatchSearching) return;
  const recallsWithImages = state.recalls.filter((recall) => Boolean(recallImageUrl(recall)));
  if (!recallsWithImages.length) {
    renderError("이미지가 있는 리콜을 먼저 불러오세요.");
    return;
  }

  state.batchResults = [];
  state.batchResultTab = "targets";
  state.batchStatusFilter = "all";
  state.isBatchSearching = true;
  state.batchCancelRequested = false;
  state.batchAbortController = new AbortController();
  applyBusyState();
  renderRecalls();
  setStateLabel("Vision 일괄 분석 중", "busy");
  setBatchProgress(`0 / ${recallsWithImages.length}`);
  renderBatchVisionResults({ inProgress: true, completed: 0, total: recallsWithImages.length });

  const basePayload = baseImagePayload();
  for (let index = 0; index < recallsWithImages.length; index += 1) {
    if (state.batchCancelRequested) break;
    const recall = recallsWithImages[index];
    const completed = index + 1;
    try {
      const result = await postJson("/api/image-search", {
        ...basePayload,
        recall,
      }, { signal: state.batchAbortController?.signal });
      state.batchResults.push({ recall, result });
    } catch (error) {
      if (error.name === "AbortError") {
        state.batchResults.push({ recall, error: "사용자가 일괄 분석을 취소했습니다." });
        break;
      }
      state.batchResults.push({ recall, error: error.message });
    }
    setBatchProgress(`${completed} / ${recallsWithImages.length}`);
    setStateLabel(`Vision 일괄 분석 ${completed}/${recallsWithImages.length}`, "busy");
    renderBatchVisionResults({ inProgress: completed < recallsWithImages.length, completed, total: recallsWithImages.length });
  }

  state.isBatchSearching = false;
  state.batchAbortController = null;
  applyBusyState();
  renderRecalls();
  setStateLabel(state.batchCancelRequested ? "Vision 일괄 분석 취소" : "Vision 일괄 분석 완료", state.batchCancelRequested ? "error" : "ready");
  setBatchProgress(`${state.batchResults.length}개 ${state.batchCancelRequested ? "취소" : "완료"}`);
  renderBatchVisionResults({ inProgress: false, completed: state.batchResults.length, total: recallsWithImages.length });
}

async function runBatchProductSearch() {
  if (state.isSearching || state.isBatchSearching) return;
  if (!state.recalls.length) {
    renderError("리콜을 먼저 불러오세요.");
    return;
  }

  state.productResults = [];
  state.batchResultTab = "products";
  state.batchStatusFilter = "all";
  state.isBatchSearching = true;
  state.batchCancelRequested = false;
  state.batchAbortController = new AbortController();
  applyBusyState();
  renderRecalls();
  setStateLabel("판매처 일괄 검색 중", "busy");
  setBatchProgress(`0 / ${state.recalls.length}`);
  renderBatchVisionResults({ inProgress: true, completed: 0, total: state.recalls.length });

  const basePayload = baseProductPayload();
  for (let index = 0; index < state.recalls.length; index += 1) {
    if (state.batchCancelRequested) break;
    const recall = state.recalls[index];
    const completed = index + 1;
    try {
      const result = await postJson("/api/product-search", {
        ...basePayload,
        recall,
      }, { signal: state.batchAbortController?.signal });
      upsertProductResult(recall, result);
    } catch (error) {
      if (error.name === "AbortError") {
        upsertProductResult(recall, null, "사용자가 일괄 검색을 취소했습니다.");
        break;
      }
      upsertProductResult(recall, null, error.message);
    }
    setBatchProgress(`${completed} / ${state.recalls.length}`);
    setStateLabel(`판매처 일괄 검색 ${completed}/${state.recalls.length}`, "busy");
    renderBatchVisionResults({ inProgress: completed < state.recalls.length, completed, total: state.recalls.length });
  }

  state.isBatchSearching = false;
  state.batchAbortController = null;
  applyBusyState();
  renderRecalls();
  setStateLabel(state.batchCancelRequested ? "판매처 일괄 검색 취소" : "판매처 일괄 검색 완료", state.batchCancelRequested ? "error" : "ready");
  setBatchProgress(`${state.productResults.length}개 ${state.batchCancelRequested ? "취소" : "완료"}`);
  renderBatchVisionResults({ inProgress: false, completed: state.productResults.length, total: state.recalls.length });
}

function cancelBatchWork() {
  if (!state.isBatchSearching) return;
  state.batchCancelRequested = true;
  state.batchAbortController?.abort();
  setStateLabel("일괄 작업 취소 중", "error");
  setBatchProgress("취소 중");
  applyBusyState();
}

async function loadImageRecalls(event) {
  if (event) event.preventDefault();
  const apiKey = els.imageRecallApiKeyInput.value.trim();
  if (apiKey) sessionStorage.setItem("recallHubApiKey", apiKey);
  setStateLabel("리콜 조회 중", "busy");
  try {
    const data = await postJson("/api/recalls", {
      api_key: apiKey,
      mode: els.imageRecallModeInput.value,
      q: els.imageRecallSearchInput.value.trim(),
      limit: Number(els.imageRecallLimitInput.value || 30),
      days: 30,
    });
    state.recalls = Array.isArray(data.data) ? data.data : [];
    state.lastRecallLoadedAt = new Date();
    setStateLabel("리콜 조회 완료", "ready");
    renderRecalls();
  } catch (error) {
    setStateLabel("리콜 조회 오류", "error");
    els.imageRecallEmptyState.hidden = false;
    els.imageRecallEmptyState.textContent = error.message;
  }
}

function renderRecalls() {
  updateRecallSummary();
  els.imageRecallList.replaceChildren();
  els.imageRecallEmptyState.hidden = state.recalls.length > 0;
  if (!state.recalls.length) return;

  state.recalls.forEach((recall) => {
    const key = recallKey(recall);
    const imageUrl = recallImageUrl(recall);
    const imageUrls = recallImageUrls(recall);
    const isSelected = state.selectedRecallKey === key || state.activeRecallKey === key;
    const card = makeEl("article", `image-recall-card ${isSelected ? "selected" : ""}`);

    if (imageUrl) {
      const imageButton = makeEl("button", "image-preview-button recall-image-button");
      imageButton.type = "button";
      const image = document.createElement("img");
      image.src = imageUrl;
      image.alt = "";
      image.loading = "lazy";
      imageButton.append(image);
      imageButton.addEventListener("click", (event) => {
        event.stopPropagation();
        openImagePreview(imageUrl, recall.display_title || recall.product_name || "리콜 이미지", imageUrl);
      });
      card.append(imageButton);
    } else {
      card.append(makeEl("div", "image-missing", "이미지 없음"));
    }

    const content = makeEl("div", "image-recall-content");
    content.tabIndex = 0;
    content.setAttribute("role", "button");
    content.setAttribute("aria-label", `${compactText(recall.display_title, "리콜")} 상세 보기`);
    content.addEventListener("click", () => renderRecallDetail(recall));
    content.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        renderRecallDetail(recall);
      }
    });
    content.append(makeEl("h3", "", compactText(recall.display_title, "이름 없는 리콜")));
    const meta = makeEl("div", "recall-meta");
    recallMetaItems(recall).forEach((item) => meta.append(makeEl("span", "meta-chip", item)));
    if (imageUrls.length > 1) meta.append(makeEl("span", "meta-chip", `이미지 ${imageUrls.length}`));
    content.append(meta);

    const actions = makeEl("div", "form-actions compact-actions");
    actions.addEventListener("click", (event) => event.stopPropagation());

    const lensButton = makeEl(
      "button",
      "button small primary image-recall-lens-button",
      "Google Lens 열기"
    );
    lensButton.type = "button";
    lensButton.dataset.hasImage = imageUrl ? "true" : "false";
    lensButton.disabled = !imageUrl;
    lensButton.addEventListener("click", () => {
      state.activeRecallKey = key;
      state.selectedRecallKey = key;
      renderRecalls();
      openLensForImage(imageUrl, recall);
    });
    actions.append(lensButton);

    const button = makeEl(
      "button",
      "button small image-recall-search-button",
      state.activeRecallKey === key && state.isSearching ? "분석 중" : "Vision 보조 분석"
    );
    button.type = "button";
    button.dataset.hasImage = imageUrl ? "true" : "false";
    button.disabled = state.isSearching || state.isBatchSearching || !imageUrl;
    button.addEventListener("click", () => {
      state.activeRecallKey = key;
      state.selectedRecallKey = key;
      renderRecalls();
      runImageSearch({ recall }, compactText(recall.display_title, "리콜 이미지"));
    });
    actions.append(button);

    const productButton = makeEl(
      "button",
      "button small product-recall-search-button",
      state.activeRecallKey === key && state.isSearching ? "검색 중" : "판매처 검색"
    );
    productButton.type = "button";
    productButton.disabled = state.isSearching || state.isBatchSearching;
    productButton.addEventListener("click", () => {
      state.activeRecallKey = key;
      state.selectedRecallKey = key;
      renderRecalls();
      runProductSearch({ recall }, compactText(recall.display_title, "리콜 제품"));
    });
    actions.append(productButton);
    content.append(actions);
    card.append(content);
    els.imageRecallList.append(card);
  });
  applyBusyState();
}

els.directImageForm.addEventListener("submit", (event) => {
  event.preventDefault();
  const imageUrl = els.directImageUrlInput.value.trim();
  if (!imageUrl) {
    els.directImageUrlInput.focus();
    return;
  }
  openLensForImage(imageUrl, directRecallPayload(imageUrl));
});

els.directImageSearchButton.addEventListener("click", () => {
  const imageUrl = els.directImageUrlInput.value.trim();
  if (!imageUrl) {
    els.directImageUrlInput.focus();
    return;
  }
  runImageSearch(
    {
      image_url: imageUrl,
      recall: directRecallPayload(imageUrl),
    },
    "직접 이미지"
  );
});

els.directProductSearchButton?.addEventListener("click", () => {
  const recall = directRecallPayload(els.directImageUrlInput.value.trim());
  if (!compactText(recall.product_name, "") && !compactText(recall.brand_name, "") && !compactText(recall.model_name, "")) {
    els.directProductInput.focus();
    return;
  }
  runProductSearch({ recall }, "직접 입력 제품");
});

els.batchVisionButton?.addEventListener("click", runBatchVisionAnalysis);
els.batchProductButton?.addEventListener("click", runBatchProductSearch);
els.cancelBatchButton?.addEventListener("click", cancelBatchWork);
els.collectLensCandidatesButton?.addEventListener("click", collectLensCandidates);
els.clearLensCandidatesButton?.addEventListener("click", () => {
  state.lensCandidates = [];
  if (els.lensCandidateInput) els.lensCandidateInput.value = "";
  renderLensCandidateList();
  renderLensCandidateResult();
});
els.imageRecallForm.addEventListener("submit", loadImageRecalls);
els.clearImageResultsButton.addEventListener("click", () => {
  state.lastResult = null;
  state.batchResults = [];
  state.productResults = [];
  state.activeRecallKey = "";
  state.selectedRecallKey = "";
  els.imageResultPanel.replaceChildren();
  const empty = makeEl("div", "detail-empty");
  empty.append(makeEl("p", "empty-title", "검색 결과 없음"));
  empty.append(makeEl("p", "empty-copy", "직접 이미지 URL을 입력하거나 이미지가 있는 리콜을 선택하세요."));
  els.imageResultPanel.append(empty);
  renderRecalls();
});

renderRecalls();
renderLensCandidateList();
setBatchProgress("대기 중", true);
