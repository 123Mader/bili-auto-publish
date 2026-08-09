import os, tempfile, unittest
from bili.scanner import scan_publish_dir

class TestScanner(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.dir.name, "sub"))

    def test_empty_dir(self):
        self.assertEqual(scan_publish_dir(self.dir.name), [])

    def test_digit_files_only(self):
        p = os.path.join(self.dir.name, "12.mp4"); open(p, "w").close()
        open(os.path.join(self.dir.name, "dog.mp4"), "w").close()
        open(os.path.join(self.dir.name, "abc.mp4"), "w").close()
        open(os.path.join(self.dir.name, "12.part"), "w").close()
        open(os.path.join(self.dir.name, "12.mp"), "w").close()
        res = scan_publish_dir(self.dir.name)
        self.assertEqual([r["num"] for r in res], [12])
        self.assertEqual(res[0]["path"], p)

    def test_sorted_ascending(self):
        for n in (9, 3, 12):
            open(os.path.join(self.dir.name, f"{n}.mp4"), "w").close()
        self.assertEqual([r["num"] for r in scan_publish_dir(self.dir.name)], [3, 9, 12])

    def test_uppercase_ext(self):
        open(os.path.join(self.dir.name, "5.MP4"), "w").close()
        self.assertEqual([r["num"] for r in scan_publish_dir(self.dir.name)], [5])

    def test_ignores_subdirs(self):
        open(os.path.join(self.dir.name, "sub", "1.mp4"), "w").close()
        self.assertEqual(scan_publish_dir(self.dir.name), [])
