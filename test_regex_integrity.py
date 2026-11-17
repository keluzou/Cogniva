"""Prevent accidental double-escaping of regex tokens in validation code."""
import ast
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parent
FILES = ("app.py", "feedback_guard.py", "organization_audit.py")
REGEX_METHODS = {"compile", "search", "match", "fullmatch", "findall", "finditer", "sub", "subn"}


class RegexIntegrityTests(unittest.TestCase):
    def test_no_double_escaped_word_or_space_tokens(self):
        for filename in FILES:
            tree = ast.parse((ROOT / filename).read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                if not (isinstance(func, ast.Attribute)
                        and isinstance(func.value, ast.Name)
                        and func.value.id == "re"
                        and func.attr in REGEX_METHODS
                        and node.args):
                    continue
                # Check constant fragments too, for concatenated patterns.
                for fragment in ast.walk(node.args[0]):
                    if isinstance(fragment, ast.Constant) and isinstance(fragment.value, str):
                        for token in (r"\\b", r"\\s"):
                            self.assertNotIn(
                                token, fragment.value,
                                f"{filename}:{node.lineno} contains double-escaped {token}",
                            )


if __name__ == "__main__":
    unittest.main()
