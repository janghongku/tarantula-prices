#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""6월 판매가 총정리 카드 — 월간 결산(스코어보드형).
순변동 = 6월초(06-02 기준가) → 6월말(06-30). 05-31 재시드 아티팩트·일시 이벤트가·왔다갔다(순변동0)는 제외.
사용: python make_june_card.py"""
import os, json
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch
import common
from make_report import ABBR, clean_name

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "outputs")
OUT = os.path.join(OUTDIR, "6월_총정리_카드.png")
BASE, JEND = "2026-06-02", "2026-06-30"   # 06-02 기준(05-31 불량 스냅샷 회피)

_fonts = {f.name for f in fm.fontManager.ttflist}
for _c in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
    if _c in _fonts:
        plt.rcParams["font.family"] = _c; break
plt.rcParams["axes.unicode_minus"] = False

BG="#fbf8f3"; INK="#2b2620"; SUB="#8a8175"; UP="#c0392b"; DOWN="#2471a3"
HAIR="#efe9df"; DIV="#e3ddd2"; PRICE="#5a5246"; GREY="#9a917f"; FOOT="#b3ada2"; BAR="#c9b79a"


def crawl_date():
    try:
        d = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8")).get("updated_at", "")
        return d[:10].replace("-", ".")
    except Exception:
        return ""


def short(s, n=16):
    s = str(s or "")
    return s if len(s) <= n else s[:n].rstrip() + "…"


def compute():
    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    bykey = {common.hist_key(p["url"]): p for p in prods if p.get("url")}
    movers = []
    for k, pts in hist.items():
        p = bykey.get(k)
        if not p:
            continue
        if "이벤트" in p["name"] or "특가" in p["name"]:      # 일시 프로모 제외
            continue
        pre = [pr for d, pr in pts if d <= BASE]              # 06-02 시점 기준가(재시드 회피)
        base = pre[-1] if pre else pts[0][1]
        jend = [pr for d, pr in pts if d <= JEND]
        end = jend[-1] if jend else base
        if base == end:                                       # 순변동 0(왔다갔다/안정) 제외
            continue
        if not (100 <= end <= 50_000_000 and 100 <= base):
            continue
        movers.append({"net": end - base, "pct": round((end - base) / base * 100),
                       "vendor": p["vendor"], "channel": p["channel"], "name": p["name"],
                       "start": base, "end": end})
    ups = sorted([m for m in movers if m["net"] > 0], key=lambda x: -x["net"])
    dns = sorted([m for m in movers if m["net"] < 0], key=lambda x: x["net"])
    sv = Counter()
    for m in movers:
        sv[m["vendor"]] += 1
    return movers, ups, dns, sv


def chab(ch):
    return "N" if ch == "네이버" else "자사"


def main():
    movers, ups, dns, sv = compute()
    total, nup, ndn = len(movers), len(ups), len(dns)
    top_up, top_dn = ups[:5], dns[:5]
    stores = sorted(sv.items(), key=lambda x: -x[1])

    W, LM = 9.0, 0.55
    RM = W - 0.55
    HEAD, LEAD, KPI, SEC, ROW, BARH, FOOTH = 1.5, 0.85, 1.35, 0.62, 0.48, 0.56, 0.95
    H = HEAD + LEAD + KPI + (SEC + len(top_up) * ROW) + (SEC + len(top_dn) * ROW) + (SEC + len(stores) * BARH) + FOOTH

    fig = plt.figure(figsize=(W, H), dpi=130)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), W, H, facecolor=BG, edgecolor="none", zorder=-1))

    # 헤더
    ax.text(LM, 0.55, "타란튤라 판매가 총정리", fontsize=23, fontweight="bold", color=INK, va="center")
    ax.text(LM, 1.15, f"2026년 6월 월간 결산  ·  순변동 {total}건", fontsize=13, color=SUB, va="center")
    ax.text(RM, 1.15, f"확인 {crawl_date()}", fontsize=11, color=SUB, va="center", ha="right")
    ax.plot([LM, RM], [HEAD, HEAD], color=DIV, lw=1)
    y = HEAD
    # 리드 한 줄
    ax.text(LM, y + LEAD / 2, f"6월 한 달 표시가가 바뀐 건 {total}건 — 오른 종 {nup}, 내린 종 {ndn}로 엇비슷했습니다.",
            fontsize=12.5, color="#4a4339", va="center")
    y += LEAD
    # KPI 띠
    seg = (RM - LM) / 3
    for i, (num, lab, col) in enumerate([(str(total), "순변동 건수", INK), (f"▲ {nup}", "인상", UP), (f"▼ {ndn}", "인하", DOWN)]):
        cx = LM + seg * (i + 0.5)
        ax.text(cx, y + 0.55, num, fontsize=27, fontweight="bold", color=col, ha="center", va="center")
        ax.text(cx, y + 1.02, lab, fontsize=11, color=SUB, ha="center", va="center")
        if i:
            ax.plot([LM + seg * i, LM + seg * i], [y + 0.14, y + KPI - 0.14], color=HAIR, lw=1)
    ax.plot([LM, RM], [y + KPI, y + KPI], color=DIV, lw=1)
    y += KPI

    def section(y, label, col, rows, is_up):
        ax.add_patch(FancyBboxPatch((LM - 0.15, y + 0.06), RM - LM + 0.3, 0.46,
                                    boxstyle="round,pad=0,rounding_size=0.08", linewidth=0, facecolor=col, alpha=0.10))
        ax.text(LM, y + 0.29, label, fontsize=14.5, fontweight="bold", color=col, va="center")
        y += SEC
        for i, m in enumerate(rows, 1):
            cy = y + ROW / 2
            ax.text(LM + 0.05, cy, str(i), fontsize=12, fontweight="bold", color=SUB, va="center")
            ax.text(LM + 0.45, cy, short(clean_name(m["name"]), 16), fontsize=12.5, color=INK, va="center")
            ax.text(RM - 2.7, cy, f"{ABBR.get(m['vendor'], m['vendor'])}·{chab(m['channel'])}",
                    fontsize=9.5, color=GREY, va="center", ha="right")
            ax.text(RM - 1.1, cy, f"{common.won(m['start'])}→{common.won(m['end'])}",
                    fontsize=10.5, color=PRICE, va="center", ha="right")
            ax.text(RM, cy, f"{'▲' if is_up else '▼'}{abs(m['pct'])}%", fontsize=12, fontweight="bold", color=col, va="center", ha="right")
            ax.plot([LM, RM], [y + ROW, y + ROW], color=HAIR, lw=0.8)
            y += ROW
        return y

    y = section(y, "▲ 인상 TOP 5", UP, top_up, True)
    y = section(y, "▼ 인하 TOP 5", DOWN, top_dn, False)

    # 매장별 순변동 막대
    ax.add_patch(FancyBboxPatch((LM - 0.15, y + 0.06), RM - LM + 0.3, 0.46,
                                boxstyle="round,pad=0,rounding_size=0.08", linewidth=0, facecolor=SUB, alpha=0.10))
    ax.text(LM, y + 0.29, "매장별 순변동 건수", fontsize=14.5, fontweight="bold", color=INK, va="center")
    y += SEC
    mx = max(c for _, c in stores)
    bx0, bxmax = LM + 1.5, RM - 0.6
    for v, c in stores:
        cy = y + BARH / 2
        ax.text(LM + 0.05, cy, ABBR.get(v, v), fontsize=12, color=INK, va="center")
        w = max((bxmax - bx0) * c / mx, 0.03)
        ax.add_patch(FancyBboxPatch((bx0, y + 0.13), w, BARH - 0.26,
                                    boxstyle="round,pad=0,rounding_size=0.05", linewidth=0, facecolor=BAR))
        ax.text(bx0 + w + 0.12, cy, str(c), fontsize=11, fontweight="bold", color=PRICE, va="center")
        y += BARH

    # 푸터
    ax.plot([LM, RM], [y + 0.18, y + 0.18], color=HAIR, lw=0.8)
    ax.text(W / 2, y + FOOTH / 2 + 0.1,
            "국내 판매처 공개 표시가 · 순변동=6월초 대비 월말 · 일시 이벤트가·데이터 보정분·단기 왕복 제외 · 구매 전 원문 확인 · 한국 타란튤라 판매가 기록",
            fontsize=8, color=FOOT, ha="center", va="center")

    os.makedirs(OUTDIR, exist_ok=True)
    fig.savefig(OUT, facecolor=BG, dpi=130)
    plt.close(fig)
    print(f"6월 총정리 카드 → {OUT} (순변동 {total}건; 인상 {nup}·인하 {ndn})")


if __name__ == "__main__":
    main()
