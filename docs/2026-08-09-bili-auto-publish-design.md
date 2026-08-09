# 设计：微信指令 → 自动制作 → B站定时发布

日期：2026-08-09
状态：已批准（用户确认方案 B + 制作规格）

## 目标
用户每天拍狗狗视频（文件名=发布标题）放 DCIM/Camera，微信发指令「发布：文件名」，系统自动：取视频 → 音源搜配乐 → ffmpeg 制作（转码+配乐+封面）→ 每晚 20:00 定时发布到 B站（汪星人分区）。无视频/无指令则当天跳过。

## 架构（方案 B：桥接文件 + 本地轮询）

```
微信「发布：VIDxxx.mp4」 → OpenClaw(微信插件) → 写 task.json（容器内 /root/bili/task.json）
                                                  │
                                                  ▼
                Termux 守护脚本（bili_daemon.py，常驻，每5分钟）
                  1. 读 task.json 新任务
                  2. 校验视频存在 /storage/emulated/0/DCIM/Camera/VIDxxx.mp4
                  3. 关键词 → lx-music-api 搜歌（音源 /storage/emulated/0/MT2/apks/ 两个 js）
                  4. ffmpeg 制作：转码压缩 + 原声+BGM(25%) + 抽帧封面(叠标题)
                  5. 状态 pending → ready → 等 20:00
                  6. 20:00 调用 biliup 上传（cookie 本地持久化）
                  7. done / 失败重试
```

## 组件

### 1. 桥接（OpenClaw → task.json）
- OpenClaw 容器内已有微信通道（fc9b02962e15-im-bot，已验证收发）。
- 新增系统提示词/工具规则：用户消息匹配 `发布[:：]\s*(\S+\.mp4)` → 用本地 shell 写 `/root/bili/task.json`（容器路径；Termux 侧同文件：`/data/data/com.termux/files/home/../usr/tmp/opencode/bili/` 经 bind 可见 → 用 bind 路径 /data/data/com.termux/files/usr/tmp/opencode/bili/task.json）。
- 格式：`{"video":"VIDxxx.mp4","status":"pending","created":...}`

### 2. 音源服务（lx-music-api）
- Termux 装 nodejs，跑 lx-music-api（本地端口 16373），加载两个 js 音源。
- 搜索词：视频文件名分词（去「VID」「.mp4」+ 常见词）→ 搜「狗狗 萌宠 日常」类；搜不到降级无配乐。
- API：GET /search?name=<词> → 取第一条 → /url?id= 拿直链 → 下载 mp3。

### 3. 制作流水线（ffmpeg 8.1.2 已装）
- 转码：`libx264 -crf 23 -preset medium`，音频 aac 128k；分辨率保持，控制 ~50MB。
- 配乐：原声 + BGM 25%（amix，短循环补齐时长）。
- 封面：视频中间 1/3 区间抽 6 帧，选锐度最高一帧 → ffmpeg drawtext 叠标题（中文字体需装）。
- 输出：`ready/标题.mp4` + `ready/封面.jpg`。

### 4. 上传（biliup-rs 或 python bilibili-uploader）
- 扫码登录一次，cookie 存本地。
- 分区：动物圈-汪星人（tid 需确认，biliup 列表取）。
- 发布参数：标题=文件名（去扩展名），简介自动（#狗狗日常 #汪星人 #萌宠），定时 20:00。

### 5. 守护（bili_daemon.py）
- 常驻循环 300s；任务状态机 pending→ready→done/failed。
- 20:00±2min 触发上传；失败保留任务次日 20:00 重试；无任务 sleep。
- 日志：bili/logs/daemon.log。

## 错误兜底
- 音源失效/搜不到 → 无配乐发布（原声直发）。
- 网络失败 → 重试 3 次 → 任务标记 failed，次日重试。
- 微信未发指令 → 不发布（即使有视频）。

## 目录
```
/usr/tmp/opencode/bili/
  task.json, daemon.py, config.json
  ready/（成品） logs/
  music_api/（lx-music-api） sources/（2个音源拷贝）
  cookie.json（B站登录态）
```

## 测试计划
1. biliup 扫码登录 OK
2. lx-music-api 加载音源 → 搜索「狗狗」返回结果
3. ffmpeg 制作今日视频 → 输出成品+封面
4. 端到端：task.json 注入 → 守护检测 → 制作 → （跳过真实发布或测试发布）
5. 微信真实指令 → task.json 写入验证
