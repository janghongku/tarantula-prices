#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""더쥬(tzblossom) 절지류>타란툴라 하위 카테고리 ID 찾기."""
import json, re
from playwright.sync_api import sync_playwright
PROFILE=".naver-profile"
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH=("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")

def cats_with_spider(page):
    # state 트리에서 name에 타란/거미 들어간 카테고리 dict 찾기
    state=page.evaluate("()=>window.__PRELOADED_STATE__||null")
    hits=[]
    def walk(o,path=""):
        if isinstance(o,dict):
            nm=o.get("categoryName") or o.get("name") or o.get("displayName")
            cid=o.get("categoryId") or o.get("id") or o.get("categoryNo")
            if isinstance(nm,str) and re.search(r"타란|거미|절지",nm):
                hits.append((str(cid), nm, sorted(o.keys())[:8]))
            for k,v in o.items(): walk(v,path+"/"+str(k))
        elif isinstance(o,list):
            for v in o: walk(v,path)
    if state: walk(state)
    return hits

with sync_playwright() as pw:
    ctx=pw.chromium.launch_persistent_context(PROFILE, headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul", viewport={"width":1280,"height":1800})
    ctx.add_init_script(STEALTH)
    page=ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto("https://smartstore.naver.com/tzblossom/category/ALL?size=80", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2500)
    print("blocked:", "nidlogin" in page.url)
    print("\n=== state 카테고리(타란/거미/절지) ===")
    for cid,nm,keys in cats_with_spider(page):
        print(f"   id={cid} | {nm} | keys={keys}")
    print("\n=== DOM 앵커(category/타란/거미 포함) ===")
    links=page.evaluate(r"""()=>[...document.querySelectorAll('a')].map(a=>({h:a.getAttribute('href')||'',t:(a.textContent||'').replace(/\s+/g,' ').trim()})).filter(x=>(/category\//.test(x.h)||/타란|거미/.test(x.t))&&x.t&&x.t.length<30)""")
    seen=set()
    for l in links:
        key=(l['t'],l['h'])
        if key in seen: continue
        seen.add(key)
        print(f"   {l['t']!r} -> {l['h']}")
    ctx.close()
