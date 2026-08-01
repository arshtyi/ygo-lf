#!/usr/bin/env python3
"""Prepare release assets for the vendored typst-ygo module."""

from __future__ import annotations

import argparse
import shutil
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = PROJECT_ROOT / "vendor" / "typst-ygo" / "assets"

DOWNLOADS = {
    "assets": "https://github.com/arshtyi/ygo-assets/releases/download/latest/assets.tar.xz",
    "ot": "https://github.com/arshtyi/ygo-cards/releases/download/latest/ot.json",
    "rd": "https://github.com/arshtyi/ygo-cards/releases/download/latest/rd.json",
}


def download(url: str, destination: Path) -> None:
    last_error: Exception | None = None
    for attempt in range(1, 4):
        request = urllib.request.Request(url, headers={"User-Agent": "ygo-lf-builder"})
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                with destination.open("wb") as output:
                    shutil.copyfileobj(response, output)
            return
        except (OSError, urllib.error.URLError) as error:
            last_error = error
            destination.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"failed to download {url}: {last_error}")


def safe_extract(archive_path: Path, destination: Path) -> None:
    destination = destination.resolve()
    with tarfile.open(archive_path, "r:*") as archive:
        members = archive.getmembers()
        for member in members:
            target = (destination / member.name).resolve()
            if target != destination and destination not in target.parents:
                raise ValueError(f"unsafe archive path: {member.name}")
            if member.issym() or member.islnk():
                raise ValueError(f"archive links are not allowed: {member.name}")
        archive.extractall(destination, members=members, filter="data")


def find_asset_root(path: Path) -> Path:
    candidates = [path / "assets", path]
    candidates.extend(item for item in path.iterdir() if item.is_dir())
    for candidate in candidates:
        if all((candidate / environment).is_dir() for environment in ("ot", "rd")):
            return candidate
    raise ValueError("asset archive must contain OT and RD directories")


def prepare_assets(destination: Path = DEFAULT_DESTINATION) -> None:
    destination = destination.resolve()
    module_path = destination.parent / "lib" / "mod.typ"
    if not module_path.is_file():
        raise FileNotFoundError(
            f"typst-ygo submodule is not initialized: {module_path}"
        )

    build_directory = PROJECT_ROOT / "build"
    build_directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ygo-lf-assets-", dir=build_directory) as temp_name:
        temp = Path(temp_name)
        downloads = temp / "downloads"
        downloads.mkdir()
        paths = {
            "assets": downloads / "assets.tar.xz",
            "ot": downloads / "ot.json",
            "rd": downloads / "rd.json",
        }

        print("Downloading card data and card assets...")
        with ThreadPoolExecutor(max_workers=len(DOWNLOADS)) as executor:
            futures = [
                executor.submit(download, DOWNLOADS[name], paths[name])
                for name in DOWNLOADS
            ]
            for future in futures:
                future.result()

        assets_extract = temp / "assets-extract"
        assets_extract.mkdir()
        safe_extract(paths["assets"], assets_extract)

        staged = temp / "assets"
        shutil.copytree(find_asset_root(assets_extract), staged)

        card_paths = {
            "ot": staged / "ot" / "card" / "ot.json",
            "rd": staged / "rd" / "card" / "rd.json",
        }
        for name, card_path in card_paths.items():
            card_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths[name], card_path)

        required = [
            staged / "ot" / "font",
            staged / "ot" / "images",
            staged / "rd" / "font",
            staged / "rd" / "images",
            *card_paths.values(),
        ]
        missing = [str(path.relative_to(staged)) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("upstream assets are incomplete: " + ", ".join(missing))

        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(staged, destination)

    print(f"Prepared typst-ygo assets at {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    return parser.parse_args()


if __name__ == "__main__":
    prepare_assets(parse_args().destination)
