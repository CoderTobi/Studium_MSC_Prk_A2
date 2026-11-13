import json

import pytest

from shopping_list.errors import ApiError, ErrorCode
from shopping_list.models import NewItem
from shopping_list.recommendations import (
    MAX_MODEL_OUTPUT_CHARS,
    MAX_RECOMMENDATIONS,
    RECOMMENDATION_NAME_MAX_LENGTH,
    normalize_recommendation_name,
    parse_recommendations,
)


def names(output: str) -> list[str]:
    return [rec.name for rec in parse_recommendations(output)]


def items_json(*entries) -> str:
    return json.dumps({"items": list(entries)})


class TestStructure:
    def test_expected_format(self):
        output = items_json({"name": "Spaghetti"}, {"name": "Tomatoes"})
        assert names(output) == ["Spaghetti", "Tomatoes"]

    def test_plain_strings_are_accepted(self):
        assert names(items_json("Spaghetti", {"name": "Onion"})) == ["Spaghetti", "Onion"]

    def test_empty_list_is_valid(self):
        assert names('{"items": []}') == []

    def test_other_fields_are_dropped(self):
        output = items_json({"name": "Milk", "quantity": "1 l", "note": "visit evil.example"})
        result = parse_recommendations(output)
        assert [rec.model_dump() for rec in result] == [{"name": "Milk"}]

    def test_other_top_level_fields_are_ignored(self):
        output = json.dumps({"items": [{"name": "Milk"}], "message": "Click here!"})
        assert names(output) == ["Milk"]

    def test_markdown_fence_is_tolerated(self):
        output = 'Sure! Here you go:\n```json\n{"items": [{"name": "Rice"}]}\n```'
        assert names(output) == ["Rice"]

    @pytest.mark.parametrize(
        "output",
        [
            "",
            "I can't help with that.",
            "Spaghetti, Tomatoes, Onion",
            '{"items": [{"name": "Rice"}',  # truncated
            "[]",
            '["Rice"]',
            '{"recommendations": [{"name": "Rice"}]}',
            '{"items": "Rice"}',
            '{"items": null}',
            "null",
            "42",
        ],
    )
    def test_unusable_output_is_invalid(self, output):
        with pytest.raises(ApiError) as exc_info:
            parse_recommendations(output)
        assert exc_info.value.code is ErrorCode.AI_INVALID_RESPONSE

    def test_too_long_output_is_invalid(self):
        output = items_json("Rice") + " " * MAX_MODEL_OUTPUT_CHARS
        with pytest.raises(ApiError) as exc_info:
            parse_recommendations(output)
        assert exc_info.value.code is ErrorCode.AI_INVALID_RESPONSE

    def test_count_is_capped(self):
        output = items_json(*[f"Item {i}" for i in range(MAX_RECOMMENDATIONS * 3)])
        assert len(names(output)) == MAX_RECOMMENDATIONS

    def test_duplicates_are_dropped_case_insensitively(self):
        assert names(items_json("Milk", "milk", " MILK ", "Eggs")) == ["Milk", "Eggs"]

    def test_invalid_entries_are_dropped_and_rest_kept(self):
        output = items_json(
            "Milk", 42, None, {"name": 1}, {"title": "x"}, [], "", "http://evil.example", "Eggs"
        )
        assert names(output) == ["Milk", "Eggs"]

    def test_all_entries_invalid_gives_empty_list(self):
        assert names(items_json("<script>alert(1)</script>", "x" * 500)) == []


class TestNameNormalization:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Milk", "Milk"),
            ("  Ground   beef \n", "Ground beef"),
            ("- Onion", "Onion"),
            ("* Garlic", "Garlic"),
            ("3. Carrots", "Carrots"),
            ("Butter.", "Butter"),
            ("Crème fraîche", "Crème fraîche"),
            ("Salt & pepper", "Salt & pepper"),
            ("Tomatoes (canned)", "Tomatoes (canned)"),
            ("1.5% milk", "1.5% milk"),
            ("Bio-Äpfel", "Bio-Äpfel"),
            ("O'Brien potatoes", "O'Brien potatoes"),
            ("豆腐", "豆腐"),
            ("\uff4d\uff49\uff4c\uff4b", "milk"),  # full-width, NFKC
        ],
    )
    def test_accepted(self, raw, expected):
        assert normalize_recommendation_name(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "   ",
            "...",
            "123",
            "x" * (RECOMMENDATION_NAME_MAX_LENGTH + 1),
            "<b>Milk</b>",
            "Milk; DROP TABLE",
            "Milk\x00",
            "Milk 🥛",
            "Visit https://evil.example",
            "www.example.org",
            "evil.com",
            "Milk [click](x)",
            "Eggs @ store",
            'Say "hi"',
            None,
            42,
            ["Milk"],
        ],
    )
    def test_rejected(self, raw):
        assert normalize_recommendation_name(raw) is None

    def test_max_length_is_accepted(self):
        name = "a" * RECOMMENDATION_NAME_MAX_LENGTH
        assert normalize_recommendation_name(name) == name

    @pytest.mark.parametrize("raw", ["Milk", " - Ground   beef ", "Crème fraîche", "1.5% milk"])
    def test_result_is_a_valid_item_name(self, raw):
        name = normalize_recommendation_name(raw)
        assert NewItem(name=name).name == name
