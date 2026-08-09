# B站本地自动发布（合规版）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 纯本地守护脚本：扫投放目录的数字命名视频 → B站官方曲库配乐 → ffmpeg 制作 → 每晚 20:00 经 B站官方投稿接口发布（原创标注，全合规）。

**Architecture:** `bili_daemon.py` 常驻（300s 循环）驱动状态机 `waiting→producing→ready→uploaded→done`，failed 重试 3 次。组件：Scanner（扫描投放目录）、Maker（ffmpeg 制作）、MusicPicker（B站官方曲库）、Uploader（官方投稿 API）、Scheduler（20:00 触发）。

**Tech Stack:** Python 3.14（Termux，unittest 无 pytest）、ffmpeg 8.1.2、requests 2.34.2、B站官方 Web 投稿接口。

## Global Constraints

- 投放目录：`/storage/emulated/0/DCIM/bili_publish/`（守护自动创建）
- 文件名：纯数字 + 扩展名（`12.mp4` 等），该数字即 B站标题
- 配乐：**只用 B站官方版权曲库**；失败则原声直发，绝不使用第三方音源
- 投稿：`copyright=1`（原创），标题=数字，简介固定合规文案（含「自制原创」声明）
- 定时：20:00±2min 发布，本地到点提交
- 环境：Termux，`python3 -m unittest`（无 pytest）；`JAVA_TOOL_OPTIONS` 无关
- 状态机持久化 `state.json`；日志 `logs/daemon.log`；重启不重发
- 失败重试：单任务最多 3 次，永久失败仅记日志
- 测试可调发布时间（config `publish_time`，测试=当前+2min）

---

### Task 1: 项目骨架 + config.py + state.py（状态机持久化）

**Files:**
- Create: `bili/__init__.py`（空包标记）
- Create: `bili/config.py`
- Create: `bili/state.py`
- Test: `tests/test_state.py`（tests 目录同时创建）

**Interfaces:**
- Consumes: 无
- Produces:
  - `bili/config.py::load_config(path) -> dict`（读 JSON，缺失键补默认值）
  - `bili/state.py::StateStore(path)` — 类；方法 `get(job_id) -> dict|None`、`set(job_id, fields: dict)`、`load_jobs() -> list[dict]`、`init_job(job_id) -> dict`
  - 状态常量：`bili/state.py::STATUS_PENDING="pending"`、`STATUS_PRODUCING="producing"`、`STATUS_READY="ready"`、`STATUS_UPLOADED="uploaded"`、`STATUS_DONE="done"`、`STATUS_FAILED="failed"`、`MAX_RETRIES=3`
  - Job 字段字典：`{"job_id":"12","status":...,"retries":0,"created":...,"ready_mp4":...,"ready_cover":...}`（job_id = 数字字符串如 `"12"`）

- [ ] **Step 1: 初始化项目与 package**

```bash
mkdir -p /data/data/com.termux/files/usr/tmp/opencode/bili/bili /data/data/com.termux/files/usr/tmp/opencode/bili/tests /data/data/com.termux/files/usr/tmp/opencode/bili/tools
touch /data/data/com.termux/files/usr/tmp/opencode/bili/bili/__init__.py /data/data/com.termux/files/usr/tmp/opencode/bili/tests/__init__.py
cd /data/data/com.termux/files/usr/tmp/opencode/bili
```

- [ ] **Step 2: 写失败测试**

`tests/test_state.py`：

```python
import os, tempfile, unittest
from bili.state import StateStore, STATUS_PENDING, STATUS_READY, STATUS_DONE

class TestStateStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self.dir.name, "state.json"))

    def test_empty(self):
        self.assertEqual(self.store.load_jobs(), [])

    def test_set_and_get(self):
        self.store.set("1", {"job_id": "1", "status": STATUS_READY})
        self.assertEqual(self.store.get("1")["status"], STATUS_READY)
        self.assertIsNone(self.store.get("nope"))

    def test_init_new_status(self):
        self.store.init_job("5")
        j = self.store.get("5")
        self.assertEqual(j["status"], STATUS_PENDING)
        self.assertEqual(j["retries"], 0)
        self.assertEqual(j["job_id"], "5")

    def test_persists_across_instances(self):
        self.store.init_job("7")
        s2 = StateStore(os.path.join(self.dir.name, "state.json"))
        self.assertEqual(s2.get("7")["status"], STATUS_PENDING)

    def test_mark_done(self):
        self.store.init_job("7")
        self.store.set("7", {"status": STATUS_DONE})
        self.assertEqual(self.store.get("7")["status"], STATUS_DONE)
```

- [ ] **Step 3: 运行确认失败**

Run: `python3 -m unittest tests.test_state -v`（否则先 `cd /data/data/com.termux/files/usr/tmp/opencode/bili`）
Expected: FAIL（ImportError: bili.state）

- [ ] **Step 4: 实现 state.py + config.py**

`bili/state.py`：

```python
import json, os, time

STATUS_PENDING = "pending"
STATUS_PRODUCING = "producing"
STATUS_READY = "ready"
STATUS_UPLOADED = "uploaded"
STATUS_DONE = "done"
STATUS_FAILED = "failed"
MAX_RETRIES = 3

class StateStore:
    def __init__(self, path):
        self.path = path
        self._jobs = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    self._jobs = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._jobs = {}

    def _save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._jobs, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.path)

    def init_job(self, job_id):
        self._jobs[job_id] = {"job_id": job_id, "status": STATUS_PENDING,
                              "retries": 0, "created": time.time()}
        self._save()
        return self._jobs[job_id]

    def get(self, job_id):
        return self._jobs.get(job_id)

    def set(self, job_id, fields):
        if job_id not in self._jobs:
            self._jobs[job_id] = {"job_id": job_id}
        self._jobs[job_id].update(fields)
        self._save()

    def load_jobs(self):
        return list(self._jobs.values())

    def remove(self, job_id):
        self._jobs.pop(job_id, None)
        self._save()
```

`bili/config.py`：

```python
import json, os

DEFAULT_CONFIG = {
    "publish_time": "20:00",
    "scan_interval": 300,
    "max_retries": 3,
    "publish_dir": "/storage/emulated/0/DCIM/bili_publish",
    "ready_dir": "ready",
    "done_dir": "done",
    "cookie_file": "cookie.json",
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
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python3 -m unittest tests.test_state -v`
Expected: 6 tests，全 PASS

- [ ] **Step 6: Commit**

```bash
git add bili tests
git commit -m "feat: 状态机持久化与配置骨架"
```

---

### Task 2: Scanner — 扫描投放目录

**Files:**
- Create: `bili/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: 无
- Produces: `bili/scanner.py::scan_publish_dir(publish_dir) -> list[dict]`，每个元素 `{"filename":"12.mp4","num":12,"path":"/abs/12.mp4"}`
  - 仅匹配 `^\d+\.(mp4|mov|avi|m4v)$`（忽略大小写）；忽略隐藏文件与 `*.part`

- [ ] **Step 1: 写失败测试**

`tests/test_scanner.py`：

```python
import os, tempfile, unittest
from bili.scanner import scan_publish_dir

class TestScanner(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.dir.name, "sub"))

    def test_empty_dir(self):
        self.assertEqual(scan_publish_dir(self.dir.name), [])

    def test_digit_files_only(self):
        p = os.path.join(self.dir.name, "12.mp4"); open(p, "w").close()
        open(os.path.join(self.dir.name, "dog.mp4"), "w").close()
        open(os.path.join(self.dir.name, "abc.mp4"), "w").close()
        open(os.path.join(self.dir.name, "12.part"), "w").close()
        open(os.path.join(self.dir.name, "12.mp"), "w").close()
        res = scan_publish_dir(self.dir.name)
        self.assertEqual([r["num"] for r in res], [12])
        self.assertEqual(res[0]["path"], p)

    def test_sorted_ascending(self):
        for n in (9, 3, 12):
            open(os.path.join(self.dir.name, f"{n}.mp4"), "w").close()
        self.assertEqual([r["num"] for r in scan_publish_dir(self.dir.name)], [3, 9, 12])

    def test_uppercase_ext(self):
        open(os.path.join(self.dir.name, "5.MP4"), "w").close()
        self.assertEqual([r["num"] for r in scan_publish_dir(self.dir.name)], [5])

    def test_ignores_subdirs(self):
        open(os.path.join(self.dir.name, "sub", "1.mp4"), "w").close()
        self.assertEqual(scan_publish_dir(self.dir.name), [])
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m unittest tests.test_scanner -v` → FAIL（ModuleNotFoundError: bili.scanner）

- [ ] **Step 3: 实现 scanner.py**

`bili/scanner.py`：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m unittest tests.test_scanner -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bili/scanner.py tests/test_scanner.py
git commit -m "feat: 投放目录扫描器"
```

---

### Task 3: Maker — ffmpeg 制作（转码+配乐+封面）

**Files:**
- Create: `bili/maker.py`
- Test: `tests/test_maker.py`

**Interfaces:**
- Consumes: scanner 任务输出的 `{"num","path"}` 字典
- Produces: `bili/maker.py::produce(job, cfg) -> dict` — 成功返回 `{"status":"ready","ready_mp4":...,"ready_cover":...}`；失败 raise `MakerError(msg)`（调用方据此置 failed）
- Produces: `bili/maker.py::MUSIC_SEARCH_FN` — 后接 Task 5，此任务先接 `None`（无配乐）

- [ ] **Step 1: 写失败测试**

`tests/test_maker.py`（测试只验证真实 ffmpeg 跑一个 1 秒测试源）：

```python
import os, subprocess, tempfile, unittest
from bili.maker import produce, MakerError

class TestMaker(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.dir.name, "12.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-shortest", self.src], check=True, capture_output=True)

    def test_produce_creates_output(self):
        cfg = {"ready_dir": os.path.join(self.dir.name, "ready"),
               "publish_dir": os.path.join(self.dir.name, "pub"),
               "music_dir": None}
        out = produce(job={"num": 5, "path": self.src}, cfg=cfg)
        self.assertTrue(os.path.exists(out["ready_mp4"]))
        self.assertTrue(os.path.exists(out["ready_cover"]))

    def test_missing_source_raises(self):
        cfg = {"ready_dir": os.path.join(self.dir.name, "ready"), "publish_dir": self.dir}
        with self.assertRaises(MakerError):
            produce(job={"num": 5, "path": "/nonexistent.mp4"}, cfg=cfg)
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m unittest tests.test_maker -v`
Expected: FAIL（ModuleNotFound）

- [ ] **Step 3: 实现 maker.py**

`bili/maker.py`（注意：无配乐时才 `-an`；配乐为可选参数 `music_path`）：

```python
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
```

（注意：本计划代码块为可执行 Python，实现时以最小通过测试为准，遇到笔误以测试结果修正。）

- [ ] **Step 4: 修正语法并运行测试**

Run: `python3 -m unittest tests.test_maker -v`
Expected: 2 tests PASS（真实 ffmpeg 产出 mp4+jpg；源缺失抛 MakerError）

- [ ] **Step 5: Commit**

```bash
git add bili/maker.py tests/test_maker.py
git commit -m "feat: ffmpeg 制作流水线（转码/配乐/封面）"
```

---

### Task 4: 配乐源 — 接 B站官方曲库（无则降级）

**Files:**
- Create: `bili/music.py`
- Test: `tests/test_music.py`

**Interfaces:**
- Consumes: 无
- Produces: `bili/music.py::pick_music(cfg) -> str|None` — 返回 mp3 本地路径或 `None`（降级原声）
  - `bili/music.py::search_official(query) -> list[dict]` —— 调 B站官方曲库接口，每项 `{"title","url"}`

- [ ] **Step 1: 写失败测试（先测降级逻辑）**

`tests/test_music.py`：

```python
import os, tempfile, unittest
from unittest import mock
from bili.music import pick_music

class TestMusic(unittest.TestCase):
    def test_no_music_dir_returns_none(self):
        self.assertIsNone(pick_music({"music_dir": None}))

    def test_search_failure_falls_back_none(self):
        cfg = {"music_dir": "/tmp/x", "num": 1}
        with mock.patch("bili.music._official_search", side_effect=Exception("net")):
            self.assertIsNone(pick_music(cfg))

    def test_cache_hit_no_network(self):
        d = tempfile.TemporaryDirectory()
        p = os.path.join(d.name, "12.mp3"); open(p, "w").close()
        cfg = {"music_dir": d.name, "num": 12}
        with mock.patch("bili.music._official_search") as ms:
            res = pick_music(cfg)
            self.assertEqual(os.path.basename(res), "12.mp3")
            ms.assert_not_called()
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m unittest tests.test_music -v`
Expected: FAIL（ModuleNotFound / pick_music 不存在）

- [ ] **Step 3: 实现 music.py**

`bili/music.py`（B站官方曲库接口在实现时以「接口以实测为准」：先封装为可 mock 的 `_official_search`，实现降级逻辑 + 缓存；真正联网实现 Task 5 附联调）：

```python
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
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m unittest tests.test_music -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bili/music.py tests/test_music.py
git commit -m "feat: 曲库选择与降级逻辑（真实官方接口待Task8）"
```

---

### Task 5: B站官方投稿接口客户端（Uploader）

**Files:**
- Create: `bili/uploader.py`
- Create: `tools/login_scan.py`（扫码登录工具，Task 8 实现完整）
- Test: `tests/test_uploader.py`（纯 mock；真实联调在测试计划第 3 步手动执行）

**Interfaces:**
- Consumes: Job `{"ready_mp4","ready_cover","num"}`
- Produces: `bili/uploader.py::Uploader` 类：
  - `Uploader(cfg, session=None)` — 构造时校验 cookie 文件与 csrf；缺 cookie 抛 `LoginRequiredError`
  - `upload(job) -> bvid` — 完整流程：`create → upload → cover → submit`；失败抛 `UploadError`（Task 8 实现）
- 关键常量：`_CSRF_RE = re.compile(r"bili_jct=([^;]+)")`

- [ ] **Step 1: 写失败测试（纯函数，可离线）**

`tests/test_uploader.py`：

```python
import os, tempfile, unittest
from bili.uploader import Uploader, LoginRequiredError, build_title, build_desc, _extract_csrf

class TestUploaderPure(unittest.TestCase):
    def test_build_title(self):
        self.assertEqual(build_title(12), "12")

    def test_build_desc(self):
        self.assertIn("自制", build_desc(12))
        self.assertIn("#汪星人", build_desc(12))

    def test_extract_csrf(self):
        self.assertEqual(_extract_csrf("a=1; bili_jct=tok; b=2"), "tok")
        self.assertIsNone(_extract_csrf("no token here"))

    def test_no_cookie_raises_login_required(self):
        d = tempfile.TemporaryDirectory()
        cfg = {"cookie_file": os.path.join(d.name, "nope.json")}
        with self.assertRaises(LoginRequiredError):
            Uploader(cfg)

    def test_cookie_without_csrf_raises(self):
        d = tempfile.TemporaryDirectory()
        p = os.path.join(d.name, "c.json")
        with open(p, "w") as f:
            f.write("SESSDATA=abc")
        with self.assertRaises(LoginRequiredError):
            Uploader({"cookie_file": p})
```

（上传链路属网络密集型，真实联调放在 Task 8：用真实文件试传并删除草稿。）

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m unittest tests.test_uploader -v`
Expected: FAIL（ModuleNotFoundError: bili.uploader）

- [ ] **Step 3: 实现 uploader.py 纯函数 + 骨架**

`bili/uploader.py`：

```python
"""B站官方投稿接口客户端（Web VU 接口，合规：原创标注）。"""

import os, re

_CSRF_RE = re.compile(r"bili_jct=([^;]+)")

class UploadError(Exception):
    pass

class LoginRequiredError(UploadError):
    pass

def _extract_csrf(cookie_str):
    m = _CSRF_RE.search(cookie_str or "")
    return m.group(1) if m else None

def build_title(num):
    return str(num)

DESC = "自制原创狗狗日常视频，配乐使用B站官方授权音乐素材。 #狗狗日常 #汪星人 #萌宠"

def build_desc(num):
    return DESC

class Uploader:
    def __init__(self, cfg, session=None):
        self.cfg = cfg
        self.cookie_file = cfg["cookie_file"]
        if not os.path.isfile(self.cookie_file):
            raise LoginRequiredError("未登录：先运行 python tools/login_scan.py")
        self.cookie = open(self.cookie_file).read().strip()
        token = _extract_csrf(self.cookie)
        if not token:
            raise LoginRequiredError("cookie 无法提取 csrf")
        if session is None:
            import requests
            session = requests.Session()
        self.session = session

    def upload(self, job):
        raise NotImplementedError("Task 8 联调实现：create → upload → cover → submit")
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python3 -m unittest tests.test_uploader -v`
Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bili/uploader.py tests/test_uploader.py
git commit -m "feat: 官方投稿客户端骨架与纯函数"
```

---

### Task 6: Scheduler — 20:00 定时逻辑

**Files:**
- Create: `bili/scheduler.py`
- Test: `tests/test_scheduler.py`

**Interfaces:**
- Consumes: StateStore、Scanner 结果
- Produces: `bili/scheduler.py::Scheduler(cfg, store, maker, uploader)`；方法 `tick(now=None) -> list[str]`（执行一轮，返回动作描述）；`should_publish(now, created_time) -> bool`（20:00±2min）

- [ ] **Step 1: 写失败测试**

`tests/test_scheduler.py`：

```python
import datetime, os, tempfile, unittest
from bili.scheduler import Scheduler, should_publish
from bili.state import StateStore

class TestSched(unittest.TestCase):
    def t(self, h, m):
        return datetime.datetime(2026, 8, 9, h, m)

    def test_should_publish_window(self):
        self.assertTrue(should_publish(self.t(20, 1), created=1))
        self.assertFalse(should_publish(self.t(19, 59), created=1))
        self.assertFalse(should_publish(self.t(20, 5), created=1))

    def test_tick_no_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(os.path.join(d, "s.json"))
            s = Scheduler(cfg={"publish_dir": d}, store=store)
            self.assertEqual(s.tick(now=self.t(20, 0))["started"], 0)

    def test_tick_starts_new_jobs(self):
        with tempfile.TemporaryDirectory() as d:
            pub = os.path.join(d, "pub"); os.makedirs(pub)
            open(os.path.join(pub, "3.mp4"), "w").close()
            store = StateStore(os.path.join(d, "s.json"))
            s = Scheduler(cfg={"publish_dir": pub, "ready_dir": os.path.join(d, "ready")}, store=store)
            s.maker = lambda job, cfg: {"ready_mp4": d + "/r.mp4", "ready_cover": d + "/r.jpg"}
            ret = s.tick(now=self.t(10, 0))
            self.assertEqual(ret["started"], 1)
            self.assertEqual(store.get("3")["status"], "ready")

    def test_tick_publishes_at_window(self):
        with tempfile.TemporaryDirectory() as d:
            pub = os.path.join(d, "pub"); os.makedirs(pub)
            done = os.path.join(d, "done")
            open(os.path.join(pub, "3.mp4"), "w").close()
            store = StateStore(os.path.join(d, "s.json"))
            store.init_job("3")
            store.set("3", {"status": "ready", "ready_mp4": d + "/r.mp4"})
            s = Scheduler(cfg={"publish_dir": pub, "done_dir": done}, store=store)
            s.uploader = lambda job: "BV-test"
            ret = s.tick(now=self.t(20, 1))
            self.assertEqual(ret["published"], 1)
            self.assertEqual(store.get("3")["status"], "done")
            self.assertFalse(os.path.exists(os.path.join(pub, "3.mp4")))
            self.assertTrue(os.path.exists(os.path.join(done, "3.mp4")))
```

- [ ] **Step 2: 运行确认失败**

Run: `python3 -m unittest tests.test_scheduler -v`  → FAIL（模块缺失）

- [ ] **Step 3: 实现 scheduler.py**

`bili/scheduler.py`：

```python
"""调度：每 tick 处理一轮状态机推进。"""
import datetime, os, shutil
from bili import scanner
from bili import maker
from bili.state import (
    STATUS_PENDING, STATUS_PRODUCING, STATUS_READY,
    STATUS_UPLOADED, STATUS_DONE, STATUS_FAILED,
)

def should_publish(now, created_ts):
    return now.hour == 20 and 0 <= now.minute <= 2

class Scheduler:
    def __init__(self, cfg, store):
        self.cfg = cfg
        self.store = store
        self.maker = maker.produce   # 可替换 mock
        self.uploader = None         # Task 7 注入

    def tick(self, now=None):
        now = now or datetime.datetime.now()
        result = {"started": 0, "published": 0, "failed": 0}
        # ① 扫描新文件 → 建 pending job
        for f in scanner.scan_publish_dir(self.cfg["publish_dir"]):
            if not self.store.get(str(f["num"])):
                self.store.init_job(str(f["num"]))
                result["started"] += 1
        # ② 推进 pending → ready；ready/failed → uploaded（20:00±2）
        for j in self.store.load_jobs():
            jid = j["job_id"]
            if j["status"] == STATUS_PENDING:
                try:
                    out = self.maker(job=scanner_lookup(self.cfg["publish_dir"], jid),
                                     cfg=self.cfg)
                    self.store.set(jid, {"status": STATUS_READY,
                                          "ready_mp4": out["ready_mp4"],
                                          "ready_cover": out.get("ready_cover", "")})
                except Exception as e:
                    self._fail(j, str(e))
            elif j["status"] in (STATUS_READY, STATUS_FAILED) and should_publish(now, j.get("created", 0)):
                if self.uploader:
                    try:
                        self.uploader(j)
                        self.store.set(jid, {"status": STATUS_DONE})
                        self._archive_source(jid)
                        result["published"] += 1
                    except Exception as e:
                        self._fail(j, str(e))
        return result

    def _archive_source(self, jid):
        """上传成功后把投放目录源文件移入 done_dir。"""
        done_dir = self.cfg.get("done_dir")
        src = os.path.join(self.cfg["publish_dir"], f"{jid}.mp4")
        if done_dir and os.path.isfile(src):
            os.makedirs(done_dir, exist_ok=True)
            shutil.move(src, os.path.join(done_dir, f"{jid}.mp4"))

    def _fail(self, j, err):
        retries = j.get("retries", 0) + 1
        self.store.set(j["job_id"], {"status": STATUS_FAILED, "retries": retries, "error": err})

def scanner_lookup(publish_dir, jid):
    """按 job_id（数字字符串）从扫描结果找回 job 字典。"""
    for f in scanner.scan_publish_dir(publish_dir):
        if str(f["num"]) == jid:
            return {"num": f["num"], "path": f["path"]}
    raise FileNotFoundError(f"源文件不存在: {jid}")
```

- [ ] **Step 4: 运行确认通过**

Run: `python3 -m unittest tests.test_scheduler -v`
Expected: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bili/scheduler.py tests/test_scheduler.py
git commit -m "feat: 20:00 定时调度状态机推进"
```

---

### Task 7: Daemon 主循环 + 架构收拢

**Files:**
- Create: `bili/daemon.py`（入口）
- Create: `setup.sh`（入口脚本：装机依赖/首次扫码）
- Test: `tests/test_daemon.py`

**Interfaces:**
- Consumes: Scheduler、Uploader、StateStore、config
- Produces: CLI：`python3 bili/daemon.py --config config.json`；常驻循环 `interval` 秒；SIGTERM 干净退出

- [ ] **Step 1: 写失败测试（守护循环时间敏感——测「一次 tick 不因异常崩溃」）**

`tests/test_daemon.py`：

```python
import unittest
from unittest import mock

class TestDaemon(unittest.TestCase):
    def test_scheduler_exception_does_not_kill_loop(self):
        sched = mock.Mock()
        sched.tick.side_effect = RuntimeError("boom")
        from bili.daemon import run_once
        run_once(sched)   # 不抛异常即通过
```

- [ ] **Step 2: 实现 daemon.py**

`bili/daemon.py`：

```python
import json, logging, os, signal, sys, time

def setup_logging(logfile):
    os.makedirs(os.path.dirname(logfile), exist_ok=True)
    logging.basicConfig(filename=logfile, level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")

def run_once(sched):
    try:
        return sched.tick()
    except Exception as e:
        logging.exception("tick failed")

def main(argv=None):
        import argparse
        p = argparse.ArgumentParser()
        p.add_argument("--config", default=os.path.join(os.path.dirname(__file__), "config.json"))
        args = p.parse_args(argv)
        cfg = json.load(open(args.config))
        logfile = cfg.get("log_file", "logs/daemon.log")
        setup_logging(logfile)
        ready_dir = cfg["ready_dir"]; os.makedirs(ready_dir, exist_ok=True)
        from bili.scheduler import Scheduler
        from bili.state import StateStore
        store = StateStore(cfg.get("state_file", "state.json"))
        sched = Scheduler(cfg, store)
        stopping = False
        def on_sig(s, f):
            nonlocal stopping; stopping = True
        signal.signal(signal.SIGTERM, on_sig)
        signal.signal(signal.SIGINT, on_sig)
        while not stopping:
            logging.info("tick")
            run_once(sched)
            time.sleep(cfg.get("interval", 300))

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: 运行测试**

Run: `python3 -m unittest tests.test_daemon -v` → PASS

- [ ] **Step 4: 创建 setup.sh（装机：建目录 + 拷贝示例配置）**

`setup.sh`：

```bash
#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$ROOT/bili" "$ROOT/tests" "$ROOT/tools" "$ROOT/logs" \
         "$ROOT/ready" "$ROOT/done" "$ROOT/music_cache"
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
```

- [ ] **Step 4: 手工冒烟：构造最小 config + 开跑 1 分钟，观察日志循环**

```bash
python3 -c "import json;json.dump({'publish_time':'19:59','interval':2,'publish_dir':'.smoke','ready_dir':'.smoke/ready','state_file':'.smoke/state.json','log_file':'.smoke/daemon.log'},open('smoke.json','w'))"
timeout 6 python3 bili/daemon.py --config smoke.json ; cat .smoke/daemon.log
```

Expected: 日志 2-3 行 tick 记录，无 traceback

- [ ] **Step 6: Commit**

```bash
git add bili/daemon.py tests/test_daemon.py setup.sh smoke.json 2>/dev/null || git add bili/daemon.py tests/test_daemon.py setup.sh
git commit -m "feat: 常驻守护入口与安装脚本"
```

---

### Task 8: 端到端联调（真实账号）

**Files:**
- Create: `tools/login_scan.py`
- Create: `tools/verify_env.sh`

**说明：本任务为手工联调，需要：
用户扫码登录（个人B站号）→ 曲库搜索 → 制作 → 私密投稿 → 校验 → 删除草稿。**

- [ ] **Step 1: 扫码登录脚本**

`tools/login_scan.py`（调 passport 二维码接口 → 等待扫码 → 存 cookie）：

```python
"""扫码登录 B站，将 cookie 写入 cfg cookie_file。"""
import os, sys, time, requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bili import config

cfg = config.load_config(sys.argv[1] if len(sys.argv) > 1 else "config.json")
s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0"})
r = s.get("https://passport.bilibili.com/x/passport-login/qrcode/generate").json()
key = r["data"]["qrcode_key"]
print("请用手机 BiliBili App 扫码以下链接：")
print("  https://passport.bilibili.com/qrcode/qrcode-check?qrcode_key=" + key)
while True:
    resp = s.post("https://passport.bilibili.com/x/passport-login/qrcode/poll",
                  data={"qrcode_key": key}).json()
    data = resp.get("data", {})
    if data.get("code") == 0:
        cookie = "; ".join(f"{k}={v}" for k, v in s.cookies.get_dict().items())
        open(cfg["cookie_file"], "w").write(cookie)
        print("登录成功，cookie 已保存")
        break
    elif data.get("code") in (86038, 86090):
        print("二维码已失效，请重跑")
        sys.exit(1)
    time.sleep(2)
```

- [ ] **Step 2: 确认 cookie 有效**

```bash
python3 -c "
import requests
ck=open('cookie.json').read(); h={'Cookie':ck,'User-Agent':'Mozilla/5.0'}
r=requests.get('https://api.bilibili.com/x/web-interface/nav',headers=h).json()
print('登录状态:', r['code'], r.get('data',{}).get('uname'))
"
```

Expected: code 0 + 用户名

- [ ] **Step 3: 官方曲库搜索验证**

手动执行 B站「创作中心→我的素材→音频素材」搜索「萌宠」，确认真实接口与响应格式；把结果固化为 `bili/music.py::_official_search` 的真实实现（替换 Task 4 占位），覆盖测试：`test_music.py` 保持不崩。

- [ ] **Step 4: 制作一个真实视频端到端**

```bash
cp /storage/emulated/0/DCIM/某狗狗视频 /tmp/bili_e2e.mp4
python3 - <<'PY'
import json
cfg = json.load(open('config.json'))
job = {"num": 9999, "path": "/tmp/bili_e2e.mp4"}
from bili import maker
print(maker.produce(job, cfg))
PY
```

Expected: 输出 ready/9999.mp4 + 9999.jpg

- [ ] **Step 5: 私密投稿验证（账号真实性验证）**

用 Task 5 的 Uploader 上传一份私密稿件（不公开），确认 UUID→上传→封面→submit 全流程返回 edit_now；然后到 B站后台删除草稿。**此步必须真实账号完成一次**，确认 copyright=1（原创）。

- [ ] **Step 6: 定时发布验证**

把 `config.json` 的 `publish_time` 改为当前时间+2min，放入一个测试视频 → 等待守护到点上传 → B站后台确认定时稿件存在且（不公开测试可选）。

- [ ] **Step 7: 上线**

```bash
python3 setup.sh          # 装机：目录、扫码登录
setsid nohup python3 bili/daemon.py --config config.json >> logs/daemon.out 2>&1 &
echo started
```

Expected: 守护常驻，日志增长，`ps aux | grep daemon` 可见。

- [ ] **Step 8: 收尾 commit**

```bash
git add tools/ bili/music.py bili/uploader.py bili/daemon.py docs/
git commit -m "feat: 端到端联调补充（真实曲库/上传实现）"
```

---

## 风险与假设（实现中确认）

1. **B站官方接口细节**：Task 5/8 的 VU 接口端点与曲库接口以实测为准，若发现 B站在维护/反爬，改用公开的官方文档端；若完全不可用则回退方案为「生成 config 提示用户手动投稿」的 readme 应急说明。
2. **ffmpeg drawtext 中文字体**：数字标题无中文字体依赖，直接部署。
3. **`CONFIG` 文件中 `copyright` 默认=1（原创）**；`tid` 需实现时查分区表（动物圈-汪星人通常是 169，实现时用 `https://member.bilibili.com/api/x/entry/part/list` 核对）。
4. Termux 后台常驻依赖 `termux-services` 或 `setsid nohup`；重启手机需手动拉起（可选 termux-boot-autostart）。
5. B站对内容审核：视频为个人狗日常，合法；简介带 # 标签合规。
6. **不纳入设计**：微信通道、第三方音源、biliup-rs——已废弃。