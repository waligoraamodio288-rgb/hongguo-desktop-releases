"""Regression cases for the public probe, without starting mpv or a server."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('probe', Path(__file__).with_name('verify_preload.py'))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ProbeTests(unittest.TestCase):
    def test_observed_cap_is_valid_without_cli_override(self):
        self.assertEqual(probe.preload_outcome({'native': {'preloadLimited': True, 'cacheComplete': False}}), 'limited')
        self.assertEqual(probe.preload_outcome({'native': {'preloadLimited': False, 'cacheComplete': True}}), 'complete')
        self.assertIsNone(probe.preload_outcome({'native': {'preloadLimited': False, 'cacheComplete': False}}))

    def test_budget_requires_stable_bytes_without_overshoot(self):
        self.assertTrue(probe.budget_stable([1000] * 16, 1000, 100))
        self.assertFalse(probe.budget_stable([1050 + i * 2 for i in range(16)], 1000, 100))
        self.assertFalse(probe.budget_stable([1101] * 16, 1000, 100))
        self.assertFalse(probe.budget_stable([1050], 1000, 100))

    def test_deadline_scales_with_100mib_rate_and_is_bounded(self):
        self.assertGreater(probe.preload_timeout(100*1024**2,.12),100*1024**2/65536*.12)
        self.assertLessEqual(probe.preload_timeout(2*1024**3,.12),3600)
        self.assertEqual(probe.preload_timeout(100*1024**2,0,60),60)
        for value in (0,-1,3601,float('nan')):
            with self.assertRaises(ValueError):probe.preload_timeout(100,0,value)

    def test_waits_for_delayed_server_start(self):
        server = SimpleNamespace(started=False)
        thread = SimpleNamespace(is_alive=lambda: True)
        with patch.object(probe.time, 'sleep', side_effect=lambda _: setattr(server, 'started', True)) as sleep:
            probe.wait_server_started(server, thread)
        sleep.assert_called_once()

    def test_server_start_is_bounded_and_detects_dead_thread(self):
        server = SimpleNamespace(started=False)
        with self.assertRaises(RuntimeError):
            probe.wait_server_started(server, SimpleNamespace(is_alive=lambda: False))
        with patch.object(probe.time, 'monotonic', side_effect=[0, 6]):
            with self.assertRaises(TimeoutError):
                probe.wait_server_started(server, SimpleNamespace(is_alive=lambda: True), timeout=5)


if __name__ == '__main__':
    unittest.main()
