"""Fixture (not real source): a module-level ``exec`` call.

Used by test_layering.py to prove the AST scanner flags ``exec`` outright,
since its argument can be an arbitrary runtime-built string that static
analysis cannot vouch for. This file is never imported/executed by
anything; it is only parsed as text.
"""

exec("import os")
