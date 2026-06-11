#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가격변동 요약을 '깔끔한 카드 이미지(PNG)'로 — 인터넷에 올리기 좋게.
긴 txt 대신 이 이미지 1장을 첨부.

실행:
  python3 make_cards.py            # 최근 7일 변동 → 가격변동_카드.png
  python3 make_cards.py --since 2026-06-02 --urgent
(matplotlib 필요)
"""
import os, json, argparse, datetime
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
from make_report import all_change_events, all_new_arrivals, ABBR, CH, STORE_ORDER, CH_ORDER
from common import won   # 단일 정의(common.py)

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "outputs")
os.makedirs(OUTDIR, exist_ok=True)
OUT = os.path.join(OUTDIR, "가격변동_카드.png")
INTRO = os.path.join(OUTDIR, "가격변동_안내.png")
NEW = os.path.join(OUTDIR, "신규입고_카드.png")

_fonts = {f.name for f in fm.fontManager.ttflist}
for _c in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
    if _c in _fonts:
        plt.rcParams["font.family"] = _c
        break
plt.rcParams["axes.unicode_minus"] = False

BG = "#fbf8f3"; INK = "#2b2620"; SUB = "#8a8175"
UP = "#c0392b"; DOWN = "#2471a3"; NEWC = "#1e8449"
W = 10.0           # 가로(인치)
ROWH = 0.40       # 항목 줄 높이
SECH = 0.58       # 섹션 헤더 높이
STOREH = 0.40     # 판매처 헤더 높이


# won은 common.py (단일 정의)


def crawl_date():
    """마지막 크롤(확인) 날짜 — prices.json updated_at. 변동이 없어도 매 크롤마다 갱신됨."""
    try:
        d = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8")).get("updated_at", "")
        return d[:10].replace("-", ".")
    except Exception:
        return ""


def short(s, n=24):
    """카드 한 줄에 들어가도록 종명 길이 제한(넘으면 …). clean_name으로도 못 줄인
    긴 한글 관용명 대비 안전장치."""
    s = str(s or "")
    return s if len(s) <= n else s[:n].rstrip() + "…"


def build_lines(events):
    up = [e for e in events if e["price"] > e["prev"]]
    down = [e for e in events if e["price"] < e["prev"]]
    lines = []  # (kind, payload, color, height)
    for title, items, col in (("▲ 가격 인상", up, UP), ("▼ 가격 인하", down, DOWN)):
        if not items:
            continue
        lines.append(("sec", f"{title}  {len(items)}건", col, SECH))
        for store in STORE_ORDER:
            for ch in CH_ORDER:
                si = sorted([e for e in items if e["vendor"] == store and e["channel"] == ch],
                            key=lambda e: (e["date"], -e["price"]))   # 날짜 오름차순(오래된 게 위, 최신이 아래) → 같은날은 가격순
                if not si:
                    continue
                lines.append(("store", f"{ABBR.get(store, store)} / {CH.get(ch, ch)}", SUB, STOREH))
                for e in si:
                    lines.append(("item", e, col, ROWH))
    return lines, len(up), len(down)


def render(events, out, urgent=False):
    if not events:
        return False
    lines, nup, ndn = build_lines(events)
    latest = max(e["date"] for e in events)
    yy, mm, dd = map(int, latest.split("-")); wk = (dd - 1) // 7 + 1

    head_h = 1.45
    foot_h = 0.5
    H = head_h + sum(h for *_, h in lines) + foot_h

    fig = plt.figure(figsize=(W, H), dpi=130)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H)
    ax.invert_yaxis(); ax.axis("off")

    title = "타란튤라 판매가 변동" if not urgent else "[긴급] 타란튤라 판매가 변동"
    ax.text(0.45, 0.45, title, fontsize=20, fontweight="bold", color=INK, va="center")
    sub = (f"{mm}월 {wk}주차" if not urgent else "긴급") + f"  ·  최근 변동 {latest.replace('-', '.')}  ·  인상 {nup} · 인하 {ndn}"
    ax.text(0.45, 1.05, sub, fontsize=12, color=SUB, va="center")
    cd = crawl_date()
    if cd:
        ax.text(W - 0.45, 1.05, f"확인 {cd}", fontsize=11, color=SUB, va="center", ha="right")
    ax.plot([0.45, W - 0.45], [1.38, 1.38], color="#e3ddd2", lw=1)

    y = head_h
    for kind, val, col, h in lines:
        cy = y + h / 2
        if kind == "sec":
            ax.add_patch(FancyBboxPatch((0.4, y + 0.06), W - 0.8, h - 0.14,
                         boxstyle="round,pad=0,rounding_size=0.08", linewidth=0,
                         facecolor=col, alpha=0.10))
            ax.text(0.62, cy, val, fontsize=14.5, fontweight="bold", color=col, va="center")
        elif kind == "store":
            ax.text(0.6, cy, val, fontsize=11, fontweight="bold", color=SUB, va="center")
        else:
            e = val; d = e["price"] - e["prev"]; pct = round(abs(d) / e["prev"] * 100)
            arr = "▲" if d > 0 else "▼"
            dt = (e.get("date") or "")[5:].replace("-", "/")          # 변동일 MM/DD
            ax.text(0.78, cy, short(e["species"]), fontsize=12.5, color=INK, va="center")
            ax.text(W - 3.95, cy, dt, fontsize=10.5, color="#9a917f", va="center", ha="right")
            ax.text(W - 1.6, cy, f"{won(e['prev'])} → {won(e['price'])}", fontsize=11.5,
                    color="#5a5246", va="center", ha="right")
            ax.text(W - 0.5, cy, f"{arr}{pct}%", fontsize=12, fontweight="bold", color=col, va="center", ha="right")
            ax.plot([0.6, W - 0.5], [y + h, y + h], color="#efe9df", lw=0.8)
        y += h

    ax.text(W / 2, H - 0.22, "국내 판매처 공개 표시가 · 날짜=표시가가 바뀐 날(관측 기준) · 구매 전 원문 확인 · 한국 타란튤라 판매가 기록 프로젝트",
            fontsize=8.5, color="#b3ada2", ha="center", va="center")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return True


def build_new_lines(arrivals):
    lines = [("sec", f"신규 입고  {len(arrivals)}건", NEWC, SECH)]
    for store in STORE_ORDER:
        for ch in CH_ORDER:
            si = sorted([a for a in arrivals if a["vendor"] == store and a["channel"] == ch],
                        key=lambda a: -a["price"])
            if not si:
                continue
            lines.append(("store", f"{ABBR.get(store, store)} / {CH.get(ch, ch)}  {len(si)}건", SUB, STOREH))
            for a in si:
                lines.append(("item", a, NEWC, ROWH))
    return lines


def render_new(arrivals, out):
    """신규입고 카드 — 가격변동 카드와 같은 톤, 판매처별 묶음. 약칭만 노출."""
    if not arrivals:
        return False
    lines = build_new_lines(arrivals)
    latest = max(a["date"] for a in arrivals)
    yy, mm, dd = map(int, latest.split("-")); wk = (dd - 1) // 7 + 1
    head_h = 1.45; foot_h = 0.5
    H = head_h + sum(h for *_, h in lines) + foot_h
    fig = plt.figure(figsize=(W, H), dpi=130); fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
    ax.text(0.45, 0.45, "타란튤라 신규 입고", fontsize=20, fontweight="bold", color=INK, va="center")
    ax.text(0.45, 1.05, f"{mm}월 {wk}주차  ·  최근 입고 {latest.replace('-', '.')}  ·  신규 {len(arrivals)}건",
            fontsize=12, color=SUB, va="center")
    cd = crawl_date()
    if cd:
        ax.text(W - 0.45, 1.05, f"확인 {cd}", fontsize=11, color=SUB, va="center", ha="right")
    ax.plot([0.45, W - 0.45], [1.38, 1.38], color="#e3ddd2", lw=1)
    y = head_h
    for kind, val, col, h in lines:
        cy = y + h / 2
        if kind == "sec":
            ax.add_patch(FancyBboxPatch((0.4, y + 0.06), W - 0.8, h - 0.14,
                         boxstyle="round,pad=0,rounding_size=0.08", linewidth=0, facecolor=col, alpha=0.10))
            ax.text(0.62, cy, val, fontsize=14.5, fontweight="bold", color=col, va="center")
        elif kind == "store":
            ax.text(0.6, cy, val, fontsize=11, fontweight="bold", color=SUB, va="center")
        else:
            a = val; dt = (a.get("date") or "")[5:].replace("-", "/")
            name = short(a["species"]) + ("  (품절)" if a.get("soldout") else "")
            ax.text(0.78, cy, name, fontsize=12.5, color=INK, va="center")
            ax.text(W - 2.9, cy, dt, fontsize=10.5, color="#9a917f", va="center", ha="right")
            ax.text(W - 0.5, cy, f"{won(a['price'])}원", fontsize=12, fontweight="bold", color=INK, va="center", ha="right")
            ax.plot([0.6, W - 0.5], [y + h, y + h], color="#efe9df", lw=0.8)
        y += h
    ax.text(W / 2, H - 0.22, "국내 판매처 공개 표시가 · 날짜=처음 확인한 날 · 구매 전 원문 확인 · 한국 타란튤라 판매가 기록 프로젝트",
            fontsize=8.5, color="#b3ada2", ha="center", va="center")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return True


def render_intro(date, out):
    """글 맨 앞 고정 안내 배너."""
    fig = plt.figure(figsize=(9, 5.4), dpi=130)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.035, 0.05), 0.93, 0.90, boxstyle="round,pad=0,rounding_size=0.022",
                 linewidth=1.3, edgecolor="#d8cdbb", facecolor="white"))
    cx = 0.5
    ax.text(cx, 0.86, "타란튤라 판매가 변동 기록", fontsize=23, fontweight="bold", color=INK, ha="center", va="center")
    ax.text(cx, 0.755, f"{date} 변동 확인", fontsize=13.5, color=SUB, ha="center", va="center")
    ax.plot([0.2, 0.8], [0.69, 0.69], color="#ece4d6", lw=1)
    body = [
        "대상:  ㄱㅁㄹ · ㅌㅋ · ㄷㅈㅅㅍ · ㅌㄹㅅㅌ   (자사몰 / N스토어)",
        "기준:  국내 판매처 공개 표시가",
        "실제 구매가 · 재고 · 배송비 · 개체 상태는 판매처 원문에서 확인하세요.",
    ]
    y = 0.60
    for ln in body:
        ax.text(cx, y, ln, fontsize=12.5, color="#4a4339", ha="center", va="center"); y -= 0.085
    notes = [
        "※ 개인적으로 확인·기록한 참고 자료이며 판매·중개·광고가 아닙니다.",
        "※ 일부 가격이 누락되거나 실제와 다를 수 있습니다.",
        "※ 잘못된 정보나 누락된 가격 변동은 댓글로 제보해 주세요 · 확인 후 반영합니다.",
    ]
    y = 0.31
    for ln in notes:
        ax.text(cx, y, ln, fontsize=10.5, color=SUB, ha="center", va="center", style="italic"); y -= 0.075
    fig.savefig(out, facecolor=BG)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--since", metavar="YYYY-MM-DD")
    ap.add_argument("--urgent", action="store_true")
    args = ap.parse_args()
    ev = all_change_events()
    if args.since:
        win = [e for e in ev if e["date"] >= args.since]
    elif ev:
        latest = max(e["date"] for e in ev)
        start = (datetime.date.fromisoformat(latest) - datetime.timedelta(days=args.days - 1)).isoformat()
        win = [e for e in ev if e["date"] >= start]
    else:
        win = []
    win = [e for e in win if "이벤트" not in (e.get("raw") or "") and "특가" not in (e.get("raw") or "")]  # 일시적 특가/이벤트 제외
    if render(win, OUT, urgent=args.urgent):
        print(f"카드 이미지 생성 → {os.path.basename(OUT)} ({len(win)}건)")
    else:
        print("변동 없음 → 카드 생략")
    # 신규입고 카드 (변동 카드와 동일 윈도우: --since 또는 최근 N일)
    arr = all_new_arrivals()
    if args.since:
        arrwin = [a for a in arr if a["date"] >= args.since]
    elif arr:
        alatest = max(a["date"] for a in arr)
        astart = (datetime.date.fromisoformat(alatest) - datetime.timedelta(days=args.days - 1)).isoformat()
        arrwin = [a for a in arr if a["date"] >= astart]
    else:
        arrwin = []
    if render_new(arrwin, NEW):
        print(f"신규입고 카드 → {os.path.basename(NEW)} ({len(arrwin)}건)")
    else:
        print("신규입고 없음 → 카드 생략")
    # 고정 안내 배너(항상 생성, 날짜만 갱신)
    idate = (max((e["date"] for e in win), default="") or max((e["date"] for e in ev), default="")
             or datetime.date.today().isoformat()).replace("-", ".")
    render_intro(idate, INTRO)
    print(f"안내 배너 → {os.path.basename(INTRO)}")


if __name__ == "__main__":
    main()
