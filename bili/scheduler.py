"""调度：每 tick 处理一轮状态机推进。"""
import datetime, os, shutil
from bili import scanner
from bili import maker
from bili.state import (
    STATUS_PENDING, STATUS_PRODUCING, STATUS_READY,
    STATUS_UPLOADED, STATUS_DONE, STATUS_FAILED,
)

def should_publish(now, created):
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
                        self.uploader(j, self.cfg)
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
