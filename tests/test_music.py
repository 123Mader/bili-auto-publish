import os, tempfile, unittest
from unittest import mock
from bili.music import pick_music

class TestMusic(unittest.TestCase):
    def test_no_music_dir_returns_none(self):
        self.assertIsNone(pick_music({"music_dir": None}))

    def test_search_failure_falls_back_none(self):
        cfg = {"music_dir": "/tmp/x", "num": 1}
        with mock.patch("bili.music._official_search", side_effect=Exception("net")):
            self.assertIsNone(pick_music(cfg))

    def test_cache_hit_no_network(self):
        d = tempfile.TemporaryDirectory()
        p = os.path.join(d.name, "12.mp3"); open(p, "w").close()
        cfg = {"music_dir": d.name, "num": 12}
        with mock.patch("bili.music._official_search") as ms:
            res = pick_music(cfg)
            self.assertEqual(os.path.basename(res), "12.mp3")
            ms.assert_not_called()
