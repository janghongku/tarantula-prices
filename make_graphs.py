#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2회 이상 가격이 변동된 거미의 '가격 추이 그래프(PNG)' 생성 → graphs/ 폴더.
글 발행 시 해당 이미지를 첨부하면 됨. (1회 변동은 그래프 의미 적어 제외)

실행:
  python3 make_graphs.py            # 2회 이상 변동된 상품 전부 그래프
  python3 make_graphs.py --demo     # 합성 예시 1장(모양 확인용)
  python3 make_graphs.py --min-changes 3
(matplotlib 필요)
"""
import json, os, re, argparse
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPHDIR = os.path.join(HERE, "graphs")

# 한글 폰트
_fonts = {f.name for f in fm.fontManager.ttflist}
for _c in ("AppleGothic", "Apple SD Gothic Neo", "NanumGothic", "Malgun Gothic"):
    if _c in _fonts:
        plt.rcParams["font.family"] = _c
        break
plt.rcParams["axes.unicode_minus"] = False


def hist_key(url):
    u = url or ""
    host = re.sub(r"^https?://", "", u).split("/")[0]
    if not host:
        return u
    m = re.search(r"/products/(\d+)", u) or re.search(r"/product/[^/]+/(\d+)", u)
    return f"{host}/{m.group(1)}" if m else u


def species_name(p, gm):
    g = gm.get(p.get("url") or "", {}) if False else gm.get(_keyOf(p), {})
    nm = g.get("n") or re.sub(r'^\(?\s*\d+월\s*이벤트\s*\)?\s*', '', p["name"].split("/")[0]).strip()
    return nm.split(",")[0].strip()


def _keyOf(p):
    return p.get("url") or (p["vendor"] + "␟" + p["name"])


def safe_filename(s):
    return re.sub(r'[^\w가-힣]+', '_', s).strip('_')[:70]


def plot(name, sub, pts, outpath):
    """pts = [[YYYY-MM-DD, price], ...] 오름차순."""
    xs = list(range(len(pts)))
    labels = [d[5:].replace('-', '/') for d, _ in pts]   # MM/DD
    prices = [pr for _, pr in pts]
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=130)
    ax.plot(xs, prices, '-o', color="#c0392b", linewidth=2.2, markersize=7, markerfacecolor="white", markeredgewidth=2)
    for x, y in zip(xs, prices):
        ax.annotate(f"{y:,}원", (x, y), textcoords="offset points", xytext=(0, 9), ha="center", fontsize=9.5, fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.3, len(pts) - 0.7)
    ax.set_title(f"{name}   ·   {sub}", fontsize=13, fontweight="bold", pad=12)
    ax.set_ylabel("표시 가격")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.grid(True, axis="y", alpha=0.3)
    ax.margins(y=0.22)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    fig.text(0.99, 0.01, "한국 타란튤라 판매가 기록 프로젝트", ha="right", va="bottom", fontsize=7, color="#999")
    fig.tight_layout()
    fig.savefig(outpath, facecolor="white")
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--min-changes", type=int, default=2)
    args = ap.parse_args()
    os.makedirs(GRAPHDIR, exist_ok=True)

    if args.demo:
        pts = [["2026-05-10", 3000], ["2026-05-20", 8000], ["2026-05-28", 6000], ["2026-06-01", 14000]]
        out = os.path.join(GRAPHDIR, "_예시.png")
        plot("상히에 아일랜드 블랙 (예시)", "거미랑 / 네이버", pts, out)
        print("데모 그래프 →", out)
        return

    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    try:
        gm = json.load(open(os.path.join(HERE, "group_map.json"), encoding="utf-8"))["map"]
    except Exception:
        gm = {}
    by_key = {hist_key(p["url"]): p for p in prods if p.get("url")}

    made = []
    for hk, pts in hist.items():
        if len(pts) - 1 < args.min_changes:    # 변동 횟수 = 점 개수 - 1
            continue
        p = by_key.get(hk)
        if not p:
            continue
        name = species_name(p, gm)
        fn = safe_filename(f"{name}_{p['vendor']}_{p['channel']}") + ".png"
        plot(name, f"{p['vendor']} / {p['channel']}", pts, os.path.join(GRAPHDIR, fn))
        made.append((name, len(pts) - 1, fn))
    print(f"그래프 {len(made)}개 생성 → {GRAPHDIR}/  ({args.min_changes}회 이상 변동된 거미)")
    for name, ch, fn in sorted(made, key=lambda x: -x[1]):
        print(f"  · {name} ({ch}회 변동) → {fn}")
    if not made:
        print("  (아직 2회 이상 변동된 상품이 없어요. 변동이 쌓이면 자동으로 생겨요.)")


if __name__ == "__main__":
    main()
