"""ffmpeg 制作：转码压缩 + 可选BGM(25%) + 封面叠数字标题。"""

import os, subprocess

class MakerError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg

def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise MakerError(f"ffmpeg failed: {r.stderr[-500:]}")

def probe_video(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1", path],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise MakerError(f"probe failed: {r.stderr.strip()}")
    return float(r.stdout.split("=")[1])

def _pick_cover_frame(src, tmpdir):
    """取中间 1/3 区间抽帧（简化）：取全片中间位置。"""
    dur = probe_video(src)
    ts = dur * 2 / 3
    mid = os.path.join(tmpdir, "mid.png")
    _run(["ffmpeg", "-y", "-ss", str(ts), "-i", src, "-frames:v", "1", mid])
    return mid

def produce(job, cfg, music_path=None, log=print):
    num = job["num"]
    src = job["path"]
    if not os.path.isfile(src):
        raise MakerError(f"源不存在: {src}")
    ready_dir = cfg["ready_dir"]
    os.makedirs(ready_dir, exist_ok=True)
    tmp = cfg.get("tmp_dir") or os.path.join(ready_dir, ".tmp")
    os.makedirs(tmp, exist_ok=True)
    base = os.path.join(ready_dir, str(num))
    muted = os.path.join(tmp, f"{num}.muted.mp4")
    # 1) 转码（预估 >50MB 自动降 crf——先固定 crf 23）
    _run(["ffmpeg", "-y", "-i", src, "-c:v", "libx264", "-crf", "23",
          "-preset", "medium", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", muted])
    # 2) 配乐（若提供且校验可读）
    final_src = muted
    if music_path and os.path.isfile(music_path):
        mixed = os.path.join(tmp, f"{num}.mixed.mp4")
        _run(["ffmpeg", "-y", "-i", muted, "-i", music_path, "-filter_complex",
              "[1:a]volume=0.25[b];[0:a][b]amix=inputs=2:duration=first:dropout_transition=2[a]",
              "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", mixed])
        final_src = mixed
    out_mp4 = base + ".mp4"
    _run(["ffmpeg", "-y", "-i", final_src, "-c", "copy", "-movflags", "+faststart", out_mp4])
    # 3) 封面：取中帧 + drawtext 数字
    frame = _pick_cover_frame(src, tmp)
    out_cover = base + ".jpg"
    _run(["ffmpeg", "-y", "-i", frame, "-vf", f"drawtext=text='{num}':fontsize=120:fontcolor=white:borderw=4:bordercolor=black:x=(w-text_w)/2:y=(h-text_h)/2",
          "-frames:v", "1", "-q:v", "2", out_cover])
    return {"ready_mp4": out_mp4, "ready_cover": out_cover}

def _pick_music(music_dir, num):
    """从 music_dir 随机挑一个 mp3（Task 4 集成后改为官方曲库结果）。"""
    import random
    candidates = [f for f in os.listdir(music_dir) if f.endswith(".mp3")]
    if not candidates:
        return None
    return os.path.join(music_dir, random.choice(candidates))
