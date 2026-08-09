# 设计：本地自动任务 → B站定时发布（纯本地 + 官方接口合规版）

日期：2026-08-09（v3：上传内核改用 bilitool 库）
状态：已批准（方案 A：本地守护 + bilitool 官方接口封装 + 官方曲库）

## 背景变更

- 原设计（`docs/2026-08-09-bili-auto-publish-design.md`）依赖微信指令触发（OpenClaw 容器 → task.json 桥接）。微信通道不稳定，用户决定**完全不通过微信**，改为纯本地部署自动任务。
- 用户追加合规要求：**使用 B站官方投稿接口 + B站官方版权曲库**，注明自制/原创，所有内容符合 B站社区规则，规避法律风险。
- GitHub 调研后（biliup-rs / bilitool / self-media-uper / social-auto-upload / ytb2bili），用户选定 **`timerring/bilitool`** 作为上传内核嵌入本方案，不再自研 VU 接口客户端。

## 目标

用户把手机拍的狗狗视频写入投放目录，文件名=数字（如 `12.mp4`，该数字即 B站标题）。守护脚本每日定时扫描：取视频 → B站官方曲库配乐 → ffmpeg 制作（转码+配乐+封面叠数字）→ 当晚 20:00 通过 **bilitool（B站官方 Web 接口客户端库）** 发布（个人 B站号，`copyright=1` 原创标注）。无新文件则当天跳过。

## 架构（方案 A：本地守护脚本）

```
用户放入 /storage/emulated/0/DCIM/bili_publish/12.mp4
                        │
                        ▼
bili_daemon.py（Termux 常驻，每 300s 一轮）
① 扫描投放目录 → 新数字文件（waiting）
② 校验 → 制作：ffmpeg 转码+压缩、B站官方曲库配乐(25%)、封面叠数字标题
③ ready/ → 等待 20:00±2min
④ bilitool UploadController 上传（个人B站号，cookie 本地持久化，copyright=1 原创）
⑤ uploaded → 源文件归档移走；failed → 次日重试，最多 3 次
```

- 全部在 Termux 本地完成；无微信/OpenClaw/容器依赖。
- 环境已备：ffmpeg 8.1.2、python3 3.14、node 26。

## 上传内核：bilitool（已选型，GitHub 调研结论）

- 来源：`timerring/bilitool`（纯 Python，MVC 分层，`pip install bilitool`），基于 [bilibili-API-collect] 官方接口实现。
- 能力（源码实证 v0.1.3）：
  - `UploadController().upload_video_entry(video_path, yaml=None, copyright, tid, title, desc, tag, source, cover, dynamic, cdn=None)`：一次调用完成 preupload→分片上传→封面 cover_up→publish，**copyright 参数受支持**（1=原创），封面传本地图片路径即可，返回 True/False
  - `LoginController().login_bilibili(export)`：TV 二维码扫码登录，cookie 持久化到包内 `config.json`，`export=True` 时同时导出 `cookie.json` 到工作目录
  - `LoginController().check_bilibili_login()`：登录态检查（守护轮询用）
  - 上传自动测速选最佳线路（或 `cdn` 参数指定）
- 合规性：bilitool 是**官方接口的本地客户端封装**（直连 api.bilibili.com，无第三方中转服务器、无中间人），不属于「第三方代传服务」；与官方投稿流程参数一一对应（copyright/tid/title/desc/tag/cover），满足用户「官方投稿接口」要求。
- **定时/私密限制**：bilitool **无 `publish_date`（服务端定时）参数，也无私密投稿参数**——上传即发布。方案 A 本来就是「本地到点（20:00）提交」，故无影响；Task 8 私密验证改为「发布后立即删除草稿」。

## 合规与法律风险规避（用户要求，核心约束）

1. **投稿通道**：仅用 B站官方 Web 接口（经 bilitool 库直连 `api.bilibili.com`），不用第三方代传/中转服务，降低账号风控风险。
2. **原创标注**：投稿参数 `copyright=1`（原创，bilitool 原生支持），标题=数字文件名；简介固定合规文案（含「自制原创」+ 配乐来源声明）。
3. **配乐来源**：**彻底弃用第三方音源**（lx-music-api / 音源 js）。只从 B站官方版权曲库搜索配乐（上传流程内的素材库/「官方授权音乐」），使用 B站授权的版权音乐。
4. **兜底**：官方曲库搜索失败/无结果 → **原声直发（无 BGM）**，绝不回退第三方音源。
5. **转载**：所有视频均为自拍原创，不存在转载。config 保留 `copyright` 字段（1=原创 2=转载），若未来有第三方素材手动切 2 并注明出处。
6. **社区规则**：内容为狗狗日常视频，符合 B站社区规定；封面无违规文字；标题/简介不含敏感、诱导、导流内容。

## 组件

### 1. 投放与扫描
- 投放目录：`/storage/emulated/0/DCIM/bili_publish/`（不存在则守护自动创建）
- 识别：`^\d+\.(mp4|mov|avi|m4v)$`（忽略大小写、隐藏文件、`*.part`）
- 多文件按文件名数字升序排队，逐个发布

### 2. 配乐（B站官方曲库）
- 方式一：B站投稿素材库 API（音乐素材搜索，带 cookie），关键词「萌宠 狗狗」→ 取第一条 → 授权直链下载 mp3
- 方式二（若素材库接口不便）：B站官方正版音乐接口（`api.bilibili.com/v2/music/...` 或当期可用之官方授权接口）
- 失败/无结果 → 跳过配乐，原声直发；不阻塞发布

### 3. 制作流水线（ffmpeg 8.1.2）
- 转码：`libx264 -crf 23 -preset medium`，音频 `aac 128k`；保持分辨率；预估 >50MB 则降 crf 直至 ≤50MB
- 配乐：原声 + BGM 25%（amix，BGM 短则循环补齐视频时长）
- 封面：视频中间 1/3 区间抽 6 帧选锐度最高帧 → `drawtext` 叠数字标题
- 输出：`ready/<数字>.mp4` + `ready/<数字>.jpg`

### 4. 发布（bilitool 官方接口封装）
- 登录：`tools/login_scan.py` 调 `LoginController().login_bilibili(export=True)` 扫码一次；cookie 存包内 `config.json`（bilitool 自动管理），并导出 `bili/cookie.json` 备份
- 上传：守护注入 `UploadController().upload_video_entry(video_path=ready_mp4, copyright=1, tid=169, title=数字, desc=合规文案, tag="狗狗日常,汪星人,萌宠", source="", cover=ready_cover, dynamic="")`
- 返回 False / 抛异常 → 记为 failed，重试 3 次
- 登录态校验：每次上传前 `check_bilibili_login()`，失效则日志告警并跳过（避免发到未登录态失败）
- 取消发布可配置（config 开关）
- 失败重试 3 次；超过 20:00 窗口视为 failed 等次日

### 5. 守护（bili_daemon.py）
- 常驻，循环 300s；状态机：`waiting→producing→ready→uploaded→done`；`failed` 保留重试，累计 3 次永久放弃并告警
- `state.json` 持久化；`logs/daemon.log` 日志；重启不重发

## 状态机

| 状态 | 含义 | 转移 |
|---|---|---|
| waiting | 磁盘上有新数字文件 | → producing（校验通过）→ failed（校验失败） |
| producing | 正在制作 | → ready（成功）→ failed（制作异常） |
| ready | 成品待发布 | → uploaded（20:00 上传成功）→ failed |
| uploaded | 已上传 | → done（归档） |
| failed | 任一环节失败 | 等待下一轮 20:00 重试，累计 3 次后永久放弃并日志告警 |

## 错误兜底
- 官方曲库无结果/接口失败 → 原声直发（无 BGM）
- ffmpeg 失败 → 重试 1 次后 failed
- 网络/上传失败 → 3 次 → failed 等次日
- 无新文件 → 空转 sleep，不发布
- 守护崩溃/重启 → state.json 恢复，不重发；`setsid nohup` 常驻（可选 termux-boot 自启）

## 目录布局

```
/usr/tmp/opencode/bili/
  daemon.py, config.json, state.json, cookie.json
  ready/（成品+封面） done/（上传过的源文件归档）
  logs/daemon.log
  music_cache/（官方曲库下载的 mp3 临时缓存）
```

## 测试计划
1. 守护扫描：放入 `3.mp4`，日志出现 waiting/producing/ready
2. 制作：ffmpeg 输出成品+封面；官方曲库不可用时降级原声
3. bilitool 投稿：账号登录 → upload_video_entry 上传 → 立即删除稿件验证后收尾
4. 20:00 定时：config 可改发布时间为「当前+2min」便于测试
5. 失败重试：断网模拟 → failed → 恢复后重试成功
6. 合规检查：投稿后进 B站后台确认 copyright=原创、标题数字、简介含声明

## 待确认（实现时定）
- 官方曲库搜索具体接口端点（实现阶段确认；备选官方授权音乐接口，均需登录态）
- B站分区 tid：投稿接口返回分区树确认「动物圈-汪星人」
- bilitool 若在目标环境安装失败/不可用 → 回退自研 Uploader 骨架（Task 5 保留的纯函数）