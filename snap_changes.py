#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
변동 감지된 상품의 페이지를 스크린샷으로 저장 — 가격 변동의 '증거' 기록용.
(오파싱/정가오인 의심 시 나중에 눈으로 검증할 수 있게.)

price_history.json에서 '가장 최근 변동일에 바뀐 상품'만 골라 그 상품 페이지를
캡처 → outputs/snapshots/<날짜>_<종명>_<업체>_<번호>.png

실행:
  python3 snap_changes.py --profile .naver-profile        # 최근 변동분 캡처
  python3 snap_changes.py --since 2026-06-07 --profile .naver-profile
  python3 snap_changes.py --headful --profile .naver-profile
(playwright 필요. 네이버는 로그인 세션 프로필 필요)

⚠ 페이지를 방문하므로 변동 건수만큼 요청이 늘어요. 변동이 적을 때만(보통 크롤당 수 건)
   가볍게 동작하도록 설계 — 전 상품 캡처는 하지 않음.
"""
import json, os, re, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "outputs")
SNAPDIR = os.path.join(OUTDIR, "snapshots")
PRICES = os.path.join(HERE, "prices.json")
HIST = os.path.join(HERE, "price_history.json")


def hist_key(url):
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


def safe(s):
    return re.sub(r"[^\w가-힣]+", "_", str(s or "")).strip("_")[:40]


def changed_products(since=None):
    """가장 최근 변동일(또는 since 이후)에 가격이 바뀐 상품 목록."""
    prods = json.load(open(PRICES, encoding="utf-8"))["products"]
    hist = json.load(open(HIST, encoding="utf-8"))
    by_key = {hist_key(p["url"]): p for p in prods if p.get("url")}
    # 변동(2점+)이 있는 키들의 마지막 변동일
    dated = [(pts[-1][0], hk) for hk, pts in hist.items() if len(pts) >= 2]
    if not dated:
        return [], None
    target = since or max(d for d, _ in dated)
    out = []
    for hk, pts in hist.items():
        if len(pts) >= 2 and pts[-1][0] >= target:
            p = by_key.get(hk)
            if p and p.get("url"):
                prev, cur = pts[-2][1], pts[-1][1]
                out.append((p, pts[-1][0], prev, cur))
    return out, target


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="이 날짜(포함) 이후 변동만")
    ap.add_argument("--profile", metavar="DIR", help="네이버 로그인 세션 프로필 폴더")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--limit", type=int, default=60, help="과다 캡처 방지 상한")
    args = ap.parse_args()

    items, date = changed_products(args.since)
    if not items:
        print("변동 상품 없음 → 캡처 생략")
        return
    if len(items) > args.limit:
        print(f"⚠ 변동 {len(items)}건 > 상한 {args.limit} → 상위 {args.limit}건만 캡처(과다 방지)")
        items = items[:args.limit]
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright 미설치 → 캡처 생략")
        return
    # scrape.py의 브라우저 설정 재사용(있으면)
    try:
        from scrape import UA_BROWSER, STEALTH_JS
    except Exception:
        UA_BROWSER = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120 Safari/537.36")
        STEALTH_JS = ""
    os.makedirs(SNAPDIR, exist_ok=True)

    with sync_playwright() as pw:
        launch = dict(headless=not args.headful, args=["--disable-blink-features=AutomationControlled"])
        ctx_opts = dict(user_agent=UA_BROWSER, locale="ko-KR", timezone_id="Asia/Seoul",
                        viewport={"width": 1280, "height": 1700})
        if args.profile:
            ctx = pw.chromium.launch_persistent_context(args.profile, **launch, **ctx_opts)
            closer = ctx
        else:
            browser = pw.chromium.launch(**launch)
            ctx = browser.new_context(**ctx_opts)
            closer = browser
        if STEALTH_JS:
            ctx.add_init_script(STEALTH_JS)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        done = 0
        for p, d, prev, cur in items:
            pid = hist_key(p["url"]).split("/")[-1]
            arrow = "up" if cur > prev else "dn"
            fn = f"{d}_{safe(p.get('vendor'))}_{safe(p['name'].split('/')[0])}_{arrow}_{prev}-{cur}_{pid}.png"
            path = os.path.join(SNAPDIR, fn)
            try:
                page.goto(p["url"], wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(2500)
                page.screenshot(path=path)        # 첫 화면(가격 영역 포함)
                done += 1
                print(f"  📸 {p['vendor']} {p['name'][:24]} {prev:,}→{cur:,} → {fn}")
            except Exception as e:
                print(f"  ⚠ 실패 {p['name'][:24]}: {e}")
        closer.close()
    print(f"\n캡처 {done}건 → {SNAPDIR}/  (변동일 {date})")


if __name__ == "__main__":
    main()
