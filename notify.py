#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
가격변동 알림. make_report 가 변동 감지 시 남긴 _새변동.txt 를 읽어:
  1) macOS 알림(즉시, 설정 불필요)
  2) (선택) 휴대폰 푸시 — notify_webhook.txt 에 주소를 넣어두면 그리로 전송

휴대폰 알림 설정(둘 중 하나, notify_webhook.txt 에 한 줄):
  · 디스코드: 웹훅 URL 그대로  (예: https://discord.com/api/webhooks/....)
  · 텔레그램: telegram:<봇토큰>:<chat_id>

cron 맨 끝에서 실행됨. 변동 없으면 아무 것도 안 함.
"""
import os, json, subprocess, urllib.request, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
FLAG = os.path.join(HERE, "outputs", "_새변동.txt")
WEBHOOK = os.path.join(HERE, "notify_webhook.txt")   # 설정 파일은 루트(찾기 쉽게)


def mac_notify(title, msg):
    def esc(s):
        return s.replace("\\", "\\\\").replace('"', '\\"')
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{esc(msg)}" with title "{esc(title)}" sound name "Glass"'],
                       check=False, timeout=10)
    except Exception:
        pass


def send_webhook(msg):
    if not os.path.exists(WEBHOOK):
        return
    url = open(WEBHOOK, encoding="utf-8").read().strip()
    if not url:
        return
    try:
        if url.startswith("telegram:"):
            _, token, chat = url.split(":", 2)
            api = f"https://api.telegram.org/bot{token}/sendMessage"
            data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
            urllib.request.urlopen(urllib.request.Request(api, data=data), timeout=15)
        else:   # 디스코드/슬랙 호환 (content/text 둘 다 넣음)
            data = json.dumps({"content": msg, "text": msg}, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=15)
        print("푸시 전송 완료")
    except Exception as e:
        print("푸시 실패:", e)


def main():
    if not os.path.exists(FLAG):
        return
    msg = open(FLAG, encoding="utf-8").read().strip()
    if not msg:
        return
    mac_notify("🕷 거미 가격변동 발생", msg)
    send_webhook("[거미 가격변동] " + msg + "\n→ 글/엑셀/이미지 자동 생성됨")
    print("알림:", msg)
    try:
        os.remove(FLAG)     # 알림 후 플래그 제거(중복 알림 방지)
    except OSError:
        pass


if __name__ == "__main__":
    main()
