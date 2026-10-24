"""`python -m hunter`, run from the project folder (adapters/cli/main.py)."""

import sys
from pathlib import Path

from hunter.adapters.cli.main import main

sys.exit(main(sys.argv[1:], Path.cwd()))
