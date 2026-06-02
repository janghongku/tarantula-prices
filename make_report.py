#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가격변동 글(txt) 자동 생성 + 변동 누적 로그(csv) 갱신.

매 크롤링(scrape.py) 뒤에 돌리면:
  - 가격변동_로그.csv : 발생한 모든 가격변동을 영구 누적(날짜·금액). 엑셀로 열림(utf-8-sig).
  - 가격변동_기록.txt : 카페/블로그용 글. 판매처별로 묶고 ▲인상/▼인하 구분.

사용:
  python3 make_report.py                 # 최근 7일 변동으로 글 생성(+로그 갱신)
  python3 make_report.py --days 14        # 최근 N일
  python3 make_report.py --since 2026-06-02   # 특정일 이후(긴급 글용: 지난 글 이후 변동만)
  python3 make_report.py --urgent --since 2026-06-02   # 제목을 [긴급]으로
  python3 make_report.py --log-only       # 글 없이 csv 로그만 갱신
"""
import json, csv, re, os, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(HERE, "가격변동_로그.csv")
TXT_FILE = os.path.join(HERE, "가격변동_기록.txt")

# 판매처/채널 약칭 (글에 쓸 표기)
ABBR = {"거미랑": "ㄱㅁㄹ", "타란툴라코리아": "ㅌㅋ", "더쥬 송파점": "ㄷㅈㅅㅍ", "타란센터": "ㅌㄹㅅㅌ"}
CH   = {"네이버": "N스토어", "자사몰": "자사몰"}
STORE_ORDER = ["거미랑", "타란툴라코리아", "더쥬 송파점", "타란센터"]
CH_ORDER = ["자사몰", "네이버"]


def keyOf(p):
    return p.get("url") or (p["vendor"] + "␟" + p["name"])


def hist_key(url):
    """price_history.json 키 규칙(scrape.py와 동일): 상품번호 기반 안정키."""
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


def species_name(p, gm):
    """묶음 대표명(가장 깔끔) 우선, 없으면 '/' 앞 + 프로모 제거."""
    g = gm.get(keyOf(p), {})
    nm = g.get("n") or re.sub(r'^\(?\s*\d+월\s*이벤트\s*\)?\s*', '', p["name"].split("/")[0]).strip()
    return nm.split(",")[0].strip()


def all_change_events():
    """price_history.json(영구 이력)에서 '가격이 바뀐 모든 시점'을 뽑는다."""
    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    try:
        gm = json.load(open(os.path.join(HERE, "group_map.json"), encoding="utf-8"))["map"]
    except Exception:
        gm = {}
    by_key = {hist_key(p["url"]): p for p in prods if p.get("url")}   # 이력 키(상품번호) → 현재 상품
    ev = []
    for hk, pts in hist.items():
        p = by_key.get(hk)
        if not p:
            continue
        for i in range(1, len(pts)):
            prev, price = pts[i - 1][1], pts[i][1]
            if prev == price:
                continue
            ev.append({"date": pts[i][0], "vendor": p["vendor"], "channel": p["channel"],
                       "species": species_name(p, gm), "prev": prev, "price": price,
                       "url": p["url"], "raw": p["name"]})
    return ev


# ── 전체 종별 현황 스냅샷 (모든 상품: 최초관측~현재) ──────────────
SNAP_FILE = os.path.join(HERE, "종별_가격현황.csv")
SNAP_COLS = ["거미", "판매처", "채널", "최초관측일", "최초가", "현재가", "변동횟수", "최근변동일", "재고", "URL"]


def write_snapshot():
    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    try:
        gm = json.load(open(os.path.join(HERE, "group_map.json"), encoding="utf-8"))["map"]
    except Exception:
        gm = {}
    rows = []
    for p in prods:
        hk = hist_key(p["url"]) if p.get("url") else None
        pts = hist.get(hk, []) if hk else []
        rows.append({
            "거미": species_name(p, gm), "판매처": p["vendor"], "채널": p["channel"],
            "최초관측일": pts[0][0] if pts else "", "최초가": pts[0][1] if pts else p["price"],
            "현재가": p["price"], "변동횟수": max(0, len(pts) - 1),
            "최근변동일": pts[-1][0] if len(pts) >= 2 else "", "재고": "품절" if p.get("soldout") else "재고",
            "URL": p.get("url", ""),
        })
    rows.sort(key=lambda r: (r["거미"], r["판매처"], r["채널"]))
    with open(SNAP_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SNAP_COLS); w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


# ── CSV 누적 로그 ─────────────────────────────────────────────
COLS = ["날짜", "판매처", "채널", "거미", "이전가", "변동가", "증감액", "증감률(%)", "방향", "URL"]


def update_log(events):
    existing, rows = set(), []
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                rows.append(r)
                existing.add((r["날짜"], r["URL"], r["변동가"]))
    new_events = []
    for e in events:
        k = (e["date"], e["url"], str(e["price"]))
        if k in existing:
            continue
        existing.add(k); new_events.append(e)
        d = e["price"] - e["prev"]; pct = round(abs(d) / e["prev"] * 100) if e["prev"] else 0
        rows.append({"날짜": e["date"], "판매처": e["vendor"], "채널": e["channel"], "거미": e["species"],
                     "이전가": e["prev"], "변동가": e["price"], "증감액": d, "증감률(%)": pct,
                     "방향": "인상" if d > 0 else "인하", "URL": e["url"]})
    rows.sort(key=lambda r: (str(r["날짜"]), str(r["판매처"]), str(r["거미"])))
    with open(LOG_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader()
        for r in rows:
            w.writerow({c: r.get(c, "") for c in COLS})
    return new_events, len(rows)


# ── 글(txt) 생성 ─────────────────────────────────────────────
def won(n):
    return format(int(n), ",")


def gen_text(events, urgent=False):
    if not events:
        return None
    latest = max(e["date"] for e in events)
    y, mo, dd = map(int, latest.split("-"))
    week = (dd - 1) // 7 + 1
    up = [e for e in events if e["price"] > e["prev"]]
    down = [e for e in events if e["price"] < e["prev"]]

    L = []
    if urgent:
        L.append(f"[긴급] 거미 가격 변동 - {len(up)}종 인상 / {len(down)}종 인하 ({latest.replace('-', '.')})")
    else:
        L.append(f"[정보] [{mo}월 {week}주차] 거미 가격 변동 - {len(up)}종 인상 / {len(down)}종 인하")
    L += ["", "타란튤라 판매가 변동 기록", f"{latest.replace('-', '.')} 변동 확인",
          "대상: ㄱㅁㄹ, ㅌㅋ, ㄷㅈㅅㅍ, ㅌㄹㅅㅌ (자사몰 / N스토어)",
          "기준: 국내 판매처 공개 표시가 · 실제 구매가·재고·배송비·개체 상태는 판매처 원문에서 확인하세요."]

    def block(head, items, word, arr):
        if not items:
            return
        L.append(""); L.append(f"{head} {len(items)}건")
        for store in STORE_ORDER:
            for ch in CH_ORDER:
                si = sorted([e for e in items if e["vendor"] == store and e["channel"] == ch],
                            key=lambda e: -e["price"])
                if not si:
                    continue
                L.append(""); L.append(f"{ABBR.get(store, store)} / {CH.get(ch, ch)} ({word} {len(si)}건)")
                for i, e in enumerate(si, 1):
                    d = abs(e["price"] - e["prev"]); pct = round(d / e["prev"] * 100) if e["prev"] else 0
                    L.extend(["", f"{i:02d}. {e['species']}",
                              f"가격: {won(e['prev'])}원 → {won(e['price'])}원",
                              f"변동: {arr}{won(d)}원 / {pct}% {word}"])

    block("▲ 가격 인상", up, "인상", "▲")
    block("▼ 가격 인하", down, "인하", "▼")

    # 자동 메모: 특가/이벤트 종료로 인한 인상 감지
    notes = []
    for store in STORE_ORDER:
        si = [e for e in up if e["vendor"] == store]
        if si and sum(1 for e in si if re.search(r'이벤트|특가', e["raw"])) >= max(1, (len(si) + 1) // 2):
            notes.append(f"※ {ABBR.get(store, store)} 인상분 상당수는 특가/이벤트 종료에 따른 것으로 보입니다.")
    if notes:
        L.append(""); L += notes
    L += ["", "※ 개인적으로 확인·기록한 참고 자료이며 판매·중개·광고가 아닙니다."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7, help="최근 N일 변동으로 글 생성 (기본 7)")
    ap.add_argument("--since", metavar="YYYY-MM-DD", help="이 날짜(포함) 이후 변동만")
    ap.add_argument("--urgent", action="store_true", help="제목을 [긴급]으로")
    ap.add_argument("--log-only", action="store_true", help="글 없이 csv 로그만 갱신")
    args = ap.parse_args()

    events = all_change_events()
    new_events, total = update_log(events)
    print(f"변동 로그: 신규 {len(new_events)}건 / 누적 {total}건 → {os.path.basename(LOG_FILE)}")
    # 새 변동 알림 플래그 (notify.py가 읽음). 변동 없으면 플래그 제거.
    flag = os.path.join(HERE, "_새변동.txt")
    if new_events:
        up = sum(1 for e in new_events if e["price"] > e["prev"]); dn = len(new_events) - up
        latest = max(e["date"] for e in new_events)
        open(flag, "w", encoding="utf-8").write(f"신규 변동 {len(new_events)}건 · 인상 {up} · 인하 {dn} · {latest}")
    elif os.path.exists(flag):
        os.remove(flag)
    nsnap = write_snapshot()
    print(f"전체 현황: {nsnap}개 상품 → {os.path.basename(SNAP_FILE)}")
    if args.log_only:
        return

    if args.since:
        win = [e for e in events if e["date"] >= args.since]
        label = f"{args.since} 이후"
    else:
        # 최근 N일: 가장 최근 변동일 기준 N일 이내
        if not events:
            print("변동 없음 → 글 생략"); return
        latest = max(e["date"] for e in events)
        ld = datetime.date.fromisoformat(latest)
        start = (ld - datetime.timedelta(days=args.days - 1)).isoformat()
        win = [e for e in events if e["date"] >= start]
        label = f"최근 {args.days}일({start}~{latest})"

    txt = gen_text(win, urgent=args.urgent)
    if not txt:
        print(f"{label}: 변동 없음 → 글 생략"); return
    open(TXT_FILE, "w", encoding="utf-8").write(txt + "\n")
    print(f"글 생성: {label}, {len(win)}건 → {os.path.basename(TXT_FILE)}")


if __name__ == "__main__":
    main()
