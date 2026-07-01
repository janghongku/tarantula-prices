#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
2회 이상 가격변동된 거미의 추이 그래프.
  - 개별 PNG  → graphs/<거미>.png
  - 모음 1장  → 가격추이_모음.png  (그리드, 글에 카드+이 1장 첨부용)
(1회 변동은 제외)

★ 시세 비교: 각 그래프에 '같은 종을 파는 다른 샵들'의 시세를 함께 표시한다.
   - 같은 종(group_map) · 같은 성장단계(유체/준성체/성체 추정) · 품절 제외 · 다른 샵만
   - 샵별 대표가(그 샵의 최저가) → 연한 띠(가격대 min~max) + 점선(중앙값)
   - 이 판매처가 '내렸다'고 해도 원래 다른 데가 그 가격이면 한눈에 보이게.

실행:
  python3 make_graphs.py            # 실제 데이터
  python3 make_graphs.py --demo     # 합성 예시(모음·시세표시 모양 확인)
  python3 make_graphs.py --min-changes 3
"""
import json, os, re, argparse, statistics
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.ticker import FuncFormatter
from make_report import ABBR, CH      # 판매처/채널 약칭 (샵 이름 직접 노출 금지)
from common import hist_key            # 단일 정의(common.py)

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
CRED = "#c0392b"          # 이 판매처(변동) 선
CPEER = "#5b6b7a"         # 타 샵 시세 점선
CBAND = "#7f8fa6"         # 타 샵 가격대 띠

# ── 성장단계 추정 (가격은 단계별로 천차만별 → 같은 단계끼리 비교해야 의미) ──
STAGE_KW = ["준성체", "아성체", "성숙", "성체", "유체", "유생", "스파이더링", "슬링", "베이비", "베비"]
STAGE_NORM = {"유생": "유체", "슬링": "스파이더링", "베이비": "스파이더링", "베비": "스파이더링", "성숙": "성체"}


def infer_stage(name, st=""):
    """st 필드 우선, 없으면 상품명에서 단계 키워드 추정. ('준성체'를 '성체'보다 먼저 검사)"""
    for src in (st or "", name or ""):
        for kw in STAGE_KW:
            if kw in src:
                return STAGE_NORM.get(kw, kw)
    return ""


# hist_key는 common.py (단일 정의)


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
            markeredgewidth=1.6 if compact else 2, zorder=3)
    for x, y in zip(xs, prices):
        ax.annotate(f"{y:,}", (x, y), textcoords="offset points", xytext=(0, 7),
                    ha="center", fontsize=8 if compact else 9.5, fontweight="bold", zorder=5)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels)
    ax.set_xlim(-0.3, len(pts) - 0.7)
    ax.set_title(name, fontsize=11 if compact else 14, fontweight="bold", pad=8)   # 종명은 위
    ax.set_xlabel(sub, fontsize=9 if compact else 11.5, fontweight="bold",         # 가게는 그래프 아래
                  color="#6b6357", labelpad=7 if compact else 9)
    if not compact:
        ax.set_ylabel("표시 가격")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.tick_params(labelsize=8 if compact else 10)
    ax.grid(True, axis="y", alpha=0.3)

    # y축 범위: 빨간 선이 라벨 여백 포함해 보이도록
    ys = list(prices)
    ymin, ymax = min(ys), max(ys)
    span = (ymax - ymin) or max(ymax * 0.2, 1)
    ax.set_ylim(ymin - span * 0.16, ymax + span * 0.30)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)


def save_individual(name, sub, pts, out):
    fig, ax = plt.subplots(figsize=(7.2, 4.3), dpi=130)
    draw_trend(ax, name, sub, pts)
    fig.text(0.99, 0.012, "한국 타란튤라 판매가 기록 프로젝트", ha="right", va="bottom", fontsize=7, color="#aaa")
    fig.tight_layout(rect=[0, 0.02, 1, 1])
    fig.savefig(out, facecolor="white")
    plt.close(fig)


def save_montage(items, out):
    n = len(items)
    cols = 1 if n == 1 else 2
    rows = (n + cols - 1) // cols
    fig = plt.figure(figsize=(7.0 * cols, 3.4 * rows + 0.6), dpi=120)
    fig.patch.set_facecolor("white")
    fig.suptitle("가격 추이 · 2회 이상 변동", fontsize=16, fontweight="bold", y=0.995)
    for i, (name, sub, pts) in enumerate(items):
        ax = fig.add_subplot(rows, cols, i + 1)
        draw_trend(ax, name, sub, pts, compact=True)
    fig.text(0.99, 0.004, "빨강=해당 판매처 표시가 · 국내 공개 표시가",
             ha="right", va="bottom", fontsize=7.5, color="#aaa")
    fig.tight_layout(rect=[0, 0.015, 1, 0.97])
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
            ("발할라 어스타이거", "ㅌㄹㅅㅌ / N스토어", [["2026-05-20", 50000], ["2026-06-03", 35000]]),
            ("코스타리칸 레드렉", "ㄱㅁㄹ / N스토어", [["2026-05-12", 120000], ["2026-05-25", 139000], ["2026-06-01", 165000]]),
            ("바히아 퍼플레드", "ㅌㅋ / N스토어", [["2026-05-15", 18000], ["2026-05-22", 25000], ["2026-06-01", 38000]]),
            ("킹바분", "ㅌㅋ / N스토어", [["2026-05-11", 13000], ["2026-05-20", 11000], ["2026-05-30", 15000], ["2026-06-01", 18000]]),
        ]
        save_montage(demo, MONTAGE)
        for name, sub, pts in demo:
            save_individual(name, sub, pts, os.path.join(GRAPHDIR, safe_filename(name) + ".png"))
        print("데모 모음 →", MONTAGE, "/ 개별 →", GRAPHDIR)
        return

    prods = json.load(open(os.path.join(HERE, "prices.json"), encoding="utf-8"))["products"]
    hist = json.load(open(os.path.join(HERE, "price_history.json"), encoding="utf-8"))
    try:
        gm = json.load(open(os.path.join(HERE, "group_map.json"), encoding="utf-8"))["map"]
    except Exception:
        gm = {}
    by_key = {hist_key(p["url"]): p for p in prods if p.get("url")}
    by_url = {p["url"]: p for p in prods if p.get("url")}

    items = []
    for hk, pts in hist.items():
        if len(pts) - 1 < args.min_changes:
            continue
        if pts[0][1] == pts[-1][1]:          # V자 완전복귀(첫값=끝값, 순변동0) → 제외
            continue
        p = by_key.get(hk)
        if not p:
            continue
        name = species_name(p, gm)
        sub = f"{ABBR.get(p['vendor'], p['vendor'])} / {CH.get(p['channel'], p['channel'])}"   # 약칭만
        save_individual(name, sub, pts,
                        os.path.join(GRAPHDIR, safe_filename(f"{name}_{p['vendor']}_{p['channel']}") + ".png"))
        items.append((name, sub, pts))

    items.sort(key=lambda x: -len(x[2]))
    print(f"개별 그래프 {len(items)}개 → {GRAPHDIR}/")
    if items:
        save_montage(items, MONTAGE)
        print(f"모음 1장 → {os.path.basename(MONTAGE)}")
        for name, _, pts in items:
            print(f"  · {name} ({len(pts) - 1}회 변동)")
    else:
        if os.path.exists(MONTAGE):
            os.remove(MONTAGE)
        print("  (2회 이상 변동된 상품이 없어요. 변동이 쌓이면 자동 생성.)")


if __name__ == "__main__":
    main()
