"""Time helpers shared by main.py and database.py.

`datetime.utcnow()` is deprecated since Python 3.12 and scheduled for removal;
on 3.14 (what this project's venv runs) every call already emits a
DeprecationWarning. The stdlib replacement, `datetime.now(timezone.utc)`,
returns an *aware* datetime -- which is not a drop-in substitute here, because
every timestamp column in models.py is a naive `DateTime` and the code compares
those columns against Python values directly (lock expiry, contest windows,
JWT expiry). Mixing aware and naive datetimes raises TypeError, so switching
call sites to `datetime.now(timezone.utc)` wholesale would break at runtime
rather than at import.

`utcnow()` below keeps the exact naive-UTC semantics the schema and the
existing comparisons already depend on, while getting the deprecated call out
of the codebase.
"""

from datetime import datetime, timezone

__all__ = ["utcnow", "aware_utcnow"]


def utcnow() -> datetime:
    """Current UTC time as a naive datetime -- what `datetime.utcnow()` returned."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def aware_utcnow() -> datetime:
    """Current UTC time as a timezone-aware datetime.

    For new code that isn't constrained by the naive DateTime columns.
    """
    return datetime.now(timezone.utc)
