"""`python -m hunter boards add <link>... [--company NAME]`, `boards probe [--limit N]` and
`discover [--campaign ID]...`, run from the project folder."""

import argparse
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TextIO

from hunter.adapters.cli.boards_command import add_boards
from hunter.adapters.cli.discover_command import run_discovery
from hunter.adapters.cli.probe_command import run_probe
from hunter.adapters.cli.project import Project


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
    return run_discovery(project, chosen.campaign, out)
