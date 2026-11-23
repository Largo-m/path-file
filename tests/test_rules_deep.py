"""Deep tests for the TOML rules engine."""

from __future__ import annotations

from pathlib import Path

import pytest

import path_file as pf
from path_file.exceptions import PathflowError
from path_file.rules import Rule, Rules


def _tree(tmp_dir: Path) -> Path:
    (tmp_dir / "old.tmp").write_text("tmp data")
    (tmp_dir / "keep.txt").write_text("keep me")
    (tmp_dir / "big.bin").write_bytes(b"x" * (2 * 1024 * 1024))
    (tmp_dir / "note.log").write_text("log entry")
    (tmp_dir / "sub").mkdir()
    (tmp_dir / "sub" / "deep.tmp").write_text("deep tmp")
    return tmp_dir


RULES_TOML = """
[[rule]]
match = "*.tmp"
action = "delete"
confirm = true

[[rule]]
match = "*.bin"
when_larger_than = "1MB"
action = "move"
dest = "big"
confirm = true
"""


class TestRulesParsing:
    def test_parse_valid(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text(RULES_TOML)
        rules = Rules.from_file(path)
        assert len(rules) == 2
        assert rules.validate() == []

    def test_rule_fields(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text(RULES_TOML)
        rules = Rules.from_file(path)
        first = rules.rules[0]
        assert first.match == "*.tmp"
        assert first.action == "delete"
        assert first.confirm is True

    def test_parse_empty_errors(self, tmp_dir):
        path = tmp_dir / "empty.toml"
        path.write_text("")
        rules = Rules.from_file(path)
        errors = rules.validate()
        assert errors

    def test_parse_missing_file(self, tmp_dir):
        with pytest.raises((PathflowError, OSError)):
            Rules.from_file(tmp_dir / "nope.toml")

    def test_from_string(self):
        rules = Rules.from_string(RULES_TOML)
        assert len(rules) == 2

    def test_iteration(self, tmp_dir):
        path = tmp_dir / "rules.toml"
        path.write_text(RULES_TOML)
        assert len(list(Rules.from_file(path))) == 2


class TestRulesValidation:
    def test_missing_action_defaults_to_none(self, tmp_dir):
        path = tmp_dir / "bad.toml"
        path.write_text('[[rule]]\nmatch = "*.tmp"\n')
        rules = Rules.from_file(path)
        assert rules.rules[0].action == "none"

    def test_missing_match_defaults_to_star(self, tmp_dir):
        path = tmp_dir / "bad2.toml"
        path.write_text('[[rule]]\naction = "delete"\n')
        rules = Rules.from_file(path)
        assert rules.rules[0].match == "*"


class TestRulesExecution:
    def test_delete_rule(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.tmp"\naction = "delete"\nconfirm = true\n')
        rules = Rules.from_file(path)
        chain = pf.find(tmp_dir).files()
        results = rules.run(chain, dry_run=False)
        assert results
        assert not (tmp_dir / "old.tmp").exists()

    def test_dry_run_default(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.tmp"\naction = "delete"\nconfirm = true\n')
        rules = Rules.from_file(path)
        results = rules.run(pf.find(tmp_dir).files())
        assert results
        assert (tmp_dir / "old.tmp").exists()

    def test_move_rule(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.bin"\naction = "move"\ndest = "moved"\nconfirm = true\n'
        )
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "moved" / "big.bin").exists()

    def test_copy_rule(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "copy"\ndest = "copied"\n')
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "copied" / "note.log").exists()

    def test_rename_rule(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "rename"\npattern = "renamed.log"\n')
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "renamed.log").exists()

    def test_archive_rule(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.log"\naction = "archive"\ndest = "logs.zip"\n')
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "logs.zip").exists()

    def test_when_larger_than(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.bin"\nwhen_larger_than = "1MB"\n'
            'action = "delete"\nconfirm = true\n'
        )
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert not (tmp_dir / "big.bin").exists()

    def test_when_smaller_than(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.bin"\nwhen_smaller_than = "1KB"\n'
            'action = "delete"\nconfirm = true\n'
        )
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "big.bin").exists()  # too big, rule skipped

    def test_when_newer_than(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.tmp"\nwhen_newer_than = "1 hour"\n'
            'action = "delete"\nconfirm = true\n'
        )
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert not (tmp_dir / "old.tmp").exists()

    def test_when_older_than_skips(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text(
            '[[rule]]\nmatch = "*.tmp"\nwhen_older_than = "7 days"\n'
            'action = "delete"\nconfirm = true\n'
        )
        rules = Rules.from_file(path)
        rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert (tmp_dir / "old.tmp").exists()  # fresh file not older than 7 days

    def test_no_match_no_action(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        path.write_text('[[rule]]\nmatch = "*.nothing"\naction = "delete"\nconfirm = true\n')
        rules = Rules.from_file(path)
        results = rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert results == [] or all(r.get("count", 0) == 0 for r in results)

    def test_error_collection(self, tmp_dir):
        _tree(tmp_dir)
        path = tmp_dir / "rules.toml"
        # delete without confirm on a real match -> refused, reported as error
        path.write_text('[[rule]]\nmatch = "*.tmp"\naction = "delete"\n')
        rules = Rules.from_file(path)
        results = rules.run(pf.find(tmp_dir).files(), dry_run=False)
        assert results
        assert (tmp_dir / "old.tmp").exists()


class TestRuleObject:
    def test_rule_defaults(self):
        rule = Rule(match="*.tmp", action="delete")
        assert rule.confirm is False
        assert rule.dry_run is True
        assert rule.overwrite is False

    def test_rule_to_dict(self):
        rule = Rule(match="*.tmp", action="delete")
        data = rule.to_dict()
        assert data["match"] == "*.tmp"
        assert data["action"] == "delete"
