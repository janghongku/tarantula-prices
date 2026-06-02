#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
거미 가격 데이터 '같은 상품(종) 묶기' — 정밀도 우선 그룹핑.

매칭 우선순위 (위에서부터 적용):
  1) 학명(binomial) 직접 표기      → 가장 신뢰
  2) 한글명→학명 자동맵 (데이터에서 추출)
  3) 별칭 사전(species_aliases.json) 의 수동 클러스터
  4) 폴백: 한글 핵심토큰 정렬키 (띄어쓰기/순서 변형 흡수)

사용법:
  python3 species_groups.py report         # 커버리지 리포트
  python3 species_groups.py candidates      # 검수용 후보 클러스터 생성 → candidates_review.txt
  python3 species_groups.py groups          # 그룹 결과를 groups.json 으로 출력
"""
import json, re, sys, os
from collections import defaultdict, Counter
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PRICES = os.path.join(HERE, "prices.json")
ALIASES = os.path.join(HERE, "species_aliases.json")

# ── 도메인 설정 ────────────────────────────────────────────────
GENERA = set("""
acanthoscurria aphonopelma augacephalus avicularia birupes bonnetina brachypelma caribena
ceratogyrus chaetopelma chilobrachys chromatopelma citharacanthus cyclosternum cyriocosmus
cyriopagopus davus dolichothele encyocratella ephebopus euathlus eucratoscelus eupalaestrus
grammostola hapalopus haplocosmia haplopelma harpactira heteroscodra heterothele homoeomma
hysterocrates idiothele lampropelma lasiodora lasiodorides megaphobema melopoeus monocentropus
neoholothele nhandu omothymus orphnaecus pamphobeteus pelinobius phlogiellus phormictopus
poecilotheria psalmopoeus pseudhapalopus pterinochilus pterinopelma sericopelma stromatopelma
tapinauchenius theraphosa thrixopelma tliltocatl typhochlaena vitalius xenesthis ybyrapora
""".split())
# 재분류된 속(屬) → 대표속 통일 (같은 종의 학명 표기 차이 흡수)
GENUS_SYN = {
    "lampropelma": "cyriopagopus", "melopoeus": "cyriopagopus", "omothymus": "cyriopagopus",
    "haplopelma": "cyriopagopus", "citharacanthus": "davus", "tliltocatl": "brachypelma",
}
NOISE = set("""
타란튤라 타란툴라 애완거미 애완용거미 거미 곤충 애완곤충 곤충키우기 거미키우기 거미분양 희귀동물 희귀
절지류 절지동물 절지 파충류 양서류 밀웜 귀뚜라미 사육 사육세트 키우기 관찰 분양 분양중 예약 택배 용품
채집통 사슴벌레 전갈 지네 사마귀 새잡이거미 대왕거미 왕거미 입문 초보 아시안포레스트 충왕전 거미랑
절사모 나무위성 배회성 버로우성 수상성 지서성 반수상성 키트 세트 마리 무료배송 안전포장 시리즈
대형 소형 중형 대형종 소형종 중형종 초대형종 형종 인기 추천 신상 한정 특가 세일 이벤트 사이즈 옵션 옵션선택 타입 노멀
""".split())
STAGE_W = ["유체", "준성체", "아성체", "성체", "성충", "약충", "베이비", "베비", "스파이더링", "슬링"]
ATTR_W = STAGE_W + ["암컷", "수컷", "한쌍", "1쌍", "쌍", "펨", "메일", "초기", "초", "중", "말", "대", "특대"]

_binom = re.compile(r"([A-Za-z]{4,})\s+([A-Za-z]{3,})")
_bracket = re.compile(r"[\[\(（【].*?[\]\)）】]")
_size = re.compile(r"\d+\.?\d*\s*cm\+?-?")


def latin_binom(full):
    """알려진 속(屬)으로 시작하는 학명만 추출 (지명/오타 노이즈 배제)."""
    for m in _binom.finditer(full):
        g, s = m.group(1).lower(), m.group(2).lower()
        if g in GENERA:
            return f"{GENUS_SYN.get(g, g)} {s}"
    return None


def stage_of(name):
    core = name.split("/")[0]
    return next((s for s in STAGE_W if s in core), None)


def core_tokens(name):
    """노이즈/속성/크기/학명 제거 후 한글 핵심 토큰."""
    c = _bracket.sub(" ", name.split("/")[0])
    c = _size.sub(" ", c)
    for k in ATTR_W:
        c = c.replace(k, " ")
    c = re.sub(r"\d+", " ", c)
    c = re.sub(r"[A-Za-z]+", " ", c)
    toks = [t for t in re.split(r"[\s,./·\-~+'\"“”‘’]+", c) if t]
    return [t for t in toks if t not in NOISE and len(t) >= 2]


def token_key(name):
    toks = core_tokens(name)
    return "".join(sorted(toks)) if toks else None


def clean_display(name):
    """표시용 깔끔한 이름: 슬래시 앞에서 괄호/크기/단계/성별만 제거(종 단어·어순 유지)."""
    c = _bracket.sub(" ", name.split("/")[0])
    c = _size.sub(" ", c)
    for k in sorted(ATTR_W, key=len, reverse=True):
        c = c.replace(k, " ")
    c = re.sub(r"[\"'“”‘’]", " ", c)
    c = re.sub(r"\s+", " ", c).strip(" -·,")
    return c


# ── 사전/자동맵 로드 ───────────────────────────────────────────
def load_aliases():
    with open(ALIASES, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("groups", []), set(data.get("split_tokens", []))


def build_korean_to_latin(prods):
    """한글핵심키 → 학명 (데이터에서 공기(共起) 추출, 일관된 것만)."""
    m = defaultdict(Counter)
    for p in prods:
        lb, kk = latin_binom(p["name"]), token_key(p["name"])
        if lb and kk:
            m[kk][lb] += 1
    return {k: v.most_common(1)[0][0] for k, v in m.items()}


# ── 핵심: 상품 → canonical (대표키, 표시명, 학명) ───────────────
def make_canonicalizer(prods):
    k2l = build_korean_to_latin(prods)
    alias_groups, _ = load_aliases()

    def alias_lookup(name):
        toks = set(core_tokens(name))
        for g in alias_groups:
            for grp in g["match"]:
                if set(grp) <= toks:
                    return g
        return None

    def canon(name):
        # 3) 별칭 사전 우선 (사람이 확정한 것이므로 학명/자동맵보다 신뢰)
        a = alias_lookup(name)
        if a:
            return ("alias:" + a["canonical"], a["canonical"], a.get("sci", ""))
        # 1) 학명 직접
        lb = latin_binom(name)
        if lb:
            return ("sci:" + lb, None, lb)
        # 2) 한글→학명 자동맵
        kk = token_key(name)
        if kk and kk in k2l:
            return ("sci:" + k2l[kk], None, k2l[kk])
        # 4) 폴백
        if kk:
            return ("ko:" + kk, None, "")
        return ("raw:" + name, None, "")

    return canon, k2l


# ── 리포트 ─────────────────────────────────────────────────────
def cmd_report():
    prods = json.load(open(PRICES, encoding="utf-8"))["products"]
    canon, k2l = make_canonicalizer(prods)
    groups = defaultdict(list)
    for p in prods:
        key, _, _ = canon(p["name"])
        groups[key].append(p)
    multi = {k: v for k, v in groups.items() if len({m["vendor"] for m in v}) >= 2}
    n = sum(len(v) for v in multi.values())
    print(f"전체 상품: {len(prods)}개 / 자동 한글→학명 맵: {len(k2l)}개")
    print(f"업체 2곳 이상 묶인 그룹: {len(multi)}개 → 상품 {n}개 ({100*n//len(prods)}%)")
    print(f"단독(비교 불가): {len(prods)-n}개 ({100*(len(prods)-n)//len(prods)}%)")


# ── 검수용 후보 생성 (자동 적용 X, 사람이 보고 사전에 옮김) ─────
def cmd_candidates():
    prods = json.load(open(PRICES, encoding="utf-8"))["products"]
    canon, _ = make_canonicalizer(prods)
    _, split_tokens = load_aliases()

    # 현재 단독(업체비교 안 되는) 상품만 후보 대상
    g = defaultdict(list)
    for p in prods:
        g[canon(p["name"])[0]].append(p)
    multi_ids = {id(m) for v in g.values() if len({x["vendor"] for x in v}) >= 2 for m in v}
    singles = [p for p in prods if id(p) not in multi_ids]

    # 토큰 문서빈도(현재 그룹키 기준)
    tok_keys = defaultdict(set)
    for p in prods:
        for t in core_tokens(p["name"]):
            tok_keys[t].add(canon(p["name"])[0])
    GENERIC = {"블루","블랙","레드","골든","화이트","그린","옐로우","핑크","오렌지","퍼플","실버","브라운",
               "버드이터","바분","타이거","핑크토","오너멘탈","로즈헤어","뷰티","자이언트","드워프","킹",
               "블루렉","레드렉","레드럼프","다이아몬드","제브라","메탈릭","러스트"} | split_tokens

    # 변별력 토큰(희귀) 공유로 후보 클러스터 — 단, 2개 이상 공유 우선(정밀)
    cand = defaultdict(list)
    for p in singles:
        toks = [t for t in core_tokens(p["name"]) if t not in GENERIC and len(tok_keys[t]) <= 5]
        if toks:
            anchor = min(toks, key=lambda t: len(tok_keys[t]))  # 가장 희귀한 토큰
            cand[anchor].append(p)

    lines = ["# 검수용 후보 — 같은 종으로 보이면 species_aliases.json 의 groups 에 추가하세요.",
             "# 함정(다른 종이 섞인 것)은 split_tokens 에 그 토큰을 넣으면 됩니다.\n"]
    rows = sorted(cand.items(), key=lambda kv: len({m["vendor"] for m in kv[1]}), reverse=True)
    for anchor, members in rows:
        vendors = {m["vendor"] for m in members}
        if len(vendors) < 2:
            continue
        lines.append(f"\n● 공통토큰 '{anchor}'  ({len(members)}개 · 업체 {len(vendors)}곳)")
        for m in sorted(members, key=lambda x: x["price"]):
            st = stage_of(m["name"]) or ""
            lines.append(f"    [{m['vendor']}] {m['name'].split('/')[0].strip()[:46]}  {m['price']:,}원 {st}")
    out = os.path.join(HERE, "candidates_review.txt")
    open(out, "w", encoding="utf-8").write("\n".join(lines))
    n_cand = sum(len(v) for a, v in cand.items() if len({m['vendor'] for m in v}) >= 2)
    print(f"검수 후보 {n_cand}개 상품 → {out}")
    print("확실한 것만 사전에 옮긴 뒤 `python3 species_groups.py report` 로 커버리지 재확인하세요.")


# ── 그룹 결과 출력 (UI 연동용) ─────────────────────────────────
def cmd_groups():
    prods = json.load(open(PRICES, encoding="utf-8"))["products"]
    canon, _ = make_canonicalizer(prods)
    g = defaultdict(list)
    for p in prods:
        key, disp, sci = canon(p["name"])
        g[key].append((p, disp, sci))
    out = {"generated_at": datetime.now().isoformat(timespec="seconds"), "groups": []}
    for key, items in g.items():
        members = [it[0] for it in items]
        # 표시명: 별칭 사전의 canonical 우선, 없으면 멤버 중 가장 짧고 깔끔한 이름
        cleaned = [c for c in (clean_display(m["name"]) for m in members) if len(c) >= 2]
        disp = next((d for _, d, _ in items if d), None) \
            or (min(cleaned, key=len) if cleaned else members[0]["name"].split("/")[0].strip())
        sci = next((s for _, _, s in items if s), "")
        prices = [m["price"] for m in members]
        out["groups"].append({
            "id": key, "name": disp, "sci": sci,
            "count": len(members), "vendors": sorted({m["vendor"] for m in members}),
            "min": min(prices), "max": max(prices),
            "items": [{**m, "stage": stage_of(m["name"])} for m in members],
        })
    out["groups"].sort(key=lambda x: (-len(x["vendors"]), -x["count"]))
    path = os.path.join(HERE, "groups.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(out['groups'])}개 그룹 → {path}")


def stable_id(p):
    return p.get("url") or (p["vendor"] + "␟" + p["name"])


def cmd_map():
    """UI용 경량 매핑: 상품(url) → {그룹id, 표시명, 학명}. prices.json 은 건드리지 않음."""
    prods = json.load(open(PRICES, encoding="utf-8"))["products"]
    canon, _ = make_canonicalizer(prods)
    byid, meta = defaultdict(list), {}
    for p in prods:
        key, disp, sci = canon(p["name"])
        byid[key].append(p)
        m = meta.setdefault(key, {"disp": None, "sci": ""})
        if disp and not m["disp"]:
            m["disp"] = disp
        if sci and not m["sci"]:
            m["sci"] = sci
    out = {}
    for key, members in byid.items():
        cleaned = [c for c in (clean_display(m["name"]) for m in members) if len(c) >= 2]
        name = meta[key]["disp"] or (min(cleaned, key=len) if cleaned else members[0]["name"].split("/")[0].strip())
        for p in members:
            out[stable_id(p)] = {"i": key, "n": name, "s": meta[key]["sci"]}
    path = os.path.join(HERE, "group_map.json")
    json.dump({"generated_at": datetime.now().isoformat(timespec="seconds"), "map": out},
              open(path, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    multi = sum(1 for k, v in byid.items() if len({m["vendor"] for m in v}) >= 2)
    print(f"{len(out)}개 상품 매핑 / {len(byid)}개 그룹(업체2곳+ {multi}) → {path}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "report"
    {"report": cmd_report, "candidates": cmd_candidates,
     "groups": cmd_groups, "map": cmd_map}.get(cmd, cmd_report)()
