import os, tempfile, unittest
from unittest import mock
from bili.music import pick_music, _select_track, _load_catalog

TRACKS = [
    {"sid": 1, "title": "A", "duration": 60, "used_count": 5},
    {"sid": 2, "title": "B", "duration": 90, "used_count": 9},
]

class TestMusic(unittest.TestCase):
    def test_no_music_dir_returns_none(self):
        self.assertIsNone(pick_music({"music_dir": None}))

    def test_catalog_failure_falls_back_none(self):
        cfg = {"music_dir": "/tmp/x", "num": 1}
        with mock.patch("bili.music._fetch_catalog", side_effect=Exception("net")):
            self.assertIsNone(pick_music(cfg))

    def test_cache_hit_no_network(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "12.m4a"); open(p, "w").close()
            cfg = {"music_dir": d, "num": 12}
            with mock.patch("bili.music._fetch_catalog") as fc:
                res = pick_music(cfg)
                self.assertEqual(os.path.basename(res), "12.m4a")
                fc.assert_not_called()

    def test_pick_downloads_play_url(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"music_dir": d, "num": 1}
            audio = os.path.join(d, "1.m4a"); open(audio, "w").close()
            with mock.patch("bili.music._fetch_catalog", return_value=TRACKS), \
                 mock.patch("bili.music._get", return_value={"play_url": "http://x/m.m4a"}), \
                 mock.patch("bili.music._download", return_value=None):
                res = pick_music(cfg)
                self.assertEqual(res, audio)

    def test_no_play_url_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"music_dir": d, "num": 1}
            with mock.patch("bili.music._fetch_catalog", return_value=TRACKS), \
                 mock.patch("bili.music._get", return_value={}):
                self.assertIsNone(pick_music(cfg))

    def test_select_track_rotates_by_num(self):
        with mock.patch("bili.music._load_catalog", return_value=TRACKS):
            self.assertEqual(_select_track({"num": 0})["sid"], 1)
            self.assertEqual(_select_track({"num": 1})["sid"], 2)
            self.assertEqual(_select_track({"num": 2})["sid"], 1)

    def test_select_track_empty_catalog_none(self):
        with mock.patch("bili.music._load_catalog", return_value=[]):
            self.assertIsNone(_select_track({"num": 0}))

    def test_load_catalog_caches(self):
        with tempfile.TemporaryDirectory() as d:
            cfg = {"music_dir": d}
            with mock.patch("bili.music._fetch_catalog", return_value=TRACKS) as fc:
                got = _load_catalog(cfg)
                self.assertEqual(got, TRACKS)
                got2 = _load_catalog(cfg)
                self.assertEqual(got2, TRACKS)
                fc.assert_called_once()
                self.assertTrue(os.path.isfile(os.path.join(d, "catalog.json")))

if __name__ == "__main__":
    unittest.main()
