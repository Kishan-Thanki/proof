"""Entry point for the Proof CLI.

Allows the package to be executed via `python -m proof`.
"""

import uvloop

from proof.cli import app

if __name__ == "__main__":
    uvloop.install()
    app()
