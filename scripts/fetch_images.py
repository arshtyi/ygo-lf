#!/usr/bin/env python3
"""Download the center artwork needed by the restricted-card previews."""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from downloads import download_file
from paths import LIMITS_FILE, TYPST_WORKSPACE


IMAGE_URL = "https://images.ygoprodeck.com/images/cards_cropped/{image_id}.jpg"


def ordered_unique(values: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(values))


def required_image_ids(
    cards: list[dict[str, Any]], card_ids: Iterable[int], source: str
) -> list[int]:
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
    url = IMAGE_URL.format(image_id=image_id)
    download_file(url, destination, timeout=timeout, validator=is_jpeg)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def fetch_images(
    limits_path: Path = LIMITS_FILE,
    workspace: Path = TYPST_WORKSPACE,
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
    parser.add_argument("--limits", type=Path, default=LIMITS_FILE)
    parser.add_argument("--workspace", type=Path, default=TYPST_WORKSPACE)
    parser.add_argument("--workers", type=int, default=8)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    fetch_images(arguments.limits, arguments.workspace, arguments.workers)
