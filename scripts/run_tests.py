"""Run discovery with isolated default data paths, never the live user's data."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path[:0]=[str(Path(__file__).resolve().parents[1]),str(Path(__file__).resolve().parents[1]/'src')]
import config

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='lmemm-tests-') as data:
        with config.use_paths(data):
            run=unittest.main(module=None,argv=[sys.argv[0],'discover','-s','tests',*sys.argv[1:]],exit=False)
            raise SystemExit(0 if run.result.wasSuccessful() else 1)
