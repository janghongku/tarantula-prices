#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2회 이상 가격변동된 거미의 추이 그래프.
  - 개별 PNG  → graphs/<거미>.png
  - 모음 1장  → 가격추이_모음.png  (그리드, 글에 카드+이 1장 첨부용)
(1회 변동은 제외)

실행:
  python3 make_graphs.py            # 실제 데이터
  python3 make_graphs.py --demo     # 합성 예시(모음 모양 확인)
  python3 make_graphs.py --min-changes 3
"""
import json, os, re, argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter
from make_report import ABBR, CH      # 판매처/채널 약칭 (샵 이름 직접 노출 금지)

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.join(HERE, "outputs")
GRAPHDIR = os.path.join(OUTDIR, "graphs")
MONTAGE = os.path.join(OUTDIR, "가격추이_모음.png")

_fonts = {f.name for f in fm.fontManager.ttflist}
for _c in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
    if _c in _fonts:
        plt.rcParams["font.family"] = _c
        break
plt.rcParams["axes.unicode_minus"] = False
CRED = "#c0392b"


def hist_key(url):
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


def _keyOf(p):
    return p.get("url") or (p["vendor"] + "␟" + p["name"])


def species_name(p, gm):
    g = gm.get(_keyOf(p), {})
    nm = g.get("n") or re.sub(r'^\(?\s*\d+월\s*이벤트\s*\)?\s*', '', p["name"].split("/")[0]).strip()
    return nm.split(",")[0].strip()


def safe_filename(s):
    return re.sub(r'[^\w가-힣]+', '_', s).strip('_')[:70]


def draw_trend(ax, name, sub, pts, compact=False):
    xs = list(range(len(pts)))
    labels = [d[5:].replace('-', '/') for d, _ in pts]
    prices = [pr for _, pr in pts]
    ax.plot(xs, prices, '-o', color=CRED, linewidth=1.7 if compact else 2.2,
            markersize=4.5 if compact else 7, markerfacecolor="white",
            markeredgewidth=1.6 if compact else 2)
    for x, y in zip(xs, prices):
        ax.annotate(f"{y:,}", (x, y), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=8 if compact else 9.5, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.3, len(pts) - 0.7)
    title = f"{name}  ·  {sub}" if not compact else f"{name}  ({sub})"
    ax.set_title(title, fontsize=10.5 if compact else 13, fontweight="bold", pad=8)
    if not compact:
        ax.set_ylabel("표시 가격")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(labelsize=8 if compact else 10)
    ax.grid(True, axis="y", alpha=0.3)
    ax.margins(y=0.24)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def save_individual(name, sub, pts, out):
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=130)
    draw_trend(ax, name, sub, pts)
    fig.text(0.99, 0.01, "한국 타란튤라 판매가 기록 프로젝트", ha="right", va="bottom", fontsize=7, color="#999")
    fig.tight_layout()
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def save_montage(items, out):
    n = len(items)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    fig = plt.figure(figsize=(7.0 * cols, 3.3 * rows + 0.5), dpi=120)
    fig.patch.set_facecolor("white")
    fig.suptitle("가격 추이 · 2회 이상 변동", fontsize=16, fontweight="bold", y=0.995)
    for i, (name, sub, pts) in enumerate(items):
        ax = fig.add_subplot(rows, cols, i + 1)
        draw_trend(ax, name, sub, pts, compact=True)
    fig.text(0.99, 0.004, "국내 공개 표시가 · 한국 타란튤라 판매가 기록 프로젝트", ha="right", va="bottom", fontsize=7.5, color="#aaa")
    fig.tight_layout(rect=[0, 0.01, 1, 0.97])
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--min-changes", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(GRAPHDIR, exist_ok=True)

    if args.demo:
        demo = [
            ("상히에 아일랜드 블랙", "ㄱㅁㄹ / N스토어", [["2026-05-10", 3000], ["2026-05-20", 8000], ["2026-05-28", 6000], ["2026-06-01", 14000]]),
            ("코스타리칸 레드렉", "ㄱㅁㄹ / N스토어", [["2026-05-12", 120000], ["2026-05-25", 139000], ["2026-06-01", 165000]]),
            ("바히아 퍼플레드", "ㅌㅋ / N스토어", [["2026-05-15", 18000], ["2026-05-22", 25000], ["2026-06-01", 38000]]),
            ("킹바분", "ㅌㅋ / N스토어", [["2026-05-11", 13000], ["2026-05-20", 11000], ["2026-05-30", 15000], ["2026-06-01", 18000]]),
            ("판케이 타이거", "ㅌㅋ / N스토어", [["2026-05-14", 23000], ["2026-05-26", 28000], ["2026-06-01", 35000]]),
        ]
        save_montage(demo, MONTAGE)
        print("데모 모음 →", MONTAGE)
        return

    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    try:
        gm = json.load(open(os.path.join(HERE, "group_map.json"), encoding="utf-8"))["map"]
    except Exception:
        gm = {}
    by_key = {hist_key(p["url"]): p for p in prods if p.get("url")}

    items = []
    for hk, pts in hist.items():
        if len(pts) - 1 < args.min_changes:
            continue
        p = by_key.get(hk)
        if not p:
            continue
        name = species_name(p, gm)
        sub = f"{ABBR.get(p['vendor'], p['vendor'])} / {CH.get(p['channel'], p['channel'])}"   # 약칭만
        save_individual(name, sub, pts, os.path.join(GRAPHDIR, safe_filename(f"{name}_{p['vendor']}_{p['channel']}") + ".png"))
        items.append((name, sub, pts))

    items.sort(key=lambda x: -len(x[2]))
    print(f"개별 그래프 {len(items)}개 → {GRAPHDIR}/")
    if items:
        save_montage(items, MONTAGE)
        print(f"모음 1장 → {os.path.basename(MONTAGE)}")
        for name, _, pts in items:
            print(f"  · {name} ({len(pts) - 1}회 변동)")
    else:
        # 모음 대상 없으면 이전 모음 제거(혼동 방지)
        if os.path.exists(MONTAGE):
            os.remove(MONTAGE)
        print("  (2회 이상 변동된 상품이 없어요. 변동이 쌓이면 자동 생성.)")


if __name__ == "__main__":
    main()
