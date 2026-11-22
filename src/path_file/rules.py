"""Declarative rules engine for file automation."""

from __future__ import annotations

import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from path_file.chain import FileChain
from path_file.entries import Entry
from path_file.units import parse_duration, parse_size

# ──────────────────────────────────────────────────────────────────────────────
# MINIMAL TOML PARSER (stdlib compatible for Python 3.10+)
# ──────────────────────────────────────────────────────────────────────────────


class SimpleTomlParser:
    """Minimal TOML parser for rules files - supports only what we need."""

    def __init__(self) -> None:
        self.rules: list[dict[str, Any]] = []
        self.current_rule: dict[str, Any] = {}
        self.line_num = 0

    def parse(self, content: str) -> list[dict[str, Any]]:
        """Parse TOML content and return list of rule dicts."""
        self.rules = []
        self.current_rule = {}

        for line_num, line in enumerate(content.splitlines(), 1):
            self.line_num = line_num
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if line.startswith("[["):
                # Save previous rule
                if self.current_rule:
                    self.rules.append(self.current_rule)
                self.current_rule = {}
                continue

            # Key = value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()
                self.current_rule[key] = self._parse_value(value)

        # Save last rule
        if self.current_rule:
            self.rules.append(self.current_rule)

        return self.rules

    def _parse_value(self, value: str) -> Any:
        """Parse TOML value."""
        # String
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]

        # Boolean
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False

        # Number
        try:
            if "." in value:
                return float(value)
            return int(value)
        except ValueError:
            pass

        # Date/time (basic support)
        # Return as string for now
        return value


# ──────────────────────────────────────────────────────────────────────────────
# RULE DEFINITION
# ──────────────────────────────────────────────────────────────────────────────


@dataclass
class Rule:
    """Single automation rule."""

    match: str = "*"  # Glob pattern
    when: list[str] = field(default_factory=list)  # Conditions
    action: str = "none"  # delete, move, copy, archive, compress, rename
    dest: str | None = None  # Destination for move/copy/archive
    pattern: str | None = None  # For rename action
    overwrite: bool = False
    confirm: bool = False
    dry_run: bool = True  # Safe by default

    def matches(self, entry: Entry) -> bool:
        """Check if entry matches this rule's conditions."""
        # Check glob pattern
        import fnmatch

        if not fnmatch.fnmatch(entry.name, self.match):
            return False

        # Check conditions
        return all(self._check_condition(entry, condition) for condition in self.when)

    def _check_condition(self, entry: Entry, condition: str) -> bool:
        """Evaluate a single condition string."""
        # Format: "key operator value" or "key=value"
        # Examples: "size > 1MB", "age > 7 days", "name contains 'temp'"

        # Try to parse as key=value
        if "=" in condition and not any(op in condition for op in [">", "<", ">=", "<="]):
            key, value = condition.split("=", 1)
            key = key.strip()
            value = value.strip().strip("\"'")
            return self._check_equality(entry, key, value)

        # Parse comparison
        for op in [">=", "<=", ">", "<", "!="]:
            if op in condition:
                key, value = condition.split(op, 1)
                key = key.strip()
                value = value.strip().strip("\"'")
                return self._check_comparison(entry, key, op, value)

        return True

    def _check_equality(self, entry: Entry, key: str, value: str) -> bool:
        """Check equality condition."""
        if key == "extension" or key == "ext":
            return entry.suffix.lower() == value.lower()
        if key == "name":
            return entry.name.lower() == value.lower()
        if key == "type":
            if value == "file":
                return entry.is_file
            if value == "dir":
                return entry.is_dir
            if value == "symlink":
                return entry.is_symlink
        return False

    def _check_comparison(self, entry: Entry, key: str, op: str, value: str) -> bool:
        """Check comparison condition."""
        # Get entry value
        entry_val = self._get_entry_value(entry, key)
        if entry_val is None:
            return False

        # Parse condition value
        cond_val = self._parse_condition_value(key, value)
        if cond_val is None:
            return False

        # Compare
        comparisons: dict[str, Callable[[Any, Any], bool]] = {
            ">": operator.gt,
            "<": operator.lt,
            ">=": operator.ge,
            "<=": operator.le,
            "!=": operator.ne,
        }
        compare = comparisons.get(op)
        if compare is None:
            return False

        return compare(entry_val, cond_val)

    def _get_entry_value(self, entry: Entry, key: str) -> Any:
        """Get comparable value from entry."""
        key = key.lower()
        if key in ("size", "filesize"):
            return entry.size
        if key in ("age", "modified_age", "mtime_age"):
            return (datetime.now() - entry.modified).total_seconds()
        if key in ("created_age", "ctime_age"):
            return (datetime.now() - entry.created).total_seconds()
        if key in ("name", "filename"):
            return entry.name.lower()
        if key in ("extension", "ext"):
            return entry.suffix.lower()
        return None

    def _parse_condition_value(self, key: str, value: str) -> Any:
        """Parse condition value based on key type."""
        key = key.lower()
        if key in ("size", "filesize"):
            return parse_size(value)
        if key in ("age", "modified_age", "mtime_age", "created_age", "ctime_age"):
            return parse_duration(value).total_seconds()
        return value.lower()


# ──────────────────────────────────────────────────────────────────────────────
# RULES COLLECTION
# ──────────────────────────────────────────────────────────────────────────────


class Rules:
    """Collection of automation rules."""

    def __init__(self, rules: list[Rule]) -> None:
        self.rules = rules

    @classmethod
    def from_file(cls, path: str | Path) -> Rules:
        """Load rules from TOML file."""
        path = Path(path)
        content = path.read_text(encoding="utf-8")
        return cls.from_string(content)

    @classmethod
    def from_string(cls, content: str) -> Rules:
        """Parse rules from TOML string."""
        parser = SimpleTomlParser()
        rule_dicts = parser.parse(content)

        rules = []
        for rd in rule_dicts:
            # Handle special when_* keys
            when_conditions = rd.get("when", [])
            if isinstance(when_conditions, str):
                when_conditions = [when_conditions]
            if "when_larger_than" in rd:
                when_conditions.append(f"when_larger_than: {rd['when_larger_than']}")
            if "when_older_than" in rd:
                when_conditions.append(f"when_older_than: {rd['when_older_than']}")
            if "when_smaller_than" in rd:
                when_conditions.append(f"when_smaller_than: {rd['when_smaller_than']}")
            if "when_newer_than" in rd:
                when_conditions.append(f"when_newer_than: {rd['when_newer_than']}")

            rule = Rule(
                match=rd.get("match", "*"),
                when=when_conditions,
                action=rd.get("action", "none"),
                dest=rd.get("dest"),
                pattern=rd.get("pattern"),
                overwrite=rd.get("overwrite", False),
                confirm=rd.get("confirm", False),
                dry_run=rd.get("dry_run", True),
            )
            rules.append(rule)

        return cls(rules)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Rules:
        """Create rules from dictionary."""
        rules = []
        for rd in data.get("rules", []):
            # Handle special when_* keys
            when_conditions = rd.get("when", [])
            if "when_larger_than" in rd:
                when_conditions.append(f"when_larger_than: {rd['when_larger_than']}")
            if "when_older_than" in rd:
                when_conditions.append(f"when_older_than: {rd['when_older_than']}")
            if "when_smaller_than" in rd:
                when_conditions.append(f"when_smaller_than: {rd['when_smaller_than']}")
            if "when_newer_than" in rd:
                when_conditions.append(f"when_newer_than: {rd['when_newer_than']}")

            rule = Rule(
                match=rd.get("match", "*"),
                when=when_conditions,
                action=rd.get("action", "none"),
                dest=rd.get("dest"),
                pattern=rd.get("pattern"),
                overwrite=rd.get("overwrite", False),
                confirm=rd.get("confirm", False),
                dry_run=rd.get("dry_run", True),
            )
            rules.append(rule)
        return cls(rules)

    def apply(self, chain: FileChain) -> FileChain:
        """
        Apply rules to a file chain.

        Returns a new chain with matched entries tagged for action.
        """
        # This is a placeholder - actual implementation would tag entries
        # For now, we return a filtered chain
        matched_entries = []
        for entry in chain:
            for rule in self.rules:
                if rule.matches(entry):
                    # Tag entry with action
                    entry._rule_action = rule.action
                    entry._rule_dest = rule.dest
                    entry._rule_params = {
                        "pattern": rule.pattern,
                        "overwrite": rule.overwrite,
                        "confirm": rule.confirm,
                        "dry_run": rule.dry_run,
                    }
                    matched_entries.append(entry)
                    break  # First matching rule wins

        return FileChain.from_entries(matched_entries)

    def validate(self) -> list[str]:
        """Validate rules and return list of errors."""
        errors = []
        for i, rule in enumerate(self.rules):
            # Check action is valid
            valid_actions = {
                "none",
                "delete",
                "move",
                "copy",
                "archive",
                "compress",
                "rename",
                "trash",
            }
            if rule.action not in valid_actions:
                errors.append(f"Rule {i}: Invalid action '{rule.action}'")

            # Check required fields
            if rule.action in ("move", "copy", "archive") and not rule.dest:
                errors.append(f"Rule {i}: Action '{rule.action}' requires 'dest'")

            if rule.action == "rename" and not rule.pattern:
                errors.append(f"Rule {i}: Action 'rename' requires 'pattern'")

            # Validate glob pattern
            try:
                import fnmatch

                fnmatch.fnmatch("test", rule.match)
            except Exception as e:
                errors.append(f"Rule {i}: Invalid match pattern: {e}")

        return errors

    def explain(self) -> str:
        """Human-readable description of rules."""
        lines = ["Rules:"]
        for i, rule in enumerate(self.rules, 1):
            lines.append(f"  {i}. Match: {rule.match}")
            if rule.when:
                lines.append(f"     When: {', '.join(rule.when)}")
            lines.append(f"     Action: {rule.action}")
            if rule.dest:
                lines.append(f"     Dest: {rule.dest}")
            if rule.pattern:
                lines.append(f"     Pattern: {rule.pattern}")
            lines.append(f"     Dry-run: {rule.dry_run}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────────
# RULE EXECUTION HELPERS
# ──────────────────────────────────────────────────────────────────────────────


def execute_rules(chain: FileChain, rules: Rules, dry_run: bool | None = None) -> list[Any]:
    """Execute rules on a file chain."""
    results = []

    for entry in chain:
        for rule in rules.rules:
            if rule.matches(entry):
                # Execute action
                result = _execute_rule_action(
                    entry, rule, dry_run if dry_run is not None else rule.dry_run
                )
                results.append(result)
                break

    return results


def _execute_rule_action(entry: Entry, rule: Rule, dry_run: bool) -> dict[str, Any]:
    """Execute a single rule action on an entry."""
    # This would integrate with actions.py
    # Placeholder for now
    return {
        "entry": entry,
        "action": rule.action,
        "dry_run": dry_run,
        "status": "would_execute" if dry_run else "executed",
    }
