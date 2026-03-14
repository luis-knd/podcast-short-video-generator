"""Root conftest – mutmut 3 compatibility patch.

mutmut ≥ 3 rejects module names that start with ``src.`` because it assumes
the standard *src-layout* (where ``src/`` is **not** a Python package).
This project treats ``src/`` as a package, so module names legitimately
begin with ``src.``.  The trampoline lazily imports
``record_trampoline_hit`` on every call, which means replacing the
attribute on the already-loaded module is enough to fix the assertion.
"""

import os

if os.environ.get("MUTANT_UNDER_TEST"):
    import mutmut.__main__ as _mm

    _original_record_trampoline_hit = _mm.record_trampoline_hit

    def _patched_record_trampoline_hit(name: str) -> None:
        if name.startswith("src."):
            name = name[len("src.") :]
        _original_record_trampoline_hit(name)

    _mm.record_trampoline_hit = _patched_record_trampoline_hit
