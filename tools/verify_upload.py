"""Task 8 真实联调：制作 → 真实投稿 → 校验 → 立即删除。

用法: python3 tools/verify_upload.py [标题数字]
默认用 12 号测试视频（ffmpeg 彩条+正弦音）。
"""

import datetime
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
from bilitool.model.model import Model

from bili.maker import produce
from bili.music import pick_music

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
TMP_ROOT = tempfile.mkdtemp(prefix="verify_upload_")


def _headers():
    return {"User-Agent": UA, "Referer": "https://member.bilibili.com/"}


def _cookies():
    cfg = Model().get_config()
    return {k: v for k, v in (cfg.get("cookies") or {}).items() if v}


def make_test_video(workdir, num):
    """生成 5s 彩条+正弦音源视频，走完整制作链（官方曲库配乐）。"""
    pub = os.path.join(workdir, "publish")
    ready = os.path.join(workdir, "ready")
    music = os.path.join(workdir, "music")
    tmp = os.path.join(workdir, "tmp")
    for d in (pub, ready, music, tmp):
        os.makedirs(d, exist_ok=True)
    src = os.path.join(pub, f"{num}.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", "testsrc=duration=5:size=640x360:rate=25",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
         "-c:v", "libx264", "-crf", "28", "-c:a", "aac", "-b:a", "96k", src],
        check=True)
    cfg = {"publish_dir": pub, "ready_dir": ready, "done_dir": ready,
           "music_dir": music, "tmp_dir": tmp,
           "copyright": 1, "tid": 169, "desc": "x"}
    mp = pick_music({**cfg, "num": num})
    print(f"[make] music: {mp or 'none (降级原声)'}")
    out = produce({"num": num, "path": src}, cfg, music_path=mp, log=print)
    print(f"[make] ready: {out['ready_mp4']} / {out['ready_cover']}")
    return out


def upload(job, cfg):
    """bilitool 上传（分片+封面）；返回 (filename, cover_url)。"""
    from bili.uploader import Uploader
    return Uploader().upload(job, cfg)


def get_aid(bvid):
    r = requests.get("https://api.bilibili.com/x/web-interface/view",
                     params={"bvid": bvid}, headers=_headers(), timeout=15)
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"view {j.get('code')}: {j.get('message')}")
    return j["data"]["aid"]


def verify_video(bvid):
    """校验视频信息（标题/原创/分区）。"""
    r = requests.get("https://api.bilibili.com/x/web-interface/view",
                     params={"bvid": bvid}, headers=_headers(), timeout=15)
    j = r.json()
    if j.get("code") != 0:
        return f"view {j.get('code')}: {j.get('message')}"
    d = j["data"]
    return (f"aid={d['aid']} title={d['title']!r} copyright={d['copyright']} "
            f"tid={d['tid']} 状态={d['state']}")


def delete_video(aid, bvid):
    """删除已发布视频（member 接口，CSRF）。"""
    ck = _cookies()
    r = requests.post("https://member.bilibili.com/x/web/archive/delete",
                      headers=_headers(), cookies=ck,
                      data={"aid": aid, "bvid": bvid, "csrf": ck.get("bili_jct", "")},
                      timeout=15)
    j = r.json()
    return j.get("code"), j.get("message")


def main():
    num = int(sys.argv[1]) if len(sys.argv) > 1 else 12
    job = make_test_video(TMP_ROOT, num)
    cfg = {"copyright": 1, "tid": 169}
    job["num"] = num
    print("[upload] 开始上传（分片+封面）…")
    from bili.uploader import Uploader
    try:
        filename, cover_url = Uploader().upload(job, cfg)
    except Exception as e:
        print(f"[FAIL] 上传失败: {e}")
        return 1
    print(f"[upload] filename={filename} cover={cover_url}")
    print("[publish] 发布 add/v3 …")
    try:
        aid, bvid = Uploader().publish(filename, cover_url, num, cfg)
    except Exception as e:
        print(f"[FAIL] 发布失败: {e}")
        return 1
    print(f"[publish] aid={aid} bvid={bvid}")
    time.sleep(3)
    print(f"[verify] {verify_video(bvid)}")
    code, msg = delete_video(aid, bvid)
    print(f"[delete] code={code} msg={msg}")
    if code == 0:
        print(f"[verify-after-delete] {verify_video(bvid)}")
    else:
        print(f"[FAIL] 删除失败（code={code} msg={msg}）")
        print(f"       请手动删除: https://member.bilibili.com 稿件管理 (bvid={bvid})")
        return 1
    print("[OK] 全链路通过")
    return 0


if __name__ == "__main__":
    import time
    sys.exit(main())
