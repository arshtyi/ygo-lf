#!/usr/bin/env python3
"""Download the center artwork needed by the restricted-card previews."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

try:
    from .fetch_assets import PROJECT_ROOT
except ImportError:
    from fetch_assets import PROJECT_ROOT


IMAGE_URL = "https://images.ygoprodeck.com/images/cards_cropped/{image_id}.jpg"
DEFAULT_LIMITS = PROJECT_ROOT / "data" / "limits.json"
DEFAULT_WORKSPACE = PROJECT_ROOT / "vendor" / "typst-ygo"


def ordered_unique(values: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(values))


def required_image_ids(cards: list[dict[str, Any]], card_ids: Iterable[int], source: str) -> list[int]:
    index = {card.get("id"): card for card in cards if isinstance(card.get("id"), int)}
    images: list[int] = []
    for identifier in card_ids:
        card = index.get(identifier)
        if card is None:
            raise ValueError(f"{source} card is missing from JSON: {identifier}")
        image_id = card.get("image")
        if not isinstance(image_id, int):
            raise ValueError(f"{source} card {identifier} has an invalid image id: {image_id!r}")
        images.append(image_id)
    return ordered_unique(images)


def is_jpeg(path: Path) -> bool:
    try:
        with path.open("rb") as source:
            return source.read(2) == b"\xff\xd8"
    except OSError:
        return False


def download_image(image_id: int, destination: Path, timeout: float = 30.0) -> None:
    if is_jpeg(destination):
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    url = IMAGE_URL.format(image_id=image_id)
    request = urllib.request.Request(url, headers={"User-Agent": "ygo-lf-builder"})
    last_error: Exception | None = None

    for attempt in range(1, 4):
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                prefix=f".{image_id}.", suffix=".tmp", dir=destination.parent, delete=False
            ) as output:
                temporary = Path(output.name)
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    shutil.copyfileobj(response, output)
            if not is_jpeg(temporary):
                raise ValueError(f"download is not a JPEG: {url}")
            temporary.replace(destination)
            return
        except (OSError, ValueError, urllib.error.URLError) as error:
            last_error = error
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if attempt < 3:
                time.sleep(attempt)
    raise RuntimeError(f"failed to download center image {image_id}: {last_error}")


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def fetch_images(
    limits_path: Path = DEFAULT_LIMITS,
    workspace: Path = DEFAULT_WORKSPACE,
    workers: int = 8,
) -> None:
    if not 1 <= workers <= 32:
        raise ValueError("workers must be between 1 and 32")
    limits = load_json(limits_path)
    ot_cards = load_json(workspace / "assets" / "ot" / "card" / "ot.json")
    rd_cards = load_json(workspace / "assets" / "rd" / "card" / "rd.json")
    ot_card_ids = ordered_unique(
        identifier
        for market in ("ocg", "tcg")
        for group in limits[market]
        for identifier in group
    )
    rd_card_ids = ordered_unique(identifier for group in limits["rd"] for identifier in group)
    targets = {
        "ot": required_image_ids(ot_cards, ot_card_ids, "OT"),
        "rd": required_image_ids(rd_cards, rd_card_ids, "RD"),
    }

    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for environment, image_ids in targets.items():
            images_dir = workspace / "assets" / environment / "images"
            for image_id in image_ids:
                jobs.append(
                    executor.submit(download_image, image_id, images_dir / f"{image_id}.jpg")
                )
        failures = []
        for future in as_completed(jobs):
            try:
                future.result()
            except Exception as error:
                failures.append(str(error))
    if failures:
        details = "\n".join(f"- {failure}" for failure in failures[:10])
        raise RuntimeError(f"{len(failures)} center image download(s) failed:\n{details}")

    print(
        f"Downloaded center images: OT={len(targets['ot'])}, RD={len(targets['rd'])}"
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limits", type=Path, default=DEFAULT_LIMITS)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    fetch_images(arguments.limits, arguments.workspace, arguments.workers)
