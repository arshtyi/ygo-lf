#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from downloads import download_file
from paths import BUILD_DIR, TYPST_WORKSPACE, TYPST_YGO_SOURCE, YGO_ASSETS_SOURCE


CARD_URLS = {
    "ot": "https://github.com/arshtyi/ygo-cards/releases/download/latest/ot.json",
    "rd": "https://github.com/arshtyi/ygo-cards/releases/download/latest/rd.json",
}
DYNAMIC_ASSET_DIRECTORIES = {"card", "images"}


def is_json_array(path: Path) -> bool:
    try:
        with path.open(encoding="utf-8") as source:
            return isinstance(json.load(source), list)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False


def require_submodules() -> None:
    required = [
        TYPST_YGO_SOURCE / "lib" / "mod.typ",
        *(YGO_ASSETS_SOURCE / environment for environment in CARD_URLS),
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "submodules are not initialized: " + ", ".join(missing)
        )


def link_static_assets(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True)
    for entry in sorted(source.iterdir()):
        if entry.name in DYNAMIC_ASSET_DIRECTORIES:
            continue
        (destination / entry.name).symlink_to(
            entry.resolve(), target_is_directory=entry.is_dir()
        )
    for name in DYNAMIC_ASSET_DIRECTORIES:
        (destination / name).mkdir()


def prepare_workspace(destination: Path = TYPST_WORKSPACE) -> None:
    require_submodules()
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="ygo-lf-workspace-", dir=BUILD_DIR
    ) as temporary_name:
        staged = Path(temporary_name) / "typst-ygo"
        staged.mkdir()
        (staged / "lib").symlink_to(
            (TYPST_YGO_SOURCE / "lib").resolve(), target_is_directory=True
        )

        assets = staged / "assets"
        for environment in CARD_URLS:
            link_static_assets(
                YGO_ASSETS_SOURCE / environment,
                assets / environment,
            )

        with ThreadPoolExecutor(max_workers=len(CARD_URLS)) as executor:
            downloads = [
                executor.submit(
                    download_file,
                    url,
                    assets / environment / "card" / f"{environment}.json",
                    validator=is_json_array,
                )
                for environment, url in CARD_URLS.items()
            ]
            for download in downloads:
                download.result()

        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(staged, destination)

    print(f"Prepared Typst workspace at {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=TYPST_WORKSPACE)
    return parser.parse_args()


if __name__ == "__main__":
    prepare_workspace(parse_args().destination)
