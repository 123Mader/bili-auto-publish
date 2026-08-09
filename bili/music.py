"""B站官方版权曲库配乐选择：缓存优先，网络失败降级 None。"""

import os

def _cache_path(cfg):
    if not cfg.get("music_dir"):
        return None
    num = cfg.get("num")
    if not num:
        return None
    p = os.path.join(cfg["music_dir"], f"{num}.mp3")
    return p if os.path.isfile(p) else None

def _official_search(query):
    """占位：由 Task 8 替换为官方接口调用。凡抛出异常均视为不可用。"""
    raise NotImplementedError

def pick_music(cfg):
    """返回本机 mp3 路径（缓存优先，否则在线搜索）或 None（降级无配乐）。"""
    cached = _cache_path(cfg)
    if cached:
        return cached
    try:
        results = _official_search(cfg.get("music_query", "萌宠"))
        if results:
            url = results[0]["url"]
            mp3 = os.path.join(cfg["music_dir"], f"{cfg['num']}.mp3")
            _download(url, mp3)
            return mp3 if os.path.isfile(mp3) else None
    except Exception:
        pass
    return None

def _download(url, dest):
    """下载 mp3 到 dest；失败抛异常（pick_music 已兜底）。"""
    import requests
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
