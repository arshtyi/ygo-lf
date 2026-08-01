#!/usr/bin/env python3
"""Extract forbidden/limited IDs from upstream card data."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from paths import LIMITS_FILE, TYPST_WORKSPACE

DEFAULT_OT = TYPST_WORKSPACE / "assets" / "ot" / "card" / "ot.json"
DEFAULT_RD = TYPST_WORKSPACE / "assets" / "rd" / "card" / "rd.json"
CARD_KIND_ORDER = {"怪兽": 0, "魔法": 1, "陷阱": 2}


def load_cards(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as source:
        cards = json.load(source)
    if not isinstance(cards, list) or not all(isinstance(card, dict) for card in cards):
        raise ValueError(f"expected a JSON array of cards in {path}")
    return cards


def card_id(card: dict[str, Any], source: str) -> int:
    value = card.get("id")
    if not isinstance(value, int):
        raise ValueError(f"{source} card has an invalid id: {value!r}")
    return value


def limit_value(value: Any, source: str, identifier: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value not in range(4):
        raise ValueError(f"{source} card {identifier} has an invalid lf value: {value!r}")
    return value


def card_type_key(
    card: dict[str, Any], source: str, identifier: int
) -> tuple[int, tuple[str, ...]]:
    value = card.get("type")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(part, str) and part for part in value)
    ):
        raise ValueError(f"{source} card {identifier} has an invalid type: {value!r}")
    parts = tuple(value)
    if parts[0] == "怪兽":
        if len(parts) < 3:
            raise ValueError(f"{source} card {identifier} has an invalid type: {value!r}")
        # Monster types are [kind, race, categories...]. Compare categories
        # before race so Fusion/Synchro/Xyz/etc. cards stay together.
        details = parts[2:] + parts[1:2]
    else:
        details = parts[1:]
    return CARD_KIND_ORDER.get(parts[0], len(CARD_KIND_ORDER)), details


def sorted_group_ids(
    groups: list[list[tuple[tuple[int, tuple[str, ...]], int]]],
) -> list[list[int]]:
    return [
        [identifier for _, identifier in sorted(group, key=lambda item: item[0])]
        for group in groups
    ]


def extract_ot(
    cards: list[dict[str, Any]],
    ignore_aliases: bool = True,
) -> tuple[list[list[int]], list[list[int]]]:
    ocg = [[], [], []]
    tcg = [[], [], []]
    for card in cards:
        if ignore_aliases and card.get("alias") != 0:
            continue
        identifier = card_id(card, "OT")
        limits = card.get("lf")
        if not isinstance(limits, list) or len(limits) != 2:
            raise ValueError(f"OT card {identifier} must have two lf values")
        type_key = None
        for groups, raw_value, market in zip((ocg, tcg), limits, ("OCG", "TCG"), strict=True):
            value = limit_value(raw_value, market, identifier)
            if value < 3:
                if type_key is None:
                    type_key = card_type_key(card, "OT", identifier)
                groups[value].append((type_key, identifier))
    return sorted_group_ids(ocg), sorted_group_ids(tcg)


def extract_rd(cards: list[dict[str, Any]], ignore_aliases: bool = True) -> list[list[int]]:
    rd = [[], [], []]
    for card in cards:
        if ignore_aliases and card.get("alias") != 0:
            continue
        identifier = card_id(card, "RD")
        value = limit_value(card.get("lf"), "RD", identifier)
        if value < 3:
            rd[value].append((card_type_key(card, "RD", identifier), identifier))
    return sorted_group_ids(rd)


def build_limits(
    ot_path: Path = DEFAULT_OT,
    rd_path: Path = DEFAULT_RD,
    output: Path = LIMITS_FILE,
    ignore_aliases: bool = True,
) -> dict[str, list[list[int]]]:
    ocg, tcg = extract_ot(load_cards(ot_path), ignore_aliases=ignore_aliases)
    result = {
        "ocg": ocg,
        "tcg": tcg,
        "rd": extract_rd(load_cards(rd_path), ignore_aliases=ignore_aliases),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2)
        destination.write("\n")
    print(
        "Extracted limits: "
        + ", ".join(
            f"{market.upper()}={len(groups[0])}/{len(groups[1])}/{len(groups[2])}"
            for market, groups in result.items()
        )
    )
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ot", type=Path, default=DEFAULT_OT)
    parser.add_argument("--rd", type=Path, default=DEFAULT_RD)
    parser.add_argument("--output", type=Path, default=LIMITS_FILE)
    parser.add_argument(
        "--ignore-aliases",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="ignore alternate-art cards whose alias is not 0 (default: true)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_limits(
        arguments.ot,
        arguments.rd,
        arguments.output,
        ignore_aliases=arguments.ignore_aliases,
    )
