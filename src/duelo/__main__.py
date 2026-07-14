"""Allow ``python -m duelo`` to behave exactly like the ``duelo`` script."""

from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
