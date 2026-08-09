"""B站官方版权曲库配乐：素材库枚举 + 详情直链下载；缓存优先，失败降级 None。"""

import os, json, time
from concurrent.futures import ThreadPoolExecutor

_MUSIC_LIST_URL = "https://cool.bilibili.com/x/co-create/music/list"
_MUSIC_DETAIL_URL = "https://cool.bilibili.com/x/co-create/music/detail"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
_REFERER = "https://member.bilibili.com/"
_CATALOG_TTL = 86400
_MAX_PN = 200

def _headers():
    return {"User-Agent": _UA, "Referer": _REFERER}

def _get(url, params, timeout=15):
    import requests
    r = requests.get(url, params=params, headers=_headers(), timeout=timeout)
    r.raise_for_status()
    j = r.json()
    if j.get("code") != 0:
        raise RuntimeError(f"bili code {j.get('code')}: {j.get('message')}")
    return j.get("data") or {}

def _fetch_catalog():
    """枚举官方素材库全部曲目（ps 恒 1，逐 pn 拉取）。返回 [{sid,title,duration,used_count}]。"""
    first = _get(_MUSIC_LIST_URL, {"pn": 1})
    total = int((first.get("pager") or {}).get("total") or 0)
    if total <= 0:
        return []
    def one(pn):
        d = _get(_MUSIC_LIST_URL, {"pn": pn})
        return [{"sid": t["sid"], "title": t.get("title", ""),
                 "duration": t.get("duration") or 0,
                 "used_count": t.get("used_count") or 0}
                for t in (d.get("list") or [])]
    with ThreadPoolExecutor(max_workers=8) as ex:
        batches = list(ex.map(one, range(1, min(total, _MAX_PN) + 1)))
    return [t for b in batches for t in b]

def _catalog_path(cfg):
    md = cfg.get("music_dir")
    return os.path.join(md, "catalog.json") if md else None

def _load_catalog(cfg):
    """目录缓存（24h）优先，否则在线枚举并写缓存；在线失败抛异常。"""
    p = _catalog_path(cfg)
    if p and os.path.isfile(p):
        try:
            with open(p) as f:
                j = json.load(f)
            if time.time() - j.get("fetched_at", 0) < _CATALOG_TTL and j.get("tracks"):
                return j["tracks"]
        except (OSError, json.JSONDecodeError):
            pass
    tracks = _fetch_catalog()
    if p:
        try:
            with open(p, "w") as f:
                json.dump({"fetched_at": time.time(), "tracks": tracks}, f)
        except OSError:
            pass
    return tracks

def _select_track(cfg):
    """从曲库轮换取一首（标题数字递增 → 自然轮换）。"""
    tracks = _load_catalog(cfg)
    if not tracks:
        return None
    num = cfg.get("num")
    if num is None:
        return tracks[0]
    return tracks[num % len(tracks)]

def _cache_path(cfg):
    if not cfg.get("music_dir") or not cfg.get("num"):
        return None
    p = os.path.join(cfg["music_dir"], f"{cfg['num']}.m4a")
    return p if os.path.isfile(p) else None

def pick_music(cfg):
    """返回本机音频路径（缓存优先，否则官方素材库选曲下载）或 None（降级原声直发）。"""
    cached = _cache_path(cfg)
    if cached:
        return cached
    try:
        track = _select_track(cfg)
        if not track:
            return None
        detail = _get(_MUSIC_DETAIL_URL, {"sid": track["sid"]})
        url = (detail or {}).get("play_url")
        if not url:
            return None
        audio = os.path.join(cfg["music_dir"], f"{cfg['num']}.m4a")
        _download(url, audio)
        return audio if os.path.isfile(audio) else None
    except Exception:
        return None

def _download(url, dest):
    """下载音频到 dest；失败抛异常（pick_music 已兜底）。"""
    import requests
    r = requests.get(url, headers=_headers(), timeout=30)
    r.raise_for_status()
    with open(dest, "wb") as f:
        f.write(r.content)
