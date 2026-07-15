from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_limits import build_limits, extract_ot
from scripts.fetch_images import required_image_ids
from scripts.render_cards import ordered_unique, typst_source


class BuildLimitsTests(unittest.TestCase):
    def test_extracts_original_cards_into_three_limit_groups(self) -> None:
        ot_cards = [
            {"id": 10, "alias": 0, "type": ["怪兽", "龙族", "效果"], "lf": [0, 3]},
            {"id": 20, "alias": 0, "type": ["魔法"], "lf": [1, 2]},
            {"id": 30, "alias": 0, "type": ["陷阱"], "lf": [2, 1]},
            {"id": 40, "alias": 0, "lf": [3, 3]},
            {"id": 41, "alias": 40, "lf": [0, 0]},
        ]
        rd_cards = [
            {"id": 50, "alias": 0, "type": ["怪兽", "龙族", "效果"], "lf": 0},
            {"id": 60, "alias": 0, "type": ["魔法"], "lf": 1},
            {"id": 70, "alias": 0, "type": ["陷阱"], "lf": 2},
            {"id": 80, "alias": 0, "lf": 3},
            {"id": 81, "alias": 80, "lf": 0},
        ]

        with tempfile.TemporaryDirectory() as temp_name:
            temp = Path(temp_name)
            ot_path = temp / "ot.json"
            rd_path = temp / "rd.json"
            output = temp / "limits.json"
            ot_path.write_text(json.dumps(ot_cards), encoding="utf-8")
            rd_path.write_text(json.dumps(rd_cards), encoding="utf-8")

            result = build_limits(ot_path, rd_path, output)

            self.assertEqual(result["ocg"], [[10], [20], [30]])
            self.assertEqual(result["tcg"], [[], [30], [20]])
            self.assertEqual(result["rd"], [[50], [60], [70]])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_sorts_by_type_category_before_monster_race(self) -> None:
        cards = [
            {"id": 10, "alias": 0, "type": ["陷阱", "永续"], "lf": [0, 1]},
            {"id": 20, "alias": 0, "type": ["怪兽", "龙族", "效果"], "lf": [0, 1]},
            {"id": 30, "alias": 0, "type": ["魔法", "速攻"], "lf": [0, 1]},
            {"id": 40, "alias": 0, "type": ["怪兽", "战士族", "效果"], "lf": [0, 1]},
            {"id": 50, "alias": 0, "type": ["魔法"], "lf": [0, 1]},
            {"id": 60, "alias": 0, "type": ["怪兽", "不死族", "融合", "效果"], "lf": [0, 1]},
            {"id": 70, "alias": 0, "type": ["怪兽", "战士族", "融合", "效果"], "lf": [0, 1]},
        ]

        ocg, tcg = extract_ot(cards)

        self.assertEqual(ocg[0], [40, 20, 60, 70, 50, 30, 10])
        self.assertEqual(tcg[1], [40, 20, 60, 70, 50, 30, 10])

    def test_rejects_malformed_ot_limits(self) -> None:
        with self.assertRaisesRegex(ValueError, "must have two lf values"):
            extract_ot([{"id": 10, "alias": 0, "lf": [0]}])

    def test_rejects_out_of_range_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid lf value"):
            extract_ot([{"id": 10, "alias": 0, "lf": [4, 3]}])

    def test_rejects_malformed_card_type(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid type"):
            extract_ot([{"id": 10, "alias": 0, "type": "怪兽", "lf": [0, 3]}])
        with self.assertRaisesRegex(ValueError, "invalid type"):
            extract_ot([{"id": 10, "alias": 0, "type": ["怪兽", "龙族"], "lf": [0, 3]}])

    def test_preview_ids_are_unique_and_stable(self) -> None:
        self.assertEqual(ordered_unique(([10, 20], [20, 30], [10])), [10, 20, 30])

    def test_preview_source_uses_typst_ygo(self) -> None:
        source = typst_source("ot", [10, 20])
        self.assertIn('import "/vendor/typst-ygo/lib/mod.typ"', source)
        self.assertIn("ot_card_by_id", source)
        self.assertIn("#let ids = (10, 20,)", source)

    def test_center_images_follow_card_image_ids(self) -> None:
        cards = [
            {"id": 10, "image": 100},
            {"id": 20, "image": 200},
            {"id": 30, "image": 100},
        ]
        self.assertEqual(required_image_ids(cards, [20, 10, 30], "OT"), [200, 100])


if __name__ == "__main__":
    unittest.main()
