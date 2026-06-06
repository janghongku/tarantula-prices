#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
거미(타란튤라) 가격 수집기 — raw 이름+가격만 긁어 prices.json 생성 (이름 가공 안 함).

  자사몰(Cafe24)        : requests + BeautifulSoup  (서버렌더)
  네이버 스마트스토어    : Playwright                (SPA)

실행:
    pip install requests beautifulsoup4 playwright
    playwright install chromium
    python scrape.py                     # 전체 (자사몰 + 네이버)
    python scrape.py --only cafe24       # 자사몰만 (GitHub Actions가 쓰는 모드)
    python scrape.py --only smartstore   # 네이버만 (집 PC에서)
    python scrape.py --headful           # 네이버 안티봇 막히면 창 띄워서
    python scrape.py --no-merge          # 기존 prices.json 무시하고 새로 (병합 끔)
    python scrape.py --debug             # 0건 나오면 debug_*.html / *_state.json 저장

★ 병합(merge) 동작 — 기본 켜짐:
   이번에 긁지 않은 채널(예: --only cafe24면 '네이버')의 상품은 기존 prices.json에서
   그대로 들고 온다. 또 긁었는데 0건이면 해당 업체의 옛 데이터를 유지한다.
   → Actions(자사몰)와 집PC(네이버)가 번갈아 돌아도 서로의 데이터를 안 지운다.

소스 추가/수정은 SOURCES 한 곳만. Cafe24 cate_no = 카테고리 클릭 시 URL의 cate_no 값.
"""

import re, json, time, argparse, datetime, pathlib
import requests
from bs4 import BeautifulSoup

# ── opt-out 연락처(선택). 비워두면 UA에서 생략. 공개 배포 시 본인이 따로 만든 이메일을 넣어도 됨.
CONTACT = ""

# ─────────────────────────────────────────────────────────────
SOURCES = [
    # 자사몰 (Cafe24) — robots.txt가 /product/list.html 을 허용함(확인). 정직한 식별 UA 사용.
    {"type": "cafe24", "vendor": "타란툴라코리아", "channel": "자사몰",
     "base": "https://tarantulakorea.com", "cate_nos": [24, 66, 67, 27]},  # 배회성24/버러우성66/나무위성67/준성체27 (실측)
    {"type": "cafe24", "vendor": "타란센터", "channel": "자사몰",
     "base": "https://tarancenter.com", "cate_nos": [51]},                 # 타란튤라=51 (실측)
    {"type": "cafe24", "vendor": "거미랑", "channel": "자사몰",
     "base": "https://theraphosidae.co.kr", "cate_nos": [24]},             # 거미=24 (실측)

    # 네이버 스마트스토어 (handle = smartstore.naver.com/뒤)
    # ⚠ 네이버 robots.txt는 전체 Disallow(*). README의 '법적/매너' 항목 참고.
    {"type": "smartstore", "vendor": "타란툴라코리아",     "channel": "네이버", "handle": "tarantulakorea"},
    {"type": "smartstore", "vendor": "타란센터",          "channel": "네이버", "handle": "tarancenter"},
    {"type": "smartstore", "vendor": "더쥬 송파점",        "channel": "네이버", "handle": "tzblossom"},
    {"type": "smartstore", "vendor": "거미랑", "channel": "네이버", "handle": "terrafactory"},
]

# 자사몰: robots 허용 구역 → 정직하게 식별되는 UA(+연락처). 네이버: 실제 브라우저 UA.
UA_BOT = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 GeomiPriceAggregator/1.0"
          + (f" (+contact: {CONTACT})" if CONTACT else ""))
UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA_BOT, "Accept-Language": "ko-KR,ko;q=0.9"}

PRICE_RE = re.compile(r"([0-9]{1,3}(?:,[0-9]{3})+|[0-9]{4,})\s*원?")
DEBUG = False

# 네이버: 로그인된 본인 세션을 재사용하는 게 가장 안정적(차단 회피용 우회 아님).
#   첫 실행:  python scrape.py --only smartstore --headful --profile .naver-profile
#   → 창에서 네이버 로그인(+캡차) 1회 → 이후엔 같은 --profile 로 세션 재사용.
STEALTH_JS = (
    "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
    "Object.defineProperty(navigator,'languages',{get:()=>['ko-KR','ko','en-US','en']});"
    "window.chrome={runtime:{}};"
)

NAME_KEYS  = ("productName", "name", "dispNm", "title")
PRICE_KEYS = ("discountedSalePrice", "salePrice", "price", "lowPrice", "sellingPrice")
ID_KEYS    = ("id", "productNo", "productId", "channelProductNo")
# 품절 감지(네이버 state): 판매상태 키 + '품절' 의미 값
SOLD_KEYS  = ("saleStatusType", "saleStatus", "productStatusType", "statusType")
SOLD_VALS  = ("OUTOFSTOCK", "SOLDOUT", "SOLD_OUT", "SUSPENSION", "CLOSE", "STOP", "END", "WAIT")
OUT_FILE   = "prices.json"
HIST_FILE  = "price_history.json"   # url -> [[날짜, 가격], ...] 가격 추이 기록(커밋해서 영구 누적)


def to_int_price(text):
    m = PRICE_RE.search(text or "")
    return int(m.group(1).replace(",", "")) if m else None


def cafe24_price(li):
    """카드 전체가 아니라 '판매가' 영역에서만 가격을 뽑는다.
    (상품명에 들어간 연도/사이즈 숫자 — 예: '완성체 (2020.01)' — 를 가격으로 오인하지 않게)"""
    desc = li.select_one(".description")
    # 1) ec-data-price 속성(있으면 가장 정확한 판매가)
    if desc and desc.get("ec-data-price"):
        digits = re.sub(r"[^0-9]", "", desc.get("ec-data-price"))
        if digits and int(digits) > 0:
            return int(digits)
    # 2) spec 목록에서 '판매가' 라벨이 붙은 줄
    spec = li.select_one("ul.xans-product-listitem") or li.select_one("ul.spec")
    if spec:
        for row in spec.select("li"):
            lab = row.select_one("strong, .title")
            if lab and "판매가" in lab.get_text(" ", strip=True):
                p = to_int_price(row.get_text(" ", strip=True))
                if p:
                    return p
        p = to_int_price(spec.get_text(" ", strip=True))   # 라벨 없으면 spec 영역 전체(이름 제외됨)
        if p:
            return p
    # 3) 최후: 카드 전체 텍스트
    return to_int_price(li.get_text(" ", strip=True))


def cafe24_soldout(li):
    """Cafe24 표준 품절 아이콘(ico_product_soldout) 또는 품절 alt 로 감지."""
    for im in li.find_all("img"):
        src = im.get("src", "").lower()
        if "soldout" in src or "sold_out" in src or "품절" in im.get("alt", ""):
            return True
    return False


def dump(name, content):
    if DEBUG:
        pathlib.Path(name).write_text(content, encoding="utf-8")
        print(f"    · 디버그 저장: {name}")


# ─────────────────────────────────────────────────────────────
# Cafe24 자사몰
# ─────────────────────────────────────────────────────────────
def scrape_cafe24(src):
    base, out, seen = src["base"], [], set()
    sess = requests.Session(); sess.headers.update(HEADERS)
    for cate in src["cate_nos"]:
        page = 1
        while page <= 50:
            url = f"{base}/product/list.html?cate_no={cate}&page={page}"
            try:
                html = sess.get(url, timeout=20).text
            except Exception as e:
                print(f"  [{src['vendor']}] 실패 {url}: {e}"); break
            soup = BeautifulSoup(html, "html.parser")
            items = (soup.select('li[id^="anchorBoxId_"]')
                     or soup.select("ul.prdList > li")
                     or soup.select(".xans-product-listmain li"))
            if not items:
                if page == 1:
                    dump(f"debug_cafe24_{src['vendor']}.html", html)
                break
            added = 0
            for li in items:
                a = li.select_one("a[href*='/product/']")
                if not a:
                    continue
                href = a.get("href", "")
                full = href if href.startswith("http") else base + href
                full = full.split("?")[0]              # 쿼리스트링 제거(같은 상품 중복 방지)
                if full in seen:
                    continue
                name_el = li.select_one(".name") or a
                name = re.sub(r"^상품명\s*:\s*", "", name_el.get_text(" ", strip=True)).strip()
                price = cafe24_price(li)
                if name and price:
                    seen.add(full)
                    prod = {"vendor": src["vendor"], "channel": src["channel"],
                            "name": name, "price": price, "url": full}
                    if cafe24_soldout(li):
                        prod["soldout"] = True
                    out.append(prod)
                    added += 1
            if added == 0:                              # 이 페이지에 새 상품 없으면(중복 페이지) 종료
                break
            page += 1
            time.sleep(0.4)
    print(f"  [{src['vendor']} 자사몰] {len(out)}건")
    return out


# ─────────────────────────────────────────────────────────────
# 네이버 스마트스토어
# ─────────────────────────────────────────────────────────────
def pull_product(d):
    """state dict 하나에서 이름/가격/id 뽑기 (키 이름 흔들려도 잡게)."""
    name = next((d[k] for k in NAME_KEYS if isinstance(d.get(k), str) and d[k].strip()), None)
    price = None
    for k in PRICE_KEYS:
        v = d.get(k)
        if isinstance(v, (int, float)) and v > 0:
            price = int(v); break
    # benefitsView 안에 할인가가 들어있는 경우
    for bk in ("benefitsView", "mobileBenefitsView"):
        bv = d.get(bk)
        if isinstance(bv, dict):
            for k in PRICE_KEYS:
                if isinstance(bv.get(k), (int, float)) and bv[k] > 0:
                    price = int(bv[k]); break
    pid = next((str(d[k]) for k in ID_KEYS if d.get(k)), None)
    sold = any(isinstance(d.get(k), str) and any(s in d[k].upper() for s in SOLD_VALS)
               for k in SOLD_KEYS)
    return name, price, pid, sold


def extract_smartstore(page, src):
    """state(SSR, 보통 첫 80개; 이름 깨끗) + 스크롤된 DOM 카드(80 초과분) 합집합."""
    handle = src["handle"]
    out = {}   # url -> product. state 우선(이름 깨끗), DOM은 빠진 것만 보충.
    state = page.evaluate("() => window.__PRELOADED_STATE__ || window.__PRELOADED_STATE || null")
    if state:
        found = {}
        def walk(o):
            if isinstance(o, dict):
                n, p, pid, sold = pull_product(o)
                if n and p and pid:           # id까지 있어야 진짜 상품(요약/혜택 객체 거름)
                    found.setdefault(pid, (n, p, sold))
                for v in o.values(): walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(state)
        for pid, (n, p, sold) in found.items():
            if not (100 <= p <= 50_000_000):           # 비정상가 거름(파싱 오류 방지)
                continue
            url = f"https://smartstore.naver.com/{handle}/products/{pid}"
            out[url] = {"vendor": src["vendor"], "channel": src["channel"], "name": n, "price": p, "url": url}
            if sold:
                out[url]["soldout"] = True

    # 스크롤로 더 로드된 카드에서 state에 없는 상품 보충
    try:
        cards = page.query_selector_all("li:has(a[href*='/products/'])")
    except Exception:
        cards = []
    for c in cards:
        link = c.query_selector("a[href*='/products/']")
        if not link: continue
        u = (link.get_attribute("href") or "").split("?")[0]
        if u.startswith("/"): u = "https://smartstore.naver.com" + u
        if not u: continue
        txt = c.inner_text()
        sold = "품절" in txt                              # 네이버 품절 딱지(가장 확실한 신호)
        if u in out:                                      # state로 이미 잡힌 상품도 DOM 품절로 보강
            if sold: out[u]["soldout"] = True
            continue
        # DOM 카드 텍스트엔 정가·할인가·배송비가 섞여 있어 가격이 모호함(API 429 폴백 시).
        # '원' 가격이 정확히 1개일 때만 신뢰. 2개 이상(정가/할인가/배송비 혼재)이면 스킵 → 기존 가격 유지.
        nums = re.findall(r"([0-9][0-9,]{2,})\s*원", txt)
        price = int(nums[0].replace(",", "")) if len(nums) == 1 else None
        lines = [l.strip() for l in txt.splitlines() if l.strip()]
        cand = [l for l in lines if not PRICE_RE.fullmatch(l.replace("원", "").strip()) and "http" not in l.lower()]
        name = max(cand, key=len) if cand else None
        if name and price and "http" not in name.lower() and 100 <= price <= 50_000_000:
            out[u] = {"vendor": src["vendor"], "channel": src["channel"],
                      "name": name, "price": price, "url": u}
            if sold: out[u]["soldout"] = True

    if not out and state:
        dump(f"debug_{handle}_state.json", json.dumps(state, ensure_ascii=False)[:300000])
    return list(out.values())


def scroll_until_stable(page, max_loops=25):
    last = -1
    for _ in range(max_loops):
        n = page.evaluate("() => document.querySelectorAll(\"a[href*='/products/']\").length")
        if n == last and n > 0:
            break
        last = n
        page.mouse.wheel(0, 6000); time.sleep(0.9)


def _blocked(page):
    u = page.url.lower()
    return "nidlogin" in u or "login" in u or "captcha" in u


# 거미(타란튤라) 카테고리로 보이는 이름 패턴 (가게마다 명칭이 달라 넉넉히)
SPIDER_KW = re.compile(r"타란|거미|스파이더|새잡이|버드이터|배회성|버러우|버로우|나무위|준성체|theraphos|spider", re.I)


def store_category_links(page):
    """스토어 카테고리 {id: 이름} — __PRELOADED_STATE__ 전체 트리(하위 카테고리 포함).
    하위 카테고리(예: 더쥬 절지류>타란툴라)는 DOM 메뉴엔 안 떠도 state엔 있다. DOM은 폴백."""
    return page.evaluate(r"""() => {
        const out = {};
        const seen = new WeakSet();
        function walk(o){
            if(!o || typeof o!=='object') return;
            if(seen.has(o)) return; seen.add(o);
            if(Array.isArray(o)){ for(const v of o) walk(v); return; }
            const cid = o.id || o.categoryId || o.categoryNo;
            const nm  = o.name || o.categoryName;
            if(cid && typeof nm==='string'){
                const t = nm.replace(/\s+/g,' ').trim();
                if(t.length>0 && t.length<=30 &&
                   ('level' in o || 'parentStoreCategoryId' in o || 'categoryName' in o || 'allProductCategory' in o))
                    out[String(cid)] = t;
            }
            for(const k in o){ try{ walk(o[k]); }catch(e){} }
        }
        const st = window.__PRELOADED_STATE__ || window.__PRELOADED_STATE || null;
        if(st) walk(st);
        if(Object.keys(out).length === 0){           // 폴백: DOM 상단 메뉴
            document.querySelectorAll("a[href*='/category/']").forEach(a=>{
                const m=(a.getAttribute('href')||'').match(/\/category\/([0-9A-Za-z]+)/);
                const t=(a.textContent||'').replace(/\s+/g,' ').trim();
                if(m && t && t.length<=30) out[m[1]]=t;
            });
        }
        return out;
    }""")


def _login_wait(page, vendor, headful, reload_url):
    """로그인/캡차 벽이면 헤드풀에서 사용자가 창에서 로그인할 때까지 대기."""
    if not _blocked(page):
        return True
    if headful:
        print(f"  ⚠ [{vendor}] 네이버 로그인 화면입니다. 열린 크롬 창에서 직접 로그인해주세요. "
              "(로그인되면 자동 진행, 최대 5분 대기)", flush=True)
        for _ in range(100):
            page.wait_for_timeout(3000)
            if not _blocked(page):
                break
        if not _blocked(page):
            print(f"  [{vendor}] 로그인 감지 → 진행", flush=True)
            try:
                page.goto(reload_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
            except Exception:
                pass
    return not _blocked(page)


def api_category_products(page, channel_uid, cid, src):
    """네이버 내부 상품목록 API로 카테고리 전체를 깨끗하게(이름/판매가) 수집. 80개 한계 없음.
    DOM 파싱(배송비·설명 오인)을 안 거쳐 #배송비/#긴이름 문제도 없음."""
    out = {}
    for pg in range(1, 26):
        api = (f"https://smartstore.naver.com/i/v2/channels/{channel_uid}/categories/{cid}/products"
               f"?categorySearchType=DISPCATG&sortType=TOTALSALE&page={pg}&pageSize=80")
        try:
            data = page.evaluate(
                "async (u)=>{try{const r=await fetch(u,{headers:{accept:'application/json'},credentials:'include'});"
                "if(!r.ok) return null; return await r.json();}catch(e){return null;}}", api)
        except Exception:
            break
        if not data:
            break
        found, stack = {}, [data]
        while stack:
            o = stack.pop()
            if isinstance(o, dict):
                n, p, pid, sold = pull_product(o)
                if n and p and pid:
                    found.setdefault(pid, (n, p, sold))
                stack.extend(o.values())
            elif isinstance(o, list):
                stack.extend(o)
        new = 0
        for pid, (n, p, sold) in found.items():
            if pid in out or not (100 <= p <= 50_000_000) or "http" in n.lower():
                continue
            out[pid] = {"vendor": src["vendor"], "channel": src["channel"], "name": n, "price": p,
                        "url": f"https://smartstore.naver.com/{src['handle']}/products/{pid}"}
            if sold:
                out[pid]["soldout"] = True
            new += 1
        if new == 0:
            break
    return list(out.values())


def click_category_products(page, base, cid, src):
    """폴백: 카테고리 페이지에서 페이지번호 클릭하며 DOM 수집."""
    url = f"{base}/category/{cid}?st=TOTALSALE&dt=IMAGE&size=80"
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500); scroll_until_stable(page)
    except Exception:
        return []
    seen, got, pagenum = set(), [], 1
    while pagenum <= 15:
        batch = [b for b in extract_smartstore(page, src) if b["url"] not in seen]
        if not batch and pagenum > 1:
            break
        for b in batch:
            seen.add(b["url"])
        got += batch
        nxt, clicked = pagenum + 1, False
        for role in ("menuitem", "link", "button"):
            try:
                loc = page.get_by_role(role, name=str(nxt), exact=True)
                if loc.count() > 0:
                    loc.first.scroll_into_view_if_needed(timeout=3000)
                    loc.first.click(timeout=4000); clicked = True; break
            except Exception:
                pass
        if not clicked:
            break
        page.wait_for_timeout(1600); scroll_until_stable(page)
        pagenum = nxt
    return got


def scrape_smartstore_all(sources, headful=False, profile=None):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  playwright 미설치 → 네이버 건너뜀"); return []
    out = []
    with sync_playwright() as pw:
        launch = dict(headless=not headful, args=["--disable-blink-features=AutomationControlled"])
        ctx_opts = dict(user_agent=UA_BROWSER, locale="ko-KR", timezone_id="Asia/Seoul",
                        viewport={"width": 1280, "height": 1800})
        if profile:                                   # 로그인 세션 재사용(권장)
            ctx = pw.chromium.launch_persistent_context(profile, **launch, **ctx_opts)
            closer = ctx
        else:
            browser = pw.chromium.launch(**launch)
            ctx = browser.new_context(**ctx_opts)
            closer = browser
        ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()

        try:                                          # 워밍업(쿠키 획득)
            page.goto("https://www.naver.com", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(1800)
        except Exception:
            pass

        for src in sources:
            base = f"https://smartstore.naver.com/{src['handle']}"
            entry = base + "/category/ALL?st=TOTALSALE&dt=IMAGE&size=80"
            try:
                page.goto(entry, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
            except Exception as e:
                print(f"  [{src['vendor']}] goto 실패: {e}"); continue
            if not _login_wait(page, src["vendor"], headful, entry):
                print(f"  [{src['vendor']}] 네이버 차단 → 건너뜀"); continue

            # 카테고리 메뉴에서 '거미' 카테고리만 고른다 (용품/먹이 제외)
            try:
                cats = store_category_links(page)
            except Exception:
                cats = {}
            spider = {cid: nm for cid, nm in cats.items() if cid != "ALL" and SPIDER_KW.search(nm)}
            print(f"  [{src['vendor']}] 카테고리 {len(cats)}개 | 거미류: "
                  + (" / ".join(sorted(set(spider.values()))) if spider else "없음"), flush=True)
            if not spider:                               # 거미 카테고리 없으면 제외(거미 안 파는 매장)
                print(f"  [{src['vendor']}] 거미 카테고리 없음 → 제외", flush=True)
                continue
            channel_uid = page.evaluate(
                "()=>{const m=JSON.stringify(window.__PRELOADED_STATE__||{})"
                ".match(/\"channelUid\":\"([^\"]+)\"/);return m?m[1]:null;}")
            seen, got, used_api = set(), [], False
            for cid in spider.keys():
                items = api_category_products(page, channel_uid, cid, src) if channel_uid else []
                if items:
                    used_api = True
                else:                                          # API 실패 시 클릭 폴백
                    items = click_category_products(page, base, cid, src)
                for it in items:
                    if it["url"] in seen:
                        continue
                    seen.add(it["url"]); got.append(it)
            print(f"  [{src['vendor']} 네이버:{src['handle']}] {len(got)}건 (거미)"
                  + (" [API]" if used_api else " [DOM]"), flush=True)
            out += got
        closer.close()
    return out


# ─────────────────────────────────────────────────────────────
# 병합: 이번에 안 긁은(또는 0건인) 채널/업체는 기존 prices.json에서 유지
# ─────────────────────────────────────────────────────────────
def load_existing():
    p = pathlib.Path(OUT_FILE)
    if not p.exists():
        return {}, {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("products", []), data.get("channels", {})
    except Exception:
        return [], {}


def merge_with_existing(new_products, attempted_channels, now_iso):
    old_products, old_channels = load_existing()
    refreshed = {(p["vendor"], p["channel"]) for p in new_products}   # 이번에 실제 데이터 나온 (업체,채널)
    merged = list(new_products)
    carried = 0
    for op in old_products:
        ch = op.get("channel"); key = (op.get("vendor"), ch)
        if ch not in attempted_channels or key not in refreshed:
            merged.append(op); carried += 1
    # 채널별 최신 시각: 이번에 데이터가 나온 채널만 갱신, 나머진 옛 값 유지
    channels = dict(old_channels)
    for ch in {p["channel"] for p in new_products}:
        channels[ch] = now_iso
    if carried:
        kept = sorted({op.get("channel") for op in old_products
                       if (op.get("channel") not in attempted_channels)
                       or ((op.get("vendor"), op.get("channel")) not in refreshed)})
        print(f"  · 병합: 기존 데이터 {carried}건 유지 (갱신 안 한 채널: {', '.join(kept) or '-'})")
    return merged, channels


# ─────────────────────────────────────────────────────────────
# 가격 변동: 직전 prices.json 대비 prev(이전가) 표시 + price_history.json 추이 기록
# ─────────────────────────────────────────────────────────────
def recent_naver_hours(now):
    """직전 네이버 수집 후 경과 시간(시간). 없으면 None."""
    last = load_existing()[1].get("네이버")
    if not last:
        return None
    try:
        return (now - datetime.datetime.fromisoformat(last)).total_seconds() / 3600
    except Exception:
        return None


def hist_key(url):
    """가격이력 키 — URL 대신 안정적인 상품번호 기반.
    상품명을 바꾸거나 재등록해 URL(슬러그)이 변해도 같은 번호면 이력이 안 끊긴다.
    네이버 .../products/{pid}, 자사몰 .../product/{슬러그}/{번호}/ 에서 번호 추출."""
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


_SPEC_LABELS = ("배송", "습성", "수명", "사육", "분양 개체", "개체 크기", "성체크기")


def _suspect_price(p, last):
    """자동 파싱 가격을 신뢰할 수 없는 경우 True (마지막 정상가 유지용).
    - 네이버 리스팅 중 '설명을 제목에 떡칠'한 상품(관용명/학명+배송·습성…): 가격 필드가
      옵션/placeholder라 엉뚱한 값(배송비 4,000 등)이 잡힘.
    - 품절/문의용 placeholder 폭등가(100만/999만…)가 직전 대비 2배 이상 점프."""
    if p.get("channel") != "네이버" or not last:
        return False
    nm = p.get("name", "")
    price = p.get("price", 0)
    stuffed = ("관용명" in nm) or (len(nm) > 60 and "학명" in nm and any(s in nm for s in _SPEC_LABELS))
    too_cheap = stuffed and price <= 5000 and price <= last * 0.5        # 배송비/동전 숫자 오인(폭락)
    placeholder = price in (1_000_000, 9_999_999, 99_999_999, 99_999_990) and price >= last * 2  # 품절/문의 폭등
    return too_cheap or placeholder


def apply_price_changes(products, now_iso):
    """price_history.json에 가격 추이를 누적하고, 각 상품에 직전가(prev)·변동일·그래프(hist)를 붙인다.
    이력 기반(직전 '다른' 가격과 비교)이라 하루에 여러 번/채널별로 돌려도 변동 표시가 안 사라지고 영구 누적."""
    hist = {}
    hp = pathlib.Path(HIST_FILE)
    if hp.exists():
        try:
            hist = json.loads(hp.read_text(encoding="utf-8"))
        except Exception:
            hist = {}
    changed = 0
    for p in products:
        p.pop("prev", None); p.pop("changed_on", None); p.pop("hist", None)
        u, price = hist_key(p["url"]), p["price"]
        h = hist.setdefault(u, [])
        last = h[-1][1] if h else None
        if last and price != last and _suspect_price(p, last):   # 신뢰 불가 → 마지막 정상가 유지
            price = p["price"] = last
        if not h or h[-1][1] != price:                 # 가격이 바뀐 날만 이력에 1점 추가
            h.append([now_iso[:10], price])
            hist[u] = h = h[-24:]
        if len(h) >= 2:                                # 과거에 다른 가격이 있었음 = 변동 이력
            p["prev"] = h[-2][1]                        # 직전 '다른' 가격
            p["changed_on"] = h[-1][0]                  # 최근 변동일
            p["hist"] = h[-12:]                         # 그래프용
            changed += 1
    try:
        hp.write_text(json.dumps(hist, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass
    return changed


def main():
    global DEBUG
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", choices=["cafe24", "smartstore"])
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--no-merge", action="store_true", help="기존 prices.json 무시(전체 덮어쓰기)")
    ap.add_argument("--profile", metavar="DIR", help="네이버 로그인 세션 재사용용 브라우저 프로필 폴더")
    ap.add_argument("--force", action="store_true", help="네이버 하루 1회 가드 무시")
    args = ap.parse_args()
    DEBUG = args.debug
    now = datetime.datetime.now()
    now_iso = now.isoformat(timespec="seconds")

    products, attempted = [], set()
    if args.only != "smartstore":
        print("자사몰 수집...")
        attempted.add("자사몰")
        for s in [s for s in SOURCES if s["type"] == "cafe24"]:
            products += scrape_cafe24(s)
    if args.only != "cafe24":
        hrs = recent_naver_hours(now)
        if hrs is not None and hrs < 20 and not args.force:
            print(f"네이버: 마지막 수집 {hrs:.1f}시간 전 → 하루 1회 가드로 건너뜀 (강제: --force)")
        else:
            print("네이버 수집...")
            attempted.add("네이버")
            products += scrape_smartstore_all([s for s in SOURCES if s["type"] == "smartstore"],
                                              headful=args.headful, profile=args.profile)

    channels = {ch: now_iso for ch in {p["channel"] for p in products}}
    if not args.no_merge:
        products, channels = merge_with_existing(products, attempted, now_iso)

    changed = apply_price_changes(products, now_iso)

    # 고정 순서로 정렬 → 매 수집마다 순서가 안 바뀌어 git diff에 '실제 변동'만 보인다
    products.sort(key=lambda p: (p.get("channel", ""), p.get("vendor", ""), p.get("url", "")))

    data = {"updated_at": now_iso, "channels": channels, "products": products}
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    by_ch = {}
    for p in products:
        by_ch[p["channel"]] = by_ch.get(p["channel"], 0) + 1
    print(f"\n→ {OUT_FILE} 저장 (총 {len(products)}건; " +
          ", ".join(f"{k} {v}" for k, v in sorted(by_ch.items())) +
          f"). 가격변동 {changed}건.")
    if not products:
        print("  0건이면 --headful --debug 로 다시 돌리고 debug_* 파일을 확인.")


if __name__ == "__main__":
    main()
