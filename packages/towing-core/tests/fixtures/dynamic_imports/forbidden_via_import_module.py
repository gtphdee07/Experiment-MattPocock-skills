"""Fixture (not real source): a forbidden module loaded via importlib.

Used by test_layering.py to prove the AST scanner catches
``importlib.import_module(...)`` the same way it catches a plain ``import``.
This file is never imported/executed by anything; it is only parsed as text.
"""

import importlib

sqlite3 = importlib.import_module("sqlite3")
