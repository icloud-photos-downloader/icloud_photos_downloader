from unittest import TestCase

from foundation.core import constant
from foundation.json import apply_rules, compile_patterns


class AppleRuleTestCase(TestCase):
    def test_str_match(self) -> None:
        input = "abc"
        context = "def"
        rules = list(map(lambda p: (p, constant("hij")), compile_patterns([r"de.*"])))
        result = apply_rules(context, rules, input)
        self.assertEqual("hij", result, "match")

    def test_str_not_match(self) -> None:
        input = "abc"
        context = "def"
        rules = list(map(lambda p: (p, constant("hij")), compile_patterns([r"ae.*"])))
        result = apply_rules(context, rules, input)
        self.assertEqual("abc", result, "not match")

    def test_str_match_for_none(self) -> None:
        input = "abc"
        context = "def"
        rules = list(map(lambda p: (p, constant(None)), compile_patterns([r"de.*"])))
        result = apply_rules(context, rules, input)
        self.assertIsNone(result, "match for None")

    def test_tuple_match(self) -> None:
        input = ("abc", "def")
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r"abc.*"])))
        result = apply_rules("", rules, input)
        self.assertEqual(("abc", "lmn"), result, "tuple match")

    def test_list_match(self) -> None:
        input = ["abc", "def"]
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r".*"])))
        result = apply_rules("", rules, input)
        self.assertEqual("lmn", result, "list match")

    def test_list_match_each(self) -> None:
        input = ["abc", "def"]
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r"\..*"])))
        result = apply_rules("", rules, input)
        self.assertEqual(["lmn", "lmn"], result, "list match")

    def test_json_match(self) -> None:
        input = {"abc": {"def": "hij"}}
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r"abc\.def.*"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": {"def": "lmn"}}, result, "json match")

    def test_json_match_by_leaf(self) -> None:
        input = {"abc": {"def": "hij"}}
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r"def.*"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": {"def": "lmn"}}, result, "json match")

    def test_json_update_object_in_list(self) -> None:
        input = {"abc": [{"def": "hij"}]}
        rules = list(map(lambda p: (p, constant("lmn")), compile_patterns([r"^abc\.def$"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": [{"def": "lmn"}]}, result, "json match")

    def test_json_drop_object_in_list(self) -> None:
        input = {"abc": [{"def": "hij"}]}
        rules = list(map(lambda p: (p, constant(None)), compile_patterns([r"^abc\.$"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": []}, result, "json match")

    def test_json_dict_drop(self) -> None:
        input = {"abc": {"def": "hij"}}
        rules = list(map(lambda p: (p, constant(None)), compile_patterns([r"abc\.def.*"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": {}}, result, "json dict drop")

    def test_json_list_drop(self) -> None:
        input = {"abc": {"def": ["hij"]}}
        rules = list(map(lambda p: (p, constant(None)), compile_patterns([r"abc\.def\..*"])))
        result = apply_rules("", rules, input)
        self.assertDictEqual({"abc": {"def": []}}, result, "json list drop")
