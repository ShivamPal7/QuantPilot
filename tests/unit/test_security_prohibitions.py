"""Security AST and static analysis test verifying zero withdrawal or transfer capability.

Per Section 2.1 of agent.md:
"No withdrawal or transfer functionality may exist anywhere in the codebase."
This is a strict security boundary for the hackathon and trading safety.
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest

FORBIDDEN_KEYWORDS = {
    "withdraw",
    "withdrawal",
    "transfer",
    "send_funds",
    "drain",
    "payout",
}


class SecurityAstScanner(ast.NodeVisitor):
    """AST Visitor searching for forbidden withdrawal and fund transfer symbols."""

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.violations: list[str] = []

    def _check_name(self, name: str, node_type: str, line_no: int) -> None:
        name_lower = name.lower()
        for kw in FORBIDDEN_KEYWORDS:
            if kw in name_lower:
                self.violations.append(
                    f"[{self.filename}:{line_no}] Forbidden {node_type} '{name}' matches '{kw}'"
                )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_name(node.name, "function", node.lineno)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_name(node.name, "async function", node.lineno)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._check_name(node.name, "class", node.lineno)
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        # Check direct function calls or method attribute calls
        if isinstance(node.func, ast.Name):
            self._check_name(node.func.id, "call", node.lineno)
        elif isinstance(node.func, ast.Attribute):
            self._check_name(node.func.attr, "method call", node.lineno)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # Check string constants for URL/API routes
        if isinstance(node.value, str):
            val_lower = node.value.lower()
            if any(val_lower.startswith(f"/{kw}") or f"/{kw}/" in val_lower for kw in FORBIDDEN_KEYWORDS):
                self.violations.append(
                    f"[{self.filename}:{node.lineno}] Forbidden route constant '{node.value}'"
                )
        self.generic_visit(node)


class TestSecurityProhibitions(unittest.TestCase):
    def setUp(self) -> None:
        # Resolve repo root directory
        self.project_root = Path(__file__).parent.parent.parent
        self.app_dir = self.project_root / "app"

    def test_zero_withdrawal_or_transfer_functionality_in_app(self) -> None:
        """Scan all Python modules in app/ and assert 0 security violations."""
        self.assertTrue(self.app_dir.is_dir(), f"app directory not found at {self.app_dir}")

        py_files = list(self.app_dir.rglob("*.py"))
        self.assertGreaterEqual(
            len(py_files),
            15,
            f"Expected at least 15 Python files under {self.app_dir}, found {len(py_files)}",
        )

        all_violations: list[str] = []

        for py_file in py_files:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
            scanner = SecurityAstScanner(filename=str(py_file.relative_to(self.project_root)))
            scanner.visit(tree)
            all_violations.extend(scanner.violations)

        self.assertEqual(
            all_violations,
            [],
            "Security violations detected! Withdrawal or transfer code is strictly prohibited:\n"
            + "\n".join(all_violations),
        )

    def test_scanner_detects_malicious_constructs_adversarial(self) -> None:
        """Adversarial validation: verify that the AST scanner correctly flags violations."""
        malicious_snippets = [
            ("def withdraw_to_wallet(addr): pass", "function 'withdraw_to_wallet'"),
            ("async def initiate_transfer(): pass", "async function 'initiate_transfer'"),
            ("class PayoutManager: pass", "class 'PayoutManager'"),
            ("client.send_funds(amount=100)", "method call 'send_funds'"),
            ('route = "/withdraw/all"', "Forbidden route constant '/withdraw/all'"),
        ]

        for code, expected_fragment in malicious_snippets:
            with self.subTest(code=code):
                tree = ast.parse(code)
                scanner = SecurityAstScanner(filename="adversarial_test.py")
                scanner.visit(tree)
                self.assertGreater(
                    len(scanner.violations),
                    0,
                    f"Scanner failed to detect violation in snippet: {code}",
                )
                self.assertTrue(
                    any(expected_fragment in v for v in scanner.violations),
                    f"Expected fragment '{expected_fragment}' not found in {scanner.violations}",
                )


if __name__ == "__main__":
    unittest.main()
