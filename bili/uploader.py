"""bilitool 上传封装：官方接口客户端库（合规：copyright=1 原创）。"""

from bilitool import LoginController, UploadController

TAG = "狗狗日常,汪星人,萌宠"
DESC = "自制原创狗狗日常视频，配乐使用B站官方授权音乐素材。 #狗狗日常 #汪星人 #萌宠"

class UploadError(Exception):
    pass

class LoginRequiredError(UploadError):
    pass

def build_title(num):
    return str(num)

def build_desc():
    return DESC

def login_ok():
    try:
        return bool(LoginController().check_bilibili_login())
    except Exception:
        return False

class Uploader:
    def __init__(self, controller=None):
        self.uploader = controller or UploadController()

    def upload(self, job, cfg):
        """上传成品+封面；失败抛 UploadError。job 需含 ready_mp4/ready_cover，num 可缺省（用 job_id）。"""
        if not login_ok():
            raise LoginRequiredError("未登录：先运行 python tools/login_scan.py 扫码")
        num = int(job.get("num") or job["job_id"])
        try:
            ok = self.uploader.upload_video_entry(
                job["ready_mp4"], None,
                cfg.get("copyright", 1), cfg.get("tid", 169),
                build_title(num), build_desc(),
                TAG, "", job["ready_cover"], "", cdn=None,
            )
        except Exception as e:
            raise UploadError(f"bilitool 上传异常: {e}") from e
        if not ok:
            raise UploadError("bilitool upload_video_entry returned False")
