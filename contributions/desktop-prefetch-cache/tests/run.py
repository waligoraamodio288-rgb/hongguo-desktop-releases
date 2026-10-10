"""Run portable fixtures; never import the installed application's backend."""
from pathlib import Path
import sys
import unittest

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root / "tests"), str(root / "src")]
suite = unittest.defaultTestLoader.discover(str(root / "tests"), pattern="test_*.py")
result = unittest.TextTestRunner(verbosity=2).run(suite)
raise SystemExit(not result.wasSuccessful())
