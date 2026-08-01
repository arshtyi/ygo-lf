#!/usr/bin/env python3
"""Run the complete ygo-lf build pipeline."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

from build_limits import build_limits
from fetch_images import fetch_images
from paths import BUILD_DIR, PROJECT_ROOT
from render_cards import render_previews
from workspace import prepare_workspace


def build(
    typst: str = "typst",
    ppi: int = 72,
    reuse_workspace: bool = False,
    ignore_aliases: bool = True,
) -> None:
    if not reuse_workspace:
        prepare_workspace()
    build_limits(ignore_aliases=ignore_aliases)
    fetch_images()
    render_previews(typst=typst, ppi=ppi)

    public = PROJECT_ROOT / "public"
    with tempfile.TemporaryDirectory(prefix="ygo-lf-site-", dir=BUILD_DIR) as temp_name:
        staged = Path(temp_name) / "public"
        staged.mkdir()
        subprocess.run(
            [
                typst,
                "compile",
                "--root",
                str(PROJECT_ROOT),
                str(PROJECT_ROOT / "main.typ"),
                str(staged / "ygo-lf.pdf"),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
        shutil.copy2(PROJECT_ROOT / "site" / "index.html", staged / "index.html")
        if public.exists():
            shutil.rmtree(public)
        shutil.move(staged, public)
    print(f"Built Pages site at {public}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--typst", default="typst")
    parser.add_argument("--ppi", type=int, default=72)
    parser.add_argument("--reuse-workspace", action="store_true")
    parser.add_argument(
        "--ignore-aliases",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="ignore alternate-art cards whose alias is not 0 (default: true)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build(
        arguments.typst,
        arguments.ppi,
        arguments.reuse_workspace,
        arguments.ignore_aliases,
    )
