# 거미(타란튤라) 가격 도감

여러 거미 분양샵의 **상품명 + 가격**을 한 곳에 모아 검색·필터·정렬하는 도구.
상품명은 **원문 그대로**(가공·매칭 안 함), 이미지는 수집 안 하고, 각 행은 원문 상품 링크로 연결.

**공개 주소: https://janghongku.github.io/tarantula-prices/** (이 링크만 주면 누구나 열람)
오프라인으로 줄 땐 `build_share.py`로 만든 `거미가격_공유.html` 단일 파일을 보내도 됨.

## 폴더 구조
```
tarantula-prices/
├── index.html            사이트 (GitHub Pages가 루트에서 서빙)
├── prices.json           수집 데이터 (사이트가 fetch)
├── group_map.json        종 묶음 매핑 (사이트가 fetch)
├── price_history.json    가격 이력 (영구 누적 — 절대 삭제 금지)
├── species_aliases.json  종 묶기 별칭 사전 (수동 편집)
│
├── scrape.py             수집 → prices.json / price_history.json
├── species_groups.py     같은 종 묶기 → group_map.json   (map / report / candidates)
├── make_report.py        변동 글(txt) + 변동로그·전체현황(csv) + 알림 플래그
├── make_xlsx.py          합본 엑셀 (요약 / 전체현황 / 가격변동)
├── make_graphs.py        2회+ 변동 추이 그래프 (개별 + 모음)
├── make_cards.py         변동 요약 카드 + 고정 안내 배너 이미지
├── notify.py             변동 시 맥 알림 (+ 선택: 휴대폰 푸시)
├── build_share.py        데이터 내장 단일 파일 생성
│
├── outputs/   ⬅ 모든 생성물 (글·csv·카드/안내/모음 png·graphs/·엑셀·공유html)
└── _dev/        실험·임시 스크립트 (비공개)
```
**생성물은 전부 `outputs/`.** 사이트가 읽는 `prices.json`·`group_map.json` 과 핵심 데이터·스크립트만 루트에 둔다.
글 발행: `outputs/가격변동_안내.png` + `가격변동_카드.png` (+ 2회+ 변동 시 `가격추이_모음.png`).

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
