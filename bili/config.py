import json, os

DEFAULT_CONFIG = {
    "publish_time": "20:00",
    "scan_interval": 300,
    "max_retries": 3,
    "publish_dir": "/storage/emulated/0/DCIM/bili_publish",
    "ready_dir": "ready",
    "done_dir": "done",
    "cookie_file": "cookie.json",
    "music_dir": "music_cache",
    "copyright": 1,
    "title_template": "{num}",
    "desc": "自制原创 · 狗狗日常 #狗狗日常 #汪星人 #萌宠",
    "tid": 1,
}

def load_config(path):
    try:
        with open(path) as f:
            user = json.load(f)
    except (OSError, json.JSONDecodeError):
        user = {}
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(user)
    return cfg
