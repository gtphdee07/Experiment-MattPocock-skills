"""Fixture (not real source): a module-level ``spec_from_file_location`` call.

Used by test_layering.py to prove the AST scanner flags
``importlib.util.spec_from_file_location`` outright, since it loads a module
from a file path rather than a name and leaves no ``ast.Import``-shaped
trace. This file is never imported/executed by anything; it is only parsed
as text.
"""

import importlib.util

spec = importlib.util.spec_from_file_location("mod", "/tmp/mod.py")
