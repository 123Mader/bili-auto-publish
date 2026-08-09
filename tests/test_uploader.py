import tempfile, unittest
from unittest import mock

from bili.uploader import Uploader, LoginRequiredError, UploadError, build_title, build_desc

def _job():
    return {"num": 12, "ready_mp4": "/tmp/12.mp4", "ready_cover": "/tmp/12.jpg"}

def _cfg():
    return {"tid": 169, "copyright": 1}

class TestUploaderPure(unittest.TestCase):
    def test_build_title(self):
        self.assertEqual(build_title(12), "12")

    def test_build_desc(self):
        self.assertIn("自制", build_desc())
        self.assertIn("#汪星人", build_desc())

class TestUploader(unittest.TestCase):
    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_upload_returns_filename_and_cover(self, UC, _lk):
        uc = UC.return_value
        uc.upload_video.return_value = "n260809bd96zfrezv1pu93oxd0r8pinl"
        uc.bili_uploader.cover_up.return_value = "http://i0.hdslb.com/cover.jpg"
        filename, cover = Uploader().upload(_job(), _cfg())
        uc.upload_video.assert_called_once_with("/tmp/12.mp4")
        uc.bili_uploader.cover_up.assert_called_once_with("/tmp/12.jpg")
        self.assertEqual(filename, "n260809bd96zfrezv1pu93oxd0r8pinl")
        self.assertEqual(cover, "http://i0.hdslb.com/cover.jpg")

    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_empty_filename_raises_upload_error(self, UC, _lk):
        UC.return_value.upload_video.return_value = ""
        UC.return_value.bili_uploader.cover_up.return_value = "x"
        with self.assertRaises(UploadError):
            Uploader().upload(_job(), _cfg())

    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_exception_raises_upload_error(self, UC, _lk):
        UC.return_value.upload_video.side_effect = RuntimeError("net")
        with self.assertRaises(UploadError):
            Uploader().upload(_job(), _cfg())

    @mock.patch("bili.uploader.login_ok", return_value=False)
    @mock.patch("bili.uploader.UploadController")
    def test_not_logged_in_raises_login_required(self, UC, _lk):
        with self.assertRaises(LoginRequiredError):
            Uploader().upload(_job(), _cfg())

    @mock.patch("bili.uploader._cookies", return_value={"bili_jct": "csrf123"})
    @mock.patch("bili.uploader._wbi_key", return_value="k" * 32)
    @mock.patch("bili.uploader._wbi_sign", return_value="wrid")
    @mock.patch("bili.uploader.requests.Session")
    def test_publish_posts_add_v3_json(self, Session, _ws, _wk, _ck):
        sess = Session.return_value
        sess.post.return_value.json.return_value = {
            "code": 0, "data": {"aid": 117063259522500, "bvid": "BV1KCuj6nEZW"}}
        aid, bvid = Uploader().publish("fname", "http://cover.jpg", 12, _cfg())
        self.assertEqual((aid, bvid), (117063259522500, "BV1KCuj6nEZW"))
        args, kwargs = sess.post.call_args
        self.assertEqual(kwargs["json"]["title"], "12")
        self.assertEqual(kwargs["json"]["tid"], 169)
        self.assertEqual(kwargs["json"]["videos"], [{"filename": "fname", "title": "12", "desc": "", "cid": 0}])
        self.assertEqual(kwargs["json"]["csrf"], "csrf123")
        self.assertEqual(kwargs["params"]["csrf"], "csrf123")
        self.assertIn("b_ret", kwargs["params"])
        self.assertEqual(kwargs["params"]["w_rid"], "wrid")

    @mock.patch("bili.uploader._cookies", return_value={"bili_jct": "csrf123"})
    @mock.patch("bili.uploader._wbi_key", return_value="k" * 32)
    @mock.patch("bili.uploader._wbi_sign", return_value="wrid")
    @mock.patch("bili.uploader.requests.Session")
    def test_publish_error_raises_upload_error(self, Session, _ws, _wk, _ck):
        sess = Session.return_value
        sess.post.return_value.json.return_value = {"code": 21001, "message": "参数错误"}
        with self.assertRaises(UploadError):
            Uploader().publish("fname", "http://cover.jpg", 12, _cfg())

    @mock.patch("bili.uploader._cookies", return_value={})
    def test_publish_not_logged_in_raises_login_required(self, _ck):
        with self.assertRaises(LoginRequiredError):
            Uploader().publish("fname", "http://cover.jpg", 12, _cfg())

if __name__ == "__main__":
    unittest.main()
