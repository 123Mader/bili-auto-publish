import unittest
from unittest import mock

class TestDaemon(unittest.TestCase):
    def test_scheduler_exception_does_not_kill_loop(self):
        sched = mock.Mock()
        sched.tick.side_effect = RuntimeError("boom")
        from bili.daemon import run_once
        run_once(sched)   # 不抛异常即通过
