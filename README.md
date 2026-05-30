# ZIGGOO

리콜 대상 위해제품이 주요 이커머스 플랫폼에서 해외직구 형태로 유통되는지 확인하는 Python 기반 모니터링 봇입니다.

## 설치

```bash
pip install -r requirements.txt
playwright install chromium
```

## 실행

```bash
python scanner.py
python scanner.py --platform coupang
python scanner.py --platform naver
python scanner.py "모델명 또는 키워드"
python scanner.py "모델명" --verify "브랜드명"
python scanner.py --file batch.example.json
python scanner.py "모델명" --platform coupang --manual-verify-blocked
```

기본 자동 스캔에서는 봇 차단이 잦은 쿠팡/G마켓을 바로 접속하지 않고 `manual_required` 상태로 남깁니다. 11번가는 자동 스캔을 계속 수행합니다. 쿠팡/G마켓을 확인해야 할 때는 `--manual-verify-blocked` 옵션 또는 대시보드의 수동 검증 스캔을 사용하세요.

## 대시보드

```bash
python dashboard.py
```

브라우저에서 `http://127.0.0.1:8765`를 열면 Recall Hub 리콜 목록을 불러오고, 필요한 항목을 선택해 플랫폼 스캔을 실행할 수 있습니다. 최근 스캔 결과, 플랫폼별 상태, 탐지 상품, 디버그 스크린샷도 함께 확인할 수 있습니다.
수동 확인이 필요한 결과나 차단된 결과는 상세 패널의 `수동 검증 스캔`/`수동 검증 재스캔` 버튼으로 다시 확인할 수 있습니다. 스캔 옵션에서 `차단 시 수동 검증`을 켜면 보안 확인 화면이 뜰 때 브라우저를 열어 사용자가 직접 통과한 뒤 같은 검색을 이어갑니다.
쿠팡은 로켓직구, G마켓은 해외직구 조건이 적용된 검색 URL로 스캔합니다. 네이버는 네이버 쇼핑/스마트스토어 검색 URL로 확인합니다.

## 이미지 기반 후보 검색

쿠팡/G마켓처럼 자동 검색이 자주 차단되는 플랫폼은 이미지 기반 보조 검증을 사용할 수 있습니다.

```bash
set ZIGGOO_GOOGLE_VISION_API_KEY=your-google-vision-api-key
python dashboard.py
```

브라우저에서 `http://127.0.0.1:8765/image-search`를 열면 리콜 이미지 또는 직접 입력한 이미지 URL을 Google Lens로 먼저 열어 확인합니다. 현재 1차 목표는 Lens 검색 결과가 정상적으로 뜨는지 검증하는 것입니다.

`Lens 후보 수집`에는 Google Lens 결과에서 복사한 상품 링크나 검색 결과 텍스트를 붙여넣을 수 있습니다. 이 기능은 붙여넣은 내용 안에서 11번가, 쿠팡, G마켓, 네이버 링크를 우선 분류하고 기타 쇼핑몰 링크는 참고 후보로 보여줍니다.

`Vision API 보조 분석` 버튼을 누르면 Google Cloud Vision Web Detection을 사용해 결과에서 11번가, 쿠팡, G마켓, 네이버 URL만 추려 동일 이미지 여부, 상품 URL 패턴, 모델명/제품명/브랜드 일치 정도를 점수화합니다. 리콜 항목에 이미지가 여러 개 있으면 가능한 이미지를 순차 분석해 후보를 병합합니다.
`판매처 검색`은 제품명, 브랜드, 모델명과 확장 검색어를 조합해 대상 쇼핑몰을 직접 검색하고 Vision이 놓친 판매 페이지 후보를 별도 탭으로 보여줍니다.
리콜 목록을 불러온 뒤 `Vision 일괄 분석`을 누르면 이미지가 있는 리콜을 순차적으로 보조 분석하고 전체 결과를 요약합니다.

상태 기준은 다음과 같습니다.

- `image_matched`: 대상 마켓에서 강하게 맞는 후보를 찾음
- `image_candidate`: 대상 마켓 후보가 있어 사람 확인 필요
- `image_no_match`: 대상 마켓을 찾지 못했거나 상품 정보가 부족함
- `image_no_image`: 리콜 이미지 없음

Recall Hub API를 쓰려면 환경 변수를 설정합니다.

```bash
set ZIGGOO_RECALL_HUB_BASE_URL=https://recall-hub-admin-dev.vercel.app
set ZIGGOO_API_KEY=your-api-key
```

스캔 결과는 대시보드가 다시 불러올 수 있도록 `results` 폴더에 보관됩니다. 화면의 `JSON 다운로드` 또는 `엑셀 다운로드` 버튼을 눌러 필요한 형식으로 내려받을 수 있습니다.
