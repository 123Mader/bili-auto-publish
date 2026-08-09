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
    def test_upload_calls_with_params(self, UC, _lk):
        uc = UC.return_value
        uc.upload_video_entry.return_value = True
        Uploader().upload(_job(), _cfg())
        uc.upload_video_entry.assert_called_once_with(
            "/tmp/12.mp4", None, 1, 169, "12", mock.ANY,
            "狗狗日常,汪星人,萌宠", "", "/tmp/12.jpg", "", cdn=None,
        )

    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_false_raises_upload_error(self, UC, _lk):
        UC.return_value.upload_video_entry.return_value = False
        with self.assertRaises(UploadError):
            Uploader().upload(_job(), _cfg())

    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_exception_raises_upload_error(self, UC, _lk):
        UC.return_value.upload_video_entry.side_effect = RuntimeError("net")
        with self.assertRaises(UploadError):
            Uploader().upload(_job(), _cfg())

    @mock.patch("bili.uploader.login_ok", return_value=True)
    @mock.patch("bili.uploader.UploadController")
    def test_copyright_override_respected(self, UC, _lk):
        uc = UC.return_value
        uc.upload_video_entry.return_value = True
        Uploader().upload(_job(), {"tid": 169, "copyright": 2})
        self.assertEqual(uc.upload_video_entry.call_args[0][2], 2)

    @mock.patch("bili.uploader.login_ok", return_value=False)
    @mock.patch("bili.uploader.UploadController")
    def test_not_logged_in_raises_login_required(self, UC, _lk):
        with self.assertRaises(LoginRequiredError):
            Uploader().upload(_job(), _cfg())
