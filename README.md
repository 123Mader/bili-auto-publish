# Bili Auto Publish

B 站视频自动定时发布守护脚本：扫描本地视频目录 → 官方曲库自动配乐（B 站官方素材库，合规）→ ffmpeg 制作（转码+封面）→ 到点自动投稿到 B 站（原创，汪星人分区）。

纯本地运行（Termux / 任意 Linux），无云服务、无第三方音源，所有环节均使用 B 站官方接口。

## 为什么做这个

每天给狗狗拍视频，想自动整理成片并定时发布到 B 站。踩坑记录见下——特别是 **bilitool 的 publish 接口已被 B 站停用（code 21590「投稿工具已停用」）**，本项目自研了基于创作中心 `web/add/v3` 的发布实现，实测可稳定投稿。

## 功能

- **官方曲库**：`cool.bilibili.com` co-create 音乐素材库，无需 cookie 即可枚举/下载 128k m4a 直链，24h 缓存
- **定时发布**：`publish_time` 窗口机制（到点 ±2 分钟窗口内自动提交）
- **自研发布**：`web/add/v3` + WBI 签名 + 风控指纹（替代已停用的 bilitool `client/add`）
- **合规配置**：`copyright=1` 原创 + 官方素材库配乐 + 官方投稿接口
- 失败重试、状态机持久化、日志完整

## 快速开始

```bash
# 1. 安装依赖
bash setup.sh

# 2. 扫码登录（B 站 TV 协议二维码，无需密码）
python tools/login_scan.py

# 3. 启动守护（默认每天 20:00 窗口自动发布）
python bili/daemon.py            # 后台: nohup python bili/daemon.py &
```

把视频放到 `publish_dir`（默认 `/storage/emulated/0/DCIM/bili_publish`），文件名即发布标题（如 `20260809.mp4` → 标题「20260809」）。

## 配置

`config.json`（模板见 `config.example.json`）：

```json
{
  "publish_time": "20:00",      // 发布窗口（该时间 ±2 分钟窗口内会自动投递）
  "interval": 300,              // 轮询间隔秒
  "publish_dir": "…",           // 待发布视频目录
  "ready_dir": "ready",         // 制作完成缓存
  "done_dir": "done",           // 已发布归档
  "music_dir": "music_cache",   // 官方曲库缓存
  "tid": 169,                   // 分区（169=动物圈·汪星人）
  "copyright": 1                // 1=原创
}
```

## 架构

```
DCIM/bili_publish/*.mp4
        │  （文件名为序号）
        ▼
scanner.py ──→ scheduler.py（状态机 pending→ready→uploaded→done）
                  ├─ music.py  官方曲库选曲（24h 缓存轮换）
                  ├─ maker.py  ffmpeg 转码 + BGM 混音 + 封面数字角标
                  └─ uploader.py（bilitool 分片上传 + 自研 web/add/v3 发布）
```

- **上传**：复用 bilitup `UploadController`（官方分片协议：preupload → upcdn → chunk → 完成）
- **发布**：`POST member.bilibili.com/x/vu/web/add/v3`，要点：
  - body 必须是 **application/json**（表单编码会返回 21001 参数错误——最大的坑）
  - `csrf` 放 **query**（而非 body）
  - query 需带 **WBI 签名**（`w_rid`/`wts`，与视频搜索接口同参数签名算法）
  - 风控字段 `b_ret`（明文 canvas/webgl 指纹，服务端只校验存在性与格式，无需真跑 wasm 风控 SDK）
- **删除**：`member.bilibili.com/x/web/archive/delete`（部分账号需要验证码，自动删除失败时工具会提示人工处理）

## 测试

```bash
python -m unittest discover -s tests   # 35 用例
```

## 合规声明

- 全部使用 B 站官方接口（投稿、素材库、删除、状态查询）
- 配乐来自 B 站官方素材库（版权合规），发布为原创分区
- 本项目仅用于个人自用，请遵守 B 站《投稿规则》与当地法律法规

## 免责声明

仅供学习交流。使用本项目产生的任何风险与法律责任由使用者自行承担。请勿滥用投稿接口。