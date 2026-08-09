"""bilitool 上传封装：官方接口客户端库（合规：copyright=1 原创）。

- 上传（视频分片+封面）：复用 bilitool 官方上传协议。
- 发布（add/v3）：bilitool 的 publish_video 已停用（21590），自研创作中心 web/add/v3。
  实测关键参数：JSON body + csrf 在 query + wbi 签名（query）+ b_ret 风控指纹。
"""

import hashlib
import time
import urllib.parse

import requests
from bilitool import LoginController, UploadController
from bilitool.model.model import Model

TAG = "狗狗日常,汪星人,萌宠"
DESC = "自制原创狗狗日常视频，配乐使用B站官方授权音乐素材。 #狗狗日常 #汪星人 #萌宠"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")

# 风控指纹 b_ret = canvas 末 20 字符 + webgl 串前 50 字符（明文指纹，服务端不校验内容真实性）
_B_RET = ("2f4a5c8d9e1f3a5b7c9d"
          "[0.25, 0.25], extensions:ANGLE_instanced_arrays;EXT_blend_minmax;EXT_color_b")

_WBI_TBL = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,
            19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,
            30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]

class UploadError(Exception):
    pass

class LoginRequiredError(UploadError):
    pass

def build_title(num):
    return str(num)

def build_desc():
    return DESC

def login_ok():
    try:
        return bool(LoginController().check_bilibili_login())
    except Exception:
        return False

def _cookies():
    cfg = Model().get_config()
    return {k: v for k, v in cfg.get("cookies", {}).items() if v}

def _headers(referer="https://member.bilibili.com/york/videoup?new"):
    return {"User-Agent": UA, "Referer": referer}

def _wbi_key(session, cookies):
    r = session.get("https://api.bilibili.com/x/web-interface/nav",
                    headers=_headers("https://www.bilibili.com/"),
                    cookies=cookies, timeout=15)
    d = r.json()["data"]["wbi_img"]
    raw = (d["img_url"].split("/")[-1].split(".")[0]
           + d["sub_url"].split("/")[-1].split(".")[0])
    return "".join(raw[i] for i in _WBI_TBL)[:32]

def _wbi_sign(params, key):
    p = dict(params)
    p["wts"] = int(time.time())
    return hashlib.md5((urllib.parse.urlencode(sorted(p.items())) + key).encode()).hexdigest()

class Uploader:
    def __init__(self, controller=None):
        self.uploader = controller or UploadController()

    def upload(self, job, cfg):
        """上传成品+封面（分片+封面，不走已停用的发布接口）。返回 (filename, cover_url)。"""
        if not login_ok():
            raise LoginRequiredError("未登录：先运行 python tools/login_scan.py 扫码")
        try:
            filename = self.uploader.upload_video(job["ready_mp4"])
            cover_url = self.uploader.bili_uploader.cover_up(job["ready_cover"])
        except Exception as e:
            raise UploadError(f"bilitool 上传异常: {e}") from e
        if not filename or not cover_url:
            raise UploadError("bilitool 上传返回空 filename/cover_url")
        return filename, cover_url

    def publish(self, filename, cover_url, num, cfg):
        """发布稿件（web/add/v3，替代停用的 bilitool publish_video）。返回 (aid, bvid)。"""
        cookies = _cookies()
        csrf = cookies.get("bili_jct")
        if not csrf:
            raise LoginRequiredError("未登录：先运行 python tools/login_scan.py 扫码")
        title = build_title(int(num))
        session = requests.Session()
        key = _wbi_key(session, cookies)
        payload = {
            "cover": cover_url,
            "title": title,
            "copyright": cfg.get("copyright", 1),
            "tid": cfg.get("tid", 169),
            "tag": TAG,
            "desc_format_id": 0,
            "desc": build_desc(),
            "dynamic": "",
            "interactive": 0,
            "recreate": 0,
            "videos": [{"filename": filename, "title": title, "desc": "", "cid": 0}],
            "web_os": 1,
            "csrf": csrf,
        }
        params = {
            "web_location": "333.1024",
            "t": int(time.time() * 1000),
            "csrf": csrf,
            "b_ret": _B_RET,
        }
        params["w_rid"] = _wbi_sign(params, key)
        params["wts"] = int(time.time())
        r = session.post("https://member.bilibili.com/x/vu/web/add/v3",
                         headers=_headers(), cookies=cookies,
                         params=params, json=payload, timeout=30)
        j = r.json()
        if j.get("code") != 0:
            raise UploadError(f"发布失败 add/v3: {j.get('code')} {j.get('message')}")
        return j["data"]["aid"], j["data"]["bvid"]
