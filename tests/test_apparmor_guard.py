"""Impide ejecutar los ensayos de permisos sobre una instalación real."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "apparmor_lab_check", ROOT / "scripts/check_apparmor.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AppArmorGuardTests(unittest.TestCase):
    def test_rejects_production_before_running_operations(self):
        with (
            patch.object(sys, "argv", ["check", "--confirm-disposable-lab"]),
            patch.object(Path, "read_text", return_value="private_git_manager (enforce)"),
            patch.object(MODULE.subprocess, "run") as command,
        ):
            with self.assertRaises(AssertionError):
                MODULE.main()
            command.assert_not_called()

    def test_requires_explicit_disposable_confirmation(self):
        with patch.object(sys, "argv", ["check"]), patch.object(Path, "read_text") as read:
            with self.assertRaises(SystemExit) as error:
                MODULE.main()
            self.assertEqual(error.exception.code, 2)
            read.assert_not_called()
