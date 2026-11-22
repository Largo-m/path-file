"""Tests for rules engine."""

from __future__ import annotations

from pathlib import Path

import path_file as pf
from path_file.rules import Rule, Rules


class TestRuleParsing:
    """Test rule parsing from TOML."""

    def test_parse_simple_rule(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.tmp"
action = "delete"
"""
        rules = Rules.from_string(content)

        assert len(rules.rules) == 1
        rule = rules.rules[0]
        assert rule.match == "*.tmp"
        assert rule.action == "delete"

    def test_parse_rule_with_conditions(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.jpg"
when_larger_than = "10MB"
when_older_than = "30 days"
action = "move"
dest = "~/Archive"
"""
        rules = Rules.from_string(content)

        assert len(rules.rules) == 1
        rule = rules.rules[0]
        assert rule.match == "*.jpg"
        assert any("when_larger_than" in c for c in rule.when)
        assert any("when_older_than" in c for c in rule.when)
        assert rule.action == "move"
        assert rule.dest == "~/Archive"

    def test_parse_multiple_rules(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.tmp"
action = "delete"

[[rule]]
match = "*.log"
action = "archive"
dest = "~/Logs"
"""
        rules = Rules.from_string(content)

        assert len(rules.rules) == 2
        assert rules.rules[0].match == "*.tmp"
        assert rules.rules[1].match == "*.log"

    def test_parse_rule_from_file(self, rules_file: Path):
        rules = Rules.from_file(rules_file)

        assert len(rules.rules) >= 1
        for rule in rules.rules:
            assert rule.match
            assert rule.action


class TestRuleMatching:
    """Test rule matching logic."""

    def test_rule_matches_glob(self, tmp_dir: Path):
        rule = Rule(match="*.txt", action="delete")

        (tmp_dir / "test.txt").write_text("text")
        (tmp_dir / "test.jpg").write_text("image")

        entry = pf.Entry.from_path(tmp_dir / "test.txt")
        assert rule.matches(entry) is True

        entry = pf.Entry.from_path(tmp_dir / "test.jpg")
        assert rule.matches(entry) is False

    def test_rule_matches_size_condition(self, tmp_dir: Path):
        # Create a file
        f = tmp_dir / "large.txt"
        f.write_text("x" * 10000)  # ~10KB

        rule = Rule(match="*.txt", when=["size > 1KB"], action="delete")
        entry = pf.Entry.from_path(f)

        assert rule.matches(entry) is True

    def test_rule_matches_age_condition(self, tmp_dir: Path):
        f = tmp_dir / "old.txt"
        f.write_text("content")

        rule = Rule(match="*.txt", when=["age > 1 hour"], action="delete")
        entry = pf.Entry.from_path(f)

        # Fresh file, should not match age condition
        assert rule.matches(entry) is False


class TestRulesApply:
    """Test applying rules to FileChain."""

    def test_apply_rules_to_chain(self, tmp_dir: Path):
        # Create test files
        (tmp_dir / "file1.tmp").write_text("temp")
        (tmp_dir / "file2.tmp").write_text("temp")
        (tmp_dir / "keep.txt").write_text("keep")

        rules_content = """
[[rule]]
match = "*.tmp"
action = "delete"
"""
        rules = Rules.from_string(rules_content)
        chain = pf.find(tmp_dir).files()

        result_chain = rules.apply(chain)

        # Should only have .tmp files (matched by rule)
        entries = result_chain.to_list()
        assert all(e.name.endswith(".tmp") for e in entries)
        assert len(entries) == 2

    def test_first_rule_wins(self, tmp_dir: Path):
        (tmp_dir / "test.tmp").write_text("temp")

        rules_content = """
[[rule]]
match = "*.tmp"
action = "delete"

[[rule]]
match = "*.tmp"
action = "archive"
dest = "~/Archive"
"""
        rules = Rules.from_string(rules_content)
        chain = pf.find(tmp_dir).files()

        result_chain = rules.apply(chain)
        entries = result_chain.to_list()

        assert len(entries) == 1
        # First rule should win
        assert entries[0]._rule_action == "delete"


class TestRulesValidation:
    """Test rule validation."""

    def test_validate_valid_rules(self, rules_file: Path):
        rules = Rules.from_file(rules_file)
        errors = rules.validate()

        assert len(errors) == 0

    def test_validate_missing_dest(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.jpg"
action = "move"
"""
        rules = Rules.from_string(content)
        errors = rules.validate()

        assert any("requires 'dest'" in e for e in errors)

    def test_validate_invalid_action(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.txt"
action = "invalid_action"
"""
        rules = Rules.from_string(content)
        errors = rules.validate()

        assert any("Invalid action" in e for e in errors)

    def test_validate_missing_pattern_for_rename(self, tmp_dir: Path):
        content = """
[[rule]]
match = "*.txt"
action = "rename"
"""
        rules = Rules.from_string(content)
        errors = rules.validate()

        assert any("requires 'pattern'" in e for e in errors)


class TestRulesExplain:
    """Test rules explanation."""

    def test_explain_output(self, rules_file: Path):
        rules = Rules.from_file(rules_file)
        explanation = rules.explain()

        assert "Rules:" in explanation
        assert "Match:" in explanation
        assert "Action:" in explanation
        assert "Dry-run:" in explanation


class TestRulesFromDict:
    """Test creating rules from dictionary."""

    def test_from_dict(self, tmp_dir: Path):
        data = {
            "rules": [
                {"match": "*.tmp", "action": "delete"},
                {"match": "*.log", "action": "move", "dest": "~/Logs"},
            ]
        }

        rules = Rules.from_dict(data)

        assert len(rules.rules) == 2
        assert rules.rules[0].action == "delete"
        assert rules.rules[1].dest == "~/Logs"
