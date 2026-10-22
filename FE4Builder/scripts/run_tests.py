"""Run FE4Builder tests from any working directory."""
from pathlib import Path
import sys
import unittest

builder=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(builder / 'tests'))
sys.path.insert(0,str(builder / 'src'))
pattern=sys.argv[1] if len(sys.argv)>1 else 'test_*.py'
suite=unittest.defaultTestLoader.discover(str(builder / 'tests'),pattern=pattern)
result=unittest.TextTestRunner(verbosity=1).run(suite)
raise SystemExit(0 if result.wasSuccessful() else 1)
