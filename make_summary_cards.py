#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""기간별 판매가 총정리 카드(스코어보드형) — 순변동 전체 랭킹.
순변동 = 기준일 시점가 → 종료일 시점가. 05-31 재시드·일시 이벤트가·왕복(순변동0)은 제외.
TOP N만 자르지 않고 '오른 종 전체 / 내린 종 전체'를 한 장에 쭉 싣는다(세로로 길어짐).
사용: python make_summary_cards.py   (6월 통합 + 3~4주차 통합 두 장)"""
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


def short(s, n=17):
    s = str(s or "")
    return s if len(s) <= n else s[:n].rstrip() + "…"


def chab(ch):
    return "N" if ch == "네이버" else "자사"


def compute(base_date, end_date):
    """[base_date, end_date] 기간의 순변동. base=기준일 시점가(그 날짜 이하 마지막 점), end=종료일 시점가."""
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
        pre = [pr for d, pr in pts if d <= base_date]          # 기준일 시점가
        inperiod = [pr for d, pr in pts if d <= end_date]
        if not inperiod:
            continue
        base = pre[-1] if pre else inperiod[0]                 # 기준일 전 점 없으면 기간내 첫 등장가
        end = inperiod[-1]
        if base == end:                                        # 순변동 0(왕복/안정) 제외
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


def render(title, subtitle, lead_period, base_date, end_date, out):
    movers, ups, dns, sv = compute(base_date, end_date)
    total, nup, ndn = len(movers), len(ups), len(dns)
    stores = sorted(sv.items(), key=lambda x: -x[1])

    W, LM = 9.0, 0.55
    RM = W - 0.55
    HEAD, LEAD, KPI, SEC, ROW, BARH, FOOTH = 1.5, 0.82, 1.35, 0.66, 0.44, 0.54, 0.95
    H = HEAD + LEAD + KPI + (SEC + nup * ROW) + (SEC + ndn * ROW) + (SEC + len(stores) * BARH) + FOOTH

    fig = plt.figure(figsize=(W, H), dpi=130)
    fig.patch.set_facecolor(BG)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.invert_yaxis(); ax.axis("off")
    ax.add_patch(plt.Rectangle((0, 0), W, H, facecolor=BG, edgecolor="none", zorder=-1))

    # 헤더
    ax.text(LM, 0.55, title, fontsize=23, fontweight="bold", color=INK, va="center")
    ax.text(LM, 1.15, f"{subtitle}  ·  순변동 {total}건", fontsize=13, color=SUB, va="center")
    ax.text(RM, 1.15, f"확인 {crawl_date()}", fontsize=11, color=SUB, va="center", ha="right")
    ax.plot([LM, RM], [HEAD, HEAD], color=DIV, lw=1)
    y = HEAD
    # 리드 한 줄
    ax.text(LM, y + LEAD / 2, f"{lead_period} 표시가가 바뀐 건 {total}건 — 오른 종 {nup}, 내린 종 {ndn}.",
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
            ax.text(LM + 0.05, cy, str(i), fontsize=11.5, fontweight="bold", color=SUB, va="center")
            ax.text(LM + 0.5, cy, short(clean_name(m["name"]), 17), fontsize=12, color=INK, va="center")
            ax.text(RM - 2.7, cy, f"{ABBR.get(m['vendor'], m['vendor'])}·{chab(m['channel'])}",
                    fontsize=9.5, color=GREY, va="center", ha="right")
            ax.text(RM - 1.1, cy, f"{common.won(m['start'])}→{common.won(m['end'])}",
                    fontsize=10.5, color=PRICE, va="center", ha="right")
            ax.text(RM, cy, f"{'▲' if is_up else '▼'}{abs(m['pct'])}%", fontsize=12, fontweight="bold", color=col, va="center", ha="right")
            ax.plot([LM, RM], [y + ROW, y + ROW], color=HAIR, lw=0.8)
            y += ROW
        return y

    y = section(y, f"▲ 인상 · 전체 {nup}건", UP, ups, True)
    y = section(y, f"▼ 인하 · 전체 {ndn}건", DOWN, dns, False)

    # 매장별 순변동 막대
    ax.add_patch(FancyBboxPatch((LM - 0.15, y + 0.06), RM - LM + 0.3, 0.46,
                                boxstyle="round,pad=0,rounding_size=0.08", linewidth=0, facecolor=SUB, alpha=0.10))
    ax.text(LM, y + 0.29, "매장별 순변동 건수", fontsize=14.5, fontweight="bold", color=INK, va="center")
    y += SEC
    mx = max((c for _, c in stores), default=1)
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
            "국내 판매처 공개 표시가 · 순변동=기준일 대비 종료일 · 일시 이벤트가·데이터 보정분·단기 왕복 제외 · 구매 전 원문 확인 · 한국 타란튤라 판매가 기록",
            fontsize=8, color=FOOT, ha="center", va="center")

    os.makedirs(OUTDIR, exist_ok=True)
    fig.savefig(out, facecolor=BG, dpi=130)
    plt.close(fig)
    print(f"→ {os.path.basename(out)}  (순변동 {total}건; 인상 {nup}·인하 {ndn})")


def main():
    render("타란튤라 판매가 총정리", "2026년 6월 월간 결산", "6월 한 달",
           "2026-06-02", "2026-06-30", os.path.join(OUTDIR, "6월_총정리_카드.png"))
    render("타란튤라 판매가 총정리", "6월 3~4주차 결산 (15~30일)", "6월 3~4주차(15~30일)",
           "2026-06-15", "2026-06-30", os.path.join(OUTDIR, "6월_3-4주차_총정리_카드.png"))


if __name__ == "__main__":
    main()
