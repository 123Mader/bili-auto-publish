#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/bili" "$ROOT/tests" "$ROOT/tools" "$ROOT/logs" \
         "$ROOT/ready" "$ROOT/done" "$ROOT/music_cache"
python3 -m pip install -q bilitool || echo "WARN: bilitool 安装失败，回退自研 Uploader（见 Task 5 说明）"
if [ ! -f "$ROOT/config.json" ]; then
  cat > "$ROOT/config.json" <<'EOF'
{
  "publish_time": "20:00",
  "interval": 300,
  "publish_dir": "/storage/emulated/0/DCIM/bili_publish",
  "ready_dir": "ready",
  "done_dir": "done",
  "cookie_file": "cookie.json",
  "state_file": "state.json",
  "log_file": "logs/daemon.log",
  "music_dir": "music_cache",
  "copyright": 1,
  "tid": 169
}
EOF
fi
echo "ready. 先运行 python tools/login_scan.py 登录 B站。"
