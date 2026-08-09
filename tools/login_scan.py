"""扫码登录 B站（TV 协议，requests 实现）：生成二维码链接 → 手机扫码 → cookie 持久化。

用法：python3 tools/login_scan.py
登录成功后 cookie 存 bilitool 包内 config.json，并导出本目录 cookie.json 备份。
"""

import hashlib
import json
import os
import sys
import time
from urllib.parse import urlencode

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

APP_KEY = "4409e2ce8ffd12b8"
APP_SEC = "59b43e04ad6965f34319062b478f83dd"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://www.bilibili.com/",
    "Content-Type": "application/x-www-form-urlencoded",
}

def sign(params):
    p = dict(params)
    p["appkey"] = APP_KEY
    q = "&".join(f"{k}={p[k]}" for k in sorted(p))
    p["sign"] = hashlib.md5((q + APP_SEC).encode()).hexdigest()
    return p

def post(api, params):
    s = requests.Session()
    r = s.post(api, data=sign(params), headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json()

def main():
    body = post("https://passport.bilibili.com/x/passport-tv-login/qrcode/auth_code",
                {"local_id": "0", "ts": str(int(time.time()))})
    if body["code"] != 0:
        raise SystemExit(f"获取二维码失败: {body}")
    login_url = body["data"]["url"]
    auth_code = body["data"]["auth_code"]
    print("=" * 60, flush=True)
    print("请用手机 B站 App 扫码登录（或手机浏览器打开链接确认）：", flush=True)
    print(login_url, flush=True)
    print("=" * 60, flush=True)
    while True:
        body = post("https://passport.bilibili.com/x/passport-tv-login/qrcode/poll",
                    {"auth_code": auth_code, "local_id": "0", "ts": str(int(time.time()))})
        if body["code"] == 0:
            break
        time.sleep(3)
    # 写入 bilitool 包内 config.json（登录态供 UploadController 使用）
    from bilitool.model.model import Model
    c = body["data"]["cookie_info"]["cookies"]
    vals = {v["name"]: v["value"] for v in c}
    Model().save_cookies_info(body["data"]["access_token"], vals.get("SESSDATA", ""),
                              vals.get("bili_jct", ""), vals.get("DedeUserID", ""),
                              vals.get("DedeUserID__ckMd5", ""), vals.get("sid", ""))
    with open("cookie.json", "w", encoding="utf-8") as f:
        json.dump(body, f, ensure_ascii=False, indent=4)
    print("登录成功，cookie 已保存。", flush=True)


if __name__ == "__main__":
    main()
