# 거미(타란튤라) 가격 도감 — 개인용

여러 거미 분양샵의 **상품명 + 가격**을 한 곳에 모아 검색·필터·정렬하는 도구.
상품명은 **원문 그대로**(가공·매칭 안 함), 이미지는 수집 안 하고, 각 행은 원문 상품 링크로 연결.
현재는 **공개 안 함 / 개인용 + 친구에게 파일로 공유**하는 방식.

## 파일
| 파일 | 역할 |
|---|---|
| `scrape.py` | 각 샵에서 이름+가격 수집 → `prices.json` 생성 |
| `prices.json` | 수집 결과(데이터) |
| `index.html` | `prices.json`을 읽어 표시 (로컬 서버로 열기) |
| `build_share.py` | 데이터를 박아넣은 **단일 파일** 생성 → 친구에게 전송용 |
| `거미가격_공유.html` | 그 단일 파일. **더블클릭하면 열림** (서버·인터넷 불필요) |
| `verify_ui.py` | 페이지가 잘 렌더되는지 점검(개발용) |

## 수집 대상
**자사몰 (Cafe24, requests+BeautifulSoup)** — robots.txt가 `/product/list.html` 허용(확인):
- 타란툴라코리아 `tarantulakorea.com` — cate_no **24·66·67·27** (배회성/버러우성/나무위성/준성체)
- 타란센터 `tarancenter.com` — **51** · 거미랑 `theraphosidae.co.kr` — **24**

**네이버 스마트스토어 (Playwright)** — ⚠ robots.txt 전체 Disallow (아래 메모):
- 타란툴라코리아 · 타란센터 · 거미랑 스마트스토어(`terrafactory`) — 각 가게의 **거미 카테고리만** 수집
- 더쥬 송파점(`tzblossom`) — 거미 전용 카테고리가 없는 등각류/용품 매장이라 **자동 제외**

## 사용법
```bash
# (최초 1회) 가상환경 + 의존성
python3 -m venv .venv && source .venv/bin/activate
pip install requests beautifulsoup4 playwright && playwright install chromium

# 1) 자사몰 갱신 — 빠름, 로그인 불필요
python scrape.py --only cafe24

# 2) 네이버 갱신 — 창이 뜨면 네이버 로그인(최초 1회). 거미 카테고리만 긁음
python scrape.py --only smartstore --headful --profile .naver-profile

# 3) 보기 (로컬) — file:// 직접 열기는 막히므로 서버로
python -m http.server 8765      # → http://localhost:8765

# 4) 친구에게 줄 단일 파일 만들기
python build_share.py           # → 거미가격_공유.html (카톡/메일로 전송, 친구는 더블클릭)
```

## 네이버 메모 (중요)
- **헤드리스는 막힘.** 반드시 `--headful` (창)으로 돌리고, 처음 한 번 그 창에서 네이버에 **직접 로그인**해야 한다. 로그인 세션은 `.naver-profile/` 에 저장돼 다음부턴 자동 통과(세션이 만료되면 다시 로그인).
- **거미 카테고리만** 가져온다(용품·먹이 제외). 가게 카테고리 메뉴에서 `타란/거미/배회성/버러우/나무위/준성체...` 이름을 자동 인식.
- **한 카테고리가 80개를 넘으면 첫 페이지(80개)에서 잘린다** — 네이버 SSR이 페이지 파라미터를 안 넘겨서 생기는 한계. 단, 타란센터·거미랑은 **자사몰에 전체 목록(525·819개)이 이미 있으므로** 사실상 커버된다(네이버는 보조).
- 너무 자주 돌리면 IP가 일시 차단(429)되니 **하루 1회 이하** 권장.

## 데이터 현황(예시)
- 자사몰 1,636 (타란툴라코리아 292 · 타란센터 525 · 거미랑 819)
- 네이버 440 (타란툴라코리아 275 · 타란센터 85 · 거미랑 80)
- 합계 ≈ 2,076개. `prices.json` 의 `channels` 에 채널별 갱신 시각 기록.

## (선택) 인터넷에 공개하고 싶어지면
- **중립 이름 GitHub Organization** 으로 repo를 만들고 GitHub Pages를 켜면 `중립이름.github.io/...` 주소로
  공개된다(개인 계정명 노출 없음). 공개 시엔 `scrape.py`/`index.html`의 연락처(`CONTACT`)에
  **개인계정과 무관한 이메일**을 넣을 것.
- 자동 갱신이 필요하면 `.github/workflows/` 에 12시간 cron 워크플로(자사몰만; 네이버는 클라우드 IP가 막힘)를 둔다.

## ⚖️ robots.txt / 매너 (변호사 자문 아님)
- **자사몰**: robots.txt가 상품목록을 허용 → 정직한 식별 UA, 저빈도로 수집(문제 없음).
- **네이버**: robots.txt가 전체 Disallow. **개인용·비공개**로 쓰는 지금은 위험이 사실상 없지만,
  이대로 **공개 재배포**하면 한국 판례(잡코리아 v 사람인, 야놀자 v 여기어때)상 위법 소지가 커진다.
  공개하려면 빈도·이미지 미수집·원문 링크·출처표기·opt-out을 지키거나, **각 샵 동의/네이버 커머스 API**가 정답.
- 누가 빼달라고 하면 `scrape.py` 의 `SOURCES` 에서 해당 샵을 제거.
