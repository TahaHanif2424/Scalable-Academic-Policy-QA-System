# This file makes src a Python package.
# Ensure that modules inside src/ can always resolve sibling imports
# (e.g. `from database import ...`) regardless of whether they are
# run directly (`python src/minhash.py`) or imported as a package
# (`from src.minhash import ...`).
import os as _os
import sys as _sys

_src_dir = _os.path.dirname(_os.path.abspath(__file__))
if _src_dir not in _sys.path:
    _sys.path.insert(0, _src_dir)
