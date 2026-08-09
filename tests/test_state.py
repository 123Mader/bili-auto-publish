import os, tempfile, unittest
from bili.state import StateStore, STATUS_PENDING, STATUS_READY, STATUS_DONE

class TestStateStore(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.store = StateStore(os.path.join(self.dir.name, "state.json"))

    def test_empty(self):
        self.assertEqual(self.store.load_jobs(), [])

    def test_set_and_get(self):
        self.store.set("1", {"job_id": "1", "status": STATUS_READY})
        self.assertEqual(self.store.get("1")["status"], STATUS_READY)
        self.assertIsNone(self.store.get("nope"))

    def test_init_new_status(self):
        self.store.init_job("5")
        j = self.store.get("5")
        self.assertEqual(j["status"], STATUS_PENDING)
        self.assertEqual(j["retries"], 0)
        self.assertEqual(j["job_id"], "5")

    def test_persists_across_instances(self):
        self.store.init_job("7")
        s2 = StateStore(os.path.join(self.dir.name, "state.json"))
        self.assertEqual(s2.get("7")["status"], STATUS_PENDING)

    def test_mark_done(self):
        self.store.init_job("7")
        self.store.set("7", {"status": STATUS_DONE})
        self.assertEqual(self.store.get("7")["status"], STATUS_DONE)
