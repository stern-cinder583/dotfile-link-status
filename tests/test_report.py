import json
import unittest
from pathlib import Path

from dotlinks import LinkResult, LinkSpec, LinkState, format, format_json, format_text, to_dict


def make_result(name: str, state: LinkState, detail: str = "") -> LinkResult:
    spec = LinkSpec(name, Path("/src") / name, Path("/home") / f".{name}")
    return LinkResult(spec, state, detail)


class ReportTests(unittest.TestCase):
    def test_to_dict_fields(self):
        r = make_result("vimrc", LinkState.WRONG_TARGET, "points at /old/vimrc")
        self.assertEqual(
            to_dict(r),
            {
                "name": "vimrc",
                "source": "/src/vimrc",
                "target": "/home/.vimrc",
                "state": "wrong_target",
                "detail": "points at /old/vimrc",
            },
        )

    def test_text_aligns_columns_and_shows_detail(self):
        results = [
            make_result("gitconfig", LinkState.OK),
            make_result("vimrc", LinkState.WRONG_TARGET, "points at /old/vimrc"),
        ]
        self.assertEqual(
            format_text(results).splitlines(),
            [
                "gitconfig  ok",
                "vimrc      wrong  (points at /old/vimrc)",
            ],
        )

    def test_text_empty(self):
        self.assertEqual(format_text([]), "no dotfiles found")

    def test_json_round_trips(self):
        results = [make_result("a", LinkState.OK), make_result("b", LinkState.MISSING)]
        data = json.loads(format_json(results))
        self.assertEqual([d["state"] for d in data], ["ok", "missing"])

    def test_json_empty_is_a_list(self):
        self.assertEqual(json.loads(format_json([])), [])

    def test_format_dispatches_on_flag(self):
        results = [make_result("a", LinkState.OK)]
        self.assertEqual(format(results), format_text(results))
        self.assertEqual(format(results, as_json=True), format_json(results))


if __name__ == "__main__":
    unittest.main()
