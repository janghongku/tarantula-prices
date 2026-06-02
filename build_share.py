#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prices.json 을 index.html 에 박아넣어 '더블클릭으로 열리는' 단일 파일 생성.
   친구에게 이 파일 하나만 보내면 됨 (서버·GitHub·인터넷 불필요).

   실행:  python build_share.py
   결과:  거미가격_공유.html
"""
import json, pathlib

html = pathlib.Path("index.html").read_text(encoding="utf-8")
data = pathlib.Path("prices.json").read_text(encoding="utf-8")

# 그룹 매핑도 함께 내장 (있으면) — 단일 파일에서도 '묶음' 토글이 동작하도록
gmap_path = pathlib.Path("group_map.json")
gmap = json.loads(gmap_path.read_text(encoding="utf-8")).get("map", {}) if gmap_path.exists() else {}
gmap_js = json.dumps(gmap, ensure_ascii=False, separators=(",", ":"))

# 데이터를 <head> 안에 inline (로더가 window.__PRICES__ 를 먼저 본다)
inject = ("<script>window.__PRICES__ = " + data + ";\n"
          "window.__GROUP_MAP__ = " + gmap_js + ";</script>\n</head>")
out = html.replace("</head>", inject, 1)

dest = pathlib.Path("거미가격_공유.html")
dest.write_text(out, encoding="utf-8")
n = len(json.loads(data).get("products", []))
print(f"→ {dest} 생성 ({n}개 상품 내장, {dest.stat().st_size//1024} KB). 더블클릭으로 열림.")
