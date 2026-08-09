import os, subprocess, tempfile, unittest
from bili.maker import produce, MakerError

class TestMaker(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.dir.name, "12.mp4")
        subprocess.run(["ffmpeg", "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=1280x720:rate=30",
                        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
                        "-shortest", self.src], check=True, capture_output=True)

    def test_produce_creates_output(self):
        cfg = {"ready_dir": os.path.join(self.dir.name, "ready"),
               "publish_dir": os.path.join(self.dir.name, "pub"),
               "music_dir": None}
        out = produce(job={"num": 5, "path": self.src}, cfg=cfg)
        self.assertTrue(os.path.exists(out["ready_mp4"]))
        self.assertTrue(os.path.exists(out["ready_cover"]))

    def test_missing_source_raises(self):
        cfg = {"ready_dir": os.path.join(self.dir.name, "ready"), "publish_dir": self.dir}
        with self.assertRaises(MakerError):
            produce(job={"num": 5, "path": "/nonexistent.mp4"}, cfg=cfg)
