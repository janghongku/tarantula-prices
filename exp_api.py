#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""네이버 스마트스토어 상품목록 API 찾기 + 페이지네이션 확인 (80개 한계 돌파용)."""
import re, json
from playwright.sync_api import sync_playwright
PROFILE=".naver-profile"
UA=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
STEALTH=("Object.defineProperty(navigator,'webdriver',{get:()=>undefined});window.chrome={runtime:{}};")
HANDLE="terrafactory"   # 거미랑 = 타란튤라 80+개
urls=[]
with sync_playwright() as pw:
    ctx=pw.chromium.launch_persistent_context(PROFILE, headless=False,
        args=["--disable-blink-features=AutomationControlled"],
        user_agent=UA, locale="ko-KR", timezone_id="Asia/Seoul", viewport={"width":1280,"height":1800})
    ctx.add_init_script(STEALTH)
    page=ctx.pages[0] if ctx.pages else ctx.new_page()
    page.on("response", lambda r: urls.append(r.url) if ("json" in r.headers.get("content-type","") and re.search(r"product|/i/|/api/",r.url)) else None)
    page.goto(f"https://smartstore.naver.com/{HANDLE}/category/ALL?st=TOTALSALE&dt=IMAGE&size=80",
              wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(3500)
    for _ in range(4): page.mouse.wheel(0,9000); page.wait_for_timeout(1200)
    print("blocked:", "nidlogin" in page.url)
    cands=sorted(set(u for u in urls if "product" in u.lower()))
    print(f"=== product API 후보 {len(cands)}개 ===")
    for u in cands:
        try:
            info=page.evaluate("""async (url)=>{
                try{ const r=await fetch(url,{credentials:'include'}); const j=await r.json();
                  const s=JSON.stringify(j);
                  const cnt=(s.match(/"productNo"/g)||[]).length;
                  const tot=(s.match(/"totalCount":(\\d+)/)||s.match(/"total":(\\d+)/)||[])[1];
                  return {ok:true, len:s.length, productNoCount:cnt, totalCount:tot, topKeys:Object.keys(j).slice(0,12)};
                }catch(e){ return {ok:false, err:String(e)}; }
            }""", u)
        except Exception as e:
            info={"ok":False,"err":str(e)}
        print(f"\nURL: {u}")
        print(f"   {info}")
    ctx.close()
