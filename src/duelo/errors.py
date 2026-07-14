"""Exception hierarchy for duelo.

Every error raised on a user-facing path derives from :class:`DueloError`,
so the CLI can catch one type, print a clean message, and exit 1 without a
traceback. Messages are written to be actionable (they name the offending
line, item, or flag to change).
"""

from __future__ import annotations


class DueloError(Exception):
    """Base class for all duelo errors."""


class ParseError(DueloError):
    """A battle log line or file could not be parsed.

    Carries ``source`` (file name) and ``line`` (1-based line number) when
    known, and prefixes the message with them.
    """

    def __init__(self, message: str, source: str = "", line: int = 0):
        self.source = source
        self.line = line
        prefix = ""
        if source:
            prefix = source
            if line:
                prefix += f":{line}"
            prefix += ": "
        super().__init__(prefix + message)


class DegenerateDataError(DueloError):
    """An item won everything or lost everything, so its maximum-likelihood
    Bradley-Terry strength sits at an infinite boundary.

    The fix is more data or a small ``prior`` (pseudo-ties), which the
    message suggests explicitly.
    """


class DisconnectedError(DueloError):
    """The comparison graph has more than one connected component, so items
    in different components cannot be placed on one scale."""
