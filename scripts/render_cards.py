#!/usr/bin/env python3
"""Rasterize restricted cards with typst-ygo at a memory-friendly PPI."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Iterable

from paths import LIMITS_FILE, PREVIEWS_DIR, PROJECT_ROOT, TYPST_WORKSPACE

PAGE_NUMBER = re.compile(r"page-(\d+)\.png$")


def ordered_unique(groups: Iterable[Iterable[int]]) -> list[int]:
    return list(dict.fromkeys(identifier for group in groups for identifier in group))


def typst_source(environment: str, identifiers: list[int], workspace: Path) -> str:
    if environment not in {"ot", "rd"}:
        raise ValueError(f"unsupported card environment: {environment}")
    card_function = f"{environment}-card"
    cards_function = f"{environment}-cards"
    values = ", ".join(str(identifier) for identifier in identifiers)
    module = (workspace / "lib" / "mod.typ").relative_to(PROJECT_ROOT)
    module_path = "/" + module.as_posix()
    return (
        f'#import "{module_path}": '
        f"{card_function}, {cards_function}\n\n"
        f"#let cards = {cards_function}()\n"
        f"#let ids = ({values},)\n\n"
        "#set page(width: auto, height: auto, margin: 0pt)\n\n"
        f"#for id in ids {{\n  {card_function}(id, cards: cards)\n"
        "  pagebreak(weak: true)\n}\n"
    )


def page_sort_key(path: Path) -> int:
    match = PAGE_NUMBER.search(path.name)
    if not match:
        raise ValueError(f"unexpected preview filename: {path.name}")
    return int(match.group(1))


def compile_environment(
    typst: str,
    environment: str,
    identifiers: list[int],
    ppi: int,
    work: Path,
    workspace: Path,
) -> Path:
    if not identifiers:
        raise ValueError(f"no restricted {environment.upper()} cards to render")

    source = work / f"{environment}.typ"
    source.write_text(
        typst_source(environment, identifiers, workspace), encoding="utf-8"
    )
    output = work / "previews" / environment
    output.mkdir(parents=True)
    pattern = output / "page-{0p}.png"
    fonts = [
        workspace / "assets" / "ot" / "font",
        workspace / "assets" / "rd" / "font",
    ]
    command = [typst, "compile", "--root", str(PROJECT_ROOT)]
    for font_path in fonts:
        command.extend(("--font-path", str(font_path)))
    command.extend(("--ppi", str(ppi), str(source), str(pattern)))
    subprocess.run(command, cwd=PROJECT_ROOT, check=True)

    pages = sorted(output.glob("page-*.png"), key=page_sort_key)
    if len(pages) != len(identifiers):
        raise RuntimeError(
            f"typst rendered {len(pages)} {environment.upper()} pages for "
            f"{len(identifiers)} cards"
        )
    for page, identifier in zip(pages, identifiers, strict=True):
        page.replace(output / f"{identifier}.png")
    return output


def render_previews(
    limits_path: Path = LIMITS_FILE,
    output: Path = PREVIEWS_DIR,
    typst: str = "typst",
    ppi: int = 72,
    workspace: Path = TYPST_WORKSPACE,
) -> None:
    if not 36 <= ppi <= 144:
        raise ValueError("preview PPI must be between 36 and 144")
    with limits_path.open(encoding="utf-8") as source:
        limits = json.load(source)

    workspace = workspace.resolve()
    ot_ids = ordered_unique((*limits["ocg"], *limits["tcg"]))
    rd_ids = ordered_unique(limits["rd"])
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ygo-lf-render-", dir=output.parent) as temp_name:
        work = Path(temp_name)
        compile_environment(typst, "ot", ot_ids, ppi, work, workspace)
        compile_environment(typst, "rd", rd_ids, ppi, work, workspace)
        staged = work / "previews"
        if output.exists():
            shutil.rmtree(output)
        shutil.move(staged, output)

    print(f"Rendered {len(ot_ids)} OT and {len(rd_ids)} RD previews at {ppi} PPI")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limits", type=Path, default=LIMITS_FILE)
    parser.add_argument("--output", type=Path, default=PREVIEWS_DIR)
    parser.add_argument("--workspace", type=Path, default=TYPST_WORKSPACE)
    parser.add_argument("--typst", default="typst")
    parser.add_argument("--ppi", type=int, default=72)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    render_previews(
        arguments.limits,
        arguments.output,
        arguments.typst,
        arguments.ppi,
        arguments.workspace,
    )
