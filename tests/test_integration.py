from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from hyrulefast.integration import patch_hookshot

FIXTURE = '''import re

import a64_lift

LABEL = re.compile(r"^L_([0-9a-f]{8}):;", re.M)
GOTO = re.compile(r"goto L_([0-9a-f]{8});")


def add_polls(text):
    return text, 0


_installed = False
stats = {"functions": 0, "polls": 0}


def install():
    global _installed
    if _installed:
        return
    _installed = True
    base = a64_lift.Lifter.emit_function

    def emit_function(self, e, texts):
        text, refs = base(self, e, texts)
        text, n = add_polls(text)
        return text, refs

    a64_lift.Lifter.emit_function = emit_function
'''


class IntegrationTests(unittest.TestCase):
    def test_patch_is_checked_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nx2").mkdir()
            poll = root / "nx2" / "poll.py"
            poll.write_text(FIXTURE, encoding="utf-8")
            self.assertTrue(patch_hookshot(root))
            patched = poll.read_text(encoding="utf-8")
            self.assertIn("HYRULE_POLL_DECIMATION_V1", patched)
            self.assertIn("_hyrule_poll_configuration()", patched)
            self.assertIn("_hyrule_add_polls(text, active_interval)", patched)
            compile(patched, str(poll), "exec")
            self.assertTrue((root / "nx2" / "poll.py.hyrule-backup").is_file())
            self.assertTrue((root / "nx2" / "hyrule_pollpass.py").is_file())
            self.assertFalse(patch_hookshot(root))

    def test_mismatched_source_is_not_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nx2").mkdir()
            poll = root / "nx2" / "poll.py"
            poll.write_text("# unknown upstream source\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                patch_hookshot(root)
            self.assertEqual(poll.read_text(encoding="utf-8"), "# unknown upstream source\n")


if __name__ == "__main__":
    unittest.main()
