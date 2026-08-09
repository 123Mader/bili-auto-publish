import datetime, os, tempfile, unittest
from unittest import mock
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
            s.maker = lambda job, cfg, music_path=None: {"ready_mp4": d + "/r.mp4", "ready_cover": d + "/r.jpg"}
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
            up = mock.Mock()
            up.upload.return_value = ("fname", "http://cover.jpg")
            s.uploader = up
            ret = s.tick(now=self.t(20, 1))
            self.assertEqual(ret["published"], 1)
            self.assertEqual(store.get("3")["status"], "done")
            self.assertFalse(os.path.exists(os.path.join(pub, "3.mp4")))
            self.assertTrue(os.path.exists(os.path.join(done, "3.mp4")))
