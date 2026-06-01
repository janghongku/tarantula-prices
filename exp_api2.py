#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""80개 한계 돌파: 페이지네이션 DOM + 페이지2 클릭 시 뜨는 상품목록 API 캡처."""
import re, json
from playwright.sync_api import sync_playwright
PROFILE=".naver-profile"
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH=("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")
HANDLE="terrafactory"
jsonurls=[]
with sync_playwright() as pw:
    ctx=pw.chromium.launch_persistent_context(PROFILE, headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul", viewport={"width":1280,"height":2200})
    ctx.add_init_script(STEALTH)
    page=ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", lambda r: jsonurls.append(r.url) if ("json" in r.headers.get("content-type","") and re.search(r"/i/|/api/|product",r.url)) else None)
    page.goto(f"https://smartstore.naver.com/{HANDLE}/category/ALL?st=TOTALSALE&dt=IMAGE&size=80",
              wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3000)
    for _ in range(5): page.mouse.wheel(0,12000); page.wait_for_timeout(900)
    print("blocked:", "nidlogin" in page.url, "| product links:", page.evaluate("()=>document.querySelectorAll(\"a[href*='/products/']\").length"))
    pag=page.evaluate(r"""()=>{const out=[];
       document.querySelectorAll('a,button').forEach(e=>{
          const t=(e.textContent||'').trim(); const al=e.getAttribute('aria-label')||'';
          if(/^\d{1,3}$/.test(t) || /다음|next|페이지/i.test(t+al)){
             out.push({tag:e.tagName,t:t.slice(0,10),aria:al.slice(0,20),cls:(typeof e.className==='string'?e.className:'').slice(0,50),role:e.getAttribute('role')||''});}});
       const u={}; return out.filter(x=>{const k=JSON.stringify(x);if(u[k])return false;u[k]=1;return true;}).slice(0,40);}""")
    print("=== pagination 후보 DOM ===")
    for p in pag: print("  ", p)
    before=set(jsonurls)
    clicked=None
    for role in ("link","button"):
        try:
            loc=page.get_by_role(role, name="2", exact=True)
            if loc.count()>0:
                loc.first.scroll_into_view_if_needed(timeout=3000); loc.first.click(timeout=4000)
                clicked=f"{role} name=2 (count={loc.count()})"; break
        except Exception as e:
            clicked=f"err:{e}"
    page.wait_for_timeout(2500)
    for _ in range(3): page.mouse.wheel(0,12000); page.wait_for_timeout(800)
    print("clicked:", clicked, "| product links after:", page.evaluate("()=>document.querySelectorAll(\"a[href*='/products/']\").length"))
    after=[u for u in jsonurls if u not in before]
    print("=== 클릭 후 새 JSON 호출 ===")
    for u in sorted(set(after)): print("  ", u)
    print("channelUid:", page.evaluate(r"""()=>{const m=JSON.stringify(window.__PRELOADED_STATE__||{}).match(/"channelUid":"([^"]+)"/);return m?m[1]:null;}"""))
    ctx.close()
