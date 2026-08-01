#!/usr/bin/env python3
"""Run the complete ygo-lf build pipeline."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

try:
    from .build_limits import build_limits
    from .fetch_assets import PROJECT_ROOT, prepare_assets
    from .fetch_images import fetch_images
    from .render_cards import render_previews
except ImportError:
    from build_limits import build_limits
    from fetch_assets import PROJECT_ROOT, prepare_assets
    from fetch_images import fetch_images
    from render_cards import render_previews


def build(
    typst: str = "typst",
    ppi: int = 72,
    skip_fetch: bool = False,
    ignore_aliases: bool = True,
) -> None:
    if not skip_fetch:
        prepare_assets()
    build_limits(ignore_aliases=ignore_aliases)
    fetch_images()
    render_previews(typst=typst, ppi=ppi)

    public = PROJECT_ROOT / "public"
    public.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ygo-lf-site-", dir=PROJECT_ROOT / "build") as temp_name:
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
    parser.add_argument("--skip-fetch", action="store_true")
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
        arguments.skip_fetch,
        arguments.ignore_aliases,
    )
