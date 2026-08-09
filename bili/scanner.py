import os, re

_PATTERN = re.compile(r"^(\d+)\.(mp4|mov|avi|m4v)$", re.IGNORECASE)

def scan_publish_dir(publish_dir):
    os.makedirs(publish_dir, exist_ok=True)
    found = []
    for name in sorted(os.listdir(publish_dir)):
        path = os.path.join(publish_dir, name)
        if not os.path.isfile(path):
            continue
        m = _PATTERN.match(name)
        if m:
            found.append({"num": int(m.group(1)), "name": name, "path": path})
    found.sort(key=lambda r: r["num"])
    return found
