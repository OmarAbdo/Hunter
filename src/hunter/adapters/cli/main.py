"""`python -m hunter boards add <link>... [--company NAME]`, `boards probe [--limit N]`,
`discover [--campaign ID]...`, `gui` and `shortcuts`, run from the project folder."""

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from hunter.adapters.cli.boards_command import add_boards
from hunter.adapters.cli.discover_command import run_discovery
from hunter.adapters.cli.probe_command import run_probe
from hunter.adapters.cli.project import Project
from hunter.adapters.gui.desktop import make_shortcuts
from hunter.adapters.gui.launch import run_gui


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m hunter")
    commands = root.add_subparsers(dest="command", required=True)
    boards = commands.add_parser("boards", help="the company registry").add_subparsers(
        dest="action", required=True
    )
    add = boards.add_parser("add", help="add the job boards these links point at")
    add.add_argument("links", nargs="+")
    add.add_argument("--company", help="the company's name, when the registry doesn't know it")
    probe = boards.add_parser("probe", help="look for the boards of companies known by name only")
    probe.add_argument("--limit", type=int, default=20, help="companies probed in one run")
    discover = commands.add_parser("discover", help="read every source for the campaigns")
    discover.add_argument("--campaign", action="append", default=[], help="all when left out")
    commands.add_parser("gui", help="open Hunter's window")
    commands.add_parser("shortcuts", help="put Hunter's icon on the desktop and in the Start menu")
    return root


def main(
    arguments: Sequence[str],
    root: Path,
    apis: Mapping[str, str] | None = None,
    out: TextIO = sys.stdout,
) -> int:
    chosen = parser().parse_args(arguments)
    project = Project(root, apis or {})
    if chosen.command == "boards" and chosen.action == "probe":
        return run_probe(project, chosen.limit, out)
    if chosen.command == "boards":
        return add_boards(project, chosen.links, chosen.company, out)
    if chosen.command == "gui":
        return run_gui(project, out)
    if chosen.command == "shortcuts":
        out.writelines(f"Made {shortcut}\n" for shortcut in make_shortcuts(root))
        return 0
    return run_discovery(project, chosen.campaign, out)
