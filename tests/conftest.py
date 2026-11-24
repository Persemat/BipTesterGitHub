"""
Shared pytest fixtures/setup for the whole tests/ package.

`rstr` (used by botium_translator.py to generate strings that match a regex) needs
network access to install and isn't always available in a sandboxed CI environment.
This stub activates ONLY if the real package is missing, so on a normal development
machine (where `pip install rstr` works) the real library is used unmodified, and
tests that care about genuinely regex-correct output still exercise the real thing.
"""
import sys
import types

try:
    import rstr  # noqa: F401  (just probing availability)
except ImportError:
    import random
    import string

    def _xeger(pattern):
        # Minimal stand-in: NOT regex-aware, just produces *a* printable string.
        # Good enough for tests that only check "a string was returned and the
        # exception-handling path wasn't triggered" rather than exact regex
        # conformance.
        return "".join(random.choices(string.ascii_letters + string.digits, k=8))

    stub = types.ModuleType("rstr")
    stub.xeger = _xeger
    sys.modules["rstr"] = stub
