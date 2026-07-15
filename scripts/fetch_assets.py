#!/usr/bin/env python3
"""Download and assemble the upstream typst-ygo workspace."""

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
DEFAULT_DESTINATION = PROJECT_ROOT / "vendor" / "typst-ygo"

DOWNLOADS = {
    "typst_ygo": "https://github.com/arshtyi/typst-ygo/archive/refs/heads/main.tar.gz",
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


def single_directory(path: Path, expected_name: str | None = None) -> Path:
    directories = [item for item in path.iterdir() if item.is_dir()]
    files = [item for item in path.iterdir() if item.is_file()]
    if expected_name:
        expected = path / expected_name
        if expected.is_dir():
            return expected
    if len(directories) != 1 or files:
        raise ValueError(f"expected one archive root directory in {path}")
    return directories[0]


def assemble(destination: Path = DEFAULT_DESTINATION) -> None:
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="ygo-lf-", dir=destination.parent) as temp_name:
        temp = Path(temp_name)
        downloads = temp / "downloads"
        downloads.mkdir()
        paths = {
            "typst_ygo": downloads / "typst-ygo.tar.gz",
            "assets": downloads / "assets.tar.xz",
            "ot": downloads / "ot.json",
            "rd": downloads / "rd.json",
        }

        print("Downloading typst-ygo, card data, and card assets...")
        with ThreadPoolExecutor(max_workers=len(DOWNLOADS)) as executor:
            futures = [
                executor.submit(download, DOWNLOADS[name], paths[name])
                for name in DOWNLOADS
            ]
            for future in futures:
                future.result()

        typst_extract = temp / "typst-extract"
        assets_extract = temp / "assets-extract"
        typst_extract.mkdir()
        assets_extract.mkdir()
        safe_extract(paths["typst_ygo"], typst_extract)
        safe_extract(paths["assets"], assets_extract)

        upstream_root = single_directory(typst_extract)
        staged = temp / "typst-ygo"
        shutil.copytree(upstream_root, staged)

        extracted_assets = assets_extract / "assets"
        if not extracted_assets.is_dir():
            if (assets_extract / "ot").is_dir() and (assets_extract / "rd").is_dir():
                extracted_assets = assets_extract
            else:
                extracted_assets = single_directory(assets_extract)
        shutil.copytree(extracted_assets, staged / "assets", dirs_exist_ok=True)

        card_paths = {
            "ot": staged / "assets" / "ot" / "card" / "ot.json",
            "rd": staged / "assets" / "rd" / "card" / "rd.json",
        }
        for name, card_path in card_paths.items():
            card_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths[name], card_path)

        required = [
            staged / "lib" / "mod.typ",
            staged / "assets" / "ot" / "images",
            staged / "assets" / "rd" / "images",
            *card_paths.values(),
        ]
        missing = [str(path.relative_to(staged)) for path in required if not path.exists()]
        if missing:
            raise FileNotFoundError("upstream workspace is incomplete: " + ", ".join(missing))

        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(staged, destination)

    print(f"Prepared typst-ygo workspace at {destination}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    return parser.parse_args()


if __name__ == "__main__":
    assemble(parse_args().destination)
