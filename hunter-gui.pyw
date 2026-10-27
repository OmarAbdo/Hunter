"""Opens Hunter's window without a console: the desktop and Start-menu icons run this file with
the project's own pythonw (`hunter shortcuts` makes them). What Hunter says goes to
var/hunter-gui.log."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
launch = importlib.import_module("hunter.adapters.gui.launch")  # found only once src is on the path
raise SystemExit(launch.without_console(ROOT))
