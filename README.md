<div align="center">

# 🎬 Bili Auto Publish

**B站视频自动定时发布守护 — auto-publish videos to Bilibili on schedule**

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org)
[![Bilibili](https://img.shields.io/badge/Bilibili-官方接口-pink.svg)](https://www.bilibili.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

*简体中文 | English*

</div>

---

## 🚀 这是什么

扫描本地视频目录 → 官方曲库自动配乐（B站官方素材库，版权合规）→ ffmpeg 制作（转码+封面）→ **到点自动投稿到 B 站**（原创，汪星人分区）。

- ✅ 纯本地运行（Termux / 任意 Linux），无云服务、无第三方音源
- ✅ 全程使用 **B 站官方接口**（投稿、素材库、删除、状态查询）
- ✅ 自研 `web/add/v3` 发布实现（bilitool 的 publish 接口已被 B 站停用，报 code 21590）

## ⚡ 快速开始

### 1️⃣ 安装依赖
```bash
bash setup.sh
```

### 2️⃣ 扫码登录（B 站 TV 协议二维码，无需密码）
```bash
python tools/login_scan.py
```

### 3️⃣ 启动守护（默认每天 20:00 窗口自动发布）
```bash
python bili/daemon.py            # 后台: nohup python bili/daemon.py &
```

把视频放到 `publish_dir`（默认 `/storage/emulated/0/DCIM/bili_publish`），**文件名即发布标题**（如 `20260809.mp4` → 标题「20260809」）。

---

## ⚙️ 配置

`config.json`（模板见 `config.example.json`）：

| 字段 | 默认值 | 说明 |
|---|---|---|
| `publish_time` | `"20:00"` | 发布窗口（该时间 ±2 分钟窗口内自动投递） |
| `interval` | `300` | 轮询间隔（秒） |
| `publish_dir` | `/storage/emulated/0/DCIM/bili_publish` | 待发布视频目录 |
| `ready_dir` | `ready` | 制作完成缓存 |
| `done_dir` | `done` | 已发布归档 |
| `music_dir` | `music_cache` | 官方曲库缓存 |
| `tid` | `169` | 分区（169=动物圈·汪星人） |
| `copyright` | `1` | 1=原创 |

## 🏗️ 架构

```
DCIM/bili_publish/*.mp4
        │  （文件名为序号）
        ▼
scanner.py ──→ scheduler.py（状态机 pending→ready→uploaded→done）
                  ├─ music.py  官方曲库选曲（24h 缓存轮换）
                  ├─ maker.py  ffmpeg 转码 + BGM 混音 + 封面数字角标
                  └─ uploader.py（bilitool 分片上传 + 自研 web/add/v3 发布）
```

- **上传**：复用 bilitool `UploadController`（官方分片协议：`preupload → upcdn → chunk → 完成`）
- **发布**：`POST member.bilibili.com/x/vu/web/add/v3`，要点：
  - body 必须是 **application/json**（表单编码会返回 21001 参数错误——最大的坑）
  - `csrf` 放 **query**（而非 body）
  - query 需带 **WBI 签名**（`w_rid`/`wts`，与视频搜索接口同参数签名算法）
  - 风控字段 `b_ret`（明文 canvas/webgl 指纹，服务端只校验存在性与格式，无需真跑 wasm 风控 SDK）
- **删除**：`member.bilibili.com/x/web/archive/delete`（部分账号需验证码，自动删除失败时工具会提示人工处理）

---

## 🧪 测试

```bash
python -m unittest discover -s tests   # 35 用例
```

---

## ❓ 常见问题

| 问题 | 解决 |
|---|---|
| 报 `21590 投稿工具已停用` | 用的是旧 bilitool publish，改用自研 `web/add/v3` 发布（本项目已内置） |
| 报 `21001 参数错误` | body 必须是 application/json，csrf 放 query，不能放 body |
| 提示需要验证码 | 删除接口触发部分账号验证，工具会提示人工处理 |

---

## 📜 版本记录

- 自研 **创作中心 `web/add/v3` 发布**（替代已停用的 bilitool `client/add`，实测稳定投稿）
- **官方曲库**：`cool.bilibili.com` co-create 音乐素材库，无需 cookie 枚举/下载 128k m4a 直链，24h 缓存
- **定时发布**：`publish_time` 窗口机制（到点 ±2 分钟窗口内自动提交）
- **合规配置**：原创 + 官方素材库配乐 + 官方投稿接口

---

## ⚖️ 合规 & 免责说明

- 全部使用 B 站官方接口（投稿、素材库、删除、状态查询）
- 配乐来自 B 站官方素材库（版权合规），发布为原创分区
- 本项目仅用于个人自用，请遵守 B 站《投稿规则》与当地法律法规
- 仅供学习交流。使用本项目产生的任何风险与法律责任由使用者自行承担。请勿滥用投稿接口。

*本项目为个人学习项目，与 B 站官方无关。*