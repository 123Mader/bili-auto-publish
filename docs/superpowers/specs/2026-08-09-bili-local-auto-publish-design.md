# 设计：本地自动任务 → B站定时发布（不通过微信）

日期：2026-08-09
状态：已批准（用户确认方案 A：守护脚本）

## 背景变更

原设计（`docs/2026-08-09-bili-auto-publish-design.md`）依赖微信指令触发（OpenClaw 容器 → task.json 桥接）。微信通道不稳定（容器 getUpdates 网络失败、liveness 告警），用户决定**完全不通过微信**，改为纯本地部署自动任务。

## 目标

用户把要发布的狗狗视频放入指定投放目录，文件名=数字（如 `12.mp4`，该数字即 B站标题）。守护脚本每日定时扫描，自动：取视频 → 配乐 → ffmpeg 制作（转码+配乐+封面叠标题）→ 当晚 20:00 定时发布到 B站（个人账号，动物圈-汪星人分区）。无新视频则当天跳过。

## 架构（方案 A：本地守护脚本）

```
用户放入 /storage/emulated/0/DCIM/bili_publish/12.mp4
                        │
                        ▼
bili_daemon.py（Termux 常驻，每 300s 一轮）
  ① 扫描投放目录 → 新数字文件（waiting）
  ② 校验视频 → 制作：ffmpeg 转码+原声+BGM(25%)+封面叠数字标题
  ③ ready/ 等待 20:00±2min
  ④ biliup 上传（个人B站号，cookie 本地持久化）
  ⑤ done → 源文件归档移走；失败重试（次日同刻，最多 3 次）
```

关键技术决策：放弃微信/OpenClaw/容器，全部在 Termux 本地完成。守护进程用 `nohup`/`setsid` 常驻，Termux 重启后需手动拉起（可选：配置 termux-boot 自启）。

## 组件

### 1. 投放与扫描
- 投放目录：`/storage/emulated/0/DCIM/bili_publish/`（不存在则守护自动创建）
- 识别规则：`^\d+\.(mp4|mov|avi)$`（忽略临时文件 `.*\.tmp|.*\.part`）
- 多个新文件按文件名数字升序排队

### 2. 音源服务（lx-music-api）
- Termux 已装 node v26，跑 lx-music-api（本地端口 16373），加载 `/storage/emulated/0/MT2/apks/` 两个 js 音源
- 搜索词：文件数字名 → 固定关键词「狗狗 萌宠」→ 取第一条 → `/url?id=` 下载 mp3
- 搜不到/音源失效 → 无配乐直发（不阻塞发布）

### 3. 制作流水线（ffmpeg 8.1.2 已装）
- 转码：`libx264 -crf 23 -preset medium`，音频 `aac 128k`；保持分辨率；若预估 >50MB 则降 crf 至 ≤50MB
- 配乐：原声 + BGM 25%（amix，BGM 短则循环补齐视频时长）
- 封面：视频中间 1/3 区间抽 6 帧选锐度最高帧 → `drawtext` 叠标题（纯数字，无中文字体依赖）
- 输出：`ready/<数字>.mp4` + `ready/<数字>.jpg`

### 4. 发布（biliup-rs 或等价 Python 实现）
- 扫码登录一次，cookie 存 `bili/cookie.json`
- 分区：动物圈-汪星人（tid 用 biliup 列表确认）
- 标题：纯数字（文件名）；简介：`#狗狗日常 #汪星人 #萌宠`
- 定时：20:00±2min；上传失败重试 3 次；超过次日 20:00 视为 failed 等明日

### 5. 守护（bili_daemon.py）
- 常驻循环 300s；状态机：`waiting→producing→ready→uploaded→done`，`failed` 保留重试
- 已处理文件记日志（`bili/logs/daemon.log` + `state.json` 持久化），重启不重发

## 状态机

| 状态 | 含义 | 转移 |
|---|---|---|
| waiting | 磁盘上有新数字文件 | → producing（校验通过）→ failed（校验失败） |
| producing | 正在制作 | → ready（成功）→ failed（制作异常，重试） |
| ready | 成品待发布 | → uploaded（20:00 上传成功）→ failed |
| uploaded | 已上传 | → done（归档） |
| failed | 任一环节失败 | 等待下一轮 20:00 重试，累计 3 次后永久放弃并日志告警 |

## 错误兜底
- 音源失效 → 无配乐发布（原声直发）
- ffmpeg 失败 → 重试 1 次后 failed
- 网络/上传失败 → 3 次 → failed 等次日
- 无新文件 → 空转 sleep，不发布
- 守护崩溃 → `nohup` + 日志；出错不吞异常（打印 traceback）

## 目录布局

```
/usr/tmp/opencode/bili/
  daemon.py, config.json, cookie.json
  ready/（成品+封面） done/（上传过的源文件归档）
  logs/daemon.log
  music_api/（lx-music-api） sources/（2 个音源拷贝）
```

## 测试计划
1. 守护扫描：放入 `3.mp4`，日志出现 waiting/producing/ready
2. 制作：ffmpeg 输出成品+封面；无音源服务器时降级原声
3. 模拟 20:00（配置可调时间戳/强制触发）→ 上传流程（先测试分区列表/tid 有效）
4. 端到端：真实制作一个短视频，验证 B站上传 API 打通（可先私有投稿验证再删）
5. 重试路径：断网模拟 → failed → 恢复后重试成功

## 待办分歧（实现时确认）
- biliup 具体实现选型：`pip install biliup`（Python）还是下载 biliup-rs 二进制——优先 Python（Termux aarch64 更顺手）
- 定时触发可测试性：config 里放 `publish_time="20:00"`，测试时可改为当前时间±1min