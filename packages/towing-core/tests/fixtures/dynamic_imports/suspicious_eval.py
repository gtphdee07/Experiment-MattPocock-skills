"""Fixture (not real source): a module-level ``eval`` call.

Used by test_layering.py to prove the AST scanner flags ``eval`` outright,
since its argument can be an arbitrary runtime-built string that static
analysis cannot vouch for. This file is never imported/executed by
anything; it is only parsed as text.
"""

eval("1 + 1")
