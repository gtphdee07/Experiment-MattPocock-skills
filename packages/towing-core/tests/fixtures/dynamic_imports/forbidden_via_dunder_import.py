"""Fixture (not real source): a forbidden module loaded via __import__.

Used by test_layering.py to prove the AST scanner catches ``__import__(...)``
the same way it catches a plain ``import``. This file is never
imported/executed by anything; it is only parsed as text.
"""

argparse = __import__("argparse")
